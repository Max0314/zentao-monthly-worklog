import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zentao_tool.uploader import (
    BatchUploader,
    comment_hash,
    normalize_comment,
    verify_manifest,
)


class FakeSettings:
    environment_name = "test"
    requested_environment_name = "test"
    base_api = "http://example/api.php/v1"
    base_web = "http://example/biz"
    account = "user"
    password = "pass"
    verify_tls = True
    timeout = 1
    project_id = 9
    comment_probe = {"type": "task", "id": 1}

    def execution(self, value):
        return {"id": int(value), "product_id": 2}


class FakeClient:
    def __init__(self):
        self.finished = []
        self.resolved = []
        self.actions = {101: [], 201: [], 301: []}
        self.task_status = "active"
        self.bug_status = "active"
        self.task_title = "T"
        self.bug_title = "B"
        self.story_title = "S"

    def list_execution_tasks(self, _scope):
        return []

    def list_execution_bugs(self, _scope):
        return []

    def list_product_stories(self, _scope):
        return []

    def create_task(self, *_args, **_kwargs):
        self.task_title = _args[1]
        return {"id": 101}

    def create_bug(self, *_args, **_kwargs):
        self.bug_title = _args[3]
        return {"id": 201}

    def create_story(self, *_args, **_kwargs):
        self.story_title = _args[1]
        return {"id": 301}

    def finish_task(self, object_id, **_kwargs):
        self.finished.append(object_id)
        self.task_status = "done"

    def resolve_bug(self, object_id, **_kwargs):
        self.resolved.append(object_id)
        self.bug_status = "resolved"

    def get_task(self, object_id):
        return {
            "id": object_id,
            "name": self.task_title,
            "status": self.task_status,
            "actions": self.actions.setdefault(object_id, []),
        }

    def get_bug(self, object_id):
        return {
            "id": object_id,
            "title": self.bug_title,
            "status": self.bug_status,
            "resolution": "fixed" if self.bug_status == "resolved" else "",
            "actions": self.actions.setdefault(object_id, []),
        }

    def get_story(self, object_id):
        return {
            "id": object_id,
            "title": self.story_title,
            "status": "active",
            "actions": self.actions.setdefault(object_id, []),
        }


class FakeWeb:
    def __init__(self, client):
        self.client = client
        self.comments = []

    def add_comment(self, object_type, object_id, text):
        self.comments.append((object_type, object_id, text))
        self.client.actions.setdefault(object_id, []).append(
            {"action": "commented", "comment": text, "aiScore": 5}
        )


