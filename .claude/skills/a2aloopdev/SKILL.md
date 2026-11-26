---
name: a2aloopdev
description: Hachi 的代理对代理（agent-to-agent）开发闭环：issue → 实现 → CI → 评审 → 修改 → 维护者合并 → 发布。在 Hachi 仓库里实现 issue、开 PR、处理评审意见、写发布说明、判断该用哪个模型时使用。
---

# a2aloopdev：Hachi 开发闭环

规则的权威来源是仓库的 `AGENTS.md` 和 `docs/orchestration.md`；本文件是执行清单，冲突时以它们为准。

## 0. 红线（任何环节都不能破）
- **范围**：Hachi 只提醒用户当前的网络出口位置，并做无账号隔离验证。不帮人绕开地区限制或平台执行；不把受限地区用户的反馈当作需求依据；不声称某个出口能让账号合规。
- **代理不做**：合并、改仓库设置和密钥、创建/推送 tag、运行 `release.yml`、删除 release 或 tag（会话也没有这个权限）、手写或编辑 `evidence/`、放宽 `release-gate.json` / `tests/acceptance.py` / 工作流条件、给 G6 走查代签。
- 不用真实 Claude/Codex/其他平台账号做故障实验；仓库里不放私有 IP、令牌、设备路径。
- 在 morita 账号下发评论时，不要裸写 `@claude`（会触发 `claude.yml`），写成反引号包起来的 `@claude` 或 “＠claude”。

## 1. 开工前
1. 确认 issue 有验收标准；没有就先在 issue 里补，再动手。
2. 同一个 issue 同时只有一个执行者；接手前在 issue 里说明。
3. 选模型（见第 6 节）。拿不准就先 Sonnet，Sonnet 连续两次做不好再升级 Opus。
4. 分支名 `<执行者>/<简短主题>`，只推到自己的分支，不推 main。

## 2. 实现
- 本地验证（macOS）：`python3 build.py`、`tests/lab.py`、`tests/branding.py`、`tests/ux_screens.py`、`tests/acceptance.py`。非 macOS 只能跑 `tests/acceptance.py --gate-only` 和 `tests/ux_baseline.py --selftest`，其余交给 CI。
- **一次提交一个完整的改动**：本地把能自检的都跑完再推。避免一串零碎的 fix 提交，每次推送都会重跑 macOS CI 并触发新一轮评审（PR #12 出现过 16 轮评审）。
- 同一轮的评审意见先全部读完、列成清单，**合成一次提交**再推。
- 不能为了让 CI 变绿而删测试、跳过检查或删减 `docs/ux-checklist.md` 的条目。

## 3. 开 PR
- 按 `.github/pull_request_template.md` 填：执行者（写明模型）、对应 issue、怎么验证。
- `claude.yml` 只推分支并给 “Create PR” 链接，不会自己开 PR；开 PR 后 CI 和评审才会开始。
- 以 morita 的 token 开的 PR，作者就是 morita，不能再向 morita 请求评审，评审要找 Claude/Codex。
- 纯文档 PR（只改 `docs/` 和 Markdown）只由 Codex 评审，不触发 Claude 评审；但 `AGENTS.md`、`docs/ux-checklist.md`、`docs/release-notes/` 例外，会触发。

## 4. CI 与评审
- 合并门槛：`Account-free macOS verification` 在当前 head 通过；至少一份非作者评审看过当前 head 且阻塞意见已解决；不是 Draft。
- CI 失败：先用 `gh api` 取 job 日志（artifact 下载常被代理挡）。这是 Sonnet 的活。只重跑失败的部分，同一命令第 5 次还在跑就停下来问。
- **截图基线**：PR 和 main 上像素差异会让 CI 失败；发布时只警告（差异图在 `release-ux-diff` 产物里）。界面有意改动时，**在同一个 PR 里更新基线**，基线只能取自 CI 渲染（`tests/ux_baseline.py --import-log <CI job 日志>`），不能用本机截图；PR 正文逐个列出变了的截图文件和原因。改了基线的 PR 由 morita 本人看过差异图再合并，代理评审不算数。
- 评审意见分三类处理：采纳并改；不采纳并在回复里说明理由；超出本 PR 范围的开新 issue。不要为了评审者重复的同类意见反复小改。
- 评审风暴的止损：同一个 PR 超过 3 轮评审还有新的阻塞意见，停下来，把剩余分歧汇总给 morita 决定。

## 5. 合并与发布
- **合并只由 morita 手动用 merge commit 完成**（不用 squash/rebase，否则证据里的 `tested_commit` 会从 main 历史里消失）。代理的收尾动作是：确认检查全绿、PR 正文最新、一句话告诉 morita 可以合并。
- **触发 `release.yml` 就等于发布**，且只接受 morita 账号触发：
  - 合并一个新增 `docs/release-notes/v<版本>.md` 的 PR，就以文件名为 tag，在合并提交上构建并发布；
  - 或 morita 手动运行 Release workflow（`version` 留空取下一个开发版本）。
- 代理发布流程里**只写发布说明文件并开 PR**：标题带“合并即发布 v<版本>”，一次只新增一个版本的说明文件，等 morita 确认后合并。tag 由工作流在构建通过后创建，代理不碰 tag。
- 无后缀版本（`v0.2`）要求 G1–G6 全部满足，否则不发布；带后缀（`v0.2-dev.N`）发预发布并标明未过门槛。`release` 环境没配审批人时，正式版只建 draft，由 morita 手动发布。
- **已知冲突**：发布自检（release self-test）与 `HACHI_UX_DIFF=warn` 在发布路径上互相打架。改动 `release.yml` 或 `tests/ux_baseline.py` 时，两条路径（PR 失败、发布只警告）都要覆盖验证，不能只测其中一条；这类改动属于第 6 节的 Opus 范围。
- 发错了不要自己删 release 或 tag：停下来告诉 morita，由 morita 在 GitHub 页面处理。

## 6. 模型调度（Opus 最稀缺）
| 模型 | 用在 |
|---|---|
| Opus | 范围/方案/验收标准、拆 issue；最难逻辑：门槛评估器、发布工作流、证据与 git 历史校验、G2 防泄漏、隧道断开时安全断网、Network Extension（G2–G5 核心）；涉及安全边界或范围的评审；Sonnet 连续两次失败的问题 |
| Sonnet | 按清楚说明实现、按评审清单修改、Claude PR 评审、CI 排查和读日志、截图差异初筛、日报 |
| Haiku | 协调与汇总：摘要、整理状态、转述结果 |
| Codex | 第二意见评审；纯文档 PR 的唯一评审 |
- 新线程默认 Sonnet；难题线程启动时指定 Opus。issue 另带 `opus` 标签，`claude.yml` 才用 Opus。
- 协调/试跑类线程用 Sonnet：Opus 的协调线程曾比全部 Actions 工作加起来还贵。
- 日报含“使用量复盘”（各模型做了什么、错配、闲置、明天的调度建议），只给建议，不自动派发。

## 7. 卡住时
- 需要 morita 决定的（范围、放宽门槛、发布）：在 issue/PR 里写清选项和推荐，发决策卡，然后继续做不依赖它的部分。
- 不可逆操作（发布、删除、改设置）一律等 morita 明确同意；已经授权过的具体动作（例如发 issue 评论）不再重复确认。
- 做完把结果、验证依据和下一步写在 PR 或 issue 里，不要只留在会话里。
