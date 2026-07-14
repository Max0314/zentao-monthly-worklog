from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


OBJECT_TYPES = ("stories", "tasks", "bugs")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, data: dict[str, Any], pretty: bool = True) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def record_key(object_type: str, record: dict[str, Any]) -> str:
    if record.get("key"):
        return str(record["key"])
    scope = record.get("execution") or record.get("product") or "none"
    raw = f"{object_type}:{scope}:{record.get('title', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_draft(draft: dict[str, Any], settings=None) -> list[str]:
    errors: list[str] = []
    if not draft.get("month"):
        errors.append("month is required")

    seen: set[tuple[str, int, str]] = set()
    for object_type in OBJECT_TYPES:
        records = draft.get(object_type, [])
        if not isinstance(records, list):
            errors.append(f"{object_type} must be a list")
            continue
        for index, record in enumerate(records, 1):
            prefix = f"{object_type}[{index}]"
            title = str(record.get("title", "")).strip()
            detail = str(record.get("detail", "")).strip()
            if not title:
                errors.append(f"{prefix}.title is required")
            if not detail:
                errors.append(f"{prefix}.detail is required")
            if object_type in {"tasks", "bugs"} and not record.get("execution"):
                errors.append(f"{prefix}.execution is required")
            if object_type in {"stories", "bugs"} and not record.get("product"):
                errors.append(f"{prefix}.product is required")
            comments = record.get("comments", [])
            if not isinstance(comments, list):
                errors.append(f"{prefix}.comments must be a list")
                comments = []
            if object_type == "tasks" and len(comments) < 2:
                errors.append(f"{prefix} needs at least 2 task completion comments")
            if object_type == "bugs" and len(comments) < 4:
                errors.append(f"{prefix} needs at least 4 bug resolution comments")
            expected = "【任务完成步骤】" if object_type == "tasks" else "【bug解决步骤】"
            if object_type in {"tasks", "bugs"} and comments and not any(
                str(comment).startswith(expected) for comment in comments
            ):
                errors.append(f"{prefix}.comments must contain {expected}")
            if object_type == "bugs" and comments and not any(
                str(comment).startswith("【伪代码】") for comment in comments
            ):
                errors.append(f"{prefix}.comments must contain 【伪代码】")

            scope = str(record.get("execution") or record.get("product") or "0")
            duplicate_key = (object_type, scope, title)
            if title and duplicate_key in seen:
                errors.append(f"{prefix} duplicates title in the same scope: {title}")
            seen.add(duplicate_key)

            if settings and record.get("execution"):
                try:
                    settings.execution(record["execution"])
                except KeyError as exc:
                    errors.append(f"{prefix}: {exc}")
    return errors
