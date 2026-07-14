import unittest

from zentao_tool.records import validate_draft


class DraftValidationTests(unittest.TestCase):
    def test_valid_task_and_bug(self):
        draft = {
            "month": "2026-07",
            "stories": [],
            "tasks": [
                {
                    "execution": 4058,
                    "title": "任务",
                    "detail": "详情",
                    "comments": ["【任务完成步骤】一", "【任务完成步骤】二"],
                }
            ],
            "bugs": [
                {
                    "execution": 4058,
                    "product": 654,
                    "title": "Bug",
                    "detail": "详情",
                    "comments": [
                        "【bug解决步骤】验证",
                        "【bug解决步骤】定位",
                        "【bug解决步骤】分析",
                        "【bug解决步骤】解决",
                        "【伪代码】处理",
                    ],
                }
            ],
        }
        self.assertEqual(validate_draft(draft), [])

    def test_rejects_missing_pseudocode(self):
        draft = {
            "month": "2026-07",
            "stories": [],
            "tasks": [],
            "bugs": [
                {
                    "execution": 1,
                    "product": 2,
                    "title": "Bug",
                    "detail": "详情",
                    "comments": ["【bug解决步骤】一"] * 4,
                }
            ],
        }
        self.assertTrue(any("伪代码" in item for item in validate_draft(draft)))


if __name__ == "__main__":
    unittest.main()
