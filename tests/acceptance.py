"""Automated acceptance: baseline checks + release-gate evaluation.

Baseline (must pass on every PR): build, loopback lab, branding, UX screenshots, gate self-test, repo hygiene,
README gate heading consistent with the evaluated gate.
Release gate (release-gate.json): each item is evaluated from evidence/ files.
Missing or malformed evidence is reported as not met, never as a pass.
What this can check: format, thresholds, and consistency with git history (tested_commit is an
ancestor, product files unchanged since, matrix present at tested_commit and unchanged). What it cannot check:
that a run really happened or the observer really was independent. Those are the maintainer's
claims, made by committing the evidence.

  python3 tests/acceptance.py                 # baseline + gate report (exit 1 only if baseline fails)
  python3 tests/acceptance.py --gate-only     # no build/tests; works on any OS
  python3 tests/acceptance.py --require-gate  # also exit 1 if any gate item is not met
Reports: build/acceptance/report.md and report.json.
"""
import argparse
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('HACHI_ACCEPTANCE_OUT') or ROOT / 'build' / 'acceptance')  # the self-test redirects this
SHA = re.compile(r'^[0-9a-f]{40}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')

# ---------- baseline ----------

def run_step(name, cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    if r.returncode:  # full output in the job log; the report keeps only the tail
        print(f'--- {name} failed ---\n{r.stdout}{r.stderr}', file=sys.stderr)
    return dict(name=name, ok=r.returncode == 0, detail=' / '.join(tail))

# hygiene-patterns-begin (only these lines are exempt from the hygiene scan)
SECRET_PATTERNS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), 'private key'),
    (re.compile(r'\bsk-ant-[A-Za-z0-9_-]{10,}'), 'Anthropic key'),
    (re.compile(r'\bsk-[A-Za-z0-9]{32,}'), 'API key'),
    (re.compile(r'\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}'), 'GitHub token'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), 'AWS key'),
    (re.compile(r'/Users/(?!Shared/)[A-Za-z0-9._-]+/|/home/(?!runner/)[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\\s]+'), 'device path'),
]
IPV4 = re.compile(r'(?<!\d)(?<!\d\.)(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?!\d|\.\d)')  # a trailing full stop still matches
ALLOWED_NETS = [ipaddress.ip_network(n) for n in
                ('127.0.0.0/8', '0.0.0.0/32', '192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24',
                 '::1/128', '2001:db8::/32')]
IPV6 = re.compile(r'(?<![0-9A-Za-z:])[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7}(?![0-9A-Za-z:])')

def looks_ipv6(t):
    """A real IPv6 address: parses, and has at least one group of 3+ hex digits, so code such as std::map,
    08:14:36 or slices like x[::2] / b[1::2] are not flagged."""
    try:
        ipaddress.IPv6Address(t)
    except ValueError:
        return False
    return any(len(g) >= 3 for g in t.split(':'))
MAC = re.compile(r'(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])')
# hygiene-patterns-end

