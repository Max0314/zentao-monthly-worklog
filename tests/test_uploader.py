import tempfile
import unittest
from pathlib import Path

from zentao_tool.uploader import BatchUploader


class FakeSettings:
    environment_name = "test"
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

    def list_execution_tasks(self, _scope):
        return []

    def list_execution_bugs(self, _scope):
        return []

    def list_product_stories(self, _scope):
        return []

    def create_task(self, *_args, **_kwargs):
        return {"id": 101}

    def create_bug(self, *_args, **_kwargs):
        return {"id": 201}

    def create_story(self, *_args, **_kwargs):
        return {"id": 301}

    def finish_task(self, object_id, **_kwargs):
        self.finished.append(object_id)

    def resolve_bug(self, object_id, **_kwargs):
        self.resolved.append(object_id)


class FakeWeb:
    def __init__(self):
        self.comments = []

    def add_comment(self, object_type, object_id, text):
        self.comments.append((object_type, object_id, text))


class UploaderTests(unittest.TestCase):
    def test_uploads_and_persists_progress(self):
        draft = {
            "month": "2026-07",
            "project_id": 9,
            "stories": [{"product": 2, "title": "S", "detail": "D", "comments": ["story comment"]}],
            "tasks": [{"execution": 1, "title": "T", "detail": "D", "comments": ["【任务完成步骤】1", "【任务完成步骤】2"]}],
            "bugs": [{"execution": 1, "product": 2, "title": "B", "detail": "D", "comments": ["【bug解决步骤】1", "【bug解决步骤】2", "【bug解决步骤】3", "【bug解决步骤】4", "【伪代码】x"]}],
        }
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            uploader = BatchUploader(FakeSettings(), manifest)
            uploader.client = FakeClient()
            uploader.web = FakeWeb()
            result = uploader.upload(draft)
            self.assertEqual(
                [item["state"] for item in result["entries"]],
                ["story_created", "done", "resolved"],
            )
            self.assertEqual(len(uploader.web.comments), 8)
            self.assertEqual(uploader.web.comments[0], ("story", 301, "story comment"))
            self.assertTrue(manifest.exists())

    def test_resumes_created_task_without_recreating_it(self):
        record = {
            "key": "resume-task",
            "execution": 1,
            "title": "Resume",
            "detail": "D",
            "comments": ["【任务完成步骤】1", "【任务完成步骤】2"],
        }
        draft = {"month": "2026-07", "stories": [], "tasks": [record], "bugs": []}
        with tempfile.TemporaryDirectory() as temp:
            uploader = BatchUploader(FakeSettings(), Path(temp) / "manifest.json")
            uploader.client = FakeClient()
            uploader.web = FakeWeb()
            entry = uploader._entry("resume-task", "tasks", record)
            entry.update({"id": 101, "state": "created", "comments_written": 1})
            uploader._save()
            uploader.upload(draft)
            self.assertEqual(len(uploader.web.comments), 1)
            self.assertEqual(uploader.client.finished, [101])


if __name__ == "__main__":
    unittest.main()
