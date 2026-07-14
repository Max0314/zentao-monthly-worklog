import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zentao_tool.collect import (
    build_session_index,
    collect_codex_sessions,
    collect_context_file,
    collect_external_contexts,
    collect_git_history,
    deduplicate_git_history,
    inspect_evidence_sessions,
    month_bounds,
    redact,
)


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

    def test_collects_messages_by_timestamp_across_session_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            june_path = Path(temp) / "2026" / "06" / "30" / "june-session.jsonl"
            july_path = Path(temp) / "2026" / "07" / "31" / "july-session.jsonl"
            june_path.parent.mkdir(parents=True)
            july_path.parent.mkdir(parents=True)
            june_rows = [
                {"timestamp": "2026-06-30T15:00:00Z", "type": "session_meta", "payload": {"id": "s-june", "cwd": "D:/repo"}},
                {"timestamp": "2026-06-30T15:01:00Z", "type": "event_msg", "payload": {"type": "user_message", "message": "六月内容"}},
                {"timestamp": "2026-07-01T01:00:00Z", "type": "event_msg", "payload": {"type": "user_message", "message": "七月内容"}},
                {"timestamp": "2026-07-01T01:01:00Z", "type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "七月完成"}},
            ]
            july_rows = [
                {"timestamp": "2026-07-31T01:00:00Z", "type": "session_meta", "payload": {"id": "s-july", "cwd": "D:/repo"}},
                {"timestamp": "2026-07-31T01:01:00Z", "type": "event_msg", "payload": {"type": "user_message", "message": "七月底内容"}},
                {"timestamp": "2026-08-01T01:01:00Z", "type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "八月完成"}},
            ]
            june_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in june_rows), encoding="utf-8")
            july_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in july_rows), encoding="utf-8")

            sessions = collect_codex_sessions(Path(temp), "2026-07")

            texts = [message["text"] for session in sessions for message in session["messages"]]
            self.assertIn("七月内容", texts)
            self.assertIn("七月完成", texts)
            self.assertIn("七月底内容", texts)
            self.assertNotIn("六月内容", texts)
            self.assertNotIn("八月完成", texts)

    def test_redact(self):
        self.assertEqual(redact("token=123"), "token=***")
        self.assertNotIn("Abc123!secret", redact("user\nAbc123!secret"))

    def test_git_history_filters_exact_month_in_configured_timezone(self):
        output = (
            "\x1einside\x1f2026-07-31T23:59:59+08:00\x1fUser\x1fu@example.com\x1ffeat: inside\n"
            "M\tinside.py\n"
            "\x1eoutside\x1f2026-08-01T00:00:00+08:00\x1fUser\x1fu@example.com\x1ffeat: outside\n"
            "M\toutside.py\n"
        )
        with patch("zentao_tool.collect.discover_git_repositories", return_value=[Path("repo")]), patch(
            "zentao_tool.collect._run_git", return_value=output
        ):
            repositories = collect_git_history(Path("."), "2026-07")
        self.assertEqual([item["hash"] for item in repositories[0]["commits"]], ["inside"])

    def test_collects_generic_jsonl_context(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "neocoder.jsonl"
            rows = [
                {"role": "user", "content": "修复导出异常 token=123"},
                {"role": "assistant", "content": [{"type": "text", "text": "已回归验证"}]},
            ]
            path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
                encoding="utf-8",
            )
            contexts = collect_context_file(path)
            self.assertEqual(len(contexts), 1)
            self.assertEqual([row["role"] for row in contexts[0]["messages"]], ["user", "assistant"])
            self.assertNotIn("123", contexts[0]["messages"][0]["text"])

    def test_collects_manual_department_and_work_description(self):
        contexts = collect_external_contexts(
            department="研发效能，负责代码评审平台",
            work_description="本月完善仓库同步并修复超时问题",
        )
        self.assertEqual(contexts[0]["source"], "manual-input")
        self.assertEqual(len(contexts[0]["messages"]), 2)
        self.assertIn("部门/团队职责", contexts[0]["messages"][0]["text"])

    def test_compact_index_keeps_details_and_limits_turns(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Path(temp) / "evidence.json"
            messages = []
            for index in range(10):
                messages.extend(
                    [
                        {"role": "user", "text": f"需求 {index} " + "x" * 500},
                        {"role": "assistant", "text": f"完成 {index} " + "y" * 500},
                    ]
                )
            sessions = [
                {
                    "session_id": "s1",
                    "cwd": "D:\\work\\bi_center-feature",
                    "source": "session-1.jsonl",
                    "messages": messages,
                },
                {
                    "session_id": "s1",
                    "cwd": "D:\\work\\bi_center-feature",
                    "source": "session-2.jsonl",
                    "messages": [{"role": "user", "text": "续接会话"}],
                },
            ]
            indexes = build_session_index(
                sessions, evidence, {"bi_center*": {"execution": "bi"}}
            )
            self.assertEqual(indexes[0]["repository"], "bi_center")
            self.assertEqual(len(indexes[0]["turns"]), 4)
            self.assertEqual(indexes[0]["omitted_turns"], 6)
            self.assertNotEqual(indexes[0]["evidence_id"], indexes[1]["evidence_id"])
            self.assertNotEqual(indexes[0]["detail_file"], indexes[1]["detail_file"])
            detail = Path(temp) / indexes[0]["detail_file"]
            self.assertTrue(detail.is_file())
            self.assertEqual(len(json.loads(detail.read_text(encoding="utf-8"))["messages"]), 20)

    def test_unmapped_session_keeps_real_first_and_last_turns(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Path(temp) / "evidence.json"
            indexes = build_session_index(
                [
                    {
                        "session_id": "unmapped",
                        "cwd": "D:/other/repo",
                        "source": "session.jsonl",
                        "messages": [
                            {"role": "user", "text": "最初需求"},
                            {"role": "assistant", "text": "阶段结果"},
                            {"role": "user", "text": "补充要求"},
                            {"role": "assistant", "text": "最终结果"},
                        ],
                    }
                ],
                evidence,
                {},
            )
            self.assertEqual(len(indexes[0]["turns"]), 2)
            self.assertEqual(indexes[0]["turns"][0]["request"], "最初需求")
            self.assertEqual(indexes[0]["turns"][0]["result"], "阶段结果")
            self.assertEqual(indexes[0]["turns"][1]["request"], "补充要求")
            self.assertEqual(indexes[0]["turns"][1]["result"], "最终结果")

    def test_workspace_root_session_infers_repository_mentions(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Path(temp) / "evidence.json"
            indexes = build_session_index(
                [
                    {
                        "session_id": "root",
                        "cwd": "D:/code_CPL",
                        "source": "session.jsonl",
                        "messages": [
                            {"role": "user", "text": "请检查 SOP 的生成问题"},
                            {"role": "assistant", "text": "已在 D:/code_CPL/SOP 完成修复"},
                        ],
                    }
                ],
                evidence,
                {"SOP": {"execution": "sop"}},
            )
            self.assertIn("SOP", indexes[0]["repository_mentions"])
            self.assertTrue(indexes[0]["mapped_repository"])

    def test_deduplicates_worktrees_by_hash_and_family(self):
        commit = {
            "hash": "abc",
            "authored_at": "2026-07-01T00:00:00Z",
            "subject": "fix: duplicate",
            "files": [{"status": "M", "path": "app.py"}],
        }
        repositories = [
            {"name": "bi_center", "path": "D:/work/bi_center", "commits": [commit]},
            {
                "name": "bi_center-feature",
                "path": "D:/work/bi_center-feature",
                "commits": [commit, {**commit, "hash": "def", "subject": "feat: new"}],
            },
        ]
        result, stats = deduplicate_git_history(
            repositories, {"bi_center*": {"execution": "bi"}}
        )
        self.assertEqual(stats["raw_commit_rows"], 3)
        self.assertEqual(stats["unique_commits"], 2)
        self.assertEqual(stats["duplicate_commit_rows_removed"], 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "bi_center")
        self.assertEqual(len(result[0]["commits"]), 2)

    def test_same_hash_in_different_repository_families_is_retained(self):
        commit = {
            "hash": "same-hash",
            "authored_at": "2026-07-01T00:00:00Z",
            "subject": "shared commit",
            "files": [],
        }
        result, stats = deduplicate_git_history(
            [
                {"name": "repo-a", "path": "D:/repo-a", "commits": [commit]},
                {"name": "repo-b", "path": "D:/repo-b", "commits": [commit]},
            ],
            {
                "repo-a": {"execution": "a"},
                "repo-b": {"execution": "b"},
            },
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(stats["unique_commits"], 2)

    def test_inspects_only_selected_compact_details(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence_path = Path(temp) / "evidence.json"
            indexes = build_session_index(
                [
                    {
                        "session_id": "s1",
                        "cwd": "D:/work/repo",
                        "source": "session.jsonl",
                        "messages": [
                            {"role": "user", "text": "导出失败"},
                            {"role": "assistant", "text": "已修复并回归测试"},
                        ],
                    }
                ],
                evidence_path,
                {"repo": {"execution": "x"}},
            )
            evidence_path.write_text(
                json.dumps(
                    {"mode": "compact", "codex_sessions": indexes, "external_contexts": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = inspect_evidence_sessions(
                evidence_path, repositories=["repo"], queries=["测试"]
            )
            self.assertEqual(result["selected_sessions"], 1)
            self.assertEqual(result["sessions"][0]["matched_messages"], 2)
            self.assertEqual(result["sessions"][0]["source"], "session.jsonl")

    def test_query_only_can_search_all_session_details(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence_path = Path(temp) / "evidence.json"
            indexes = build_session_index(
                [
                    {
                        "session_id": "s1",
                        "cwd": "D:/code_CPL",
                        "source": "session.jsonl",
                        "messages": [
                            {"role": "user", "text": "SOP 上传失败"},
                            {"role": "assistant", "text": "已经修复并验证"},
                        ],
                    }
                ],
                evidence_path,
                {},
            )
            evidence_path.write_text(
                json.dumps({"mode": "compact", "codex_sessions": indexes, "external_contexts": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            result = inspect_evidence_sessions(evidence_path, queries=["SOP"])
            self.assertEqual(result["sessions"][0]["matched_messages"], 2)


if __name__ == "__main__":
    unittest.main()
