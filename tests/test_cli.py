import argparse
import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from zentao_tool.cli import _settings, main


class CliSettingsTests(unittest.TestCase):
    def test_agent_can_initialize_from_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "nested" / "config.local.json"
            workspace = Path(temp) / "work"
            workspace.mkdir()
            with patch.dict(
                os.environ,
                {"ZENTAO_ACCOUNT": "agent-user", "ZENTAO_PASSWORD": "agent-pass"},
            ):
                result = main(
                    [
                        "init-config",
                        "--path",
                        str(config),
                        "--workspace-root",
                        str(workspace),
                        "--git-author",
                        "Agent User",
                    ]
                )
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(data["account"], "agent-user")
            self.assertEqual(data["git_authors"], ["Agent User"])

    def test_init_config_writes_selected_account_and_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.local.json"
            workspace = Path(temp) / "work"
            workspace.mkdir()
            result = main(
                [
                    "init-config",
                    "--path",
                    str(config),
                    "--account",
                    "sample-user",
                    "--password",
                    "sample-pass",
                    "--workspace-root",
                    str(workspace),
                ]
            )
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(data["active_environment"], "formal_auto")
            self.assertEqual(data["account"], "sample-user")
            self.assertEqual(Path(data["workspace_root"]), workspace)

    def test_configure_execution_adds_repository_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.local.json"
            config.write_text(
                json.dumps({"executions": {}, "repositories": {}}), encoding="utf-8"
            )
            result = main(
                [
                    "--config",
                    str(config),
                    "configure-execution",
                    "review",
                    "1708",
                    "代码评审",
                    "654",
                    "--repository",
                    "review-*",
                    "--project-id",
                    "1292",
                ]
            )
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(data["executions"]["review"]["id"], 1708)
            self.assertEqual(data["repositories"]["review-*"]["execution"], "review")
            self.assertEqual(data["project_id"], 1292)

    def test_network_selection_falls_back_to_external(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.local.json"
            config.write_text(
                json.dumps(
                    {
                        "active_environment": "formal_auto",
                        "account": "user",
                        "password": "pass",
                        "environments": {
                            "formal_internal": {"base_url": "http://internal.invalid"},
                            "formal_external": {"base_url": "https://external.example.com"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(config=str(config), environment=None)

            class Probe:
                def __init__(self, environment_name):
                    self.environment_name = environment_name

                def ping(self):
                    if self.environment_name == "formal_internal":
                        raise OSError("unreachable")

            with patch(
                "zentao_tool.client.ZentaoClient.from_settings",
                side_effect=lambda settings: Probe(settings.environment_name),
            ):
                settings = _settings(args, network=True)

            self.assertEqual(settings.requested_environment_name, "formal_auto")
            self.assertEqual(settings.environment_name, "formal_external")


if __name__ == "__main__":
    unittest.main()
