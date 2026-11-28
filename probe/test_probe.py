"""Loopback tests. Only documentation addresses (RFC 5737 / 3849) are used as
'observed' values; the observer is a local HTTP server, nothing leaves the host."""
import http.server, itertools, json, threading, unittest
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
    def check(self, replies, expected, status, samples=3):
        s, url = serve(replies)
        try:
            out = hp.run(url, expected, "demo", samples)
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

    def test_bad_scheme(self):
        out = hp.run("file:///etc/passwd", "203.0.113.0/24", "x", 1)
        self.assertEqual(out["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
