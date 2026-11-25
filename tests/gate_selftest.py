"""Self-test for the release-gate evaluators: good evidence passes, each weakening fails."""
import copy
import os
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A

A.unsupported_workflows = lambda: set()  # never depend on real evidence on disk; tested explicitly below
items = {i['id']: i for i in json.loads((A.ROOT / 'release-gate.json').read_text(encoding='utf-8'))['items']}
head = A.git('rev-parse', 'HEAD').stdout.strip()
# Temporary fixtures inside the repo (removed at exit): a raw record and a gaps document.
import atexit
RAW, GAPS = 'evidence/.selftest-raw.json', 'docs/.selftest-gaps.md'
(A.ROOT / RAW).write_text('{"runs": []}\n', encoding='utf-8')
(A.ROOT / GAPS).write_text('# Transfer\n\n## Gaps\n- none observed\n', encoding='utf-8')
atexit.register(lambda: [(A.ROOT / p).unlink(missing_ok=True) for p in (RAW, GAPS)])
base = dict(tested_commit=head, environments=['macOS 15 arm64'], credentials='synthetic', raw_results=dict(path=RAW, sha256=hashlib.sha256((A.ROOT / RAW).read_bytes()).hexdigest()))
good = {
    'G1': dict(base, matrix_preregistered='tests/lab.py', workflows={
        w: dict(attempts=400, successes=396, seeds=[1, 2, 3], timing=dict(median_s=4.2, p95_s=9.8)) for w in items['G1']['workflows']}),
    'G2': dict(base, observer=dict(independent=True, kind='gateway pcap'), scenarios={
        c: dict(protected_flows=50, control_workloads=10, direct_or_wrong_route_egress=0, control_interruptions=0,
                control_route_changes=0) for c in items['G3']['cases'] if c.startswith('inject_')}),
    'G3': dict(base, cases={c: dict(result='pass') for c in items['G3']['cases']}),
    'G4': dict(base, fixture_clients=['fixture'], signed_clients=['client'], same_enforcement_mechanism=True,
               gaps_document=GAPS),
    'G5': dict(base, signed_extension_loaded=True, data_plane_tested=True, unavailable_behavior_tested=True),
}
bad = [
    ('G1', lambda e: e['workflows']['mcp'].update(successes=376)),
    ('G1', lambda e: e['workflows']['mcp'].update(attempts=60, successes=57)),  # rejected by min_attempts
    ('G1', lambda e: e['workflows']['cli'].update(attempts=60, successes=60)),  # rejected by min_attempts
    ('G1', lambda e: e['workflows']['cli'].update(attempts=400, successes=380)),  # point 95.0% but Wilson lower bound ~92.4%
    ('G1', lambda e: e['workflows']['cli'].update(attempts=100, successes=99)),  # point 99% but lower bound ~94.6%
    ('G1', lambda e: e['workflows'].pop('cli')),
    ('G1', lambda e: e['workflows']['desktop'].update(attempts=10, successes=10)),
    ('G1', lambda e: e['workflows']['desktop'].update(attempts=72, successes=72)),  # rejected by min_attempts (= 73)
    ('G1', lambda e: e['workflows'].__setitem__('mcp', dict(supported=False))),
    ('G1', lambda e: [e['workflows'].__setitem__(w, dict(supported=False, reason='n/a'))
                      for w in ('cli', 'browser_authorization', 'mcp')]),
    ('G1', lambda e: e.update(credentials='real_account')),
    ('G1', lambda e: e['workflows'].__setitem__('cli', dict(supported=False, reason='n/a'))),  # cli is mandatory
    ('G1', lambda e: e['workflows']['desktop'].update(successes=401)),
    ('G1', lambda e: e['workflows']['desktop'].update(attempts=400.0)),
    ('G1', lambda e: e['workflows']['desktop'].pop('timing')),
    ('G1', lambda e: e.update(matrix_preregistered='tests/../README.md')),
    ('G2', lambda e: e['scenarios']['inject_update'].update(direct_or_wrong_route_egress=0.5)),
    ('G2', lambda e: e['scenarios']['inject_update'].update(control_interruptions='0')),
    ('G2', lambda e: e['scenarios']['inject_update'].update(protected_flows=1e999)),
    ('G4', lambda e: e.update(gaps_document='/etc/hosts')),
    ('G2', lambda e: e['scenarios']['inject_sleep_wake'].update(direct_or_wrong_route_egress=1)),
    ('G2', lambda e: e['scenarios'].pop('inject_route_change')),
    ('G2', lambda e: e['scenarios']['inject_update'].update(protected_flows=1)),
    ('G2', lambda e: e['scenarios']['inject_update'].update(control_workloads=0)),
    ('G2', lambda e: e['observer'].update(independent=False)),
    ('G2', lambda e: e['scenarios']['inject_interface_switch'].pop('control_route_changes')),
    ('G3', lambda e: e['cases'].pop('dns_ipv6')),
    ('G3', lambda e: e['cases']['inject_sleep_wake'].update(result='fail')),
    ('G3', lambda e: e['cases']['dns_udp'].update(result='not_supported')),  # not an optional case
    ('G3', lambda e: e['cases']['mcp_remote_streaming'].update(result='not_supported')),  # G1 does not mark mcp unsupported
    ('G4', lambda e: e.update(gaps_document='docs/missing.md')),
    ('G4', lambda e: e.update(gaps_document='README.md')),
    ('G4', lambda e: e.update(gaps_document='docs/roundtable.md')),  # no "## Gaps" section
    ('G4', lambda e: e['raw_results'].update(path='evidence/README.md')),  # README is not a raw record
    ('G4', lambda e: e.update(raw_results='evidence/README.md')),  # bare path without hash
    ('G4', lambda e: e.update(raw_results=dict(url='https://example.invalid/log', sha256='x'))),
    ('G4', lambda e: e['raw_results'].update(sha256='0' * 64)),  # hash does not match file
    ('G4', lambda e: e.update(credentials='authorized_test')),  # no authorized-credential path
    ('G1', lambda e: e.update(matrix_preregistered='tests/not-yet-written.md')),
    ('G5', lambda e: e.update(data_plane_tested=False)),
    ('G5', lambda e: e.update(tested_commit='main')),
]

