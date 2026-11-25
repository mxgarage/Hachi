# Hachi 协作规则（人和 AI 代理通用）

## 范围
- Hachi 只提醒用户当前的网络出口位置，并做无账号的隔离验证。不改变平台账号资格，不帮人绕开地区限制或平台执行。
- 仓库里不放私有 IP/配置、账号令牌、设备路径或真实测试凭据。

## 改动流程
1. 所有改动都走 PR，不直接推 main，维护者本人也一样。仓库是免费组织下的私有仓库，GitHub 不会强制分支保护，这条只靠约定，所以每个人和每个代理都要自觉遵守。分支名：`<执行者>/<简短主题>`，例如 `claude/pr-workflow`。
2. PR 正文按 `.github/pull_request_template.md` 填写，写明执行者、对应 issue、怎么验证。
3. 合并前必须满足：
   - `Account-free macOS verification`（`verify.yml`）在当前 head 上通过；
   - 至少一份非作者本人的评审（人，或另一个 AI 评审者）已看过当前 head，提出的阻塞意见已解决；
   - 不是 Draft。
4. **合并只由维护者（daniel-to-the-moon）手动操作，用 merge commit（不用 squash 或 rebase）**，否则证据里记录的 `tested_commit` 会从 main 的历史里消失，证据永远过不了检查。 AI 代理可以开 PR、改自己的 PR、回复评审，但不合并、不发布、不改仓库设置和密钥。
5. 同一个 issue 同一时间只有一个代理在实现；接手前在 issue 里说明。

## 自动化边界
- 可以自动运行的：CI（`verify.yml`）、PR 评审（`claude-review.yml` 和 Codex，只评论）、代理按 issue 自动实现并开 PR（`claude.yml`：仓库成员/协作者（人类账号）给 issue 打 `claude` 标签，或发一条以 `@claude` 开头的评论；正文中间或引用里提到 @claude、bot 评论不触发，带 Claude Code 落款的代理代发评论按约定也不触发）、圆桌各轮由定时任务或评论触发。
- 自动验收：`verify.yml` 每次运行 `tests/acceptance.py`（构建、测试、仓库卫生检查，并按 `release-gate.json` 评估发布门槛），报告写进 job summary，app 和报告作为产物上传。
- 自迭代：`acceptance-backlog.yml` 每周和门槛/证据变化时运行，给每个未满足的门槛项保持一条 `acceptance` issue，格式检查通过后在 issue 里注明、由维护者确认并手动关闭，之后又不满足（例如证据过期）会重新打开。它不打 `claude` 标签；维护者看过后自己打标签，才会让 Claude 开始实现。
- 范围决定：维护者 2026-11-25 在项目讨论里确认，G2–G5 按原门槛保留，维护者给对应 issue 打 `claude` 标签后可以交给 Claude 实现（`release-gate.json` 里 `agent_ok: true`）。实验仍只用合成账号、本地夹具和隔离网络。
- 体验验收（G6，维护者 2026-11-25 决定加入）：CI 渲染每个菜单和提醒状态的截图（`tests/ux_screens.py`），维护者本人在真机上按 `docs/ux-checklist.md` 走查并签字（`agent_ok: false`）。代理可以修走查发现的问题、维护截图脚本，但不能代签，也不能为了通过而删减清单项。CI 还把每张截图和 `tests/ux-baseline/` 里的基线逐像素比较，有差异就失败（`tests/ux_baseline.py`）。界面有意改动时，代理可以在同一个 PR 里更新基线，并在 PR 正文逐个列出变了的截图文件和原因；这类 PR 由维护者本人看过差异图再合并，代理评审不算数；基线只能取自 CI 渲染结果，不能用本机截图，也不能为了让 CI 变绿而更新没解释过的差异。
- 发布：**推 `v*` tag 就等于发布**，`release.yml` 只接受维护者账号推的 tag。代理不得创建或推送任何 tag。无后缀 tag（`v0.2`）要求门槛全部满足，否则不发布；带后缀 tag（`v0.2-dev.1`）发预发布并标明未通过门槛。真正创建 Release 的 job 绑定 `release` environment，需要在仓库设置里给它配审批人才会停下来等审批；没配（或读不到审批规则）时只建 draft release，由维护者手动发布。截至 2026-11-25，这个私有仓库的套餐不提供 environment 审批人（`release` 环境已建，但没有 Required reviewers 选项），所以实际行为是：推 tag 只生成 draft，由维护者在 Releases 页面手动点发布。
- 不自动做的：合并、打 tag 和发布、改仓库设置和密钥。这些由维护者决定。
- 不用真实 Claude/Codex/其他平台账号做故障实验。

## 验收证据
- `evidence/` 下的证据只能来自真实的实验运行和独立观察器，由维护者提交。代理可以写产生证据的工具和测试，但不得手写、编辑或"补齐" `evidence/` 下的文件，也不得为了让门槛通过而放宽 `release-gate.json` 或 `tests/acceptance.py` 的条件；要改条件，先在 issue 里提出，由维护者决定。这条规则同样适用于 `.github/workflows/` 和 `.github/scripts/`（例如去掉 `--require-gate`）。来自代理分支（`claude/`、`codex/`、`muse/`）或带代理署名 trailer 的提交如果改了 `evidence/`，CI 会失败，其他分支名或不带 trailer 的提交识别不出来，这只能防止无心之失；对门槛定义、评估器和这些工作流的改动只会给出警告，靠维护者审阅把关。

## 本地验证
```
python3 build.py
python3 tests/lab.py
python3 tests/branding.py
python3 tests/acceptance.py   # 包含以上三步，另做卫生检查和门槛评估
```
`tests/check.py` 是可选的手动冒烟测试，不属于验收或 CI。
