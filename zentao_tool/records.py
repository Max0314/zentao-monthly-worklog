from __future__ import annotations

import hashlib
import json
from datetime import datetime
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
    seen_record_keys: set[str] = set()
    default_date = str(draft.get("date", "")).strip()
    if default_date:
        try:
            datetime.strptime(default_date, "%Y-%m-%d")
        except ValueError:
            errors.append("date must use YYYY-MM-DD format")
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
            detail_prefix = {
                "stories": "【需求详细描述】",
                "tasks": "【任务详细描述】",
                "bugs": "【bug详细描述】",
            }[object_type]
            if detail and not detail.startswith(detail_prefix):
                errors.append(f"{prefix}.detail must start with {detail_prefix}")
            if object_type in {"tasks", "bugs"} and not record.get("execution"):
                errors.append(f"{prefix}.execution is required")
            if object_type in {"stories", "bugs"} and not record.get("product"):
                errors.append(f"{prefix}.product is required")
            if object_type == "stories" and not record.get("estimate"):
                errors.append(f"{prefix}.estimate is required")
            if record.get("estimate") is not None:
                try:
                    if float(record["estimate"]) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"{prefix}.estimate must be a positive number")
            if object_type == "bugs":
                project_id = record.get("project") or draft.get("project_id") or getattr(
                    settings, "project_id", 0
                )
                if not project_id:
                    errors.append(f"{prefix}.project or draft.project_id is required")
            if object_type in {"tasks", "bugs"}:
                record_date = str(record.get("date") or default_date).strip()
                if not record_date:
                    errors.append(f"{prefix}.date or draft.date is required")
                else:
                    try:
                        datetime.strptime(record_date, "%Y-%m-%d")
                    except ValueError:
                        errors.append(f"{prefix}.date must use YYYY-MM-DD format")
            comments = record.get("comments", [])
            if not isinstance(comments, list):
                errors.append(f"{prefix}.comments must be a list")
                comments = []
            if object_type == "tasks":
                if not 3 <= len(comments) <= 8:
                    errors.append(f"{prefix} needs 3-8 task completion comments")
                for comment_index, comment in enumerate(comments, 1):
                    if not str(comment).startswith("【任务完成步骤】"):
                        errors.append(
                            f"{prefix}.comments[{comment_index}] must start with 【任务完成步骤】"
                        )
            if object_type == "bugs":
                solution_comments = [
                    comment
                    for comment in comments
                    if str(comment).startswith("【bug解决步骤】")
                ]
                pseudocode_comments = [
                    comment for comment in comments if str(comment).startswith("【伪代码】")
                ]
                if len(solution_comments) < 5:
                    errors.append(f"{prefix} needs at least 5 bug resolution comments")
                if not pseudocode_comments:
                    errors.append(f"{prefix}.comments must contain 【伪代码】")
                for comment_index, comment in enumerate(comments, 1):
                    if not str(comment).startswith(("【bug解决步骤】", "【伪代码】")):
                        errors.append(
                            f"{prefix}.comments[{comment_index}] must start with 【bug解决步骤】 or 【伪代码】"
                        )

            scope = str(record.get("execution") or record.get("product") or "0")
            duplicate_key = (object_type, scope, title)
            if title and duplicate_key in seen:
                errors.append(f"{prefix} duplicates title in the same scope: {title}")
            seen.add(duplicate_key)

            explicit_key = str(record.get("key", "")).strip()
            if explicit_key:
                if explicit_key in seen_record_keys:
                    errors.append(f"{prefix} has duplicate record key: {explicit_key}")
                seen_record_keys.add(explicit_key)

            if settings and record.get("execution"):
                try:
                    settings.execution(record["execution"])
                except KeyError as exc:
                    errors.append(f"{prefix}: {exc}")
    return errors
