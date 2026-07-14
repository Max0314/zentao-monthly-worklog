import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zentao_tool.config import load_settings


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


if __name__ == "__main__":
    unittest.main()
