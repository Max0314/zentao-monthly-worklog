import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zentao_tool.config import load_settings, load_settings_candidates


class ConfigTests(unittest.TestCase):
    def test_local_config_has_precedence_over_stale_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.local.json"
            path.write_text(
                json.dumps(
                    {
                        "active_environment": "formal_internal",
                        "account": "config-user",
                        "password": "config-pass",
                        "environments": {
                            "formal_internal": {
                                "base_url": "http://127.0.0.1",
                                "path_prefix": "/biz",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"ZENTAO_ACCOUNT": "stale-user", "ZENTAO_PASSWORD": "stale-pass"},
            ):
                settings = load_settings(path)
            self.assertEqual(settings.account, "config-user")
            self.assertEqual(settings.password, "config-pass")
            self.assertEqual(settings.base_web, "http://127.0.0.1/biz")

    def test_formal_auto_returns_internal_then_external_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.local.json"
            path.write_text(
                json.dumps(
                    {
                        "active_environment": "formal_auto",
                        "account": "user",
                        "password": "pass",
                        "environments": {
                            "formal_internal": {"base_url": "http://10.0.0.1"},
                            "formal_external": {"base_url": "https://zentao.example.com"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            candidates = load_settings_candidates(path)
            self.assertEqual(
                [item.environment_name for item in candidates],
                ["formal_internal", "formal_external"],
            )
            self.assertTrue(all(item.requested_environment_name == "formal_auto" for item in candidates))


if __name__ == "__main__":
    unittest.main()
