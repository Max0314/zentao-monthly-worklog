import unittest

from zentao_tool.draft import build_draft


class FakeSettings:
    project_id = 1
    repositories = {"repo*": {"execution": "work", "display_name": "工作项目"}}

    def execution(self, value):
        self.assert_execution = value
        return {"id": 10, "name": "迭代", "product_id": 20}


class DraftTests(unittest.TestCase):
    def test_fix_commit_is_candidate_not_resolved_bug(self):
        evidence = {
            "month": "2026-07",
            "git_repositories": [
                {
                    "name": "repo",
                    "commits": [
                        {
                            "hash": "abc123",
                            "subject": "fix: export failure",
                            "files": [{"path": "export.py"}],
                        }
                    ],
                }
            ],
        }
        draft = build_draft(evidence, FakeSettings())
        self.assertEqual(draft["bugs"], [])
        self.assertEqual(len(draft["bug_candidates"]), 1)
        self.assertIn("inspect conversation evidence", draft["bug_candidates"][0]["reason"])
        self.assertEqual(len(draft["tasks"]), 1)
        self.assertIn("abc123", draft["tasks"][0]["sources"])
        self.assertRegex(draft["date"], r"^2026-07-\d{2}$")


if __name__ == "__main__":
    unittest.main()
