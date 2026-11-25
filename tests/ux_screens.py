"""UX screenshots: render every menu-bar, menu and alert state (light and dark) with `Hachi --render-ui`,
check the set is complete and the texts keep the scope disclaimers, and write an index page.

Output: build/acceptance/ux/ (uploaded with the CI artifact). The maintainer reviews these together with
docs/ux-checklist.md for the G6 sign-off; this script only proves the states render and say what they should.
Menus are drawn from the real menu items, not captured from the system menu bar.
"""
import html
import json
import os
from pathlib import Path
import struct
import subprocess

root = Path(__file__).resolve().parents[1]
binary = root / 'build/Hachi.app/Contents/MacOS/Hachi'
out = Path(os.environ.get('HACHI_ACCEPTANCE_OUT') or root / 'build' / 'acceptance') / 'ux'
assert binary.is_file(), 'Hachi.app has not been built'
subprocess.run([str(binary), '--render-ui', str(out)], check=True, timeout=60)
manifest = json.loads((out / 'ui-states.json').read_text(encoding='utf-8'))

EXPECTED = ['menubar-rest', 'menubar-wag', 'menubar-checking', 'menu-network-waiting', 'menu-network-available',
            'menu-network-unavailable', 'menu-checking-claude', 'alert-claude-passed', 'alert-claude-blocked',
            'alert-codex-passed', 'alert-codex-blocked', 'alert-entry-missing']
states = {(s['state'], s['appearance']): s for s in manifest['states']}
missing = [f'{n}/{a}' for n in EXPECTED for a in ('light', 'dark') if (n, a) not in states]
assert not missing, f'states not rendered: {missing}'

def png_size(path):
    data = path.read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n'), f'{path.name} is not a PNG'
    return struct.unpack('>II', data[16:24])

images = {}
for (name, look), s in states.items():
    w, h = png_size(out / s['file'])
    assert w >= 40 and h >= 20, f'{s["file"]} is only {w}x{h}'
    images[(name, look)] = (out / s['file']).read_bytes()
for name in EXPECTED:
    assert images[(name, 'light')] != images[(name, 'dark')], f'{name}: light and dark render identically'
assert images[('menubar-rest', 'light')] != images[('menubar-wag', 'light')], 'tail pose does not change the icon'
assert images[('menu-checking-claude', 'light')] != images[('menu-network-available', 'light')], \
    'a check in progress must visibly disable its row'

texts = lambda n: states[(n, 'light')]['texts']
for n in EXPECTED:
    if n.startswith('menu-'):
        t = texts(n)
        assert '[disabled] 观察模式 · 不拦截运行中流量' in t and '[disabled] 浏览器授权 / MCP：未覆盖' in t, (n, t)
        assert '退出' in t, (n, t)
    if n.startswith('alert-'):
        body = '\n'.join(texts(n))
        assert '未启动客户端' in body and '未覆盖' in body, (n, body)
        assert '示例' in body, f'{n}: screenshot evidence must be labelled as an example'
assert '[disabled] 系统网络：等待状态' in texts('menu-network-waiting')
assert any('可用（不是出口验证）' in t for t in texts('menu-network-available'))
assert '[disabled] 检查 Claude 出口' in texts('menu-checking-claude') and '检查 Codex 出口' in texts('menu-checking-claude')
assert texts('alert-claude-passed')[0] == 'Claude：预检通过' and texts('alert-codex-blocked')[0] == 'Codex：预检未通过'
assert manifest['tooltips'] == {'idle': 'Hachi · 观察模式（不拦截）', 'checking': 'Hachi · 预检中'}

rows = []
for name in EXPECTED:
    cells = ''.join(f'<td><img src="{html.escape(states[(name, a)]["file"])}" alt="{name} {a}"></td>' for a in ('light', 'dark'))
    words = '<br>'.join(html.escape(t).replace('\n', '<br>') for t in texts(name))
    rows.append(f'<tr><th>{name}</th>{cells}<td>{words}</td></tr>')
(out / 'index.html').write_text(
    '<!doctype html><meta charset="utf-8"><title>Hachi UX states</title>'
    '<style>body{font:14px -apple-system,sans-serif;margin:16px}td,th{border:1px solid #ccc;padding:8px;vertical-align:top}'
    'img{max-width:420px}table{border-collapse:collapse}</style>'
    '<h1>Hachi UX states</h1><p>菜单按真实菜单项绘制，不是系统菜单截图。提醒里的预检输出是示例。'
    '对照 docs/ux-checklist.md 验收。</p>'
    '<table><tr><th>状态</th><th>浅色</th><th>深色</th><th>文字</th></tr>' + ''.join(rows) + '</table>\n',
    encoding='utf-8')
print(f'PASS: {len(states)} UX screenshots ({len(EXPECTED)} states x light/dark) in {out}')
