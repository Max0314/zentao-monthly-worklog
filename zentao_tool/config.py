from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_NAME = "config.local.json"


@dataclass(frozen=True)
class Settings:
    config_path: Path
    environment_name: str
    base_web: str
    base_api: str
    verify_tls: bool
    timeout: int
    account: str
    password: str
    project_id: int
    workspace_root: Path
    codex_sessions_root: Path
    executions: dict[str, dict[str, Any]]
    repositories: dict[str, dict[str, Any]]
    git_authors: list[str]
    comment_probe: dict[str, Any] | None

    def execution(self, value: str | int) -> dict[str, Any]:
        if isinstance(value, int) or str(value).isdigit():
            execution_id = int(value)
            for key, item in self.executions.items():
                if int(item["id"]) == execution_id:
                    return {"key": key, **item}
            raise KeyError(f"Execution {execution_id} is not configured")
        if value not in self.executions:
            raise KeyError(f"Execution alias {value!r} is not configured")
        return {"key": value, **self.executions[value]}


def find_config(path: str | os.PathLike[str] | None = None) -> Path:
    candidates = []
    if path:
        candidates.append(Path(path))
    if os.environ.get("ZENTAO_TOOL_CONFIG"):
        candidates.append(Path(os.environ["ZENTAO_TOOL_CONFIG"]))
    candidates.extend([Path.cwd() / DEFAULT_CONFIG_NAME, PROJECT_ROOT / DEFAULT_CONFIG_NAME])
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "No config.local.json found. Run `zentao-tool init-config` or copy config.example.json."
    )


def load_settings(
    path: str | os.PathLike[str] | None = None,
    environment: str | None = None,
    require_password: bool = True,
) -> Settings:
    config_path = find_config(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    environment_name = environment or data.get("active_environment", "formal_internal")
    environments = data.get("environments", {})
    if environment_name not in environments:
        raise KeyError(f"Environment {environment_name!r} is not configured")

    env = environments[environment_name]
    base_url = str(env["base_url"]).rstrip("/")
    path_prefix = str(env.get("path_prefix", "/biz")).strip()
    if path_prefix and not path_prefix.startswith("/"):
        path_prefix = "/" + path_prefix
    base_web = (base_url + path_prefix).rstrip("/")
    base_api = str(env.get("base_api") or (base_web + "/api.php/v1")).rstrip("/")

    account = str(env.get("account") or data.get("account", "")) or os.environ.get(
        "ZENTAO_ACCOUNT", ""
    )
    password = str(env.get("password") or data.get("password", "")) or os.environ.get(
        "ZENTAO_PASSWORD", ""
    )
    if not account:
        raise ValueError("ZenTao account is empty in config.local.json")
    if require_password and not password:
        raise ValueError("ZenTao password is empty in config.local.json")

    return Settings(
        config_path=config_path,
        environment_name=environment_name,
        base_web=base_web,
        base_api=base_api,
        verify_tls=bool(env.get("verify_tls", True)),
        timeout=int(env.get("timeout", 30)),
        account=account,
        password=password,
        project_id=int(data.get("project_id", 0)),
        workspace_root=Path(data.get("workspace_root", PROJECT_ROOT.parent)).expanduser().resolve(),
        codex_sessions_root=Path(
            data.get("codex_sessions_root", Path.home() / ".codex" / "sessions")
        ).expanduser().resolve(),
        executions=data.get("executions", {}),
        repositories=data.get("repositories", {}),
        git_authors=[str(item).lower() for item in data.get("git_authors", [])],
        comment_probe=env.get("comment_probe", data.get("comment_probe")),
    )


def write_default_config(path: str | os.PathLike[str], account: str = "chenpenglie") -> Path:
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"Config already exists: {target}")
    template = json.loads((PROJECT_ROOT / "config.example.json").read_text(encoding="utf-8"))
    template["account"] = account
    target.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