def allowed_ip(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False  # e.g. a MAC address: also device-identifying
    return any(ip in net for net in ALLOWED_NETS if net.version == ip.version)

def hygiene():
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    problems = []
    for f in filter(None, files):
        path = ROOT / f.decode()
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        exempt = False
        for n, line in enumerate(text.splitlines(), 1):
            if path == Path(__file__).resolve():
                if '# hygiene-patterns-begin' in line or '# hygiene-patterns-end' in line:
                    exempt = '# hygiene-patterns-begin' in line
                    continue
                if exempt:
                    continue
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    problems.append(f'{path.relative_to(ROOT)}:{n} {label}')
            for m in IPV4.finditer(line):
                ip = m.group(0)
                if all(int(p) <= 255 for p in m.groups()) and not allowed_ip(ip):
                    problems.append(f'{path.relative_to(ROOT)}:{n} IP address {ip} (use 192.0.2.x/198.51.100.x/203.0.113.x)')
            for m in IPV6.finditer(line):
                ip = m.group(0).lower()
                if looks_ipv6(ip) and not allowed_ip(ip):
                    problems.append(f'{path.relative_to(ROOT)}:{n} IPv6 address {ip} (use 2001:db8::/32)')
            for m in MAC.finditer(line):
                problems.append(f'{path.relative_to(ROOT)}:{n} MAC address {m.group(0)}')
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

def count(v):
    """Strict non-negative integer: 0.5, "0", True and floats are rejected."""
    return v if type(v) is int and v >= 0 else None

def repo_file(rel, prefixes):
    """A relative path inside the repo under one of prefixes, that exists."""
    if not isinstance(rel, str) or not rel.startswith(prefixes):
        return False
    path = (ROOT / rel).resolve()
    return (path.is_relative_to(ROOT) and '..' not in Path(rel).parts and not (ROOT / rel).is_symlink()
            and path.is_file())

RAW_SUFFIXES = ('.json', '.jsonl', '.log', '.csv', '.pcap', '.pcapng')
DEFAULT_CREDENTIALS = ('none', 'synthetic')  # no authorized/live credentials path (AGENTS.md); adding one is a maintainer decision

def common(item, ev):
    errs = []
    if not SHA.match(str(ev.get('tested_commit', ''))):
        errs.append('tested_commit 必须是 40 位提交哈希')
    envs = ev.get('environments')
    if not isinstance(envs, list) or not envs or not all(isinstance(e, str) and e.strip() for e in envs):
        errs.append('environments 必须是非空的字符串列表（写明 OS/架构）')
    allowed = tuple(item.get('allowed_credentials', DEFAULT_CREDENTIALS))
    if ev.get('credentials') not in allowed:
        errs.append(f'credentials 必须是 {" / ".join(allowed)}（不能用真实平台账号）')
    # raw records are pinned by hash: {path: evidence/..., sha256} (hash checked here) or {url: https://..., sha256}
    # (for large captures; CI does not download it, so the hash is only the maintainer's record)
    raw = ev.get('raw_results')
    if not isinstance(raw, dict) or not SHA256.match(str(raw.get('sha256', ''))):
        errs.append('raw_results 必须是 {path 或 url, sha256}（64 位小写十六进制）')
    elif 'path' in raw:
        if (not repo_file(raw['path'], ('evidence/',)) or raw['path'] == 'evidence/README.md'
                or raw['path'] in {i['evidence'] for i in MANIFEST['items']}
                or not raw['path'].endswith(RAW_SUFFIXES)):
            errs.append(f'raw_results.path 必须是 evidence/ 下的原始记录文件（{"/".join(RAW_SUFFIXES)}，不能是 README）')
        elif hashlib.sha256((ROOT / raw['path']).read_bytes()).hexdigest() != raw['sha256']:
            errs.append('raw_results.sha256 与文件内容不符')
    elif not str(raw.get('url', '')).startswith('https://'):
        errs.append('raw_results.url 必须是 https 链接')
    return errs

# Everything that can affect the built app or the evidence runners: all tracked files except docs, evidence, the
# gate evaluator, CI and markdown.
# (git pathspec, so new source files, resources or a Network Extension target are covered automatically)
# tests/ counts too (the runners that produce evidence live there), except the gate evaluator itself.
PRODUCT_FILES = ['.', ':(exclude)docs/', ':(exclude)evidence/', ':(exclude)tests/acceptance.py',
                 ':(exclude)tests/gate_selftest.py', ':(exclude).github/',
                 ':(exclude)*.md', ':(exclude)release-gate.json', ':(exclude).gitignore']

GIT_ROOT = ROOT  # the self-test points this at a throwaway repository
RELEASE_COMMIT = None  # set by evaluate_gate; used when G3 checks the G1 waiver

def git(*args):
    return subprocess.run(['git', *args], cwd=GIT_ROOT, capture_output=True, text=True)

def provenance(ev, release_commit):
    """Evidence must describe code that is actually in this history and unchanged since."""
    commit = str(ev.get('tested_commit', ''))
    if not SHA.match(commit):
        return []  # reported by common()
    if git('cat-file', '-e', f'{commit}^{{commit}}').returncode != 0:
        return [f'tested_commit {commit[:7]} 不在仓库历史里（CI 需要完整历史 fetch-depth: 0）']
    target = release_commit or 'HEAD'
    errs = []
    if git('merge-base', '--is-ancestor', commit, target).returncode != 0:
        errs.append(f'tested_commit {commit[:7]} 不是 {target[:12]} 的祖先'
                    '（证据要在已合入 main 的提交上测；squash/rebase 合并会让 PR 分支上的提交不在 main 历史里）')
    elif git('diff', '--quiet', commit, target, '--', *PRODUCT_FILES).returncode != 0:
        changed = git('diff', '--name-only', commit, target, '--', *PRODUCT_FILES).stdout.split()
        errs.append(f'证据已过期：产品文件（{", ".join(changed[:5])}）在 {commit[:7]} 之后有改动，需要重新测')
    matrix = ev.get('matrix_preregistered')
    if isinstance(matrix, str):
        if git('cat-file', '-e', f'{commit}:{matrix}').returncode != 0:
            errs.append(f'matrix_preregistered {matrix} 在 tested_commit 时还不存在（不算事先登记）')
        elif git('diff', '--quiet', commit, target, '--', matrix).returncode != 0:
            errs.append(f'matrix_preregistered {matrix} 在 tested_commit 之后被改过，需要按新矩阵重新测')
    return errs

def eval_workflow_success(item, ev):
    errs, notes = [], []
    if not repo_file(ev.get('matrix_preregistered'), ('docs/', 'tests/')):
        errs.append('matrix_preregistered 必须指向 docs/ 或 tests/ 下事先提交的场景矩阵')
    flows = ev.get('workflows', {})
    for name in item['workflows']:
        w = flows.get(name)
        if not isinstance(w, dict):
            errs.append(f'{name}: 没有数据（缺覆盖不算通过）')
            continue
        if w.get('supported') is False:
            # 只有 README 写了 "where supported" 的工作流（release-gate.json 的 optional_workflows）可以标为不支持；
            # 其余声明的工作流要缩小范围，由维护者改 release-gate.json 和 README。
            if name in item.get('optional_workflows', []) and w.get('reason'):
                notes.append(f'{name}: 不支持（{w["reason"]}），发布说明不得声称覆盖')
            else:
                errs.append(f'{name}: 证据标为不支持；这是必需的工作流（或没写 reason），缩小范围需维护者改 release-gate.json 和 README')
            continue
        n, k = count(w.get('attempts')), count(w.get('successes'))
        if n is None or k is None or k > n:
            errs.append(f'{name}: attempts/successes 必须是非负整数且 successes ≤ attempts')
            continue
        seeds, timing = w.get('seeds'), w.get('timing')
        if not isinstance(seeds, list) or not seeds or not all(count(s) is not None for s in seeds):
            errs.append(f'{name}: seeds 必须是非空的非负整数列表（种子）')
        if not isinstance(timing, dict) or not timing or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in timing.values()):
            errs.append(f'{name}: timing 必须是非空的 {{名称: 秒数}}（耗时）')
        if n < item['min_attempts']:
            errs.append(f'{name}: 次数 {n} < {item["min_attempts"]}')
        # No pooling: per-scenario and per-environment breakdowns must add up to the totals, every slice needs at
        # least min_slice_attempts runs, and no slice may fall below min_rate on its own point estimate
        # (README: do not pool easy scenarios to hide a failure).
        min_slice = item.get('min_slice_attempts', 1)
        for split in ('by_scenario', 'by_environment'):
            parts = w.get(split)
            if not isinstance(parts, dict) or not parts:
                errs.append(f'{name}: 缺少 {split} 拆分')
                continue
            pn = [count(p.get('attempts')) if isinstance(p, dict) else None for p in parts.values()]
            pk = [count(p.get('successes')) if isinstance(p, dict) else None for p in parts.values()]
            if None in pn or None in pk or sum(pn) != n or sum(pk) != k or any(b > a for a, b in zip(pn, pk)):
                errs.append(f'{name}: {split} 的计数必须是整数且加起来等于总数')
                continue
            small = [s for s, a in zip(parts, pn) if a < min_slice]
            if small:
                errs.append(f'{name}: {split} 中次数少于 {min_slice} 的部分：' + ', '.join(small))
            weak = [s for s, a, b in zip(parts, pn, pk) if a and b / a < item['min_rate']]
            if weak:
                errs.append(f'{name}: {split} 中低于 {item["min_rate"]:.0%} 的部分：' + ', '.join(weak))
        by_env = w.get('by_environment')
        if isinstance(by_env, dict):
            listed = ev['environments'] if isinstance(ev.get('environments'), list) else []
            missing_env = [e for e in listed if e not in by_env]
            if missing_env:
                errs.append(f'{name}: environments 里列出但没有数据：' + ', '.join(map(str, missing_env)))
            extra_env = [e for e in by_env if e not in listed]
            if extra_env:
                errs.append(f'{name}: by_environment 里有 environments 没列出的环境：' + ', '.join(map(str, extra_env)))
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
    # Zero critical failures must hold in every G3 scenario (normal flows and fault injection), each with enough
    # traffic; only MCP cases waived by met G1 evidence are skipped.
    lab = next(i for i in MANIFEST['items'] if i['kind'] == 'lab_cases')
    waived = unsupported_workflows()
    required = [c for c in lab['cases'] if lab.get('optional_cases', {}).get(c) not in waived]
    scenarios = ev.get('scenarios', {})
    if not isinstance(scenarios, dict):
        scenarios = {}
    missing = [s for s in required if not isinstance(scenarios.get(s), dict)]
    if missing:
        errs.append('故障矩阵缺场景：' + ', '.join(missing))
    for name in required:
        s = scenarios.get(name)
        if not isinstance(s, dict):
            continue
        flows = count(s.get('protected_flows'))
        if flows is None or flows < item['min_flows_per_scenario']:
            errs.append(f'{name}: protected_flows 必须是 ≥ {item["min_flows_per_scenario"]} 的整数')
        if not count(s.get('control_workloads')):
            errs.append(f'{name}: control_workloads 必须是正整数')
        for key in ('direct_or_wrong_route_egress', 'control_interruptions', 'control_route_changes'):
            if count(s.get(key)) != 0:
                errs.append(f'{name}: {key} = {s.get(key)!r}（必须是整数 0）')
    return errs, [f'观察器：{obs.get("kind", "?")}；{len(required) - len(missing)}/{len(required)} 个场景有数据']

