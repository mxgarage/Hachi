# Hachi 编排说明：谁在什么时候做什么

这份文档把仓库里的自动化、人和各个 AI 代理的分工写在一处。规则本身以 [AGENTS.md](../AGENTS.md) 为准；这里讲流程怎么串起来、每一步该交给谁。

## 一次改动的完整流程

1. **开工**：维护者在 issue 上打 `claude` 标签（或发一条以 `@claude` 开头的评论），`claude.yml` 让 Claude 在新分支上实现（默认 Sonnet，issue 另带 `opus` 标签时用 Opus）。它只推分支，在 issue 评论里给一个 “Create PR” 链接，不会自己开 PR：维护者（或替维护者工作的代理）点链接按模板开 PR 后，CI 和评审才开始；其他代理（Codex、Muse）或人自己开 `<执行者>/<主题>` 分支。同一个 issue 同时只有一个执行者。
2. **开 PR**：按 `.github/pull_request_template.md` 填写，写明执行者和用的模型（见下面的“模型调度”）。
3. **自动检查**（PR 每次推送）：
   - `verify.yml`（`Account-free macOS verification`，`macos-15`）：跑 `tests/acceptance.py`，其中包括构建、loopback 实验、品牌检查、UX 截图渲染、截图与 `tests/ux-baseline/` 的逐像素比较、门槛自检、仓库卫生检查和门槛评估；然后上传 app zip、验收报告和截图差异图（产物 `hachi-<sha>`）。代理分支改了 `evidence/` 直接失败；改门槛定义、工作流或截图基线只在 job summary 里给警告，留给维护者看。
   - `claude-review.yml`：Claude（Sonnet）评审，只发评论。纯文档 PR（只改 `docs/` 和 Markdown；`AGENTS.md`、`evidence/README.md`、PR 模板和 `docs/ux-checklist.md` 除外）不触发，只由 Codex 评审。
   - Codex：PR 打开时自动评审一次。
4. **合并**：满足 AGENTS.md 的合并门槛后，由维护者本人手动用 merge commit 合并。改了截图基线的 PR 要维护者本人看过差异图，代理评审不算数。
5. **合并后**：`verify.yml` 在 main 上再跑一次；`acceptance-backlog.yml` 按门槛状态同步 `acceptance` issue（每次推 main，以及每周一 01:17 UTC）。
6. **发布**：维护者推 `v*` tag，`release.yml` 构建、跑同一套验收（包括截图像素比较）、ad-hoc 签名并挂到 Release 上。代理不打 tag。

## 工作流一览

| 工作流 | 触发 | 做什么 | 权限 |
|---|---|---|---|
| `verify.yml` | 推到 main、任意 PR、手动 | 验收基线 + 门槛评估，上传产物 | 只读 |
| `claude-review.yml` | 非 Draft PR 打开/更新（纯文档 PR 除外） | Sonnet 评审评论 | 评论 |
| `claude.yml` | issue 打 `claude` 标签；成员以 `@claude` 开头的评论 | Claude 实现，推分支并给出 “Create PR” 链接（默认 Sonnet，`opus` 标签用 Opus） | 写分支、评论 |
| `acceptance-backlog.yml` | 推到 main、每周一、手动 | 维护 `acceptance` issue | 写 issue |
| `release.yml` | 维护者推 `v*` tag、手动（已有 tag） | 构建、验收、签名、挂到 Release | 只有最后一步可写 |

仓库 2026-11-26 起公开，Actions 用 GitHub 标准托管 runner。来自 fork 的 PR 拿不到仓库 Secret，所以 Claude 评审和 Claude 实现在 fork PR 上会跳过，`verify.yml` 照常运行。

`verify.yml` 只在推 main 和 PR 上运行，不再对每个分支推送单独跑一遍（之前同一次推送会在 push 和 pull_request 上各跑一次 macOS job）。还没开 PR 的分支想跑 CI，可以在 Actions 页面手动运行，或直接开 Draft PR。同一个 PR 连续推送时，旧的运行会被取消。

## 本地命令

需要 macOS、Apple 命令行工具和 Python 3.9+。