class UploaderTests(unittest.TestCase):
    def test_comment_normalization_preserves_pseudocode_placeholders(self):
        plain = "【伪代码】if score < 5: emit(<value>)"
        html = "<p>【伪代码】if score &lt; 5:<br>emit(&lt;value&gt;)</p>"
        self.assertEqual(normalize_comment(plain), normalize_comment(html))

    def test_uploads_and_persists_progress(self):
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "project_id": 9,
            "stories": [{"product": 2, "estimate": 3, "title": "S", "detail": "【需求详细描述】D", "comments": ["story comment"]}],
            "tasks": [{"execution": 1, "title": "T", "detail": "【任务详细描述】D", "comments": ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"]}],
            "bugs": [{"execution": 1, "product": 2, "title": "B", "detail": "【bug详细描述】D", "comments": ["【bug解决步骤】1", "【bug解决步骤】2", "【bug解决步骤】3", "【bug解决步骤】4", "【bug解决步骤】5", "【伪代码】x"]}],
        }
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            uploader = BatchUploader(FakeSettings(), manifest)
            uploader.client = FakeClient()
            uploader.web = FakeWeb(uploader.client)
            result = uploader.upload(draft)
            self.assertEqual(
                [item["state"] for item in result["entries"]],
                ["story_created", "done", "resolved"],
            )
            self.assertEqual(len(uploader.web.comments), 10)
            self.assertEqual(uploader.web.comments[0], ("story", 301, "story comment"))
            self.assertTrue(manifest.exists())

    def test_resumes_created_task_without_recreating_it(self):
        record = {
            "key": "resume-task",
            "execution": 1,
            "title": "Resume",
            "detail": "【任务详细描述】D",
            "comments": ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"],
        }
        draft = {"month": "2026-07", "date": "2026-07-14", "stories": [], "tasks": [record], "bugs": []}
        with tempfile.TemporaryDirectory() as temp:
            uploader = BatchUploader(FakeSettings(), Path(temp) / "manifest.json")
            uploader.client = FakeClient()
            uploader.client.actions[101] = [
                {"action": "commented", "comment": "【任务完成步骤】1", "aiScore": 5}
            ]
            uploader.client.task_title = "Resume"
            uploader.web = FakeWeb(uploader.client)
            entry = uploader._entry("resume-task", "tasks", record, draft)
            entry.update({"id": 101, "state": "created", "comments_written": 0})
            uploader._save()
            uploader.upload(draft)
            self.assertEqual(len(uploader.web.comments), 2)
            self.assertEqual(uploader.client.finished, [101])

    def test_rejects_manifest_from_another_environment(self):
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "stories": [],
            "tasks": [
                {
                    "execution": 1,
                    "title": "T",
                    "detail": "【任务详细描述】D",
                    "comments": ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"],
                }
            ],
            "bugs": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(
                '{"schema_version": 2, "target": "formal", "account": "user", "entries": []}',
                encoding="utf-8",
            )
            uploader = BatchUploader(FakeSettings(), manifest)
            uploader.client = FakeClient()
            uploader.web = FakeWeb(uploader.client)
            with self.assertRaisesRegex(ValueError, "target"):
                uploader.upload(draft)

    def test_existing_title_requires_explicit_adoption(self):
        class ExistingClient(FakeClient):
            def list_execution_tasks(self, _scope):
                return [{"id": 101, "name": "T"}]

        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "stories": [],
            "tasks": [
                {
                    "execution": 1,
                    "title": "T",
                    "detail": "【任务详细描述】D",
                    "comments": ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"],
                }
            ],
            "bugs": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            uploader = BatchUploader(FakeSettings(), Path(temp) / "manifest.json")
            uploader.client = ExistingClient()
            uploader.web = FakeWeb(uploader.client)
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                uploader.upload(draft)

        with tempfile.TemporaryDirectory() as temp:
            uploader = BatchUploader(
                FakeSettings(), Path(temp) / "manifest.json", adopt_existing=True
            )
            uploader.client = ExistingClient()
            uploader.web = FakeWeb(uploader.client)
            result = uploader.upload(draft)
            self.assertEqual(result["entries"][0]["origin"], "existing")
            self.assertEqual(len(uploader.web.comments), 3)
            self.assertEqual(uploader.client.finished, [101])

    def test_verify_matches_expected_comments_and_ai_scores(self):
        client = FakeClient()
        client.task_status = "done"
        client.actions[101] = [
            {"action": "commented", "comment": "【任务完成步骤】1", "score": "4"},
            {"action": "commented", "comment": "【任务完成步骤】2", "score": "5"},
            {"action": "commented", "comment": "【任务完成步骤】3", "score": "4.5"},
        ]
        comments = ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"]
        manifest = {
            "schema_version": 2,
            "target": "test",
            "account": "user",
            "entries": [
                {
                    "type": "tasks",
                    "id": 101,
                    "origin": "created",
                    "title": "T",
                    "expected_comments": 3,
                    "comment_hashes": [comment_hash(comment) for comment in comments],
                }
            ],
        }
        with patch(
            "zentao_tool.uploader.ZentaoClient.from_settings", return_value=client
        ):
            rows = verify_manifest(FakeSettings(), manifest)
        self.assertEqual(rows[0]["matched_comments"], 3)
        self.assertEqual(rows[0]["scored_comments"], 3)
        self.assertEqual(rows[0]["duplicate_expected_comments"], 0)

    def test_resume_does_not_finish_an_already_done_task_again(self):
        record = {
            "key": "done-task",
            "execution": 1,
            "title": "T",
            "detail": "【任务详细描述】D",
            "comments": ["【任务完成步骤】1", "【任务完成步骤】2", "【任务完成步骤】3"],
        }
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "stories": [],
            "tasks": [record],
            "bugs": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            uploader = BatchUploader(FakeSettings(), Path(temp) / "manifest.json")
            uploader.client = FakeClient()
            uploader.client.task_status = "done"
            uploader.client.actions[101] = [
                {"action": "commented", "comment": comment, "score": "5"}
                for comment in record["comments"]
            ]
            uploader.web = FakeWeb(uploader.client)
            entry = uploader._entry("done-task", "tasks", record, draft)
            entry.update({"id": 101, "origin": "created", "state": "done"})
            uploader._save()
            uploader.upload(draft)
            self.assertEqual(uploader.client.finished, [])
            self.assertEqual(len(uploader.web.comments), 0)


if __name__ == "__main__":
    unittest.main()
