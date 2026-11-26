# Hachi 协作规则（人和 AI 代理通用）

## 范围
- Hachi 只提醒用户当前的网络出口位置，并做无账号的隔离验证。不改变平台账号资格，不帮人绕开地区限制或平台执行。
- 仓库里不放私有 IP/配置、账号令牌、设备路径或真实测试凭据。

## 改动流程
1. 所有改动都走 PR，不直接推 main，维护者本人也一样。仓库 2026-11-26 起公开，但还没配分支保护或 ruleset（要不要配由维护者决定），这条目前只靠约定，所以每个人和每个代理都要自觉遵守。分支名：`<执行者>/<简短主题>`，例如 `claude/pr-workflow`。
2. PR 正文按 `.github/pull_request_template.md` 填写，写明执行者、对应 issue、怎么验证。
3. 合并前必须满足：
   - `Account-free macOS verification`（`verify.yml`）在当前 head 上通过；
   - 至少一份非作者本人的评审（人，或另一个 AI 评审者）已看过当前 head，提出的阻塞意见已解决；
   - 不是 Draft。
4. **合并只由维护者（daniel-to-the-moon）手动操作，用 merge commit（不用 squash 或 rebase）**，否则证据里记录的 `tested_commit` 会从 main 的历史里消失，证据永远过不了检查。 AI 代理可以开 PR、改自己的 PR、回复评审，但不合并、不发布、不改仓库设置和密钥。
5. 同一个 issue 同一时间只有一个代理在实现；接手前在 issue 里说明。

## 自动化边界
- 可以自动运行的：CI（`verify.yml`）、PR 评审（`claude-review.yml` 和 Codex，只评论）、代理按 issue 自动实现并开 PR（`claude.yml`：仓库成员/协作者（人类账号）给 issue 打 `claude` 标签（默认用 Sonnet，另打 `opus` 标签用 Opus），或发一条以 `@claude` 开头的评论；正文中间或引用里提到 @claude、bot 评论不触发，带 Claude Code 落款的代理代发评论按约定也不触发）、圆桌各轮由定时任务或评论触发。
- 自动验收：`verify.yml` 每次运行 `tests/acceptance.py`（构建、测试、仓库卫生检查，并按 `release-gate.json` 评估发布门槛），报告写进 job summary，app 和报告作为产物上传。
- 自迭代：`acceptance-backlog.yml` 每周和门槛/证据变化时运行，给每个未满足的门槛项保持一条 `acceptance` issue，格式检查通过后在 issue 里注明、由维护者确认并手动关闭，之后又不满足（例如证据过期）会重新打开。它不打 `claude` 标签；维护者看过后自己打标签，才会让 Claude 开始实现。
- 范围决定：维护者 2026-11-25 在项目讨论里确认，G2–G5 按原门槛保留，维护者给对应 issue 打 `claude` 标签后可以交给 Claude 实现（`release-gate.json` 里 `agent_ok: true`）。实验仍只用合成账号、本地夹具和隔离网络。
- 体验验收（G6，维护者 2026-11-25 决定加入）：CI 渲染每个菜单和提醒状态的截图（`tests/ux_screens.py`），维护者本人在真机上按 `docs/ux-checklist.md` 走查并签字（`agent_ok: false`）。代理可以修走查发现的问题、维护截图脚本，但不能代签，也不能为了通过而删减清单项。CI 还把每张截图和 `tests/ux-baseline/` 里的基线逐像素比较，有差异就失败（`tests/ux_baseline.py`）。界面有意改动时，代理可以在同一个 PR 里更新基线，并在 PR 正文逐个列出变了的截图文件和原因；这类 PR 由维护者本人看过差异图再合并，代理评审不算数（这是约定：CI 拿 PR 自带的基线比较，界面和基线一起改照样会绿，代理改基线时只给警告）；基线只能取自 CI 渲染结果，不能用本机截图，也不能为了让 CI 变绿而更新没解释过的差异。
- 发布：**触发 `release.yml` 就等于发布**（推 `v*` tag、合并新增 `docs/release-notes/v*.md` 的 PR、或手动运行都算，见下一条），`release.yml` 只接受维护者账号触发的运行。代理不得创建或推送任何 tag。无后缀 tag（`v0.2`）要求门槛全部满足，否则不发布；带后缀 tag（`v0.2-dev.1`）发预发布并标明未通过门槛。真正创建 Release 的 job 绑定 `release` environment。**正式版**（无后缀 tag）：需要给它配审批人才会停下来等审批，没配（或读不到审批规则）时只建 draft release，由维护者手动发布；目前 `release` 环境还没配 Required reviewers（仓库 2026-11-26 之前是私有的，套餐不提供；公开后维护者可以在 Settings → Environments 里配），所以正式版现在只会生成 draft。**预发布**（带后缀 tag）：不再因为没配审批人而退回草稿，直接发布（维护者 2026-11-26 要求免点击发布；“预发布直接发布”这一点在 PR #21 里等维护者明确确认）。以后如果给 `release` 环境配了审批人，publish job 仍会停下来等这个审批。发布前同样跑截图像素比较。
- 免点击发布（维护者 2026-11-26 要求）：维护者合并一个新增 `docs/release-notes/v<版本>.md` 的 PR，`release.yml` 就用文件名当 tag，在合并的提交上构建，通过后创建 tag 和 release（正文 = 这份说明 + 验收报告）；或者在 Actions → Release → Run workflow 里把 `version` 留空（自动取下一个开发版本）或填版本号。工作流只接受维护者账号触发的运行；新版本的 tag 在构建通过之后才创建（手动推 tag 的路径除外，那时 tag 已经存在）；预发布直接发布（合并说明文件、运行工作流就是维护者的批准），正式版仍要求全部门槛满足，且 `release` 环境没有审批人时只建草稿。代理仍然不创建或推送 tag，也不运行发布工作流；代理只写发布说明文件并开 PR。**新增 `docs/release-notes/v*.md` 的 PR 合并即发布预发布，不是普通文档 PR：PR 标题必须带“合并即发布 v<版本>”，由维护者本人确认后再合并，一次合并只新增一个版本的说明文件。**这条改动本身改了 `.github/workflows/`，合并前由维护者审阅。
- 不自动做的：合并、改仓库设置和密钥，以及代理打 tag 和发布。这些由维护者决定。
- 不用真实 Claude/Codex/其他平台账号做故障实验。