def problems(item_id, ev):
    errs, _ = A.EVALUATORS[items[item_id]['kind']](items[item_id], ev)
    return A.common(items[item_id], ev) + A.provenance(ev, None) + errs

for k, n in ((380, 400), (99, 100)):  # make sure these really exercise the lower bound, not min_attempts
    assert n >= items['G1']['min_attempts'] and k / n >= items['G1']['min_rate'] > A.wilson_lower(k, n)
assert A.wilson_lower(73, 73) >= items['G1']['min_rate'] > A.wilson_lower(72, 72), 'min_attempts must be the smallest passing all-success count'
# --release-commit path (used by release.yml): HEAD as release commit passes (the failing direction is in the
# throwaway-repository cases below).
assert not A.provenance(good['G5'], head)
# G3 mcp cases may be not_supported only when G1 marks mcp unsupported
ev = copy.deepcopy(good['G3'])
ev['cases']['mcp_remote_streaming']['result'] = 'not_supported'
A.unsupported_workflows = lambda: {'mcp'}
assert not problems('G3', ev), problems('G3', ev)
ev['cases']['dns_udp']['result'] = 'not_supported'
assert problems('G3', ev), 'non-optional case accepted as not_supported'
A.unsupported_workflows = lambda: set()
# mcp is "where supported": it may be marked unsupported with a reason
ev = copy.deepcopy(good['G1'])
ev['workflows']['mcp'] = dict(supported=False, reason='no MCP client in this release')
assert not problems('G1', ev), problems('G1', ev)

for item_id, ev in good.items():
    assert not problems(item_id, ev), (item_id, problems(item_id, ev))
for item_id, weaken in bad:
    ev = copy.deepcopy(good[item_id])
    weaken(ev)
    assert problems(item_id, ev), (item_id, 'weakened evidence still passed')
assert good.keys() == items.keys(), 'every gate item needs a self-test'
# History checks run against a throwaway repository, so they work in shallow clones and do not depend on
# the shape of this repo's real history: c1 product v1, c2 evidence-only change, c3 product change.
import subprocess, tempfile
with tempfile.TemporaryDirectory() as tmp:
    def g(*args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args],
                              cwd=tmp, check=True, capture_output=True, text=True).stdout.strip()
    g('init', '-q')
    Path(tmp, 'main.swift').write_text('v1\n'); g('add', '.'); g('commit', '-qm', 'c1'); c1 = g('rev-parse', 'HEAD')
    Path(tmp, 'evidence').mkdir(); Path(tmp, 'evidence/x.json').write_text('{}\n'); g('add', '.'); g('commit', '-qm', 'c2')
    c2 = g('rev-parse', 'HEAD')
    Path(tmp, 'main.swift').write_text('v2\n'); g('commit', '-qam', 'c3'); c3 = g('rev-parse', 'HEAD')
    saved, A.GIT_ROOT = A.GIT_ROOT, Path(tmp)
    try:
        ev = lambda c: dict(good['G5'], tested_commit=c)
        assert not A.provenance(ev(c1), c2), 'evidence-only commit after the test must not make evidence stale'
        assert any('过期' in p for p in A.provenance(ev(c1), c3)), 'stale evidence passed'
        assert any('祖先' in p for p in A.provenance(ev(c2), c1)), 'evidence newer than the release commit passed'
        assert any('不在仓库历史' in p for p in A.provenance(ev('e' * 40), c3)), 'unknown tested_commit passed'
    finally:
        A.GIT_ROOT = saved
tail = ' and 4 history cases (stale, evidence-only, not-ancestor, unknown commit)'
print(f'PASS: gate evaluators accept {len(good)} complete records, reject {len(bad)} weakened ones{tail}')
