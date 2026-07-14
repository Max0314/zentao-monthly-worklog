from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import ZentaoClient, extract_created_id
from .records import OBJECT_TYPES, load_json, record_key, save_json, validate_draft
from .web_comments import ZentaoWebComments


FINAL_STATES = {"story_created", "done", "resolved", "skipped_existing", "verified"}
SINGULAR_TYPES = {"stories": "story", "tasks": "task", "bugs": "bug"}


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


class BatchUploader:
    def __init__(self, settings, manifest_path: str | Path):
        self.settings = settings
        self.client = ZentaoClient.from_settings(settings)
        self.web = ZentaoWebComments.from_settings(
            settings, token_provider=lambda: self.client.token
        )
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest()
        self._title_cache: dict[tuple[str, int], dict[str, int]] = {}

    def _load_manifest(self):
        if self.manifest_path.exists():
            return load_json(self.manifest_path)
        return {
            "environment": self.settings.environment_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "entries": [],
        }

    def _save(self):
        self.manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_json(self.manifest_path, self.manifest)

    def _entry(self, key: str, object_type: str, record: dict[str, Any]):
        for entry in self.manifest["entries"]:
            if entry["key"] == key:
                return entry
        entry = {
            "key": key,
            "type": object_type,
            "title": record["title"],
            "id": None,
            "state": "pending",
            "comments_written": 0,
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
        self.manifest["month"] = draft["month"]
        self._save()

        for object_type in OBJECT_TYPES:
            for record in draft.get(object_type, []):
                self._upload_record(object_type, record, draft)
        return self.manifest

    def _upload_record(self, object_type: str, record: dict[str, Any], draft: dict[str, Any]):
        key = record_key(object_type, record)
        entry = self._entry(key, object_type, record)
        if entry["state"] in FINAL_STATES:
            return
        scope = self._scope(object_type, record)
        try:
            if entry["id"] is None:
                existing_id = self._existing_titles(object_type, scope).get(record["title"].strip())
                if existing_id:
                    entry.update({"id": existing_id, "state": "skipped_existing", "error": None})
                    self._save()
                    return
                entry["id"] = self._create(object_type, record, draft)
                entry["state"] = "created"
                self._save()

            comments = record.get("comments", [])
            while entry["comments_written"] < len(comments):
                index = entry["comments_written"]
                self.web.add_comment(SINGULAR_TYPES[object_type], entry["id"], comments[index])
                entry["comments_written"] += 1
                self._save()

            date = record.get("date") or draft.get("date")
            if object_type == "tasks":
                estimate = float(record.get("estimate", 3))
                self.client.finish_task(entry["id"], consumed=estimate, date=date)
                entry["state"] = "done"
            elif object_type == "bugs":
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

    def _create(self, object_type: str, record: dict[str, Any], draft: dict[str, Any]) -> int:
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
                int(record.get("project") or draft.get("project_id") or self.settings.project_id),
                record["title"],
                record["detail"],
            )
            return extract_created_id(response, "bug")
        response = self.client.create_story(
            int(record["product"]),
            record["title"],
            record["detail"],
            project_id=int(record.get("project") or draft.get("project_id") or self.settings.project_id),
            execution_id=int(record.get("execution") or 0),
            estimate=float(record.get("estimate", 3)),
            verify=record.get("verify", ""),
        )
        return extract_created_id(response, "story")


def verify_manifest(settings, manifest: dict[str, Any]) -> list[dict[str, Any]]:
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
        rows.append(
            {
                "type": SINGULAR_TYPES[object_type],
                "id": entry["id"],
                "expected_title": entry["title"],
                "title": title,
                "found": bool(item),
                "actual_status": item.get("status"),
                "resolution": item.get("resolution"),
                "expected_comments": int(entry.get("comments_written", 0)),
                "commented_actions": sum(
                    1 for action in item.get("actions", []) if action.get("action") == "commented"
                ),
            }
        )
    return rows
