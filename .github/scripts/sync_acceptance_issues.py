"""Keep one open issue per unmet release-gate item (label `acceptance`).

Reads build/acceptance/report.json from tests/acceptance.py --gate-only.
- unmet item, no issue  -> create it
- unmet item, issue closed by this workflow -> reopen it (closed by a person -> leave it, warn)
- unmet item, body changed -> update it
- met format_only item -> mark the body (open or closed), leave closing to the maintainer
- met item that CI fully verifies (none today), issue open -> comment and close it as completed
Never adds the `claude` label: starting an implementation stays a human decision.
Env: GITHUB_TOKEN, GITHUB_REPOSITORY. --dry-run prints actions without calling GitHub.
"""
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'acceptance'
API = 'https://api.github.com'
DRY = '--dry-run' in sys.argv
REPO = os.environ.get('GITHUB_REPOSITORY', 'mxgarage/hachi')
BOT = 'github-actions[bot]'

def gh(method, path, body=None):
    if DRY and method != 'GET':
        print(f'[dry-run] {method} {path} {json.dumps(body, ensure_ascii=False)[:200] if body else ""}')
        return {}
    if DRY and 'GITHUB_TOKEN' not in os.environ:
        return [] if '/issues?' in path else {}
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
                                          'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        if method == 'GET' and e.code == 404:
            return None
        raise

MET_MARK = '<!-- hachi-gate-met -->'

def norm(text):
    return '\n'.join(line.rstrip() for line in (text or '').replace('\r\n', '\n').strip().splitlines())

def marker(item_id):
    return f'<!-- hachi-gate:{item_id} -->'

def body_for(g):
    problems = '\n'.join(f'- {p}' for p in g['problems']) or '- 无'
    if g['met']:
        problems = ('- 证据的格式、阈值和 git 历史检查已通过。CI 无法验证实验是否真的跑过、观察器是否独立；'
                    '维护者确认后请手动关闭这条 issue。')
    if g.get('agent_ok') is True:  # allow-list: an item without agent_ok is not handed to agents
        start = ('维护者看过后给这条 issue 打 `claude` 标签，Claude 会在新分支上实现上面的下一步并开 PR'
                 '（只能由人打标签，工作流不会自动打）。范围：Hachi 只提醒用户当前的出口位置，不帮人绕开地区限制或平台执行；'
                 '实现和实验只用本地合成夹具、隔离网络和合成账号，不针对任何真实平台的地区或账号检测。')
    else:
        start = ('**暂不交给代理。** 这一项涉及流量的强制路由或数据面，是否在 Hachi 的范围内（只提醒当前出口位置、'
                 '不帮人绕开地区限制或平台执行）需要维护者先确认。确认前请不要给这条 issue 打 `claude` 标签；'
                 '确认后由维护者修改 `release-gate.json` 里的 `agent_ok`。')
    return f"""{marker(g['id'])}{MET_MARK if g['met'] else ''}
由 `acceptance-backlog` 工作流自动维护，内容会随每次验收刷新。格式检查通过后这里会注明，由维护者确认后手动关闭；关闭后如果这一项又变成未满足（例如证据过期），会自动重新打开。

## 验收条件
{g['title']}

> {g['readme']}

## 当前未满足的原因
{problems}

## 怎样算完成
`python3 tests/acceptance.py` 在 `{g['evidence']}` 上评估这一项（格式见 `release-gate.json` 和 `tests/acceptance.py`）。证据必须来自真实的实验运行和独立观察器，只能由维护者提交；代理不得手写或修改 `evidence/` 下的文件。

## 建议的下一步（可以交给代理做的部分）
{g['next_step']}

## 怎样启动
{start}
"""

def main():
    report = json.loads((ROOT / 'build/acceptance/report.json').read_text(encoding='utf-8'))
    if gh('GET', f'/repos/{REPO}/labels/{LABEL}') is None:
        gh('POST', f'/repos/{REPO}/labels', dict(name=LABEL, color='0e8a16', description='Release-gate item (auto-maintained)'))
    issues = []
    for page in range(1, 11):  # 1000 issues; far above the handful of gate items
        batch = gh('GET', f'/repos/{REPO}/issues?labels={LABEL}&state=all&per_page=100&page={page}') or []
        issues += [i for i in batch if 'pull_request' not in i]
        if len(batch) < 100:
            break
    for g in report['gate']:
        # only issues this workflow created; a hand-written issue containing the marker is ignored
        existing = [i for i in issues if marker(g['id']) in (i.get('body') or '')
                    and i['user']['login'] == BOT]
        issue = next((i for i in existing if i['state'] == 'open'), existing[0] if existing else None)
        if issue and issue['state'] == 'closed' and not g['met']:
            # Reopen only what this workflow itself closed (the item regressed). A person's close, for any
            # reason, is respected; the summary says how to resume reminders.
            # Exception: an issue the maintainer closed after it was met (body carries MET_MARK) is reopened when
            # the item regresses, e.g. evidence went stale after a product change.
            closer = ((gh('GET', f'/repos/{REPO}/issues/{issue["number"]}') or {}).get('closed_by') or {}).get('login')
            if closer != BOT and MET_MARK not in (issue.get('body') or ''):
                msg = (f'{g["id"]}: 未满足，但 {closer or "维护者"} 已手动关闭 #{issue["number"]}'
                       f'（{issue.get("state_reason") or "closed"}），不再提醒；要恢复提醒就重新打开它')
                print(msg)
                if os.environ.get('GITHUB_STEP_SUMMARY'):
                    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                        f.write(f'- ⚠️ {msg}\n')
                continue
        title = f'[发布门槛 {g["id"]}] {g["title"]}'
        if g['met'] and g.get('format_only'):
            # CI only checked format and history; the maintainer confirms and closes the issue by hand.
            body = body_for(g)
            # Write MET_MARK into the body whether the issue is open or already closed by a person: a later
            # regression reopens it only if the mark is there. The state is never changed here.
            if issue and norm(issue.get('body')) != norm(body):
                gh('PATCH', f'/repos/{REPO}/issues/{issue["number"]}', dict(body=body))
                print(f'{g["id"]}: format check passed, #{issue["number"]} marked ({issue["state"]}) for the maintainer')
            else:
                print(f'{g["id"]}: format check passed')
            continue
        if g['met']:
            # Only for items whose content CI can verify (no format_only); every current item is format_only.
            if issue and issue['state'] == 'open':
                gh('POST', f'/repos/{REPO}/issues/{issue["number"]}/comments', dict(body='自动验收显示这一项已满足，关闭。'))
                gh('PATCH', f'/repos/{REPO}/issues/{issue["number"]}', dict(state='closed', state_reason='completed'))
                print(f'{g["id"]}: met, closed #{issue["number"]}')
            else:
                print(f'{g["id"]}: met')
            continue
        body = body_for(g)
        if not issue:
            created = gh('POST', f'/repos/{REPO}/issues', dict(title=title, body=body, labels=[LABEL]))
            print(f'{g["id"]}: not met, created #{created.get("number", "?")}')
        elif issue['state'] != 'open' or norm(issue.get('body')) != norm(body) or issue['title'] != title:
            gh('PATCH', f'/repos/{REPO}/issues/{issue["number"]}', dict(title=title, body=body, state='open'))
            print(f'{g["id"]}: not met, updated #{issue["number"]}')
        else:
            print(f'{g["id"]}: not met, #{issue["number"]} up to date')

if __name__ == '__main__':
    main()