def unsupported_workflows():
    """Workflows that G1 evidence marks unsupported (only optional ones count, see eval_workflow_success).
    The waiver counts only when the G1 evidence itself is met, so stale or invalid G1 evidence cannot excuse G3 cases."""
    g1 = next(i for i in MANIFEST['items'] if i['kind'] == 'workflow_success')
    try:
        ev = json.loads((ROOT / g1['evidence']).read_text(encoding='utf-8'))
        flows = ev.get('workflows', {})
        errs, _ = EVALUATORS[g1['kind']](g1, ev)
        if errs or common(g1, ev) or provenance(ev, RELEASE_COMMIT):
            return set()
    except Exception:
        return set()
    return {n for n in g1.get('optional_workflows', []) if isinstance(flows.get(n), dict) and flows[n].get('supported') is False}

def eval_lab_cases(item, ev):
    cases = ev.get('cases', {})
    skip_ok = unsupported_workflows()
    missing, failed, skipped = [], [], []
    for c in item['cases']:
        result = cases.get(c, {}).get('result') if isinstance(cases.get(c), dict) else None
        if result == 'pass':
            continue
        workflow = item.get('optional_cases', {}).get(c)
        if result == 'not_supported' and workflow in skip_ok:
            skipped.append(c)  # consistent with G1 marking this optional workflow unsupported
        elif c not in cases:
            missing.append(c)
        else:
            failed.append(c)
    errs = []
    if missing:
        errs.append('缺用例：' + ', '.join(missing))
    if failed:
        errs.append('未通过（not_supported 只允许用于 G1 里也标为不支持的可选工作流）：' + ', '.join(failed))
    notes = [f'{len(item["cases"]) - len(missing) - len(failed) - len(skipped)}/{len(item["cases"])} 个用例通过']
    if skipped:
        notes.append('不支持（与 G1 一致）：' + ', '.join(skipped))
    return errs, notes

