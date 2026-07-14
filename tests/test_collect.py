import json
import tempfile
import unittest
from pathlib import Path

from zentao_tool.collect import collect_codex_sessions, month_bounds, redact


class CollectTests(unittest.TestCase):
    def test_month_bounds(self):
        self.assertEqual(month_bounds("2026-12"), ("2026-12-01", "2027-01-01"))

    def test_collects_only_user_and_final_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "2026" / "07" / "01" / "session.jsonl"
            path.parent.mkdir(parents=True)
            rows = [
                {"timestamp": "2026-07-01T00:00:00Z", "type": "session_meta", "payload": {"id": "s1", "cwd": "D:/repo"}},
                {"timestamp": "2026-07-01T00:00:01Z", "type": "event_msg", "payload": {"type": "user_message", "message": "修复问题 password:abc"}},
                {"timestamp": "2026-07-01T00:00:02Z", "type": "response_item", "payload": {"type": "reasoning", "summary": "hidden"}},
                {"timestamp": "2026-07-01T00:00:03Z", "type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "已经修复"}},
            ]
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            sessions = collect_codex_sessions(Path(temp), "2026-07")
            self.assertEqual(len(sessions), 1)
            self.assertEqual([item["role"] for item in sessions[0]["messages"]], ["user", "assistant"])
            self.assertNotIn("abc", sessions[0]["messages"][0]["text"])

    def test_redact(self):
        self.assertEqual(redact("token=123"), "token=***")


if __name__ == "__main__":
    unittest.main()
