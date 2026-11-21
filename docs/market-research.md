# Hachi · 市场调研

调研日期：2026-11-21。范围：公开产品网站、GitHub README、发布与许可信息；未安装竞品做断线测试。下表区分项目自述、证据缺口和商业推断。报价为调研时的公开标价，不代表成交或付费需求。

## 结论

不是空白市场。**MySafeAI 和 Kordon 已高度覆盖原定一期**：按应用观察出口、异常暂停、恢复及部分浏览器保护。免费项目也覆盖了当前原型的预检与告警。不要以“菜单栏 + IP 告警 + 暂停 Claude/Codex”作为独立商业卖点，也不承诺降低封号率。

| 项目 | 已公开的重合能力 | 边界或未证实部分 |
|---|---|---|
| [MySafeAI](https://github.com/in-devp/MySafeAI/blob/main/README.en.md)（免费、MIT） | 双来源 IP 校验；应用和子进程暂停；Codex 启动前检查；扩展按站点暂停，普通网页可继续 | 文档明确不是系统包级防火墙；已排队的包、部分已有流和 WebRTC 不在保证范围。见[浏览器边界](https://github.com/in-devp/MySafeAI/blob/main/docs/browser-extension.md)。 |
| [Kordon](https://github.com/ef1m03/kordon/blob/main/README.en.md)（当前闭源） | Claude/Codex 预设，变化后暂停/恢复进程树，包括 MCP 子进程；浏览器扩展 | 文档承认检测到冻结有窗口，不是网络层拦截。[官网](https://efimovdev.ru/kordon/en/)调研时标价 149 卢布/月起，未核验销量。 |
| [AI 网络护航](https://github.com/IllegalCreed/ai-network-guard)（MIT）与 [claude-safe](https://github.com/tianxuanai/claude-safe)（MIT） | 菜单栏出口监测、DNS/STUN 和通知；后者做 Claude Code 启动门禁与漂移提醒 | 前者可选在特定条件下关闭应用，默认不开启；后者以预检和告警为主，不是持续包级拦截。 |
| [Egress Workbench](https://github.com/bbfp/egress-workbench-app/blob/main/README.zh-CN.md)（源码未公开） | Claude Code、Codex 和 Chromium 共用受管工作环境及出口；内部授权失败不回退到普通浏览器 | 自带工作环境，不等于保护用户现有的原生客户端。[许可与源码说明](https://github.com/bbfp/egress-workbench-app/blob/main/README.md)。 |
| [ProxyRouter](https://github.com/kogodm/proxyrouter-macos)（闭源） | 按应用及连接选路或拒绝；其资料称支持 UDP/QUIC。[官网](https://proxyrouter.app/)标示 $1.99/月、$19.99 买断 | 未在查阅的资料中找到针对 Claude/Codex 原生客户端、授权回调和 MCP 的完整故障验收；不等于产品无法做到。 |

## 值得验证的差异

对已安装的原生客户端，验证已批准出口失效时，**受管旧连接和新连接都不走未批准路径，而普通网页、终端和未受管应用照常联网**。浏览器 OAuth 与本地/远程 MCP 分别列出覆盖范围，不能用一次预检替代。

公开资料未证实有人完整做到上述承诺并公开了独立验收证据；这既不是能力独占，也不是付费需求成立。下次立项前，先以合成流量对照测试 MySafeAI 与现有按应用分流工具，使用独立观测点检测错误出口和误伤。不使用用户真实 Claude/Codex 账号。若现有组合能满足目标用户，停止重复开发；若存在可复现差距且有人愿为之付费，再投入运行时拦截。保持开发仓库私有，未达到项目发布门槛不发布客户端。
