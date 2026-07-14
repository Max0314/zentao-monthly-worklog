import unittest

from zentao_tool.client import ZentaoClient


class RecordingClient(ZentaoClient):
    def __init__(self):
        self.account = "user"
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return {"id": 1}


class ClientPayloadTests(unittest.TestCase):
    def test_create_story_uses_zentao_product_field(self):
        client = RecordingClient()

        client.create_story(223, "Story", "Detail", project_id=1292, execution_id=2826)

        method, path, payload = client.calls[0]
        self.assertEqual((method, path), ("POST", "/stories"))
        self.assertEqual(payload["product"], 223)
        self.assertNotIn("productID", payload)


if __name__ == "__main__":
    unittest.main()