```sh
python3 build.py                        # 构建 build/Hachi.app
python3 tests/lab.py                    # loopback 实验
python3 tests/branding.py               # 品牌和文案检查
python3 tests/ux_screens.py             # 渲染所有菜单和提醒状态的截图
python3 tests/ux_baseline.py --selftest # 截图比较工具自检（任何系统都能跑）
python3 tests/ux_baseline.py --compare-locally   # 在本机也和基线比较；本机渲染和 CI 基线本来就会不同，只用来看差异
python3 tests/ux_baseline.py --import-log <log>  # 从 CI job 日志里取新基线（会校验 checksum）
python3 tests/acceptance.py             # 以上全部 + 卫生检查和门槛评估，报告在 build/acceptance/
python3 tests/acceptance.py --gate-only # 只评估门槛（不需要 macOS）
```

本机跑 `tests/acceptance.py` 时，截图像素比较会自动跳过，只做自检；像素比较只在 CI 上算数。基线只能取自 CI 渲染，流程见 [tests/ux-baseline/README.md](../tests/ux-baseline/README.md)。

## 模型调度

维护者 2026-11-26 定的规则：**给每个模型匹配最合适的任务，充分用满订阅额度。** Opus 最稀缺，只用在主脑决策和最难的代码逻辑上；能交给 Sonnet、Haiku 或 Codex 的事就不占用 Opus。

| 模型 | 交给它的事 |
|---|---|
| Claude Opus | 范围和方案决策、拆 issue、定验收标准；最难的代码逻辑：门槛评估器（`tests/acceptance.py`、`release-gate.json`）、发布工作流、证据和 git 历史校验、Network Extension 与防泄漏和隧道断开时安全断网（G2–G5）的核心逻辑；涉及安全边界或范围判断的评审；其他模型连续两次做不好的问题 |
| Claude Sonnet | 按清楚的说明实现（issue 已写明验收标准）、按评审意见清单逐条修改、PR 的 Claude 评审（`claude-review.yml`）、CI 失败排查和读日志、截图基线差异初筛、每天的日报 |
| Claude Haiku | 协调和汇总：issue 和讨论摘要、整理状态、转述结果 |
| Codex | 第二意见评审（PR 打开时自动评审）；纯文档 PR 只要 Codex 评审 |

落地方式：

- `claude.yml` 默认用 Sonnet。issue 同时带 `opus` 标签时用 Opus，留给左栏第一行那类任务；维护者打 `claude` 标签前先判断交给谁。
- `claude-review.yml` 用 Sonnet，且不评审纯文档 PR（只改 `docs/` 和 Markdown，规则文件和 G6 走查清单除外）；纯文档 PR 由 Codex 评审即可满足“至少一份非作者评审”。
- PR 模板的“执行者”一栏写明用的模型，日报据此统计。
- 不管谁做，产出都走 PR、CI 和评审，规则不因执行者不同而放宽。

2026-11-26 试跑（issue #16 → PR #17，只改测试的小任务，费用是 Actions 日志里 `total_cost_usd` 的 API 价估算）：Sonnet 实现 11 轮、28 秒、约 $0.15；Sonnet 评审 1 轮、8 轮对话、约 $0.12；macOS CI 一次，35 秒；从打标签到 CI、Claude 评审和 Codex 评审全部完成约 3.5 分钟，没有返工。之前同类工作全在 Opus 上（例如纯文档 PR #12 约 $15.9、16 轮 Claude 评审）。

## 日报里的使用量复盘

每天的自动化日报加一节“使用量复盘”，内容固定为：

1. **用量**：过去 24 小时 Opus、Sonnet、Haiku、Codex 各做了哪些事；`claude.yml`、`claude-review.yml` 的运行次数和耗时；订阅额度用了多少、还剩多少。数据来自 Actions 运行记录和各 PR 的“执行者”一栏，拿不到的写“未知”，不估算。
2. **错配**：哪些 Opus 做的事其实 Sonnet 或 Haiku 就够（例如 Opus 评审了只改措辞的 PR、Opus 排查了一个读日志就能解决的 CI 失败），反过来哪些事便宜的模型做砸了、应该升级。
3. **闲置**：额度有没有剩着没用。剩得多时，指出可以提前做的待办（例如让 Sonnet 补测试、做已写好说明的 issue）。
4. **明天的调度建议**：按上面的表，列出待办里每件交给哪个模型，每件一句理由。

日报只读：只给建议，不自动改标签、不自动派发。

## 长任务放哪

完整测试和构建在 CI（`verify.yml`）上跑：推分支、开 PR，看检查结果。CI 产物下载被某些代理网络挡住时，可以用 `gh api` 下载 job 日志，`tests/ux_baseline.py --import-log` 直接从日志里取基线。
