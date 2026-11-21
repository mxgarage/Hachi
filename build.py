from pathlib import Path
import plistlib
import subprocess

root = Path(__file__).resolve().parent
build = root / 'build'
app = build / 'AI Egress Guard.app' / 'Contents'
(app / 'MacOS').mkdir(parents=True, exist_ok=True)
(app / 'Info.plist').write_bytes(plistlib.dumps(dict(
    CFBundleExecutable='AI-Egress-Guard', CFBundleIdentifier='local.ai-egress-guard.dev',
    CFBundlePackageType='APPL', CFBundleName='AI Egress Guard', CFBundleVersion='1',
    CFBundleShortVersionString='0.1', CFBundleIconFile='SailShield.icns', LSUIElement=True)))
subprocess.run(['/usr/bin/swiftc', '-module-cache-path', str(build / 'module-cache'),
                str(root / 'main.swift'), '-o', str(app / 'MacOS/AI-Egress-Guard')], check=True)
resources = app / 'Resources'
resources.mkdir(exist_ok=True)
iconset = build / 'SailShield.iconset'
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
        subprocess.run([str(app / 'MacOS/AI-Egress-Guard'), '--draw-icon', str(size*scale), str(iconset/name)], check=True)
subprocess.run(['/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o', str(resources/'SailShield.icns')], check=True)
subprocess.run(['/usr/bin/plutil', '-lint', str(app / 'Info.plist')], check=True)
print(app.parent)
