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

def frames(elapsed, reduced=False):
    return json.loads(subprocess.check_output([str(binary), '--wag-frame', str(elapsed), str(reduced).lower()]))['pose']

assert frames(0) == frames(23) == frames(25.1) == 0
assert frames(24.1) == 1 and frames(24.2) == -1 and frames(48.1) == 1
assert frames(24.1, True) == frames(24.2, True) == 0
with tempfile.TemporaryDirectory() as directory:
    paths = [Path(directory) / f'{pose}.png' for pose in (0, 1, -1)]
    for path, pose in zip(paths, (0, 1, -1)):
        subprocess.run([str(binary), '--draw-icon', '128', str(path), str(pose)], check=True, timeout=10)
    images = [p.read_bytes() for p in paths]
    assert all(im.startswith(b'\x89PNG\r\n\x1a\n') for im in images)
    assert len(set(images)) == 3, 'tail poses must render visually distinct frames'
print('PASS: Hachi app and icon, periodic wag and reduced motion, three distinct artwork frames')
