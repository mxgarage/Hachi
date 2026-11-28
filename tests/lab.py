"""Loopback-only fixture; never starts an official client or reads credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone

# HACHI_APP: test an already-built (e.g. downloaded, signed) Hachi.app instead of build/Hachi.app
APP = Path(os.environ.get('HACHI_APP') or Path(__file__).resolve().parents[1] / 'build/Hachi.app') / 'Contents/MacOS/Hachi'
CASES = dict(approved=(200, {'route': 'lab-approved'}, 'matched'), drift=(200, {'route': 'lab-other'}, 'mismatch'), malformed=(200, 'not-json', 'unknown'), outage=(503, {}, 'unknown'), redirect=(302, {}, 'unknown'), oversize=(200, {'route': 'lab-approved', 'pad': 'x' * 2048}, 'unknown'))
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

def status(record, raw=None):
    """Run `status --json` against a synthetic record file (None = no file). Returns (exit code, parsed JSON, stdout)."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'record.json'
        if record is not None or raw is not None:
            path.write_text(raw if raw is not None else json.dumps(record))
        r = subprocess.run([str(APP), 'status', '--json'], capture_output=True, text=True, timeout=10,
                           env={**os.environ, 'HACHI_STATUS_RECORD': str(path)})
    return r.returncode, json.loads(r.stdout), r.stdout

def status_cases():
    now = datetime.now(timezone.utc)
    iso = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
    good = dict(checked_at=iso(now - timedelta(minutes=5)), checks=5, successes=5,
                observed_ip='203.0.113.10', recorded_prefix='203.0.113')
    def with_(**kw):
        return {**good, **kw}
    # (name, record, raw, expected status, expected exit code)
    cases = [
        ('ok', good, None, 'ok', 0),
        ('ok-ipv6', with_(observed_ip='2001:db8:1:2:3:4:5:6', recorded_prefix='2001:db8:1::/48'), None, 'ok', 0),
        ('attention', with_(observed_ip='198.51.100.7'), None, 'attention', 1),
        ('attention-family', with_(observed_ip='2001:db8:1::1'), None, 'attention', 1),
        ('stale', with_(checked_at=iso(now - timedelta(days=3))), None, 'stale', 2),
        ('no-file', None, None, 'setup_incomplete', 2),
        ('empty-record', {}, None, 'setup_incomplete', 2),
        ('no-recorded-prefix', {k: v for k, v in good.items() if k != 'recorded_prefix'}, None, 'setup_incomplete', 2),
        ('bad-recorded-prefix', with_(recorded_prefix='not-an-address'), None, 'setup_incomplete', 2),
        ('unstable', with_(successes=4), None, 'unverified', 2),
        ('no-checks', with_(checks=0, successes=0), None, 'unverified', 2),
        ('successes-exceed-checks', with_(successes=6), None, 'unverified', 2),
        ('no-observed', {k: v for k, v in good.items() if k != 'observed_ip'}, None, 'unverified', 2),
        ('bad-observed', with_(observed_ip='999.1.1.1'), None, 'unverified', 2),
        ('no-time', {k: v for k, v in good.items() if k != 'checked_at'}, None, 'unverified', 2),
        ('future-time', with_(checked_at=iso(now + timedelta(hours=2))), None, 'unverified', 2),
        ('malformed', None, 'not-json', 'unverified', 2),
        ('wrong-type', with_(checks='5'), None, 'unverified', 2),
    ]
    for name, record, raw, expected, code in cases:
        rc, out, text = status(record, raw)
        assert (rc, out['status']) == (code, expected), (name, rc, out)
        assert out['schema'] == 1 and out['needs_cloud_check'] == (expected != 'ok'), (name, out)
        assert set(out) == {'schema', 'status', 'checked_at', 'checks', 'successes', 'observed_prefix', 'recorded_prefix', 'needs_cloud_check'}, out
        # only the first three segments (IPv6: first 48 bits) may appear; the host part never does
        for full in ('203.0.113.10', '198.51.100.7', '2001:db8:1:2:3:4:5:6', '2001:db8:1::1'):
            assert full not in text, (name, text)
    rc, out, _ = status(good)
    assert out['observed_prefix'] == '203.0.113' and out['recorded_prefix'] == '203.0.113', out
    rc, out, _ = status(with_(observed_ip='198.51.100.7'))
    assert out['observed_prefix'] == '198.51.100' and '.7' not in out['observed_prefix'], out
    rc, out, _ = status(with_(observed_ip='2001:db8:1:2:3:4:5:6'))
    assert out['observed_prefix'] == '2001:db8:1::/48', out
    h = subprocess.run([str(APP), 'status', '--help'], capture_output=True, text=True, timeout=10)
    assert h.returncode == 0 and '只读，不修改任何设置' in h.stdout, h
    print(f'PASS: status --json, {len(cases)} cases covering every status; addresses truncated to the first three segments; --help says read-only')

def main():
    with ThreadingHTTPServer(('127.0.0.1', 0), Observer) as observer:
        port = observer.server_port
        threading.Thread(target=observer.serve_forever, daemon=True).start()
        try:
            for case, (_, _, expected) in CASES.items():
                r = run('--lab-probe', f'http://127.0.0.1:{port}/{case}', 'lab-approved')
                assert r.returncode == 0, (case, r.stderr, r.returncode)
                assert json.loads(r.stdout) == {'status': expected, 'mode': 'synthetic_probe_only'}, (case, r.stdout)
            rejected = (
                f'http://127.0.0.1:{port}/approved?secret=never-send',
                'https://example.invalid/probe',
                f'http://user:pw@127.0.0.1:{port}/approved',
                f'http://127.0.0.1:{port}/approved#x',
                f'http://localhost:{port}/approved',
                'http://127.0.0.1/approved',
                'http://127.0.0.1:0/approved',
            )
            for url in rejected:
                r = run('--lab-probe', url, 'lab-approved')
                assert r.returncode == 2, (url, r.returncode, r.stdout)
            r = run('--lab-probe', f'http://127.0.0.1:{port}/approved', '')
            assert r.returncode == 2, ('empty expected', r.returncode, r.stdout)
            assert seen == [(f'/{case}', None, None) for case in CASES], seen
            print(f'PASS: {len(CASES)} live loopback scenarios, {len(rejected)} rejected URLs, empty expected rejected; no credentials or redirect follows')
        finally:
            observer.shutdown()
    r = run('--lab-probe', f'http://127.0.0.1:{port}/approved', 'lab-approved')
    assert r.returncode == 0 and json.loads(r.stdout)['status'] == 'unknown', r
    print('PASS: closed-port failure never reports matched')
    status_cases()

if __name__ == '__main__':
    main()
