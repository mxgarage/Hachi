from pathlib import Path
import os
import plistlib
import subprocess

MIN_MACOS = '13.0'
root = Path(__file__).resolve().parent
build = root / 'build'
app = build / 'Hachi.app' / 'Contents'
(app / 'MacOS').mkdir(parents=True, exist_ok=True)
(app / 'Info.plist').write_bytes(plistlib.dumps(dict(
    CFBundleExecutable='Hachi', CFBundleIdentifier='local.ai-egress-guard.dev',
    CFBundlePackageType='APPL', CFBundleName='Hachi', CFBundleDisplayName='Hachi', CFBundleVersion='2',
    CFBundleShortVersionString='0.2', CFBundleIconFile='Hachi.icns', LSUIElement=True,
    LSMinimumSystemVersion=MIN_MACOS)))
# One universal binary (Apple silicon + Intel), so the single signed package runs on both.
# HACHI_ARCHS can narrow it for a local build, e.g. HACHI_ARCHS=arm64.
archs = os.environ.get('HACHI_ARCHS', 'arm64 x86_64').split()
slices = []
for arch in archs:
    out = build / f'Hachi-{arch}'
    subprocess.run(['/usr/bin/swiftc', '-target', f'{arch}-apple-macos{MIN_MACOS}',
                    '-module-cache-path', str(build / 'module-cache'),
                    str(root / 'main.swift'), '-o', str(out)], check=True)
    slices.append(str(out))
subprocess.run(['/usr/bin/lipo', '-create', *slices, '-output', str(app / 'MacOS/Hachi')], check=True)
resources = app / 'Resources'
resources.mkdir(exist_ok=True)
iconset = build / 'Hachi.iconset'
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
        subprocess.run([str(app / 'MacOS/Hachi'), '--draw-icon', str(size*scale), str(iconset/name)], check=True)
subprocess.run(['/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o', str(resources/'Hachi.icns')], check=True)
subprocess.run(['/usr/bin/plutil', '-lint', str(app / 'Info.plist')], check=True)
print(app.parent)
