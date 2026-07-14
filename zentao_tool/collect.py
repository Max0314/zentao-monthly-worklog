from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .records import save_json


SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "data",
    "logs",
    "persistent_data",
    "__pycache__",
}
SECRET_RE = re.compile(
    r"(?i)((?:password|passwd|pwd|token|secret|api[_-]?key|密码)\s*[:=：]\s*)[^\s,;]+"
)


def month_bounds(month: str) -> tuple[str, str]:
    start = datetime.strptime(month, "%Y-%m")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1***", text)


def collect_codex_sessions(root: Path, month: str) -> list[dict[str, Any]]:
    month_dir = root / month[:4] / month[5:7]
    if not month_dir.exists():
        return []

    sessions = []
    for path in sorted(month_dir.rglob("*.jsonl")):
        meta: dict[str, Any] = {}
        messages: list[dict[str, str]] = []
        timestamps: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = str(item.get("timestamp", ""))
                if timestamp:
                    timestamps.append(timestamp)
                item_type = item.get("type")
                payload = item.get("payload") or {}
                if item_type == "session_meta":
                    meta = {
                        "session_id": payload.get("session_id") or payload.get("id"),
                        "cwd": payload.get("cwd"),
                        "originator": payload.get("originator"),
                    }
                elif item_type == "event_msg" and payload.get("type") == "user_message":
                    text = payload.get("message") or ""
                    if text:
                        messages.append({"role": "user", "text": redact(str(text))})
                elif item_type == "event_msg" and payload.get("type") == "task_complete":
                    text = payload.get("last_agent_message") or ""
                    if text:
                        messages.append({"role": "assistant", "text": redact(str(text))})

        if not messages:
            continue
        sessions.append(
            {
                **meta,
                "started_at": min(timestamps) if timestamps else None,
                "ended_at": max(timestamps) if timestamps else None,
                "source": str(path),
                "messages": messages,
            }
        )
    return sessions


def discover_git_repositories(root: Path) -> list[Path]:
    repositories: list[Path] = []
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        if ".git" in dirs or (current_path / ".git").is_file():
            repositories.append(current_path)
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
    return sorted(set(repositories))


def _run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}")
    return result.stdout


def collect_git_history(root: Path, month: str, authors: list[str] | None = None) -> list[dict[str, Any]]:
    since, until = month_bounds(month)
    author_filters = [item.lower() for item in (authors or [])]
    repositories = []
    for repo in discover_git_repositories(root):
        output = _run_git(
            repo,
            [
                "log",
                f"--since={since}",
                f"--until={until}",
                "--no-merges",
                "--date=iso-strict",
                "--format=%x1e%H%x1f%aI%x1f%an%x1f%ae%x1f%s",
                "--name-status",
            ],
        )
        commits = []
        for block in output.split("\x1e"):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            fields = lines[0].split("\x1f", 4)
            if len(fields) != 5:
                continue
            commit_hash, authored_at, author, email, subject = fields
            author_text = f"{author} {email}".lower()
            if author_filters and not any(value in author_text for value in author_filters):
                continue
            files = []
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) >= 2:
                    files.append({"status": parts[0], "path": parts[-1]})
            commits.append(
                {
                    "hash": commit_hash,
                    "authored_at": authored_at,
                    "author": author,
                    "email": email,
                    "subject": subject,
                    "files": files,
                }
            )
        if commits:
            repositories.append({"name": repo.name, "path": str(repo), "commits": commits})
    return repositories


def collect_month(settings, month: str, output: str | Path | None = None) -> Path:
    result = {
        "month": month,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(settings.workspace_root),
        "codex_sessions": collect_codex_sessions(settings.codex_sessions_root, month),
        "git_repositories": collect_git_history(
            settings.workspace_root, month, authors=settings.git_authors
        ),
    }
    target = Path(output) if output else Path("output") / month / "evidence.json"
    return save_json(target, result)