def eval_transfer(item, ev):
    errs = []
    if not ev.get('fixture_clients'):
        errs.append('fixture_clients 为空')
    if not ev.get('signed_clients'):
        errs.append('signed_clients 为空')
    if ev.get('same_enforcement_mechanism') is not True:
        errs.append('same_enforcement_mechanism 必须为 true')
    gaps = ev.get('gaps_document', '')
    if not repo_file(gaps, ('docs/',)):
        errs.append('gaps_document 必须指向 docs/ 下存在的差距文档')
    elif not re.search(r'^## (Gaps|差距)\b', (ROOT / gaps).read_text(encoding='utf-8'), re.M):
        errs.append('gaps_document 里需要一个 "## Gaps" 或 "## 差距" 章节')
    return errs, []

def eval_network_extension(item, ev):
    errs = []
    for key in ('signed_extension_loaded', 'data_plane_tested', 'unavailable_behavior_tested'):
        if ev.get(key) is not True:
            errs.append(f'{key} 必须为 true')
    doc = ev.get('feasibility_document')
    if not repo_file(doc, ('docs/',)):
        errs.append('feasibility_document 必须指向 docs/ 下存在的可行性文档')
    elif not re.search(r'^## (Unavailable|扩展不可用)', (ROOT / doc).read_text(encoding='utf-8'), re.M):
        errs.append('feasibility_document 里需要 "## Unavailable" 或 "## 扩展不可用" 章节')
    return errs, []

