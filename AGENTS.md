# Hachi 协作规则（人和 AI 代理通用）

## 范围
- Hachi 只提醒用户当前的网络出口位置，并做无账号的隔离验证。不改变平台账号资格，不帮人绕开地区限制或平台执行。
- 仓库里不放私有 IP/配置、账号令牌、设备路径或真实测试凭据。

## 改动流程
1. 所有改动都走 PR，不直接推 main。分支名：`<执行者>/<简短主题>`，例如 `claude/pr-workflow`。
2. PR 正文按 `.github/pull_request_template.md` 填写，写明执行者、对应 issue、怎么验证。
3. 合并前必须满足：
   - `Account-free macOS verification`（`verify.yml`）在当前 head 上通过；
   - 至少一份非作者本人的评审（人，或另一个 AI 评审者）已看过当前 head，提出的阻塞意见已解决；
   - 不是 Draft。
4. **合并只由维护者（daniel-to-the-moon）手动操作。** AI 代理可以开 PR、改自己的 PR、回复评审，但不合并、不发布、不改仓库设置和密钥。
5. 同一个 issue 同一时间只有一个代理在实现；接手前在 issue 里说明。

## 自动化边界
- 自动触发的只有：CI（`verify.yml`）和 PR 评审（`claude-review.yml`，只评论，不改代码）。
- `docs/roundtable.md` 的圆桌规则继续有效：圆桌各轮手动启动，不由评论自动触发，不自动改代码、合并或发布。
- 不用真实 Claude/Codex/其他平台账号做故障实验。

## 本地验证
```
python3 build.py
python3 tests/lab.py
python3 tests/branding.py
```
`tests/check.py` 是可选的手动冒烟测试，不属于验收或 CI。
