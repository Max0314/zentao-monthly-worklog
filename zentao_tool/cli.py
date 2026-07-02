import argparse
import json
import sys

from .client import ZentaoClient
from .web_comments import ZentaoWebComments


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zentao-tool")
    sub = parser.add_subparsers(dest="command", required=True)

    comment_parser = sub.add_parser("comment", help="Add a real ZenTao web comment.")
    comment_parser.add_argument("object_type", choices=["task", "bug"])
    comment_parser.add_argument("object_id", type=int)
    comment_parser.add_argument("text")

    sub.add_parser("verify-june-2026", help="Verify the 2026-06 created task/bug batch.")

    args = parser.parse_args(argv)

    if args.command == "comment":
        web = ZentaoWebComments()
        web.add_comment(args.object_type, args.object_id, args.text)
        print(json.dumps({"ok": True, "type": args.object_type, "id": args.object_id}, ensure_ascii=False))
        return 0

    if args.command == "verify-june-2026":
        from scripts.zentao_june_records_helper import CREATED_BUGS, CREATED_TASKS
        from .batch import verify_records

        client = ZentaoClient()
        rows = verify_records(client, CREATED_TASKS, CREATED_BUGS)
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

