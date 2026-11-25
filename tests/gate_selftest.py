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
base = dict(tested_commit=head, environments=['macOS 15 arm64'], credentials='synthetic', raw_results=dict(path='evidence/README.md', sha256=hashlib.sha256((A.ROOT / 'evidence/README.md').read_bytes()).hexdigest()))
good = {
    'G1': dict(base, matrix_preregistered='tests/lab.py', workflows={
        w: dict(attempts=400, successes=396, seeds=[1, 2, 3], timing=dict(median_s=4.2, p95_s=9.8)) for w in items['G1']['workflows']}),
    'G2': dict(base, observer=dict(independent=True, kind='gateway pcap'), scenarios={
        c: dict(protected_flows=50, control_workloads=10, direct_or_wrong_route_egress=0, control_interruptions=0,
                control_route_changes=0) for c in items['G3']['cases'] if c.startswith('inject_')}),
    'G3': dict(base, cases={c: dict(result='pass') for c in items['G3']['cases']}),
    'G4': dict(base, fixture_clients=['fixture'], signed_clients=['client'], same_enforcement_mechanism=True,
               gaps_document='docs/roundtable.md'),
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
    ('G4', lambda e: e.update(raw_results='evidence/README.md')),  # bare path without hash
    ('G4', lambda e: e.update(raw_results=dict(url='https://example.invalid/log', sha256='x'))),
    ('G4', lambda e: e['raw_results'].update(sha256='0' * 64)),  # hash does not match file
    ('G4', lambda e: e.update(credentials='authorized_test')),  # no authorized-credential path
    ('G1', lambda e: e.update(matrix_preregistered='tests/not-yet-written.md')),
    ('G1', lambda e: e.update(tested_commit='f' * 40)),
    ('G5', lambda e: e.update(data_plane_tested=False)),
    ('G5', lambda e: e.update(tested_commit='main')),
]

def problems(item_id, ev):
    errs, _ = A.EVALUATORS[items[item_id]['kind']](items[item_id], ev)
    return A.common(items[item_id], ev) + A.provenance(ev, None) + errs

for k, n in ((380, 400), (99, 100)):  # make sure these really exercise the lower bound, not min_attempts
    assert n >= items['G1']['min_attempts'] and k / n >= items['G1']['min_rate'] > A.wilson_lower(k, n)
assert A.wilson_lower(73, 73) >= items['G1']['min_rate'] > A.wilson_lower(72, 72), 'min_attempts must be the smallest passing all-success count'
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
# Stale evidence: a commit whose product files differ from HEAD must be rejected. This uses real history:
# CI checks out with fetch-depth: 0 and sets HACHI_REQUIRE_HISTORY=1, so there a missing case fails.
# In a shallow local clone it is skipped with a warning instead of failing the baseline.
shallow = A.git('rev-parse', '--is-shallow-repository').stdout.strip() == 'true'
stale = None if shallow else next((c for c in A.git('rev-list', 'HEAD', '--', *A.PRODUCT_FILES).stdout.split()
                                   if A.git('diff', '--quiet', c, 'HEAD', '--', *A.PRODUCT_FILES).returncode != 0), None)
if stale:
    assert any('过期' in p for p in A.provenance(dict(good['G5'], tested_commit=stale), None)), 'stale evidence passed'
    tail = f' and stale evidence ({stale[:7]})'
else:
    assert os.environ.get('HACHI_REQUIRE_HISTORY') != '1', 'stale-evidence case needs full history (fetch-depth: 0)'
    tail = '; WARNING: stale-evidence case skipped (shallow clone or no older product change)'
print(f'PASS: gate evaluators accept {len(good)} complete records, reject {len(bad)} weakened ones{tail}')