CHECK_ID = re.compile(r'^- \*\*(UX-\d{2})\*\*', re.M)
RUN_URL = re.compile(r'^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}')

def checklist_ids(path):
    return CHECK_ID.findall((ROOT / path).read_text(encoding='utf-8'))

def eval_ux_signoff(item, ev):
    """The maintainer's own walkthrough of docs/ux-checklist.md, with CI screenshots of the same commit."""
    errs = []
    doc = item['checklist']
    ids = checklist_ids(doc) if repo_file(doc, ('docs/',)) else []
    if not ids:
        errs.append(f'{doc} 里没有清单项（- **UX-nn**）')
    if len(set(ids)) != len(ids):
        errs.append(f'{doc} 里有重复的清单 ID')
    checks = ev.get('checks')
    if not isinstance(checks, dict):
        checks = {}
        errs.append('checks 必须是 {清单 ID: {result, note}}')
    missing = [i for i in ids if i not in checks]
    if missing:
        errs.append('清单项没有结果：' + ', '.join(missing))
    failed = [i for i in ids if i in checks and not (isinstance(checks[i], dict) and checks[i].get('result') == 'pass')]
    if failed:
        errs.append('清单项未通过：' + ', '.join(failed))
    unknown = [i for i in checks if i not in ids]
    if unknown:
        errs.append('清单里没有这些 ID（清单改过？）：' + ', '.join(map(str, unknown)))
    looks = ev.get('appearances')
    if not isinstance(looks, list) or not set(item.get('appearances', [])) <= set(looks):
        errs.append('appearances 必须包含 ' + ' / '.join(item.get('appearances', [])))
    if not RUN_URL.match(str(ev.get('screenshots_run', ''))):
        errs.append('screenshots_run 必须是这次 tested_commit 的 CI 运行链接（https://github.com/<owner>/<repo>/actions/runs/<id>）')
    who = ev.get('signed_off_by')
    if not isinstance(who, str) or not who.strip():
        errs.append('signed_off_by 必须写明签字的维护者')
    if not DATE.match(str(ev.get('signed_off_at', ''))):
        errs.append('signed_off_at 必须是日期（YYYY-MM-DD）')
    # docs/ is not a product file, so the checklist's own history is checked here: it must have existed at
    # tested_commit and be unchanged since, otherwise the walkthrough was against a different list.
    # (A malformed or unknown tested_commit is reported by common() / provenance(), which run for every item.)
    commit = str(ev.get('tested_commit', ''))
    if SHA.match(commit) and git('cat-file', '-e', f'{commit}^{{commit}}').returncode == 0:
        target = RELEASE_COMMIT or 'HEAD'
        if git('cat-file', '-e', f'{commit}:{doc}').returncode != 0:
            errs.append(f'{doc} 在 tested_commit 时还不存在')
        else:
            rc = git('diff', '--quiet', commit, target, '--', doc).returncode
            if rc == 1:
                errs.append(f'{doc} 在 tested_commit 之后被改过，需要按新清单重新走查')
            elif rc:
                errs.append(f'无法比较 {doc} 的历史（git diff 失败）')
    notes = [f'{len(ids) - len(missing) - len(failed)}/{len(ids)} 个清单项通过']
    if isinstance(who, str) and who.strip():
        notes.append(f'签字：{who.strip()} {ev.get("signed_off_at", "")}')
    return errs, notes

