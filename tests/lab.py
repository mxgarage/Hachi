"""Loopback-only fixture; never starts an official client or reads credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading

APP = Path(__file__).resolve().parents[1] / 'build/Hachi.app/Contents/MacOS/Hachi'
CASES = dict(approved=(200, {'route': 'lab-approved'}, 'matched'), drift=(200, {'route': 'lab-other'}, 'mismatch'), malformed=(200, 'not-json', 'unknown'), outage=(503, {}, 'unknown'), redirect=(302, {}, 'unknown'))
seen = []

class Observer(BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append((self.path, self.headers.get('Authorization'), self.headers.get('Cookie')))
        status, body, _ = CASES.get(self.path.strip('/'), (404, {}, 'unknown'))
        self.send_response(status)
        if status == 302:
            self.send_header('Location', '/approved')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass

def run(*args):
    return subprocess.run([str(APP), *args], capture_output=True, text=True, timeout=10)

def main():
    with ThreadingHTTPServer(('127.0.0.1', 0), Observer) as observer:
        port = observer.server_port
        threading.Thread(target=observer.serve_forever, daemon=True).start()
        try:
            for case, (_, _, expected) in CASES.items():
                r = run('--lab-probe', f'http://127.0.0.1:{port}/{case}', 'lab-approved')
                assert r.returncode == 0, (case, r.stderr, r.returncode)
                assert json.loads(r.stdout) == {'status': expected, 'mode': 'synthetic_probe_only'}, (case, r.stdout)
            for url in (f'http://127.0.0.1:{port}/approved?secret=never-send', 'https://example.invalid/probe'):
                assert run('--lab-probe', url, 'lab-approved').returncode == 2
            assert seen == [(f'/{case}', None, None) for case in CASES], seen
            print('PASS: 5 live loopback scenarios, 2 rejected URLs; no credentials or redirect follows')
        finally:
            observer.shutdown()
    r = run('--lab-probe', f'http://127.0.0.1:{port}/approved', 'lab-approved')
    assert r.returncode == 0 and json.loads(r.stdout)['status'] == 'unknown', r
    print('PASS: closed-port failure never reports matched')

if __name__ == '__main__':
    main()
