# Agent Privacy Check

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.0](https://img.shields.io/badge/version-0.1.0-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

Agent Privacy Check 用大白话告诉普通用户，一个 AI agent 的隐私边界在哪里。它检查
agent 能接触什么、数据可能发到哪里、不可信内容能否影响敏感操作、最坏会发生什么，以及
应该先改哪几处。

它适配 Codex、Claude Code 和其他通用 agent 运行时。报告会分开说明已配置的能力、这次
实际观察到的行为，以及仍然不知道的边界。

[English](README.md) · [简体中文](README.zh-CN.md)

## 它会回答什么

- agent 能接触哪些文件、对话、凭据、浏览器状态、工具和服务。
- 哪些模型供应商、API、Webhook、浏览器、连接器、日志或其他 agent 可能收到数据。
- 是否同时存在三项危险条件：Secret Source、External Sink、Untrusted Content。
- 恶意内容或误导性指令在最坏情况下可能造成什么后果。
- 哪些收缩权限、隔离、人工确认和监控措施应该先做。

## 三项危险组合

| 问题 | 大白话解释 |
| --- | --- |
| Secret Source | agent 能不能读到私密或有价值的东西，例如 API key、SSH key、浏览器会话、客户记录或机密文档？ |
| External Sink | agent 能不能通过模型请求、HTTP、上传、邮件、聊天、Git push、连接器或遥测服务把数据送出可信边界？ |
| Untrusted Content | 网页、邮件、Issue、Pull Request、下载文件、Skill、记忆或工具结果能不能影响它接下来做什么？ |

组合结果会写成 Confirmed、Likely、Not demonstrated 或 Unknown。能走通一条外泄路径，
与已经发生过外泄，会在报告中分开说明。接收预期上下文的指定供应商属于需要记录的数据流，
但不会自动被当成攻击者可控的外发通道。

## 风险等级

| 等级 | 大白话解释 |
| --- | --- |
| Low | 在检查范围内，访问范围小且受控，没有重要的数据源、外发通道或审计盲区。 |
| Medium | 存在真实缺口或不确定性，但当前路径受限，或者还没有形成高影响路径。 |
| High | agent 有广泛访问、shell 或写入权限，能对外写入，缺少隔离或确认，或 Likely 的危险组合形成了现实的严重伤害路径。 |
| Critical | 已经有泄露或入侵证据，或者 Confirmed 的三项组合可以在攻击者影响的指令下把敏感数据送到外部。 |

这些等级是本 Skill 自己的操作性判断，不是 OWASP 评分、法律结论或安全认证。

## 使用方法

建议先安装到当前项目：

~~~bash
cd /path/to/project
npx skills add WardLu/skills --skill agent-privacy-check --agent <agent-name> --copy
~~~

只有在明确希望所有项目都启用这个 Skill 时才使用 --global，因为它会扩大 Skill
可能影响的运行范围。--yes 会跳过安装提示，先审阅来源后再选择是否使用。

带上明确范围，请 agent 只读检查。例如：

~~~text
请使用 Agent Privacy Check，只读审查当前项目的 agent 设置。告诉我它能看到什么、数据能发到哪里、Secret Source + External Sink + Untrusted Content 是否连通、最坏后果是什么，以及前三项整改建议。每条结论标注 observed、available、not found 或 unknown。
~~~

如果能补充平台名称、项目或 Skill、指定配置目录，以及明确纳入检查的边界，结果会更准确。

## 报告与边界

报告包含检查范围、访问清单、外发清单、不可信内容清单、危险组合结果、风险等级和置信度、
最坏后果、按顺序排列的整改建议、证据与未知项。

默认只读。它不会打印秘密值，不会用真实数据测试外泄，不会在没有单独授权时安装或删除
Skill、修改权限、轮换凭据、上传文件、commit、push、发布或部署。配置中存在某项能力，
不等于本次运行真的使用过它。

## 参考资料

工作流参考了
[OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
和
[OWASP Agentic Skills Top 10](https://owasp.org/www-project-agentic-skills-top-10/)。
适配边界见 [references/sources.md](references/sources.md)。

<details>
<summary>维护者</summary>

运行离线契约测试：

~~~bash
python3 -m unittest discover -s tests -v
~~~

合成评估案例在 [evals/cases.json](evals/cases.json)。它们用于检查 agent 是否输出完整且
带证据标签的报告，不包含真实凭据或用户数据。

</details>

## 许可证

MIT。见 [LICENSE](../LICENSE)。
