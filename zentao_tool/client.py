import json
import os
import ssl
import urllib.error
import urllib.request


DEFAULT_BASE_WEB = "http://10.70.33.19/biz"
DEFAULT_BASE_API = DEFAULT_BASE_WEB + "/api.php/v1"


class ZentaoClient:
    def __init__(
        self,
        base_api=DEFAULT_BASE_API,
        base_web=DEFAULT_BASE_WEB,
        account=None,
        password=None,
        verify_tls=True,
        timeout=30,
    ):
        self.base_api = base_api.rstrip("/")
        self.base_web = base_web.rstrip("/")
        self.account = account or os.environ.get("ZENTAO_ACCOUNT", "")
        self.password = password or os.environ.get("ZENTAO_PASSWORD", "")
        self.verify_tls = verify_tls
        self.timeout = timeout
        self._token = None

    @classmethod
    def from_settings(cls, settings):
        return cls(
            base_api=settings.base_api,
            base_web=settings.base_web,
            account=settings.account,
            password=settings.password,
            verify_tls=settings.verify_tls,
            timeout=settings.timeout,
        )

    @property
    def ssl_context(self):
        if self.verify_tls:
            return None
        return ssl._create_unverified_context()

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
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                return json.load(resp)["token"]
        except urllib.error.HTTPError as exc:
            raise ZentaoApiError("POST", "/tokens", exc.code, exc.read()) from exc

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
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise ZentaoApiError(method, path, exc.code, exc.read()) from exc
        return json.loads(raw.decode("utf-8")) if raw else {}

    def ping(self):
        return self.request("GET", "/products?limit=1")

    def list_execution_tasks(self, execution_id, limit=300):
        return self.request("GET", f"/executions/{execution_id}/tasks?limit={limit}").get("tasks", [])

    def list_execution_bugs(self, execution_id, limit=300):
        return self.request("GET", f"/executions/{execution_id}/bugs?limit={limit}").get("bugs", [])

    def list_product_stories(self, product_id, limit=300):
        return self.request("GET", f"/products/{product_id}/stories?limit={limit}").get("stories", [])

    def get_task(self, task_id):
        return self.request("GET", f"/tasks/{task_id}")

    def get_bug(self, bug_id):
        return self.request("GET", f"/bugs/{bug_id}")

    def get_story(self, story_id):
        return self.request("GET", f"/stories/{story_id}")

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

    def create_story(
        self,
        product_id,
        title,
        detail,
        project_id=0,
        execution_id=0,
        assigned_to=None,
        estimate=3,
        verify="",
    ):
        payload = {
            "product": product_id,
            "title": title,
            "pri": 3,
            "module": 0,
            "parent": 0,
            "estimate": estimate,
            "spec": detail,
            "category": 1,
            "source": "dev",
            "verify": verify,
            "assignedTo": assigned_to or self.account,
            "project": project_id,
            "execution": execution_id,
        }
        return self.request("POST", "/stories", payload)

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


class ZentaoApiError(RuntimeError):
    def __init__(self, method, path, status, body):
        text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        super().__init__(f"ZenTao API {method} {path} failed with HTTP {status}: {text[:500]}")
        self.status = status
        self.body = text
