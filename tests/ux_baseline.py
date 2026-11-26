"""UX screenshot regression: compare every screenshot from tests/ux_screens.py with the stored baseline in
tests/ux-baseline/ and fail on any difference.

  python3 tests/ux_baseline.py                  # in CI: compare build/acceptance/ux/ with tests/ux-baseline/
                                                # elsewhere: self-test only, comparison skipped (see below)
  python3 tests/ux_baseline.py --compare-locally  # compare off CI anyway; expected to differ
  HACHI_UX_DIFF=warn python3 tests/ux_baseline.py # differences warn instead of failing (release.yml only)
  python3 tests/ux_baseline.py --selftest       # check the PNG reader/writer and the diff (any OS)
  python3 tests/ux_baseline.py --import-log LOG # take a new baseline from a CI job log (see below)

Output: build/acceptance/ux-diff/ (uploaded with the CI artifact): for each differing state a PNG with three panels
(baseline | this build | changed pixels in magenta), and index.html. build/acceptance/ux-candidate-baseline/ holds
this build's screenshots in baseline form, so a reviewed change can be accepted by copying it to tests/ux-baseline/.

Baselines must come from CI (macos-15 runner), not from a developer Mac: fonts, scale and OS version differ. When
the comparison fails in CI, the job log also carries the candidate baseline as a checksummed base64 bundle between
HACHI-UX-BUNDLE markers; `--import-log` unpacks it after checking the checksum. Updating the baseline is a visible
change to tests/ux-baseline/ in the PR (GitHub shows the images); a reviewer accepts it like any other change.
A baseline update never replaces the maintainer's walkthrough in docs/ux-checklist.md.

Pure standard library (zlib), so it runs on the runner's stock Python.
"""
import argparse
import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('HACHI_ACCEPTANCE_OUT') or ROOT / 'build' / 'acceptance')
CURRENT = OUT / 'ux'
DIFF = OUT / 'ux-diff'
CANDIDATE = OUT / 'ux-candidate-baseline'
BASELINE = ROOT / 'tests' / 'ux-baseline'
META = 'baseline.json'
# A pixel counts as changed when any channel differs by more than CHANNEL_TOLERANCE (0-255). Any changed pixel fails.
CHANNEL_TOLERANCE = 0
BEGIN, END = 'HACHI-UX-BUNDLE-BEGIN', 'HACHI-UX-BUNDLE-END'

# ---------- PNG (8/16-bit grey, grey+alpha, RGB, RGBA; non-interlaced) ----------

