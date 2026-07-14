import unittest

from zentao_tool.records import validate_draft


class DraftValidationTests(unittest.TestCase):
    def test_valid_task_and_bug(self):
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "project_id": 9,
            "stories": [],
            "tasks": [
                {
                    "execution": 4058,
                    "title": "任务",
                    "detail": "【任务详细描述】详情",
                    "comments": ["【任务完成步骤】一", "【任务完成步骤】二", "【任务完成步骤】三"],
                }
            ],
            "bugs": [
                {
                    "execution": 4058,
                    "product": 654,
                    "title": "Bug",
                    "detail": "【bug详细描述】详情",
                    "comments": [
                        "【bug解决步骤】验证",
                        "【bug解决步骤】定位",
                        "【bug解决步骤】分析",
                        "【bug解决步骤】解决",
                        "【bug解决步骤】回归",
                        "【伪代码】处理",
                    ],
                }
            ],
        }
        self.assertEqual(validate_draft(draft), [])

    def test_rejects_missing_pseudocode(self):
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "project_id": 9,
            "stories": [],
            "tasks": [],
            "bugs": [
                {
                    "execution": 1,
                    "product": 2,
                    "title": "Bug",
                    "detail": "【bug详细描述】详情",
                    "comments": ["【bug解决步骤】一"] * 5,
                }
            ],
        }
        self.assertTrue(any("伪代码" in item for item in validate_draft(draft)))

    def test_rejects_wrong_prefixes_and_duplicate_keys(self):
        draft = {
            "month": "2026-07",
            "date": "2026-07-14",
            "project_id": 9,
            "stories": [],
            "tasks": [
                {
                    "key": "duplicate",
                    "execution": 1,
                    "title": "任务一",
                    "detail": "错误描述",
                    "comments": ["【任务完成步骤】一", "未评分步骤", "【任务完成步骤】三"],
                },
                {
                    "key": "duplicate",
                    "execution": 1,
                    "title": "任务二",
                    "detail": "【任务详细描述】详情",
                    "comments": ["【任务完成步骤】一", "【任务完成步骤】二", "【任务完成步骤】三"],
                },
            ],
            "bugs": [],
        }
        errors = validate_draft(draft)
        self.assertTrue(any("任务详细描述" in error for error in errors))
        self.assertTrue(any("must start" in error for error in errors))
        self.assertTrue(any("duplicate record key" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
