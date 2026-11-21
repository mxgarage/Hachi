from pathlib import Path
import json
import plistlib
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
contents = root / 'build/Hachi.app/Contents'
binary = contents / 'MacOS/Hachi'
assert contents.is_dir(), 'Hachi.app has not been built'
info = plistlib.loads((contents / 'Info.plist').read_bytes())
assert info['CFBundleName'] == 'Hachi' and info['LSUIElement']
assert (contents / 'Resources' / info['CFBundleIconFile']).stat().st_size > 0

def frame(elapsed, reduced=False):
    return json.loads(subprocess.check_output([str(binary), '--wag-frame', str(elapsed), str(reduced).lower()]))

assert frame(0)['pose'] == 0
poses = [frame(i / 30)['pose'] for i in range(28)]
assert max(poses) > 4 and min(poses) < -4 and len(set(poses)) >= 12
assert max(abs(b-a) for a, b in zip(poses, poses[1:])) < 9
for start in (0.0, 0.9, 9.0, 90.0):
    assert frame(start + 0.225)['pose'] == max(poses)
    assert frame(start + 0.675)['pose'] == min(poses)
    assert abs(frame(start + 0.9)['pose'] - frame(start + 0.9 - 1 / 30)['pose']) < 9
    assert frame(start + 0.225, True)['pose'] == 0
with tempfile.TemporaryDirectory() as directory:
    paths = [Path(directory) / f'{pose}.png' for pose in (0, max(poses), min(poses))]
    for path, pose in zip(paths, (0, max(poses), min(poses))):
        subprocess.run([str(binary), '--draw-icon', '128', str(path), str(pose)], check=True, timeout=10)
    images = [p.read_bytes() for p in paths]
    assert all(im.startswith(b'\x89PNG\r\n\x1a\n') for im in images)
    assert len(set(images)) == 3, 'tail poses must render visually distinct frames'
print('PASS: Hachi artwork, seamless continuous wag from startup, and reduced motion')