EVALUATORS = dict(workflow_success=eval_workflow_success, critical_failures=eval_critical_failures,
                  lab_cases=eval_lab_cases, transfer=eval_transfer, network_extension=eval_network_extension,
                  ux_signoff=eval_ux_signoff)

MANIFEST = json.loads((ROOT / 'release-gate.json').read_text(encoding='utf-8'))

def evaluate_gate(release_commit=None):
    global RELEASE_COMMIT
    RELEASE_COMMIT = release_commit
    results = []
    for item in MANIFEST['items']:
        path = ROOT / item['evidence']
        if not path.is_file():
            errs, notes = [f'没有证据文件 {item["evidence"]}'], []
        else:
            try:
                ev = json.loads(path.read_text(encoding='utf-8'))
                errs, notes = EVALUATORS[item['kind']](item, ev)
                errs = common(item, ev) + provenance(ev, release_commit) + errs
            except Exception as e:  # any malformed evidence is not met, never a crash
                errs, notes = [f'证据文件格式错误：{e}'], []
        if not errs and item.get('format_only'):
            notes = ['仅检查了证据格式和历史一致性，内容未经验证（维护者声明）'] + notes
        results.append(dict(id=item['id'], title=item['title'], met=not errs, problems=errs, notes=notes,
                            format_only=bool(item.get('format_only')), agent_ok=item.get('agent_ok') is True,
                            agent_note=item.get('agent_note', ''),
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
        mark = ('☑️ 格式满足' if g.get('format_only') else '✅') if g['met'] else '⬜'
        lines.append(f'- {mark} **{g["id"]}** {g["title"]}')
        lines += [f'  - {p}' for p in g['problems'] + g['notes']]
    return '\n'.join(lines) + '\n'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gate-only', action='store_true', help='skip build/tests (works off macOS)')
    ap.add_argument('--require-gate', action='store_true', help='fail unless every gate item is met')
    ap.add_argument('--release-commit', help='commit being released; evidence must be its ancestor with unchanged product code')
    args = ap.parse_args()

    baseline = []
    if not args.gate_only:
        py = sys.executable
        baseline.append(run_step('build (build.py)', [py, 'build.py']))
        if baseline[-1]['ok']:
            baseline.append(run_step('loopback lab (tests/lab.py)', [py, 'tests/lab.py']))
            baseline.append(run_step('branding (tests/branding.py)', [py, 'tests/branding.py']))
            baseline.append(run_step('UX screenshots (tests/ux_screens.py)', [py, 'tests/ux_screens.py']))
        baseline.append(run_step('gate evaluator self-test (tests/gate_selftest.py)', [py, 'tests/gate_selftest.py']))
        baseline.append(hygiene())
    gate = evaluate_gate(args.release_commit)
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
