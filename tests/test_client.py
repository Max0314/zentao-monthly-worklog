import unittest
from unittest.mock import patch

from zentao_tool.client import ZentaoClient


class RecordingClient(ZentaoClient):
    def __init__(self):
        self.account = "user"
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return {"id": 1}


class ClientPayloadTests(unittest.TestCase):
    def test_lists_available_scopes(self):
        client = ZentaoClient(account="user", password="pass")
        with patch.object(
            client,
            "request",
            side_effect=[
                {"products": [{"id": 1}]},
                {"projects": [{"id": 2}]},
                {"executions": [{"id": 3}]},
            ],
        ):
            self.assertEqual(client.list_products(), [{"id": 1}])
            self.assertEqual(client.list_projects(), [{"id": 2}])
            self.assertEqual(client.list_executions(), [{"id": 3}])

    def test_create_story_uses_zentao_product_field(self):
        client = RecordingClient()

        client.create_story(223, "Story", "Detail", project_id=1292, execution_id=2826)

        method, path, payload = client.calls[0]
        self.assertEqual((method, path), ("POST", "/stories"))
        self.assertEqual(payload["product"], 223)
        self.assertNotIn("productID", payload)

    def test_list_all_follows_zentao_pages(self):
        client = ZentaoClient(account="user", password="pass")
        with patch.object(
            client,
            "request",
            side_effect=[
                {"total": 3, "executions": [{"id": 1}, {"id": 2}]},
                {"total": 3, "executions": [{"id": 3}]},
            ],
        ) as request:
            rows = client._list_all("/executions", "executions", limit=10, page_size=2)
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertIn("page=2", request.call_args_list[1].args[1])

    def test_list_all_keeps_page_size_when_limit_is_partial_page(self):
        client = ZentaoClient(account="user", password="pass")
        with patch.object(
            client,
            "request",
            side_effect=[
                {"total": 5, "executions": [{"id": 1}, {"id": 2}]},
                {"total": 5, "executions": [{"id": 3}, {"id": 4}]},
            ],
        ) as request:
            rows = client._list_all("/executions", "executions", limit=3, page_size=2)
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertIn("limit=2&page=2", request.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
