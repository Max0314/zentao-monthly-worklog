from __future__ import annotations

import hashlib
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
SIGNAL_PATTERNS = {
    "bug": re.compile(r"(?i)bug|异常|报错|错误|失败|不一致|无法|缺失|超时"),
    "fix": re.compile(r"(?i)fix|修复|解决|兼容|兜底|恢复"),
    "test": re.compile(r"(?i)test|pytest|unittest|测试|验证|回归|构建通过"),
    "deploy": re.compile(r"(?i)deploy|release|部署|发布|上线|重启|健康检查"),
    "pending": re.compile(r"(?i)pending|blocked|未完成|待确认|暂停|未上线|尚未"),
}


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


def repository_alias(
    repository_name: str, mappings: dict[str, dict[str, Any]] | None = None
) -> tuple[str, bool]:
    mappings = mappings or {}
    lower = repository_name.lower()
    for pattern in sorted(mappings, key=len, reverse=True):
        pattern_lower = pattern.lower()
        if pattern_lower == lower:
            return pattern.rstrip("*"), True
        if pattern.endswith("*") and lower.startswith(pattern_lower[:-1]):
            return pattern[:-1], True
    return repository_name, False


def _truncate(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def _session_turns(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for message in messages:
        role = message.get("role")
        text = str(message.get("text", ""))
        if role == "user":
            if current:
                turns.append(current)
            current = {"request": text, "result": ""}
        elif role == "assistant":
            if current is None:
                current = {"request": "", "result": text}
            else:
                current["result"] = text
    if current:
        turns.append(current)
    return turns


def _sample_turns(turns: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    if limit == 1 and turns:
        selected = [
            {
                "request": turns[0].get("request", ""),
                "result": turns[-1].get("result", ""),
            }
        ]
    elif len(turns) <= limit:
        selected = turns
    else:
        head = min(2, max(1, limit // 3))
        selected = turns[:head] + turns[-(limit - head) :]
    return [
        {
            "request": _truncate(turn.get("request", ""), 160),
            "result": _truncate(turn.get("result", ""), 220),
        }
        for turn in selected
    ]


def _session_signals(messages: list[dict[str, str]]) -> dict[str, int]:
    text = "\n".join(str(message.get("text", "")) for message in messages)
    return {
        name: len(pattern.findall(text))
        for name, pattern in SIGNAL_PATTERNS.items()
        if pattern.search(text)
    }


def build_session_index(
    sessions: list[dict[str, Any]],
    evidence_target: Path,
    repository_mappings: dict[str, dict[str, Any]] | None = None,
    kind: str = "codex",
) -> list[dict[str, Any]]:
    detail_dir = evidence_target.parent / "details" / "sessions"
    result = []
    for index, session in enumerate(sessions, start=1):
        messages = session.get("messages", [])
        session_id = str(
            session.get("session_id")
            or hashlib.sha256(str(session.get("source", index)).encode("utf-8")).hexdigest()[:16]
        )
        source_digest = hashlib.sha256(
            f"{session.get('source', '')}:{index}".encode("utf-8")
        ).hexdigest()[:8]
        evidence_id = f"{session_id}-{source_digest}"
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", evidence_id)
        detail_path = detail_dir / f"{kind}-{safe_id}.json"
        detail = {
            **session,
            "kind": kind,
            "session_id": session_id,
            "evidence_id": evidence_id,
        }
        save_json(detail_path, detail, pretty=False)

        cwd = str(session.get("cwd") or "")
        repo_name = re.split(r"[\\/]", cwd)[-1] if cwd else ""
        alias, mapped = repository_alias(repo_name, repository_mappings)
        turns = _session_turns(messages)
        turn_limit = 4 if mapped else 1
        result.append(
            {
                "evidence_id": evidence_id,
                "session_id": session_id,
                "kind": kind,
                "cwd": cwd or None,
                "repository": alias or None,
                "mapped_repository": mapped,
                "started_at": session.get("started_at"),
                "ended_at": session.get("ended_at"),
                "detail_file": detail_path.relative_to(evidence_target.parent).as_posix(),
                "message_count": len(messages),
                "character_count": sum(len(str(item.get("text", ""))) for item in messages),
                "turn_count": len(turns),
                "omitted_turns": max(0, len(turns) - turn_limit),
                "signals": _session_signals(messages),
                "turns": _sample_turns(turns, turn_limit),
            }
        )
    return result


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


def deduplicate_git_history(
    repositories: list[dict[str, Any]],
    repository_mappings: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_hash: dict[str, dict[str, Any]] = {}
    raw_rows = 0
    for repository in repositories:
        alias, mapped = repository_alias(repository["name"], repository_mappings)
        for commit in repository.get("commits", []):
            raw_rows += 1
            entry = by_hash.setdefault(
                commit["hash"],
                {"commit": commit, "occurrences": []},
            )
            entry["occurrences"].append(
                {
                    "name": repository["name"],
                    "path": repository.get("path"),
                    "alias": alias,
                    "mapped": mapped,
                }
            )

    groups: dict[str, dict[str, Any]] = {}
    for entry in by_hash.values():
        occurrences = sorted(
            entry["occurrences"],
            key=lambda item: (not item["mapped"], len(str(item.get("path") or ""))),
        )
        chosen = occurrences[0]
        alias = chosen["alias"]
        group = groups.setdefault(alias, {"name": alias, "paths": set(), "commits": []})
        group["paths"].update(
            str(item["path"]) for item in occurrences if item.get("path")
        )
        commit = dict(entry["commit"])
        files = commit.get("files", [])
        commit["file_count"] = len(files)
        commit["files"] = files[:10]
        commit["observed_in"] = sorted({item["name"] for item in occurrences})
        group["commits"].append(commit)

    result = []
    for group in groups.values():
        paths = sorted(group["paths"], key=lambda value: (len(value), value))
        result.append(
            {
                "name": group["name"],
                "path": paths[0] if paths else None,
                "paths": paths,
                "commits": sorted(
                    group["commits"], key=lambda item: item.get("authored_at", "")
                ),
            }
        )
    return sorted(result, key=lambda item: item["name"].lower()), {
        "raw_commit_rows": raw_rows,
        "unique_commits": len(by_hash),
        "duplicate_commit_rows_removed": raw_rows - len(by_hash),
    }


def inspect_evidence_sessions(
    evidence_path: str | Path,
    session_ids: list[str] | None = None,
    repositories: list[str] | None = None,
    queries: list[str] | None = None,
    max_sessions: int = 6,
    max_messages: int = 12,
    max_characters: int = 30000,
) -> dict[str, Any]:
    evidence_path = Path(evidence_path).resolve()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    session_ids = set(session_ids or [])
    repository_filters = {item.lower() for item in (repositories or [])}
    query_filters = [item.lower() for item in (queries or [])]
    indexes = evidence.get("codex_sessions", []) + evidence.get("external_contexts", [])
    selected = []
    for item in indexes:
        matches_id = not session_ids or bool(
            {str(item.get("session_id")), str(item.get("evidence_id"))} & session_ids
        )
        matches_repo = not repository_filters or str(item.get("repository", "")).lower() in repository_filters
        if matches_id and matches_repo:
            selected.append(item)
    if not session_ids and not repository_filters:
        raise ValueError("Select at least one --session or --repository")

    selected.sort(key=lambda item: str(item.get("ended_at") or ""), reverse=True)
    result = []
    remaining_characters = max_characters
    for item in selected:
        if item.get("detail_file"):
            detail_path = evidence_path.parent / item["detail_file"]
            detail = json.loads(detail_path.read_text(encoding="utf-8"))
            messages = detail.get("messages", [])
        else:
            detail = item
            messages = item.get("messages", [])
        if query_filters:
            messages = [
                message
                for message in messages
                if any(query in str(message.get("text", "")).lower() for query in query_filters)
            ]
            if not messages:
                continue
        if len(messages) > max_messages:
            head = max(1, max_messages // 3)
            messages = messages[:head] + messages[-(max_messages - head) :]

        output_messages = []
        for message in messages:
            if remaining_characters <= 0:
                break
            text = str(message.get("text", ""))
            text = text[:remaining_characters]
            remaining_characters -= len(text)
            output_messages.append({"role": message.get("role"), "text": text})
        result.append(
            {
                "session_id": item.get("session_id"),
                "evidence_id": item.get("evidence_id"),
                "repository": item.get("repository"),
                "source": detail.get("source"),
                "matched_messages": len(output_messages),
                "messages": output_messages,
            }
        )
        if remaining_characters <= 0 or len(result) >= max_sessions:
            break
    return {
        "selected_sessions": len(result),
        "character_budget": max_characters,
        "characters_returned": max_characters - remaining_characters,
        "sessions": result,
    }


def collect_month(
    settings,
    month: str,
    output: str | Path | None = None,
    context_files: list[str] | None = None,
    department: str | None = None,
    work_description: str | None = None,
    compact: bool = True,
) -> Path:
    target = Path(output) if output else Path("output") / month / "evidence.json"
    codex_sessions = collect_codex_sessions(settings.codex_sessions_root, month)
    external_contexts = collect_external_contexts(
        context_files=context_files,
        department=department,
        work_description=work_description,
    )
    raw_git = collect_git_history(
        settings.workspace_root, month, authors=settings.git_authors
    )
    git_repositories, git_stats = deduplicate_git_history(
        raw_git, settings.repositories
    )
    result = {
        "evidence_version": 2,
        "mode": "compact" if compact else "full",
        "month": month,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(settings.workspace_root),
        "stats": {
            "codex_sessions": len(codex_sessions),
            "codex_messages": sum(len(item.get("messages", [])) for item in codex_sessions),
            "codex_characters": sum(
                len(str(message.get("text", "")))
                for item in codex_sessions
                for message in item.get("messages", [])
            ),
            "external_contexts": len(external_contexts),
            **git_stats,
        },
        "codex_sessions": (
            build_session_index(codex_sessions, target, settings.repositories, "codex")
            if compact
            else codex_sessions
        ),
        "external_contexts": (
            build_session_index(external_contexts, target, settings.repositories, "external")
            if compact
            else external_contexts
        ),
        "git_repositories": git_repositories,
    }
    return save_json(target, result, pretty=False)