## 模型调度（维护者 2026-11-26 定）
- 给每个模型匹配最合适的任务，充分用满订阅额度。Opus 最稀缺，只用在主脑决策（范围、方案、验收标准、安全边界判断）和最难的代码逻辑（门槛评估器、发布工作流、G2–G5 的防泄漏和断网逻辑）上。
- Sonnet：按清楚的说明实现、按评审意见清单修改、PR 评审、CI 排查和读日志、截图基线差异初筛、日报。Haiku：协调和汇总。Codex：第二意见评审；纯文档 PR 只要 Codex 评审。
- `claude.yml` 默认用 Sonnet，issue 另带 `opus` 标签才用 Opus；`claude-review.yml` 用 Sonnet，不评审纯文档 PR。PR 的“执行者”一栏写明用的模型。
- 每天的自动化日报加“使用量复盘”：各模型做了什么、哪些用错了地方、额度有没有闲置、第二天的调度建议。日报只给建议，不自动派发。
- 详细分工表和日报格式见 [docs/orchestration.md](docs/orchestration.md)。

## 验收证据
- `evidence/` 下的证据只能来自真实的实验运行和独立观察器，由维护者提交。代理可以写产生证据的工具和测试，但不得手写、编辑或"补齐" `evidence/` 下的文件，也不得为了让门槛通过而放宽 `release-gate.json` 或 `tests/acceptance.py` 的条件；要改条件，先在 issue 里提出，由维护者决定。这条规则同样适用于 `.github/workflows/` 和 `.github/scripts/`（例如去掉 `--require-gate`）。来自代理分支（`claude/`、`codex/`、`muse/`）或带代理署名 trailer 的提交如果改了 `evidence/`，CI 会失败，其他分支名或不带 trailer 的提交识别不出来，这只能防止无心之失；对门槛定义、评估器和这些工作流的改动只会给出警告，靠维护者审阅把关。

## 本地验证
```
python3 build.py
python3 tests/lab.py
python3 tests/branding.py
python3 tests/ux_screens.py   # 渲染所有菜单和提醒状态的截图
python3 tests/acceptance.py   # 包含以上各步和截图基线比较，另做卫生检查和门槛评估
```
截图像素比较只在 CI 上算数：本机运行时 `tests/ux_baseline.py` 只做自检，`--compare-locally` 可以强制在本机比较（本机渲染本来就和 CI 基线不同）。基线只能取自 CI，`--import-log <CI job 日志>` 可以从日志里取，流程见 `tests/ux-baseline/README.md`。截图和基线不一致时，PR 和 main 上 CI 失败；发布（`release.yml`）时只警告，差异图放在 `release-ux-diff` 产物里（维护者 2026-11-26 决定）。
`tests/check.py` 是可选的手动冒烟测试，不属于验收或 CI。
