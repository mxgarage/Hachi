## 改了什么
<!-- 一两句话说清楚改动和原因 -->

## 对应 issue
<!-- 例如 Closes #N 或 Refs #N -->

## 执行者
<!-- 人 / Claude / Codex / Muse，以及是谁要求的 -->

## 怎么验证的
- [ ] `python3 build.py`
- [ ] `python3 tests/lab.py`
- [ ] `python3 tests/branding.py`
- [ ] `python3 tests/acceptance.py`（基线通过；门槛未满足是正常的）
- [ ] 其他（写明）：

## 范围检查
- [ ] 不涉及绕开地区限制或平台执行
- [ ] 没有提交私有 IP/配置、令牌、设备路径或真实凭据
- [ ] 没有手写或修改 `evidence/`，没有放宽 `release-gate.json` 的条件（如有，说明原因并请维护者决定）
