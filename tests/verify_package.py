"""Launch check for a built Hachi.app on the machine it runs on.

usage: verify_package.py PATH/TO/Hachi.app [--archs arm64,x86_64]

Used by the release workflow on an Apple silicon and an Intel runner, against the very zip that will be published,
and by verify.yml on an Intel runner. Checks: the binary contains exactly the declared architectures, the signature
is valid, the slice for THIS machine really runs (not just that the file exists), the app stays up after launch,
and the loopback lab and branding tests pass against this exact app.
"""
from pathlib import Path
import os
import platform
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
args = sys.argv[1:]
want = {'arm64', 'x86_64'}
if '--archs' in args:
    i = args.index('--archs')
    want = set(args[i + 1].split(','))
    del args[i:i + 2]
app = Path(args[0]).resolve()
binary = app / 'Contents/MacOS/Hachi'
host = platform.machine()  # arm64 or x86_64
assert binary.is_file(), f'{binary} missing'

have = set(subprocess.check_output(['/usr/bin/lipo', '-archs', str(binary)], text=True).split())
assert have == want, f'architectures in the binary: {sorted(have)}, declared: {sorted(want)}'
assert host in have, f'this machine is {host} but the app only has {sorted(have)}'
print(f'OK: lipo -archs = {sorted(have)}; host = {host}')

subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
print('OK: codesign --verify --deep --strict')

# the slice for this machine must execute ("Bad CPU type in executable" would fail here)
subprocess.run([str(binary), '--wag-frame', '0', 'false'], check=True, capture_output=True, timeout=20)
print(f'OK: {host} slice executes')

# launch it for real: it must still be running a few seconds later
p = subprocess.Popen([str(binary)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    time.sleep(5)
    assert p.poll() is None, f'Hachi exited {p.returncode} within 5 s of launch: {p.stderr.read().decode()[:500]}'
    print('OK: app launched and kept running for 5 s')
finally:
    if p.poll() is None:
        p.terminate()
        p.wait(timeout=10)

env = dict(os.environ, HACHI_APP=str(app))
for test in ('lab.py', 'branding.py'):
    subprocess.run([sys.executable, str(root / 'tests' / test)], check=True, env=env)
print(f'PASS: Hachi.app launches and passes lab + branding on {host} ({",".join(sorted(have))})')
