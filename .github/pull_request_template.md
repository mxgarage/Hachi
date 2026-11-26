## 改了什么
<!-- 一两句话说清楚改动和原因 -->

## 对应 issue
<!-- 例如 Closes #N 或 Refs #N -->

## 执行者
<!-- 人 / Claude / Codex / Muse，用的模型，以及是谁要求的。分工见 docs/orchestration.md 的“模型调度” -->

## 怎么验证的
- [ ] `python3 build.py`
- [ ] `python3 tests/lab.py`
- [ ] `python3 tests/branding.py`
- [ ] `python3 tests/ux_screens.py`
- [ ] `python3 tests/acceptance.py`（基线通过；门槛未满足是正常的；本机不做截图像素比较，以 CI 为准）
- [ ] 其他（写明）：

## 范围检查
- [ ] 不涉及绕开地区限制或平台执行
- [ ] 没有提交私有 IP/配置、令牌、设备路径或真实凭据
- [ ] 如果改了 `tests/ux-baseline/`：下面逐个列出变了的截图和原因，基线取自 CI，等维护者本人看过差异图再合并
- [ ] 没有手写或修改 `evidence/`，没有放宽 `release-gate.json` 的条件（如有，说明原因并请维护者决定）
