import html
import http.cookiejar
import os
import urllib.parse
import urllib.request


DEFAULT_BASE_WEB = "http://10.70.33.19/biz"


class ZentaoWebComments:
    def __init__(self, base_web=DEFAULT_BASE_WEB, account=None, password=None):
        self.base_web = base_web.rstrip("/")
        self.account = account or os.environ.get("ZENTAO_ACCOUNT", "chenpenglie")
        self.password = password or os.environ["ZENTAO_PASSWORD"]
        self._opener = None

    @property
    def opener(self):
        if self._opener is None:
            self._opener = self.login()
        return self._opener

    def login(self):
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        data = urllib.parse.urlencode(
            {
                "account": self.account,
                "password": self.password,
                "referer": self.base_web,
                "keepLogin": "on",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base_web + "/user-login.html",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        opener.open(req, timeout=30).read()
        return opener

    def add_comment(self, object_type, object_id, text):
        if object_type not in {"task", "bug"}:
            raise ValueError("object_type must be 'task' or 'bug'")

        data = urllib.parse.urlencode({"actioncomment": to_html(text)}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_web}/action-comment-{object_type}-{object_id}.html",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
            method="POST",
        )
        return self.opener.open(req, timeout=30).read()


def to_html(text):
    return "<p>" + html.escape(text).replace("\n", "<br />") + "</p>"

