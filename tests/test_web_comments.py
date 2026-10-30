import io
import unittest

from zentao_tool.web_comments import ZentaoWebComments


class WebEntryTests(unittest.TestCase):
    def test_rejects_route_error_with_http_200(self):
        web = ZentaoWebComments(base_web="https://example.com/biz")

        class Opener:
            def open(self, request, timeout):
                self.url = request.full_url
                return io.BytesIO(b"biz/user-login illegal")

        web.opener = Opener()
        with self.assertRaisesRegex(RuntimeError, "not a login page"):
            web.check_web_entry()
        self.assertEqual(web.opener.url, "https://example.com/biz/user-login.html")

    def test_accepts_root_login_page(self):
        web = ZentaoWebComments(base_web="https://example.com")

        class Opener:
            def open(self, request, timeout):
                self.url = request.full_url
                return io.BytesIO(b'<form id="loginForm"><input name="password"></form>')

        web.opener = Opener()
        web.check_web_entry()
        self.assertEqual(web.opener.url, "https://example.com/user-login.html")


if __name__ == "__main__":
    unittest.main()
