import json
from pathlib import Path
import subprocess

APP = Path(__file__).resolve().parents[1] / 'build/AI Egress Guard.app/Contents/MacOS/AI-Egress-Guard'

def check(provider):
    r = subprocess.run([str(APP), '--check', provider], capture_output=True, text=True, timeout=45)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d['provider'] == provider and d['mode'] == 'preflight_only', d
    assert d['browserOAuth'] == 'not_covered' and d['mcp'] == 'not_covered', d
    assert d['status'] in ('passed', 'blocked'), d
    assert d['evidence'], d
    assert ('claude.ai:' if provider == 'claude' else 'chatgpt.com:') in d['evidence'], d
    if provider == 'claude':
        assert 'chatgpt.com:' not in d['evidence'], d
    else:
        assert 'claude.ai:' not in d['evidence'], d
    print(f'{provider}: {d["status"]}; preflight only; browser OAuth and MCP not covered')

if __name__ == '__main__':
    check('claude')
    check('codex')
    r = subprocess.run([str(APP), '--check', 'unknown'], capture_output=True, timeout=5)
    assert r.returncode == 2
    print('unknown provider rejected')
