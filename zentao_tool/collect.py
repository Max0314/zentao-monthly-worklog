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


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("message")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _normalize_external_messages(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        if isinstance(value.get("messages"), list):
            value = value["messages"]
        else:
            value = [value]
    if not isinstance(value, list):
        return []

    messages = []
    for item in value:
        if isinstance(item, str):
            messages.append({"role": "user", "text": redact(item)})
            continue
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("author") or "user")
        text = _content_text(item.get("text") or item.get("message") or item.get("content"))
        if text:
            messages.append({"role": role, "text": redact(text)})
    return messages


def collect_context_file(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Context file does not exist: {source}")

    suffix = source.suffix.lower()
    raw = source.read_text(encoding="utf-8", errors="replace")
    contexts: list[dict[str, Any]] = []
    if suffix == ".jsonl":
        rows = []
        for line in raw.splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        messages = _normalize_external_messages(rows)
        if messages:
            contexts.append({"source": str(source), "format": "jsonl", "messages": messages})
        return contexts

    if suffix == ".json":
        value = json.loads(raw)
        sessions = value.get("sessions") if isinstance(value, dict) else None
        if isinstance(sessions, list):
            for index, session in enumerate(sessions, start=1):
                messages = _normalize_external_messages(session)
                if messages:
                    contexts.append(
                        {
                            "source": f"{source}#session-{index}",
                            "format": "json",
                            "messages": messages,
                        }
                    )
        else:
            messages = _normalize_external_messages(value)
            if messages:
                contexts.append({"source": str(source), "format": "json", "messages": messages})
        return contexts

    text = redact(raw.strip())
    if text:
        contexts.append(
            {
                "source": str(source),
                "format": suffix.lstrip(".") or "text",
                "messages": [{"role": "user", "text": text}],
            }
        )
    return contexts


def collect_external_contexts(
    context_files: list[str] | None = None,
    department: str | None = None,
    work_description: str | None = None,
) -> list[dict[str, Any]]:
    contexts = []
    for path in context_files or []:
        contexts.extend(collect_context_file(path))

    manual_messages = []
    if department:
        manual_messages.append(
            {"role": "user", "text": redact(f"【部门/团队职责】{department.strip()}")}
        )
    if work_description:
        manual_messages.append(
            {"role": "user", "text": redact(f"【本月工作描述】{work_description.strip()}")}
        )
    if manual_messages:
        contexts.append({"source": "manual-input", "format": "manual", "messages": manual_messages})
    return contexts


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


def collect_month(
    settings,
    month: str,
    output: str | Path | None = None,
    context_files: list[str] | None = None,
    department: str | None = None,
    work_description: str | None = None,
) -> Path:
    result = {
        "month": month,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(settings.workspace_root),
        "codex_sessions": collect_codex_sessions(settings.codex_sessions_root, month),
        "external_contexts": collect_external_contexts(
            context_files=context_files,
            department=department,
            work_description=work_description,
        ),
        "git_repositories": collect_git_history(
            settings.workspace_root, month, authors=settings.git_authors
        ),
    }
    target = Path(output) if output else Path("output") / month / "evidence.json"
    return save_json(target, result)