def read_png(path):
    """Returns (width, height, rgba bytes)."""
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError(f'{Path(path).name} is not a PNG')
    pos, idat, head, palette = 8, [], None, None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            head = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            palette = body
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
    w, h, depth, ctype, _, _, interlace = head
    if interlace or depth not in (8, 16) or ctype not in (0, 2, 3, 4, 6) or (ctype == 3 and depth != 8):
        raise ValueError(f'{Path(path).name}: unsupported PNG (depth {depth}, colour type {ctype}, interlace {interlace})')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = channels * depth // 8
    stride = w * bpp
    raw = zlib.decompress(b''.join(idat))
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                line[x] = (line[x] + ((line[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b, c = prev[x], prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif f != 0:
            raise ValueError(f'{Path(path).name}: bad filter {f}')
        rows.append(line)
        prev = line
    px = bytearray()
    step = depth // 8
    for line in rows:
        s = line[::step] if step == 2 else line  # 16-bit: keep the high byte
        if ctype == 6:
            px += s
        elif ctype == 2:
            for x in range(0, len(s), 3):
                px += s[x:x + 3] + b'\xff'
        elif ctype == 4:
            for x in range(0, len(s), 2):
                px += bytes((s[x], s[x], s[x], s[x + 1]))
        elif ctype == 0:
            for v in s:
                px += bytes((v, v, v, 255))
        else:
            for v in s:
                px += palette[3 * v:3 * v + 3] + b'\xff'
    return w, h, bytes(px)

def write_png(path, w, h, rgba):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

# ---------- comparison ----------

def changed_pixels(a, b):
    """Indexes of pixels whose channels differ by more than CHANNEL_TOLERANCE (same-size RGBA buffers)."""
    if a == b:
        return []
    out = []
    for i in range(0, len(a), 4):
        if a[i:i + 4] != b[i:i + 4] and max(abs(a[i + k] - b[i + k]) for k in range(4)) > CHANNEL_TOLERANCE:
            out.append(i // 4)
    return out

def diff_image(base, cur, changed):
    """baseline | current | current faded with changed pixels in magenta, on a neutral grey canvas."""
    (bw, bh, bp), (cw, ch, cp) = base, cur
    pw, ph, gap = max(bw, cw), max(bh, ch), 8
    W = pw * 3 + gap * 2
    canvas = bytearray(b'\x80\x80\x80\xff' * (W * ph))
    def paste(px, w, h, x0, fade=False):
        for y in range(h):
            row = bytearray(px[y * w * 4:(y + 1) * w * 4])
            if fade:
                for i in range(0, len(row), 4):
                    for k in range(3):
                        row[i + k] = 255 - (255 - row[i + k]) // 4
                    row[i + 3] = 255
            canvas[(y * W + x0) * 4:(y * W + x0 + w) * 4] = row
    paste(bp, bw, bh, 0)
    paste(cp, cw, ch, pw + gap)
    x0 = 2 * (pw + gap)
    if (bw, bh) == (cw, ch):
        paste(cp, cw, ch, x0, fade=True)
        for i in changed:
            y, x = divmod(i, cw)
            canvas[(y * W + x0 + x) * 4:(y * W + x0 + x) * 4 + 4] = b'\xff\x00\xff\xff'
    else:  # different size: mark the whole third panel
        for y in range(ph):
            canvas[(y * W + x0) * 4:(y * W + x0 + pw) * 4] = b'\xff\x00\xff\xff' * pw
    return W, ph, bytes(canvas)

def environment():
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ''
    return {'runner_image': f'{os.environ.get("ImageOS", "")} {os.environ.get("ImageVersion", "")}'.strip() or 'local',
            'macos': run(['sw_vers', '-productVersion']) or platform.platform(),
            'arch': platform.machine()}

def compare(current=None, baseline=None, out=None, warn=None):
    """0 if every screenshot matches. On a difference: 1, or 0 with a warning when warn is set (HACHI_UX_DIFF=warn,
    used by release.yml: PRs and main already fail on a difference, so one that first shows up at release time is
    almost always a runner image update)."""
    if warn is None:
        warn = os.environ.get('HACHI_UX_DIFF') == 'warn'
    CURRENT, BASELINE, DIFF, CANDIDATE = _dirs(current, baseline, out)
    states = json.loads((CURRENT / 'ui-states.json').read_text(encoding='utf-8'))['states']
    files = sorted(s['file'] for s in states)
    for d in (DIFF, CANDIDATE):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    env = environment()
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    try:  # a pull_request run checks out a temporary merge commit; record the PR head, which stays in history
        commit = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())['pull_request']['head']['sha']
    except (KeyError, OSError, ValueError, TypeError):
        pass
    for f in files:
        shutil.copy2(CURRENT / f, CANDIDATE / f)
    (CANDIDATE / META).write_text(json.dumps(dict(env, rendered_at_commit=commit, files=files), indent=2,
                                             ensure_ascii=False) + '\n', encoding='utf-8')
    meta = json.loads((BASELINE / META).read_text(encoding='utf-8')) if (BASELINE / META).is_file() else None
    stored = sorted(p.name for p in BASELINE.glob('*.png')) if BASELINE.is_dir() else []

    problems, rows = [], []
    for f in files:
        if f not in stored:
            problems.append(f'{f}: no baseline')
            continue
        try:
            base, cur = read_png(BASELINE / f), read_png(CURRENT / f)
        except Exception as e:  # a damaged or missing file is a difference, and the report is still written
            problems.append(f'{f}: cannot read ({e})')
            continue
        if base[:2] != cur[:2]:
            changed, why = None, f'size {base[0]}x{base[1]} -> {cur[0]}x{cur[1]}'
        else:
            changed = changed_pixels(base[2], cur[2])
            why = f'{len(changed)} pixels changed ({100 * len(changed) / (cur[0] * cur[1]):.2f}%)' if changed else ''
        if why:
            name = f[:-4] + '-diff.png'
            write_png(DIFF / name, *diff_image(base, cur, changed or []))
            problems.append(f'{f}: {why}')
            rows.append(f'<tr><th>{html.escape(f)}</th><td>{html.escape(why)}</td>'
                        f'<td><img src="{html.escape(name)}" alt="{html.escape(f)} diff"></td></tr>')
    for f in sorted(set(stored) - set(files)):
        problems.append(f'{f}: baseline for a state that is no longer rendered')

    drift = ''
    if meta and problems:
        changed_env = [k for k in ('runner_image', 'macos', 'arch') if meta.get(k) != env.get(k)]
        if changed_env:
            drift = ('Rendering environment differs from the baseline\'s ('
                     + ', '.join(f'{k}: {meta.get(k)} -> {env.get(k)}' for k in changed_env)
                     + '); the difference may come from a runner image update, not from Hachi. Check the diff images; '
                     'if only the runner changed, refresh the baseline in its own PR (tests/ux-baseline/README.md). '
                     'This still fails on purpose: a runner change and a real UI change look the same here.')
    (DIFF / 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>Hachi UX diff</title>'
        '<style>body{font:14px -apple-system,sans-serif;margin:16px}td,th{border:1px solid #ccc;padding:8px;'
        'vertical-align:top}img{max-width:100%}table{border-collapse:collapse}</style>'
        f'<h1>Hachi UX screenshot diff</h1><p>{len(files)} screenshots compared with tests/ux-baseline/; '
        f'{len(problems)} differ. Panels: baseline | this build | changed pixels (magenta).</p>'
        + (f'<p><b>{html.escape(drift)}</b></p>' if drift else '')
        + '<ul>' + ''.join(f'<li>{html.escape(p)}</li>' for p in problems) + '</ul>'
        + '<table>' + ''.join(rows) + '</table>\n', encoding='utf-8')

    if not problems:
        print(f'PASS: {len(files)} UX screenshots match tests/ux-baseline/ pixel for pixel')
        return 0
    print('UX screenshots differ from tests/ux-baseline/:')
    for p in problems:
        print(f'  - {p}')
    if drift:
        print(drift)
    print(f'Diff images: {DIFF}/ (CI artifact hachi-<sha> -> acceptance/ux-diff/index.html).')
    print('If the change is intended, replace tests/ux-baseline/ with acceptance/ux-candidate-baseline/ from the '
          'artifact, or run: python3 tests/ux_baseline.py --import-log <this job log>')
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print_bundle(CANDIDATE)
    if warn:
        print(f'::warning::{len(problems)} UX screenshots differ from the baseline (release: warning only)'
              + (' — runner environment changed' if drift else ''))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write('### ⚠️ 截图和基线不一致（发布时只警告，不阻断）\n\n'
                        + (f'{drift}\n\n' if drift else '')
                        + ''.join(f'- {p}\n' for p in problems)
                        + '\n差异图在本次运行的 `release-ux-diff` 产物里（`ux-diff/index.html`）。'
                          '如果只是 runner 变了，请开一个刷新基线的 PR；如果界面真的变了，请看差异图决定是否撤回这次发布。\n\n')
        print(f'WARN: {len(problems)} differences between {len(files)} UX screenshots and the baseline (not failing)')
        return 0
    print(f'FAIL: {len(problems)} differences between {len(files)} UX screenshots and the baseline')
    return 1

# ---------- baseline transport ----------

def print_bundle(candidate):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for p in sorted(candidate.iterdir()):
            tar.add(p, arcname=p.name)
    blob = buf.getvalue()
    text = base64.b64encode(blob).decode()
    print(f'::group::candidate baseline bundle ({len(blob)} bytes)')
    print(f'{BEGIN} sha256={hashlib.sha256(blob).hexdigest()}')
    for i in range(0, len(text), 76):
        print(text[i:i + 76])
    print(END)
    print('::endgroup::')

def replace_baseline(src_dir):
    names = json.loads((src_dir / META).read_text(encoding='utf-8'))['files']
    for f in names:
        if not re.fullmatch(r'[a-z0-9-]+-(light|dark)\.png', f):
            raise SystemExit(f'refusing unexpected file name in bundle: {f!r}')
        read_png(src_dir / f)  # must be a readable PNG
    BASELINE.mkdir(parents=True, exist_ok=True)
    for old in list(BASELINE.glob('*.png')) + [BASELINE / META]:  # README.md stays
        old.unlink(missing_ok=True)
    for f in names + [META]:
        shutil.copy2(src_dir / f, BASELINE / f)
    print(f'baseline replaced: {len(names)} screenshots in {BASELINE.relative_to(ROOT)}/ — review them before committing')

def _dirs(current, baseline, out):
    out = Path(out) if out else OUT
    return (Path(current) if current else CURRENT, Path(baseline) if baseline else BASELINE,
            out / 'ux-diff', out / 'ux-candidate-baseline')

def import_log(log):
    stamp = re.compile(r'^\d{4}-\d\d-\d\dT[\d:.]+Z ')
    lines = [stamp.sub('', l.rstrip('\r\n')) for l in Path(log).read_text(encoding='utf-8', errors='replace').splitlines()]
    starts = [i for i, l in enumerate(lines) if l.startswith(BEGIN)]
    if not starts:
        raise SystemExit(f'no {BEGIN} in {log}')
    i = starts[-1]
    m = re.fullmatch(re.escape(BEGIN) + r' sha256=([0-9a-f]{64})', lines[i].strip())
    if not m or END not in lines[i:]:
        raise SystemExit('bundle in the log is incomplete (no checksum or no end marker); download the whole log again')
    want, j = m.group(1), lines.index(END, i)
    try:
        blob = base64.b64decode(''.join(lines[i + 1:j]), validate=True)
    except ValueError:
        raise SystemExit('bundle in the log is not valid base64; download the whole log again')
    if hashlib.sha256(blob).hexdigest() != want:
        raise SystemExit('bundle checksum mismatch; download the log again')
    tmp = OUT / 'ux-imported'
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        for m in tar.getmembers():
            if not m.isfile() or '/' in m.name or m.name.startswith('.'):
                raise SystemExit(f'refusing bundle member {m.name!r}')
            (tmp / m.name).write_bytes(tar.extractfile(m).read())
    replace_baseline(tmp)

# ---------- self-test ----------

def selftest():
    tmp = OUT / 'ux-selftest'
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    w, h = 7, 5
    a = b''.join(bytes((x * 30 % 256, y * 50 % 256, (x * y * 13) % 256, 255)) for y in range(h) for x in range(w))
    write_png(tmp / 'a.png', w, h, a)
    assert read_png(tmp / 'a.png') == (w, h, a), 'PNG round trip'
    for f in range(5):  # every filter type decodes
        raw = b''
        prev = bytearray(w * 4)
        for y in range(h):
            line = a[y * w * 4:(y + 1) * w * 4]
            enc = bytearray(line)
            for x in range(len(line)):
                left = line[x - 4] if x >= 4 else 0
                up, ul = prev[x], prev[x - 4] if x >= 4 else 0
                p = left + up - ul
                pred = [0, left, up, (left + up) // 2,
                        left if abs(p - left) <= abs(p - up) and abs(p - left) <= abs(p - ul) else up if abs(p - up) <= abs(p - ul) else ul][f]
                enc[x] = (line[x] - pred) & 255
            raw += bytes([f]) + enc
            prev = bytearray(line)
        crc = lambda k, b: struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
        (tmp / 'f.png').write_bytes(b'\x89PNG\r\n\x1a\n' + crc(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                                    + crc(b'IDAT', zlib.compress(raw)) + crc(b'IEND', b''))
        assert read_png(tmp / 'f.png')[2] == a, f'filter {f}'
    b = bytearray(a)
    b[4 * 8 + 1] ^= 1  # one channel of one pixel off by one
    assert changed_pixels(a, a) == [] and changed_pixels(a, bytes(b)) == [8], 'one changed pixel is found'
    W, H, px = diff_image((w, h, a), (w, h, bytes(b)), [8])
    assert (W, H) == (3 * w + 16, h) and px[(1 * W + 2 * (w + 8) + 1) * 4:][:4] == b'\xff\x00\xff\xff', 'diff marks it'
    # other colour types and 16-bit samples decode to the same RGBA
    grey = bytes(v for y in range(h) for v in range(y, y + w))
    for ctype, depth, rows, want in [
            (0, 8, [grey[y * w:(y + 1) * w] for y in range(h)], b''.join(bytes((v, v, v, 255)) for v in grey)),
            (2, 8, [b''.join(a[(y * w + x) * 4:(y * w + x) * 4 + 3] for x in range(w)) for y in range(h)], a),
            (6, 16, [bytes(b for c in a[y * w * 4:(y + 1) * w * 4] for b in (c, 7)) for y in range(h)], a)]:
        raw = b''.join(b'\x00' + r for r in rows)
        crc = lambda k, b: struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
        (tmp / 't.png').write_bytes(b'\x89PNG\r\n\x1a\n' + crc(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
                                    + crc(b'IDAT', zlib.compress(raw)) + crc(b'IEND', b''))
        assert read_png(tmp / 't.png') == (w, h, want), f'colour type {ctype}, depth {depth}'
    # compare(): match, changed pixel, size change, missing, stale and unreadable baselines, report always written
    cur, base, out = tmp / 'cur', tmp / 'base', tmp / 'out'
    cur.mkdir(); base.mkdir()
    names = ['same-light.png', 'pixel-light.png', 'size-light.png', 'new-light.png', 'broken-light.png']
    for n in names:
        write_png(cur / n, w, h, a)
    (cur / 'ui-states.json').write_text(json.dumps({'states': [{'file': n} for n in names]}))
    write_png(base / 'same-light.png', w, h, a)
    write_png(base / 'pixel-light.png', w, h, bytes(b))
    write_png(base / 'size-light.png', w + 1, h, a + a[:h * 4])
    (base / 'broken-light.png').write_bytes(b'not a png')
    write_png(base / 'gone-light.png', w, h, a)
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()) as log:
        rc = compare(cur, base, out)  # in CI this also prints the (small) bundle into the captured text
    text = log.getvalue()
    assert rc == 1 and 'same-light.png' not in text, text
    for n, why in [('pixel-light.png', '1 pixels changed'), ('size-light.png', 'size 8x5 -> 7x5'),
                   ('new-light.png', 'no baseline'), ('broken-light.png', 'cannot read'),
                   ('gone-light.png', 'baseline for a state that is no longer rendered')]:
        assert f'{n}: {why}' in text, (n, text)
    assert (out / 'ux-diff' / 'index.html').is_file() and (out / 'ux-diff' / 'pixel-light-diff.png').is_file()
    assert sorted(p.name for p in (out / 'ux-candidate-baseline').glob('*.png')) == sorted(names)
    summary = tmp / 'summary.md'
    old_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    os.environ['GITHUB_STEP_SUMMARY'] = str(summary)
    try:
        with contextlib.redirect_stdout(io.StringIO()) as log:
            assert compare(cur, base, out, warn=True) == 0, 'warn mode does not fail'
    finally:
        if old_summary is None:
            del os.environ['GITHUB_STEP_SUMMARY']
        else:
            os.environ['GITHUB_STEP_SUMMARY'] = old_summary
    assert '::warning::5 UX screenshots differ' in log.getvalue() and 'WARN: 5 differences' in log.getvalue(), log.getvalue()
    assert 'pixel-light.png: 1 pixels changed' in summary.read_text(encoding='utf-8')
    for n in names:
        write_png(base / n, w, h, a)
    (base / 'gone-light.png').unlink()
    with contextlib.redirect_stdout(io.StringIO()):
        assert compare(cur, base, out) == 0, 'identical sets pass'
    shutil.rmtree(tmp)
    print('PASS: PNG reader/writer (filters 0-4, grey/RGB/16-bit), pixel diff, and compare() on every outcome incl. release warn mode')

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--selftest', action='store_true')
    g.add_argument('--import-log', metavar='LOG')
    g.add_argument('--compare-locally', action='store_true', help='compare off CI anyway (expected to differ)')
    args = ap.parse_args()
    if args.import_log:
        import_log(args.import_log)
        return
    selftest()
    if args.selftest:
        return
    if os.environ.get('GITHUB_ACTIONS') != 'true' and not args.compare_locally:
        # The baseline is rendered by the CI runner; any other Mac differs in scale, fonts or OS, so a local
        # comparison would always fail without saying anything about Hachi.
        print('SKIP: pixel comparison runs only in CI (the baseline comes from the CI runner); '
              'pass --compare-locally to see the local diff anyway')
        return
    sys.exit(compare())

if __name__ == '__main__':
    main()
