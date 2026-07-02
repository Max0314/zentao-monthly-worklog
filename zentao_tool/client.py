import json
import os
import urllib.request


DEFAULT_BASE_WEB = "http://10.70.33.19/biz"
DEFAULT_BASE_API = DEFAULT_BASE_WEB + "/api.php/v1"


class ZentaoClient:
    def __init__(self, base_api=DEFAULT_BASE_API, account=None, password=None):
        self.base_api = base_api.rstrip("/")
        self.account = account or os.environ.get("ZENTAO_ACCOUNT", "chenpenglie")
        self.password = password or os.environ["ZENTAO_PASSWORD"]
        self._token = None

    @property
    def token(self):
        if not self._token:
            self._token = self.login()
        return self._token

    def login(self):
        payload = {"account": self.account, "password": self.password}
        data = json.dumps(payload, ensure_ascii=True).encode("ascii")
        req = urllib.request.Request(
            self.base_api + "/tokens",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["token"]

    def request(self, method, path, payload=None):
        data = None
        headers = {"Token": self.token}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode("ascii")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(
            self.base_api + path,
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def list_execution_tasks(self, execution_id, limit=300):
        return self.request("GET", f"/executions/{execution_id}/tasks?limit={limit}").get("tasks", [])

    def list_execution_bugs(self, execution_id, limit=300):
        return self.request("GET", f"/executions/{execution_id}/bugs?limit={limit}").get("bugs", [])

    def create_task(self, execution_id, title, detail, assigned_to=None, estimate=3, date=None):
        date = date or ""
        payload = {
            "name": title,
            "type": "devel",
            "pri": 3,
            "assignedTo": assigned_to or self.account,
            "estimate": estimate,
            "left": estimate,
            "desc": detail,
            "stageAttr": "dev",
        }
        if date:
            payload["estStarted"] = date
            payload["deadline"] = date
        return self.request("POST", f"/executions/{execution_id}/tasks", payload)

    def finish_task(self, task_id, consumed=3, date=None):
        payload = {
            "status": "done",
            "assignedTo": self.account,
            "consumed": consumed,
            "left": 0,
            "finishedBy": self.account,
        }
        if date:
            payload["finishedDate"] = date
        return self.request("PUT", f"/tasks/{task_id}", payload)

    def create_bug(self, product_id, execution_id, project_id, title, detail, assigned_to=None):
        payload = {
            "title": title,
            "project": project_id,
            "execution": execution_id,
            "branch": 0,
            "module": 0,
            "type": "codeerror",
            "severity": 3,
            "pri": 3,
            "steps": detail,
            "openedBuild": "trunk",
            "assignedTo": assigned_to or self.account,
            "confirmed": 1,
        }
        return self.request("POST", f"/products/{product_id}/bugs", payload)

    def resolve_bug(self, bug_id, date=None):
        payload = {
            "status": "resolved",
            "resolution": "fixed",
            "resolvedBy": self.account,
            "resolvedBuild": "trunk",
            "openedBuild": "trunk",
            "assignedTo": self.account,
        }
        if date:
            payload["resolvedDate"] = date
        return self.request("PUT", f"/bugs/{bug_id}", payload)


def extract_created_id(data, key):
    if isinstance(data, dict):
        if isinstance(data.get(key), dict) and data[key].get("id"):
            return int(data[key]["id"])
        if data.get("id"):
            return int(data["id"])
        if isinstance(data.get("data"), dict) and data["data"].get("id"):
            return int(data["data"]["id"])
    raise ValueError(f"Cannot find created {key} id in response: {data!r}")

