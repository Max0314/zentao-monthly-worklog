from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from .collect import collect_month, inspect_evidence_sessions
from .config import (
    DEFAULT_CONFIG_PATH,
    find_config,
    load_settings,
    load_settings_candidates,
    write_default_config,
)
from .draft import create_draft_file
from .records import load_json, validate_draft
from .uploader import BatchUploader, preview_draft, verify_manifest
from .web_comments import ZentaoWebComments


def _print(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _settings(args, require_password=True, network=False):
    candidates = load_settings_candidates(
        args.config, args.environment, require_password=require_password
    )
    if not network or len(candidates) == 1:
        return candidates[0]

    from .client import ZentaoClient

    failures = []
    for settings in candidates:
        probe_settings = replace(settings, timeout=min(settings.timeout, 5))
        try:
            ZentaoClient.from_settings(probe_settings).ping()
            return settings
        except Exception as exc:
            failures.append(f"{settings.environment_name}: {type(exc).__name__}")
    raise ConnectionError(
        "No configured ZenTao endpoint is reachable (" + ", ".join(failures) + ")"
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="zentao-tool",
        description="Collect AI conversations/Git monthly work and record it in ZenTao.",
    )
    parser.add_argument("--config", help="Path to the user configuration file")
    parser.add_argument("--env", dest="environment", help="Environment name from config")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-config", help="Create a local configuration file")
    init.add_argument("--path", default=str(DEFAULT_CONFIG_PATH))
    init.add_argument("--account", help="ZenTao account; prompted when omitted")
    init.add_argument("--password", help="Password; prompted when omitted")
    init.add_argument(
        "--environment",
        choices=["formal_auto", "formal_internal", "formal_external", "test"],
        default="formal_auto",
        help="Default ZenTao environment",
    )
    init.add_argument("--workspace-root", help="Root directory containing Git repositories")
    init.add_argument(
        "--git-author",
        action="append",
        default=[],
        help="Git author name or email to include; repeat for aliases",
    )

    sub.add_parser("show-config", help="Show the active environment without exposing password")
    sub.add_parser("ping", help="Test REST and web login without changing ZenTao data")
    scopes = sub.add_parser("list-scopes", help="List accessible ZenTao products, projects, and executions")
    scopes.add_argument("--limit", type=int, default=200)

    configure_execution = sub.add_parser(
        "configure-execution", help="Add a local execution and repository mapping"
    )
    configure_execution.add_argument("alias")
    configure_execution.add_argument("execution_id", type=int)
    configure_execution.add_argument("name")
    configure_execution.add_argument("product_id", type=int)
    configure_execution.add_argument("--repository", action="append", default=[])
    configure_execution.add_argument("--display-name")
    configure_execution.add_argument("--project-id", type=int)

    collect = sub.add_parser("collect", help="Collect AI sessions, work notes, and Git changes")
    collect.add_argument("month", help="Month in YYYY-MM format")
    collect.add_argument("--output")
    collect.add_argument(
        "--context",
        action="append",
        default=[],
        help="Additional AI conversation or work-note file (JSON, JSONL, Markdown, or text)",
    )
    collect.add_argument("--department", help="Department or team ownership context")
    collect.add_argument("--work-description", help="Manual work summary when chat records are absent")
    collect.add_argument(
        "--full",
        action="store_true",
        help="Embed complete conversation messages in evidence instead of compact indexes",
    )

    inspect_evidence = sub.add_parser(
        "inspect-evidence", help="Read selected compact session details within a token budget"
    )
    inspect_evidence.add_argument("evidence")
    inspect_evidence.add_argument("--session", action="append", default=[])
    inspect_evidence.add_argument("--repository", action="append", default=[])
    inspect_evidence.add_argument("--query", action="append", default=[])
    inspect_evidence.add_argument("--max-sessions", type=int, default=6)
    inspect_evidence.add_argument("--max-messages", type=int, default=12)
    inspect_evidence.add_argument("--max-characters", type=int, default=30000)

    draft = sub.add_parser("draft", help="Create an editable draft from an evidence file")
    draft.add_argument("evidence")
    draft.add_argument("--output")

    validate = sub.add_parser("validate", help="Validate a draft without network access")
    validate.add_argument("draft")

    preview = sub.add_parser("preview", help="Preview records that would be uploaded")
    preview.add_argument("draft")

    upload = sub.add_parser("upload", help="Create stories/tasks/bugs and write individual comments")
    upload.add_argument("draft")
    upload.add_argument("--manifest")
    upload.add_argument("--yes", action="store_true", help="Skip interactive confirmation")

    verify = sub.add_parser("verify", help="Verify uploaded records from a manifest")
    verify.add_argument("manifest")

    comment = sub.add_parser("comment", help="Add one real ZenTao web comment")
    comment.add_argument("object_type", choices=["story", "task", "bug"])
    comment.add_argument("object_id", type=int)
    comment.add_argument("text")

    sub.add_parser("verify-june-2026", help="Verify the historical 2026-06 batch")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.command == "init-config":
        account = args.account or os.environ.get("ZENTAO_ACCOUNT") or input("ZenTao account: ").strip()
        if not account:
            raise ValueError("ZenTao account cannot be empty")
        password = args.password
        if password is None:
            password = os.environ.get("ZENTAO_PASSWORD") or getpass.getpass("ZenTao password: ")
        if not password:
            raise ValueError("ZenTao password cannot be empty")
        target = write_default_config(
            args.path,
            account=account,
            environment=args.environment,
            workspace_root=args.workspace_root,
            git_authors=args.git_author,
        )
        data = load_json(target)
        data["password"] = password
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Created {target}")
        return 0

    if args.command == "show-config":
        settings = _settings(args, require_password=False)
        candidates = load_settings_candidates(
            args.config, args.environment, require_password=False
        )
        _print(
            {
                "config": str(settings.config_path),
                "requested_environment": settings.requested_environment_name,
                "environment_candidates": [item.environment_name for item in candidates],
                "default_candidate": settings.environment_name,
                "base_web": settings.base_web,
                "base_api": settings.base_api,
                "account": settings.account,
                "password": "***" if settings.password else "",
                "workspace_root": str(settings.workspace_root),
                "codex_sessions_root": str(settings.codex_sessions_root),
            }
        )
        return 0

    if args.command == "ping":
        from .client import ZentaoClient

        settings = _settings(args, network=True)
        client = ZentaoClient.from_settings(settings)
        client.ping()
        web = ZentaoWebComments.from_settings(settings, token=client.token)
        probe = settings.comment_probe
        if probe:
            web.get_comment_form(probe["type"], int(probe["id"]))
        _print(
            {
                "ok": True,
                "requested_environment": settings.requested_environment_name,
                "selected_environment": settings.environment_name,
                "base_web": settings.base_web,
                "comment_probe": probe,
            }
        )
        return 0

    if args.command == "list-scopes":
        from .client import ZentaoClient

        client = ZentaoClient.from_settings(_settings(args, network=True))

        def compact(rows, fields):
            return [{key: row.get(key) for key in fields if key in row} for row in rows]

        _print(
            {
                "products": compact(client.list_products(args.limit), ["id", "name", "status"]),
                "projects": compact(client.list_projects(args.limit), ["id", "name", "status"]),
                "executions": compact(
                    client.list_executions(args.limit),
                    ["id", "name", "project", "products", "status"],
                ),
            }
        )
        return 0

    if args.command == "configure-execution":
        config_path = find_config(args.config)
        data = load_json(config_path)
        data.setdefault("executions", {})[args.alias] = {
            "id": args.execution_id,
            "name": args.name,
            "product_id": args.product_id,
        }
        for repository in args.repository:
            data.setdefault("repositories", {})[repository] = {
                "execution": args.alias,
                "display_name": args.display_name or args.name,
            }
        if args.project_id is not None:
            data["project_id"] = args.project_id
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _print(
            {
                "ok": True,
                "config": str(config_path),
                "execution": data["executions"][args.alias],
                "repositories": args.repository,
            }
        )
        return 0

    if args.command == "collect":
        target = collect_month(
            _settings(args, require_password=False),
            args.month,
            args.output,
            context_files=args.context,
            department=args.department,
            work_description=args.work_description,
            compact=not args.full,
        )
        evidence = load_json(target)
        _print(
            {
                "evidence": str(target.resolve()),
                "mode": evidence.get("mode"),
                "bytes": target.stat().st_size,
                "stats": evidence.get("stats", {}),
            }
        )
        return 0

    if args.command == "inspect-evidence":
        _print(
            inspect_evidence_sessions(
                args.evidence,
                session_ids=args.session,
                repositories=args.repository,
                queries=args.query,
                max_sessions=args.max_sessions,
                max_messages=args.max_messages,
                max_characters=args.max_characters,
            )
        )
        return 0

    if args.command == "draft":
        target = create_draft_file(args.evidence, _settings(args, require_password=False), args.output)
        draft_data = load_json(target)
        _print(
            {
                "draft": str(target.resolve()),
                "stories": len(draft_data.get("stories", [])),
                "tasks": len(draft_data.get("tasks", [])),
                "bugs": len(draft_data.get("bugs", [])),
                "bug_candidates": len(draft_data.get("bug_candidates", [])),
                "unclassified": len(draft_data.get("unclassified", [])),
            }
        )
        return 0

    if args.command == "validate":
        errors = validate_draft(load_json(args.draft), _settings(args, require_password=False))
        _print({"ok": not errors, "errors": errors})
        return 1 if errors else 0

    if args.command == "preview":
        draft = load_json(args.draft)
        errors = validate_draft(draft, _settings(args, require_password=False))
        _print({"ok": not errors, "errors": errors, "records": preview_draft(draft)})
        return 1 if errors else 0

    if args.command == "upload":
        settings = _settings(args, network=True)
        draft = load_json(args.draft)
        errors = validate_draft(draft, settings)
        rows = preview_draft(draft)
        _print({"environment": settings.environment_name, "records": rows, "errors": errors})
        if errors:
            return 1
        if not args.yes:
            answer = input("Upload these records to ZenTao? Type YES to continue: ").strip()
            if answer != "YES":
                print("Cancelled.")
                return 2
        manifest = args.manifest or str(
            Path("records")
            / "manifests"
            / f"{draft['month']}-{settings.requested_environment_name}.json"
        )
        result = BatchUploader(settings, manifest).upload(draft)
        _print(result)
        return 0

    if args.command == "verify":
        rows = verify_manifest(_settings(args, network=True), load_json(args.manifest))
        _print(rows)
        failed = [
            row
            for row in rows
            if not row["found"]
            or row["title"] != row["expected_title"]
            or (row["type"] == "task" and row["actual_status"] != "done")
            or (
                row["type"] == "bug"
                and (row["actual_status"] != "resolved" or row.get("resolution") != "fixed")
            )
            or row.get("commented_actions", 0) < row.get("expected_comments", 0)
        ]
        return 1 if failed else 0

    if args.command == "comment":
        settings = _settings(args, network=True)
        web = ZentaoWebComments.from_settings(settings)
        web.add_comment(args.object_type, args.object_id, args.text)
        _print({"ok": True, "type": args.object_type, "id": args.object_id})
        return 0

    if args.command == "verify-june-2026":
        from scripts.zentao_june_records_helper import CREATED_BUGS, CREATED_TASKS
        from .batch import verify_records
        from .client import ZentaoClient

        rows = verify_records(ZentaoClient.from_settings(_settings(args)), CREATED_TASKS, CREATED_BUGS)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        failed = [
            row
            for row in rows
            if not row["found"]
            or (row["type"] == "task" and row["status"] != "done")
            or (row["type"] == "bug" and (row["status"] != "resolved" or row.get("resolution") != "fixed"))
        ]
        return 1 if failed else 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
