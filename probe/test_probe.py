"""Loopback tests. Only documentation addresses (RFC 5737 / 3849) are used as
'observed' values; the observer is a local HTTP server, nothing leaves the host."""
import contextlib, http.server, io, itertools, json, os, threading, unittest
import hachi_probe as hp


def serve(replies):
    it = itertools.cycle(replies)
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            r = next(it)
            if r is None:
                self.send_response(500); self.end_headers(); return
            self.send_response(200); self.end_headers(); self.wfile.write(r.encode())
        def log_message(self, *a): pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}/"


class T(unittest.TestCase):
    def check(self, replies, expected, status, samples=3, role="cloud"):
        s, url = serve(replies)
        try:
            out = hp.run(url, expected, "demo", samples, role)
        finally:
            s.shutdown()
            s.server_close()
        self.assertEqual(out["status"], status)
        self.assertTrue(out["read_only"])
        return out

    def test_match(self):
        o = self.check(["ip=203.0.113.7\nloc=XX\n"], "203.0.113.0/24", "match")
        self.assertEqual(o["observed_ip_masked"], "203.0.113.0/24")
        self.assertNotIn("203.0.113.7", json.dumps(o))

    def test_mismatch(self):
        self.check(["198.51.100.9"], "203.0.113.0/24", "mismatch")

    def test_ipv6(self):
        o = self.check(["2001:db8::1"], "2001:db8::/32", "match")
        self.assertEqual(o["ip_family"], "ipv6")

    def test_unstable_is_unverified(self):
        self.check(["203.0.113.7", "198.51.100.9"], "203.0.113.0/24", "unverified")

    def test_failure_is_unverified(self):
        self.check([None], "203.0.113.0/24", "unverified")

    def test_single_sample_failure_not_pass(self):
        self.check(["203.0.113.7", "203.0.113.7", None], "203.0.113.0/24", "unverified")

    def test_no_expected_is_unverified(self):
        self.check(["203.0.113.7"], None, "unverified")

    def test_bad_expected_is_unverified_not_mismatch(self):
        o = self.check(["203.0.113.7"], "not-an-ip", "unverified")
        self.assertEqual(o["reason"], "bad_expected")

    def test_cli_bad_expected_exit_code_is_2(self):
        s, url = serve(["203.0.113.7"])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = hp.main(["--endpoint", url, "--expected", "junk", "--samples", "1"])
        finally:
            s.shutdown(); s.server_close()
        self.assertEqual(code, 2)

    def test_family_differs_both_ways(self):
        o = self.check(["2001:db8::1"], "203.0.113.0/24", "unverified")
        self.assertEqual(o["reason"], "family_differs")
        self.check(["203.0.113.7"], "2001:db8::/32", "unverified")

    def test_role_wording(self):
        o = self.check(["198.51.100.9"], "203.0.113.0/24", "mismatch", role="local")
        self.assertIn("这台电脑", o["plain"]["detail"])
        self.assertNotIn("云主机", o["plain"]["detail"])

    def test_redirect_is_not_trusted(self):
        class R(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/")
                self.end_headers()
            def log_message(self, *a): pass
        s = http.server.HTTPServer(("127.0.0.1", 0), R)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        try:
            out = hp.run(f"http://127.0.0.1:{s.server_port}/", "203.0.113.0/24", "x", 1)
        finally:
            s.shutdown(); s.server_close()
        self.assertEqual(out["status"], "unverified")
        self.assertEqual(out["evidence"]["samples_failed"], 1)

    def test_multiline_reply_takes_first_address_line(self):
        self.check(["fl=1\nip=203.0.113.7\nloc=XX\n"], "203.0.113.0/24", "match")

    def test_proxy_env_ignored_by_default(self):
        s, url = serve(["203.0.113.7"])
        old = os.environ.get("HTTP_PROXY")
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"  # dead proxy: would fail if used
        try:
            out = hp.run(url, "203.0.113.0/24", "x", 1)
            self.assertEqual(out["status"], "match")
            self.assertTrue(out["evidence"]["proxy_env_detected"])
            self.assertFalse(out["evidence"]["proxy_env_used"])
            self.assertIn("代理环境变量", out["plain"]["detail"])
            out = hp.run(url, "203.0.113.0/24", "x", 1, use_env_proxy=True)
            self.assertTrue(out["evidence"]["proxy_env_used"])
            self.assertNotIn("代理环境变量，本次检查没有使用", out["plain"]["detail"])
        finally:
            if old is None: os.environ.pop("HTTP_PROXY", None)
            else: os.environ["HTTP_PROXY"] = old
            s.shutdown(); s.server_close()

    def test_bad_scheme(self):
        out = hp.run("file:///etc/passwd", "203.0.113.0/24", "x", 1)
        self.assertEqual(out["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
