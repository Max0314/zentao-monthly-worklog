import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zentao_tool.batch import verify_records
from zentao_tool.client import ZentaoClient
from zentao_tool.config import load_settings
from scripts.zentao_june_records_helper import CREATED_BUGS, CREATED_TASKS


def main():
    client = ZentaoClient.from_settings(load_settings())
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


if __name__ == "__main__":
    raise SystemExit(main())
