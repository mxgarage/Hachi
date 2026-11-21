# Hachi #1：证据评审与派发

[GitHub 任务与回执](https://github.com/daniel-to-the-moon/Hachi/issues/1) · [竞品调研基线](market-research.md)

## 独立交稿，再互相质询

| 角色 | 交付物 | 必答反方问题 |
|---|---|---|
| GPT / Codex CLI：网络实验审核 | 从论文与标准推导一个可复现实验，明确对照、时间零点和独立观测 | 如何证明没有走错路，而不是没有发出流量？ |
| Claude Code：平台与竞品反方 | 区分官方政策、未公开风控和厂商自述；给出既有工具足以取代 Hachi 的条件 | 哪些功能确实有实测证据，哪些只是宣称？ |
| Muse Code：用户体验反方 | 用公开反馈评估断线、误拦与恢复；给出一个具体、少打扰的体验突破 | 用户是否愿为它改变现有操作？如何验证？ |

首轮各自交稿，不提供其他评审的意见；第二轮交换三份报告，各自指出一个致命假设、给出一个可证伪的反例。三方到齐后由 Hermes 汇总共识、分歧和实验验收。回执分为：未接通 / 已调用 / 已回稿 / 来源核验。CLI 退出码不替代内容验收。只手动启动，不由评论自动触发，不自动改代码、合并、发布或使用真实 Claude/Codex 账号做故障实验。未到齐不宣称达成三方共识。

## 共同证据包

- [P1] NDSS 2022, *VPNalyzer: Systematic Investigation of the VPN Ecosystem*：把隧道故障、DNS、IPv6 和已有流量分开测，不能只看「已连接」状态。https://www.ndss-symposium.org/wp-content/uploads/2022-285-paper.pdf
- [P2] PoPETs 2015, *A Glance through the VPN Looking Glass: IPv6 Leakage and DNS Hijacking in Commercial VPN Clients*：IPv6 与 DNS 要独立观测；旧论文不代表当前 macOS 或某一竞品的实测。https://www.petsymposium.org/popets/2015/popets-2015-0006.php
- [N1] RFC 9000 §9：QUIC 连接迁移；不得从 TCP 测试推定 QUIC。https://www.rfc-editor.org/rfc/rfc9000.html#section-9
- [N2] RFC 8305：双栈连接选择。https://www.rfc-editor.org/rfc/rfc8305.html
- [O1] OpenAI：异常地点或设备等可能触发安全提醒；未公开固定 IP 的豁免或封禁阈值。https://help.openai.com/en/articles/10471992-why-am-i-receiving-a-suspicious-activity-alert
- [O2] OpenAI：支持地区与访问资格。https://help.openai.com/en/articles/7947663-chatgpt-supported-countries
- [A1] Anthropic：政策涉及真实所在地，网络出口不能替代服务资格。https://www.anthropic.com/legal/supported-regions
- [A2] Anthropic：公开的限制原因与申诉渠道。https://support.claude.com/en/articles/8241253-safeguards-warnings-and-appeals
- [C1] MySafeAI：进程暂停与浏览器过滤不是操作系统级包拦截。https://github.com/in-devp/MySafeAI/blob/main/README.en.md
- [C2] Kordon：文档承认网络变化和冻结之间有窗口。https://github.com/ef1m03/kordon/blob/main/README.en.md
- [C3] ProxyRouter：按应用分流，不能把文档当成已有连接故障实测。https://github.com/kogodm/proxyrouter-macos
- [C4] Egress Workbench：受管工作区及共享浏览器；不同于保护已安装原生应用。https://github.com/bbfp/egress-workbench-app/blob/main/README.zh-CN.md
- [U1] 用户报告：强制代理环境下的 Codex MCP OAuth 发现。https://github.com/openai/codex/issues/22667
- [U2] 用户报告：Codex 桌面端本地回调后令牌交换失败。https://github.com/openai/codex/issues/38482
- [U3] 用户报告：Tableau MCP OAuth 回调兼容性。https://github.com/openai/codex/issues/31658

不能把来源打不开当作否定证据。竞品公开描述不是独立体验，Issue 个例不是发生率、封号因果或付费证据。下一轮的候选突破只保留一个：去掉批准出口时，受管旧连接和新连接不误出，其他应用不中断，恢复过程可解释。先做无账号隔离对照，未通过不扩展。
