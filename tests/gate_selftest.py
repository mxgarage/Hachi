"""Self-test for the release-gate evaluators: good evidence passes, each weakening fails."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A

items = {i['id']: i for i in json.loads((A.ROOT / 'release-gate.json').read_text(encoding='utf-8'))['items']}
head = A.git('rev-parse', 'HEAD').stdout.strip()
base = dict(tested_commit=head, environments=['macOS 15 arm64'], credentials='synthetic', raw_results='evidence/README.md')
good = {
    'G1': dict(base, matrix_preregistered='tests/lab.py', workflows={
        w: dict(attempts=400, successes=396, seeds=[1, 2, 3]) for w in items['G1']['workflows']}),
    'G2': dict(base, observer=dict(independent=True, kind='gateway pcap'), protected_flows=50, control_workloads=10,
               direct_or_wrong_route_egress=0, control_interruptions=0, control_route_changes=0),
    'G3': dict(base, cases={c: dict(result='pass') for c in items['G3']['cases']}),
    'G4': dict(base, fixture_clients=['fixture'], signed_clients=['client'], same_enforcement_mechanism=True,
               gaps_document='docs/roundtable.md'),
    'G5': dict(base, signed_extension_loaded=True, data_plane_tested=True, unavailable_behavior_tested=True),
}
bad = [
    ('G1', lambda e: e['workflows']['mcp'].update(successes=376)),
    ('G1', lambda e: e['workflows']['mcp'].update(attempts=60, successes=57)),  # 95.0% point estimate, lower bound 86%
    ('G1', lambda e: e['workflows']['cli'].update(attempts=60, successes=60)),  # 100% but lower bound 94%
    ('G1', lambda e: e['workflows'].pop('cli')),
    ('G1', lambda e: e['workflows']['desktop'].update(attempts=10, successes=10)),
    ('G1', lambda e: e['workflows'].__setitem__('mcp', dict(supported=False))),
    ('G1', lambda e: [e['workflows'].__setitem__(w, dict(supported=False, reason='n/a'))
                      for w in ('cli', 'browser_authorization', 'mcp')]),
    ('G1', lambda e: e.update(credentials='real_account')),
    ('G2', lambda e: e.update(direct_or_wrong_route_egress=1)),
    ('G2', lambda e: e['observer'].update(independent=False)),
    ('G2', lambda e: e.pop('control_route_changes')),
    ('G3', lambda e: e['cases'].pop('dns_ipv6')),
    ('G3', lambda e: e['cases']['inject_sleep_wake'].update(result='fail')),
    ('G4', lambda e: e.update(gaps_document='docs/missing.md')),
    ('G4', lambda e: e.update(gaps_document='README.md')),
    ('G4', lambda e: e.update(raw_results='ci-artifact')),
    ('G4', lambda e: e.update(raw_results=dict(url='https://example.invalid/log', sha256='x'))),
    ('G1', lambda e: e.update(matrix_preregistered='tests/not-yet-written.md')),
    ('G1', lambda e: e.update(tested_commit='f' * 40)),
    ('G5', lambda e: e.update(data_plane_tested=False)),
    ('G5', lambda e: e.update(tested_commit='main')),
]

def problems(item_id, ev):
    errs, _ = A.EVALUATORS[items[item_id]['kind']](items[item_id], ev)
    return A.common(ev) + A.provenance(ev, None) + errs

for item_id, ev in good.items():
    assert not problems(item_id, ev), (item_id, problems(item_id, ev))
for item_id, weaken in bad:
    ev = copy.deepcopy(good[item_id])
    weaken(ev)
    assert problems(item_id, ev), (item_id, 'weakened evidence still passed')
assert good.keys() == items.keys(), 'every gate item needs a self-test'
# stale evidence: product code changed after tested_commit
first = A.git('rev-list', '--max-parents=0', 'HEAD').stdout.split()[0]
if A.git('diff', '--quiet', first, 'HEAD', '--', *A.PRODUCT_FILES).returncode != 0:
    assert A.provenance(dict(good['G5'], tested_commit=first), None), 'stale evidence passed'
    bad.append(('G5', 'stale'))
print(f'PASS: gate evaluators accept {len(good)} complete records and reject {len(bad)} weakened ones')
