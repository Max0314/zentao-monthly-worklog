from __future__ import annotations

import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import ZentaoClient, extract_created_id
from .records import OBJECT_TYPES, load_json, record_key, save_json, validate_draft
from .web_comments import ZentaoWebComments


SINGULAR_TYPES = {"stories": "story", "tasks": "task", "bugs": "bug"}
MANIFEST_SCHEMA_VERSION = 2
COMMENT_HTML_TAG_RE = re.compile(
    r"</?(?:a|b|blockquote|br|code|div|em|font|i|li|ol|p|pre|span|strong|u|ul)\b[^>]*>",
    re.IGNORECASE,
)


def preview_draft(draft: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for object_type in OBJECT_TYPES:
        for record in draft.get(object_type, []):
            rows.append(
                {
                    "type": SINGULAR_TYPES[object_type],
                    "title": record.get("title"),
                    "execution": record.get("execution"),
                    "product": record.get("product"),
                    "comments": len(record.get("comments", [])),
                }
            )
    return rows


def environment_target(settings_or_name) -> str:
    name = (
        settings_or_name.environment_name
        if hasattr(settings_or_name, "environment_name")
        else str(settings_or_name or "")
    )
    return "formal" if name.startswith("formal") else name


def validate_manifest_target(settings, manifest: dict[str, Any]) -> None:
    expected_target = environment_target(settings)
    actual_target = manifest.get("target") or environment_target(
        manifest.get("environment")
    )
    if actual_target and actual_target != expected_target:
        raise ValueError(
            f"Manifest target {actual_target!r} does not match selected target "
            f"{expected_target!r}"
        )
    manifest_account = str(manifest.get("account") or "")
    if manifest_account and manifest_account != settings.account:
        raise ValueError(
            f"Manifest account {manifest_account!r} does not match selected account"
        )


def normalize_comment(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = COMMENT_HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def comment_hash(value: Any) -> str:
    return hashlib.sha256(normalize_comment(value).encode("utf-8")).hexdigest()


def _action_comment(action: dict[str, Any]) -> Any:
    return action.get("comment") or action.get("actioncomment") or action.get("extra")


def _comment_actions(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        action
        for action in item.get("actions", [])
        if str(action.get("action", "")).lower() == "commented"
    ]


def _match_comment_actions(
    actions: list[dict[str, Any]], expected_hashes: list[str]
) -> list[dict[str, Any]]:
    matched = []
    cursor = 0
    action_hashes = [comment_hash(_action_comment(action)) for action in actions]
    for expected in expected_hashes:
        found = None
        for index in range(cursor, len(actions)):
            if action_hashes[index] == expected:
                found = index
                break
        if found is None:
            break
        matched.append(actions[found])
        cursor = found + 1
    return matched


def _record_hash(
    object_type: str, record: dict[str, Any], draft: dict[str, Any]
) -> str:
    effective = {
        "type": object_type,
        "record": record,
        "project_id": (
            record.get("project") or draft.get("project_id")
            if object_type in {"stories", "bugs"}
            else None
        ),
        "date": (
            record.get("date") or draft.get("date")
            if object_type in {"tasks", "bugs"}
            else None
        ),
    }
    raw = json.dumps(effective, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _draft_hash(draft: dict[str, Any]) -> str:
    raw = json.dumps(draft, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BatchUploader:
    def __init__(
        self,
        settings,
        manifest_path: str | Path,
        adopt_existing: bool = False,
    ):
        self.settings = settings
        self.client = ZentaoClient.from_settings(settings)
        self.web = ZentaoWebComments.from_settings(
            settings, token_provider=lambda: self.client.token
        )
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest()
        self.adopt_existing = adopt_existing
        self._title_cache: dict[tuple[str, int], dict[str, int]] = {}

    def _load_manifest(self):
        if self.manifest_path.exists():
            return load_json(self.manifest_path)
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "target": environment_target(self.settings),
            "environment": self.settings.environment_name,
            "requested_environment": getattr(
                self.settings, "requested_environment_name", self.settings.environment_name
            ),
            "base_web": self.settings.base_web,
            "account": self.settings.account,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "entries": [],
        }

    def _bind_manifest(self, draft: dict[str, Any]) -> None:
        validate_manifest_target(self.settings, self.manifest)
        existing_month = self.manifest.get("month")
        if existing_month and existing_month != draft["month"] and self.manifest.get("entries"):
            raise ValueError(
                f"Manifest month {existing_month!r} does not match draft month {draft['month']!r}"
            )
        self.manifest.update(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "target": environment_target(self.settings),
                "environment": self.settings.environment_name,
                "requested_environment": getattr(
                    self.settings,
                    "requested_environment_name",
                    self.settings.environment_name,
                ),
                "base_web": self.settings.base_web,
                "account": self.settings.account,
                "month": draft["month"],
                "draft_hash": _draft_hash(draft),
            }
        )
        self._save()

    def _save(self):
        self.manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_json(self.manifest_path, self.manifest)

    def _entry(
        self,
        key: str,
        object_type: str,
        record: dict[str, Any],
        draft: dict[str, Any] | None = None,
    ):
        draft = draft or {}
        expected_comments = list(record.get("comments", []))
        expected_hashes = [comment_hash(comment) for comment in expected_comments]
        current_hash = _record_hash(object_type, record, draft)
        scope = self._scope(object_type, record)
        for entry in self.manifest["entries"]:
            if entry["key"] != key:
                continue
            if entry.get("type") != object_type:
                raise ValueError(f"Manifest key {key!r} belongs to another object type")
            if entry.get("title") != record["title"]:
                raise ValueError(f"Manifest key {key!r} belongs to another title")
            if entry.get("scope") not in (None, scope):
                raise ValueError(f"Manifest key {key!r} belongs to another scope")
            previous_hash = entry.get("record_hash")
            if previous_hash and previous_hash != current_hash and entry.get("id"):
                raise ValueError(
                    f"Manifest record {key!r} changed after ZenTao object {entry['id']} was created"
                )
            entry.update(
                {
                    "scope": scope,
                    "record_hash": current_hash,
                    "expected_comments": len(expected_comments),
                    "comment_hashes": expected_hashes,
                }
            )
            return entry
        entry = {
            "key": key,
            "type": object_type,
            "title": record["title"],
            "scope": scope,
            "record_hash": current_hash,
            "id": None,
            "origin": None,
            "state": "pending",
            "expected_comments": len(expected_comments),
            "comment_hashes": expected_hashes,
            "comments_written": 0,
            "confirmed_comment_actions": [],
            "error": None,
        }
        self.manifest["entries"].append(entry)
        self._save()
        return entry

    def _scope(self, object_type: str, record: dict[str, Any]) -> int:
        if object_type == "stories":
            return int(record["product"])
        return int(record["execution"])

    def _existing_titles(self, object_type: str, scope: int) -> dict[str, int]:
        cache_key = (object_type, scope)
        if cache_key in self._title_cache:
            return self._title_cache[cache_key]
        if object_type == "tasks":
            items = self.client.list_execution_tasks(scope)
            titles = {str(item.get("name", "")).strip(): int(item["id"]) for item in items}
        elif object_type == "bugs":
            items = self.client.list_execution_bugs(scope)
            titles = {str(item.get("title", "")).strip(): int(item["id"]) for item in items}
        else:
            items = self.client.list_product_stories(scope)
            titles = {str(item.get("title", "")).strip(): int(item["id"]) for item in items}
        self._title_cache[cache_key] = titles
        return titles

    def upload(self, draft: dict[str, Any]) -> dict[str, Any]:
        errors = validate_draft(draft, self.settings)
        if errors:
            raise ValueError("Draft validation failed:\n- " + "\n- ".join(errors))
        self._bind_manifest(draft)

        for object_type in OBJECT_TYPES:
            for record in draft.get(object_type, []):
                self._upload_record(object_type, record, draft)
        return self.manifest

    def _get_object(self, object_type: str, object_id: int) -> dict[str, Any]:
        if object_type == "tasks":
            return self.client.get_task(object_id)
        if object_type == "bugs":
            return self.client.get_bug(object_id)
        return self.client.get_story(object_id)

    @staticmethod
    def _object_title(object_type: str, item: dict[str, Any]) -> str:
        return str(item.get("name") if object_type == "tasks" else item.get("title"))

    def _reconcile_comments(
        self, object_type: str, record: dict[str, Any], entry: dict[str, Any]
    ) -> dict[str, Any]:
        item = self._get_object(object_type, int(entry["id"]))
        if self._object_title(object_type, item) != record["title"]:
            raise RuntimeError(
                f"ZenTao {object_type} {entry['id']} title does not match the manifest"
            )
        actions = _comment_actions(item)
        expected_hashes = list(entry.get("comment_hashes", []))
        matched = _match_comment_actions(actions, expected_hashes)
        if len(matched) < len(expected_hashes):
            missing_index = len(matched)
            later_hashes = set(expected_hashes[missing_index + 1 :])
            action_hashes = {comment_hash(_action_comment(action)) for action in actions}
            if later_hashes & action_hashes:
                raise RuntimeError(
                    f"ZenTao comments for {object_type} {entry['id']} are out of expected order"
                )
        entry["comments_written"] = len(matched)
        entry["confirmed_comment_actions"] = [
            action.get("id") for action in matched if action.get("id") is not None
        ]
        self._save()
        return item

    def _upload_record(
        self, object_type: str, record: dict[str, Any], draft: dict[str, Any]
    ):
        key = record_key(object_type, record)
        entry = self._entry(key, object_type, record, draft)
        scope = self._scope(object_type, record)
        try:
            if entry.get("state") == "skipped_existing" and not self.adopt_existing:
                raise RuntimeError(
                    f"ZenTao {object_type} titled {record['title']!r} already exists; "
                    "rerun with --adopt-existing only after confirming ownership"
                )
            if entry["id"] is None:
                existing_id = self._existing_titles(object_type, scope).get(
                    record["title"].strip()
                )
                if existing_id:
                    if not self.adopt_existing:
                        entry.update(
                            {
                                "id": existing_id,
                                "origin": "existing",
                                "state": "conflict_existing",
                                "error": "Explicit adoption is required",
                            }
                        )
                        self._save()
                        raise RuntimeError(
                            f"ZenTao {object_type} titled {record['title']!r} already exists; "
                            "rerun with --adopt-existing only after confirming ownership"
                        )
                    entry.update(
                        {
                            "id": existing_id,
                            "origin": "existing",
                            "state": "created",
                            "error": None,
                        }
                    )
                    self._save()
                else:
                    entry["id"] = self._create(object_type, record, draft)
                    entry["origin"] = "created"
                    entry["state"] = "created"
                    self._save()
            elif entry.get("origin") == "existing" and not self.adopt_existing:
                raise RuntimeError(
                    f"Manifest record {key!r} refers to an existing ZenTao object; "
                    "--adopt-existing is required"
                )

            server_item = self._reconcile_comments(object_type, record, entry)
            comments = record.get("comments", [])
            while entry["comments_written"] < len(comments):
                index = entry["comments_written"]
                self.web.add_comment(
                    SINGULAR_TYPES[object_type], entry["id"], comments[index]
                )
                entry["comments_written"] += 1
                self._save()

            date = record.get("date") or draft.get("date")
            if object_type == "tasks":
                estimate = float(record.get("estimate", 3))
                if server_item.get("status") != "done":
                    self.client.finish_task(entry["id"], consumed=estimate, date=date)
                entry["state"] = "done"
            elif object_type == "bugs":
                if not (
                    server_item.get("status") == "resolved"
                    and server_item.get("resolution") == "fixed"
                ):
                    self.client.resolve_bug(entry["id"], date=date)
                entry["state"] = "resolved"
            else:
                entry["state"] = "story_created"
            entry["error"] = None
            self._save()
        except Exception as exc:
            entry["state"] = "error"
            entry["error"] = str(exc)
            self._save()
            raise

    def _create(
        self, object_type: str, record: dict[str, Any], draft: dict[str, Any]
    ) -> int:
        if object_type == "tasks":
            response = self.client.create_task(
                int(record["execution"]),
                record["title"],
                record["detail"],
                estimate=float(record.get("estimate", 3)),
                date=record.get("date") or draft.get("date"),
            )
            return extract_created_id(response, "task")
        if object_type == "bugs":
            response = self.client.create_bug(
                int(record["product"]),
                int(record["execution"]),
                int(
                    record.get("project")
                    or draft.get("project_id")
                    or self.settings.project_id
                ),
                record["title"],
                record["detail"],
            )
            return extract_created_id(response, "bug")
        response = self.client.create_story(
            int(record["product"]),
            record["title"],
            record["detail"],
            project_id=int(
                record.get("project")
                or draft.get("project_id")
                or self.settings.project_id
            ),
            execution_id=int(record.get("execution") or 0),
            estimate=float(record.get("estimate", 3)),
            verify=record.get("verify", ""),
        )
        return extract_created_id(response, "story")


def verify_manifest(settings, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    validate_manifest_target(settings, manifest)
    client = ZentaoClient.from_settings(settings)
    rows = []
    for entry in manifest.get("entries", []):
        if not entry.get("id"):
            rows.append({**entry, "found": False, "actual_status": None})
            continue
        object_type = entry["type"]
        if object_type == "tasks":
            item = client.get_task(entry["id"])
            title = item.get("name")
        elif object_type == "bugs":
            item = client.get_bug(entry["id"])
            title = item.get("title")
        else:
            item = client.get_story(entry["id"])
            title = item.get("title")
        actions = _comment_actions(item)
        expected_hashes = list(entry.get("comment_hashes", []))
        expected_comments = int(
            entry.get("expected_comments", entry.get("comments_written", 0))
        )
        matched = (
            _match_comment_actions(actions, expected_hashes)
            if expected_hashes
            else actions[:expected_comments]
        )
        action_hash_counts = Counter(
            comment_hash(_action_comment(action)) for action in actions
        )
        expected_hash_counts = Counter(expected_hashes)
        duplicate_expected_comments = sum(
            max(0, action_hash_counts[value] - count)
            for value, count in expected_hash_counts.items()
        )
        ai_scores = [
            action.get("aiScore")
            if action.get("aiScore") not in (None, "")
            else action.get("score")
            for action in matched
        ]
        rows.append(
            {
                "type": SINGULAR_TYPES[object_type],
                "id": entry["id"],
                "origin": entry.get("origin"),
                "expected_title": entry["title"],
                "title": title,
                "found": bool(item),
                "actual_status": item.get("status"),
                "resolution": item.get("resolution"),
                "expected_comments": expected_comments,
                "matched_comments": len(matched),
                "commented_actions": len(actions),
                "duplicate_expected_comments": duplicate_expected_comments,
                "scored_comments": sum(
                    score not in (None, "") for score in ai_scores
                ),
                "comment_ai_scores": ai_scores,
            }
        )
    return rows
