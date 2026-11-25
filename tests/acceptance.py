"""Automated acceptance: baseline checks + release-gate evaluation.

Baseline (must pass on every PR): build, loopback lab, branding, gate self-test, repo hygiene,
README gate heading consistent with the evaluated gate.
Release gate (release-gate.json): each item is evaluated from evidence/ files.
Missing or malformed evidence is reported as not met, never as a pass.

  python3 tests/acceptance.py                 # baseline + gate report (exit 1 only if baseline fails)
  python3 tests/acceptance.py --gate-only     # no build/tests; works on any OS
  python3 tests/acceptance.py --require-gate  # also exit 1 if any gate item is not met
Reports: build/acceptance/report.md and report.json.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'acceptance'
SHA = re.compile(r'^[0-9a-f]{40}$')

# ---------- baseline ----------

def run_step(name, cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    return dict(name=name, ok=r.returncode == 0, detail=' / '.join(tail))

SECRET_PATTERNS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), 'private key'),
    (re.compile(r'\bsk-ant-[A-Za-z0-9_-]{10,}'), 'Anthropic key'),
    (re.compile(r'\bsk-[A-Za-z0-9]{32,}'), 'API key'),
    (re.compile(r'\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}'), 'GitHub token'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), 'AWS key'),
    (re.compile(r'/Users/(?!Shared/)[A-Za-z0-9._-]+/'), 'device path'),
]
IPV4 = re.compile(r'(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])')
ALLOWED_IP_PREFIXES = ('127.', '0.0.0.0', '192.0.2.', '198.51.100.', '203.0.113.')

def hygiene():
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    problems = []
    for f in filter(None, files):
        path = ROOT / f.decode()
        if path.name == 'acceptance.py' and path.parent.name == 'tests':
            continue  # this file holds the patterns themselves
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    problems.append(f'{path.relative_to(ROOT)}:{n} {label}')
            for m in IPV4.finditer(line):
                ip = m.group(0)
                if all(int(p) <= 255 for p in m.groups()) and not ip.startswith(ALLOWED_IP_PREFIXES):
                    problems.append(f'{path.relative_to(ROOT)}:{n} IP address {ip} (use 192.0.2.x/198.51.100.x/203.0.113.x)')
    return dict(name='repo hygiene (no keys, tokens, device paths, real IPs)', ok=not problems,
                detail='; '.join(problems[:10]) or 'clean')

def readme_consistent(all_met):
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    m = re.search(r'^## Release gate \((met|not met)\)', text, re.M)
    if not m:
        return dict(name='README release-gate heading', ok=False, detail='heading "## Release gate (not met)" missing')
    claimed = m.group(1) == 'met'
    ok = claimed == all_met
    return dict(name='README release-gate heading', ok=ok,
                detail=f'README says "{m.group(1)}", evidence says "{"met" if all_met else "not met"}"')

# ---------- gate ----------

def wilson_lower(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d

def common(ev):
    errs = []
    if not SHA.match(str(ev.get('tested_commit', ''))):
        errs.append('tested_commit 必须是 40 位提交哈希')
    if not ev.get('environments'):
        errs.append('environments 为空（需写明 OS/架构）')
    if ev.get('credentials') not in ('none', 'synthetic', 'authorized_test'):
        errs.append('credentials 必须是 none / synthetic / authorized_test（不能用真实平台账号）')
    if not ev.get('raw_results'):
        errs.append('raw_results 为空（需指向原始记录，例如 CI 产物或日志链接）')
    return errs

def eval_workflow_success(item, ev):
    errs, notes = [], []
    if not ev.get('matrix_preregistered'):
        errs.append('matrix_preregistered 为空（需指向事先登记的场景矩阵）')
    flows = ev.get('workflows', {})
    for name in item['workflows']:
        w = flows.get(name)
        if not isinstance(w, dict):
            errs.append(f'{name}: 没有数据（缺覆盖不算通过）')
            continue
        if w.get('supported') is False:
            # 声明的工作流不能靠证据自行豁免；要缩小范围，由维护者改 release-gate.json 和 README。
            errs.append(f'{name}: 证据标为不支持；声明的工作流必须有数据，缩小范围需维护者从 release-gate.json 和 README 中删除它')
            continue
        n, k = int(w.get('attempts', 0)), int(w.get('successes', 0))
        if not w.get('seeds'):
            errs.append(f'{name}: 没记录种子')
        if n < item['min_attempts']:
            errs.append(f'{name}: 次数 {n} < {item["min_attempts"]}')
            continue
        rate, low = k / n, wilson_lower(k, n)
        notes.append(f'{name}: {k}/{n} = {rate:.1%}（Wilson 95% 下界 {low:.1%}）')
        if low < item['min_rate']:
            # 判定用置信下界而不是点估计：样本必须足以说明总体成功率 ≥ min_rate。
            errs.append(f'{name}: 成功率 95% 置信下界 {low:.1%} < {item["min_rate"]:.0%}（点估计 {rate:.1%}，需要更多次数或更少失败）')
    return errs, notes

def eval_critical_failures(item, ev):
    errs = []
    obs = ev.get('observer', {})
    if obs.get('independent') is not True:
        errs.append('observer.independent 必须为 true（应用日志不算）')
    for key in ('protected_flows', 'control_workloads'):
        if int(ev.get(key, 0)) <= 0:
            errs.append(f'{key} 必须 > 0')
    for key in ('direct_or_wrong_route_egress', 'control_interruptions', 'control_route_changes'):
        if key not in ev:
            errs.append(f'缺少 {key}')
        elif int(ev[key]) != 0:
            errs.append(f'{key} = {ev[key]}（必须为 0）')
    return errs, [f'观察器：{obs.get("kind", "?")}']

def eval_lab_cases(item, ev):
    cases = ev.get('cases', {})
    missing = [c for c in item['cases'] if c not in cases]
    failed = [c for c in item['cases'] if c in cases and cases[c].get('result') != 'pass']
    errs = []
    if missing:
        errs.append('缺用例：' + ', '.join(missing))
    if failed:
        errs.append('未通过：' + ', '.join(failed))
    return errs, [f'{len(item["cases"]) - len(missing) - len(failed)}/{len(item["cases"])} 个用例通过']

def eval_transfer(item, ev):
    errs = []
    if not ev.get('fixture_clients'):
        errs.append('fixture_clients 为空')
    if not ev.get('signed_clients'):
        errs.append('signed_clients 为空')
    if ev.get('same_enforcement_mechanism') is not True:
        errs.append('same_enforcement_mechanism 必须为 true')
    gaps = ev.get('gaps_document', '')
    if not gaps or not (ROOT / gaps).is_file():
        errs.append('gaps_document 必须指向仓库里存在的差距文档')
    return errs, []

def eval_network_extension(item, ev):
    errs = []
    for key in ('signed_extension_loaded', 'data_plane_tested', 'unavailable_behavior_tested'):
        if ev.get(key) is not True:
            errs.append(f'{key} 必须为 true')
    return errs, []

EVALUATORS = dict(workflow_success=eval_workflow_success, critical_failures=eval_critical_failures,
                  lab_cases=eval_lab_cases, transfer=eval_transfer, network_extension=eval_network_extension)

def evaluate_gate():
    manifest = json.loads((ROOT / 'release-gate.json').read_text(encoding='utf-8'))
    results = []
    for item in manifest['items']:
        path = ROOT / item['evidence']
        if not path.is_file():
            errs, notes = [f'没有证据文件 {item["evidence"]}'], []
        else:
            try:
                ev = json.loads(path.read_text(encoding='utf-8'))
                errs, notes = EVALUATORS[item['kind']](item, ev)
                errs = common(ev) + errs
            except (ValueError, TypeError, AttributeError) as e:
                errs, notes = [f'证据文件格式错误：{e}'], []
        results.append(dict(id=item['id'], title=item['title'], met=not errs, problems=errs, notes=notes,
                            evidence=item['evidence'], next_step=item.get('next_step', ''), readme=item['readme']))
    return results

# ---------- report ----------

def report(baseline, gate, gate_only):
    met = sum(g['met'] for g in gate)
    lines = ['# Hachi 自动验收报告', '']
    if gate_only:
        lines += ['基线检查：本次未运行（--gate-only）', '']
    else:
        ok = all(b['ok'] for b in baseline)
        lines += [f'## 基线检查：{"通过" if ok else "失败"}', '']
        lines += [f'- {"✅" if b["ok"] else "❌"} {b["name"]} — {b["detail"]}' for b in baseline] + ['']
    lines += [f'## 发布门槛：{met}/{len(gate)} 项满足{"" if met == len(gate) else "（未达到发布条件）"}', '']
    for g in gate:
        lines.append(f'- {"✅" if g["met"] else "⬜"} **{g["id"]}** {g["title"]}')
        lines += [f'  - {p}' for p in g['problems'] + g['notes']]
    return '\n'.join(lines) + '\n'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gate-only', action='store_true', help='skip build/tests (works off macOS)')
    ap.add_argument('--require-gate', action='store_true', help='fail unless every gate item is met')
    args = ap.parse_args()

    baseline = []
    if not args.gate_only:
        py = sys.executable
        baseline.append(run_step('build (build.py)', [py, 'build.py']))
        if baseline[-1]['ok']:
            baseline.append(run_step('loopback lab (tests/lab.py)', [py, 'tests/lab.py']))
            baseline.append(run_step('branding (tests/branding.py)', [py, 'tests/branding.py']))
        baseline.append(run_step('gate evaluator self-test (tests/gate_selftest.py)', [py, 'tests/gate_selftest.py']))
        baseline.append(hygiene())
    gate = evaluate_gate()
    all_met = all(g['met'] for g in gate)
    if not args.gate_only:
        baseline.append(readme_consistent(all_met))

    text = report(baseline, gate, args.gate_only)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.md').write_text(text, encoding='utf-8')
    (OUT / 'report.json').write_text(json.dumps(dict(baseline=baseline, gate=gate, gate_met=all_met),
                                                ensure_ascii=False, indent=2), encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(text)
    print(text)
    if not all(b['ok'] for b in baseline):
        sys.exit(1)
    if args.require_gate and not all_met:
        print('FAIL: release gate not met', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
