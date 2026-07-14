import html
import json
import os
import re
import ssl
import urllib.parse
import urllib.request


DEFAULT_BASE_WEB = "http://10.70.33.19/biz"


class ZentaoWebComments:
    def __init__(
        self,
        base_web=DEFAULT_BASE_WEB,
        base_api=None,
        account=None,
        password=None,
        token=None,
        token_provider=None,
        verify_tls=True,
        timeout=30,
    ):
        self.base_web = base_web.rstrip("/")
        self.base_api = (base_api or (self.base_web + "/api.php/v1")).rstrip("/")
        self.account = account or os.environ.get("ZENTAO_ACCOUNT", "chenpenglie")
        self.password = password or os.environ["ZENTAO_PASSWORD"]
        self.verify_tls = verify_tls
        self.timeout = timeout
        self._token = token
        self._token_provider = token_provider
        handlers = []
        if not verify_tls:
            handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
        self.opener = urllib.request.build_opener(*handlers)

    @classmethod
    def from_settings(cls, settings, token=None, token_provider=None):
        return cls(
            base_web=settings.base_web,
            base_api=settings.base_api,
            account=settings.account,
            password=settings.password,
            token=token,
            token_provider=token_provider,
            verify_tls=settings.verify_tls,
            timeout=settings.timeout,
        )

    @property
    def token(self):
        if not self._token:
            if self._token_provider:
                self._token = self._token_provider()
                return self._token
            payload = json.dumps(
                {"account": self.account, "password": self.password}, ensure_ascii=True
            ).encode("ascii")
            req = urllib.request.Request(
                self.base_api + "/tokens",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with self.opener.open(req, timeout=self.timeout) as response:
                self._token = json.load(response)["token"]
        return self._token

    def _headers(self, **extra):
        headers = {
            "Token": self.token,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0",
        }
        headers.update(extra)
        return headers

    def get_comment_form(self, object_type, object_id):
        self._validate_type(object_type)
        url = f"{self.base_web}/action-comment-{object_type}-{object_id}.html"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with self.opener.open(req, timeout=self.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        uid_match = re.search(r'name="uid"\s+value="([^"]+)"', body)
        if not uid_match:
            raise RuntimeError(
                f"ZenTao comment form for {object_type} {object_id} did not contain uid"
            )
        return url, uid_match.group(1)

    def add_comment(self, object_type, object_id, text):
        url, uid = self.get_comment_form(object_type, object_id)
        data = urllib.parse.urlencode(
            {"actioncomment": to_html(text), "uid": uid}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(
                **{
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                }
            ),
            method="POST",
        )
        with self.opener.open(req, timeout=self.timeout) as response:
            body = response.read()
        try:
            result = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            result = {}
        if result.get("result") == "fail":
            raise RuntimeError(f"ZenTao comment failed: {result}")
        return body

    @staticmethod
    def _validate_type(object_type):
        if object_type not in {"task", "bug", "story"}:
            raise ValueError("object_type must be 'task', 'bug', or 'story'")


def to_html(text):
    return "<p>" + html.escape(text).replace("\n", "<br />") + "</p>"
