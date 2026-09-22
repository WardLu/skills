<div align="center">

# WardLu Skills

面向 agent 工作流的专注型、可版本管理、开源 Skill 集合。

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![集合版本 0.4.0](https://img.shields.io/badge/collection%20version-0.4.0-2563eb.svg)](VERSION)
[![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [变更记录](CHANGELOG.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

面向重复性 agent 工作的小而专注、可组合 Skill，提供清晰的安全边界和独立版本。

## Skill 列表

按你要完成的任务选择 Skill：

| Skill | 用途 | 版本 | 文档 |
| --- | --- | --- | --- |
| `agent-privacy-check` | 检查 agent 能接触什么、数据能发到哪里，并给出大白话隐私风险报告。 | `0.1.0` | [English](agent-privacy-check/README.md) · [简体中文](agent-privacy-check/README.zh-CN.md) |
| `codex-cross-provider-session-repair` | 修复供应商、导入或分叉导致的 Codex Desktop 旧会话问题。 | `0.7.7` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |
| `codex-doctor` | 分析本地 Codex 会话 telemetry，寻找有证据支持的工作流改进。 | `0.1.2` | [English](codex-doctor/README.md) · [简体中文](codex-doctor/README.zh-CN.md) |
| `github-repo-i18n` | 让选定的仓库文档在不同语言之间保持一致。 | `0.1.1` | [English](github-repo-i18n/README.md) · [简体中文](github-repo-i18n/README.zh-CN.md) |
| `public-release-gate` | 审核发布元数据、产物、许可证、部署状态和附件。 | `0.1.4` | [English](public-release-gate/README.md) · [简体中文](public-release-gate/README.zh-CN.md) |
| `public-repo-git-gate` | 在 commit、push 或 Pull Request 前检查公开内容和 Git 边界。 | `0.1.2` | [English](public-repo-git-gate/README.md) · [简体中文](public-repo-git-gate/README.zh-CN.md) |
| `shadow-skill-publisher` | 在手动发布前校验、打包和跟踪本地 Agent Skill。 | `0.6.4` | [English](shadow-skill-publisher/README.md) · [简体中文](shadow-skill-publisher/README.zh-CN.md) |
| `test-scope-routing` | 为一次改动选择最小但足够的验证范围。 | `0.1.2` | [English](test-scope-routing/README.md) · [简体中文](test-scope-routing/README.zh-CN.md) |

## 安装

为受支持的 agent 安装一个 Skill：

```bash
npx skills add WardLu/skills --skill <skill-name> --global --agent <agent-name> --yes
```

将 `<skill-name>` 和 `<agent-name>` 替换为任务与 agent 对应的值。安装整个集合时使用
`--skill '*'`。该命令需要 Node.js/npm。

使用同一个 CLI 管理已安装的 Skill：

```bash
npx skills list
npx skills update <skill-name>
npx skills remove <skill-name>
```

## 分发

这个公开 GitHub 集合也可以通过开放的
[skills.sh 目录和排行榜](https://skills.sh/) 发现。Hermes Agent 可以搜索 skills.sh
来源，或将本仓库添加为 GitHub tap，再通过 Skills Hub 检查并安装单个 Skill。安装任何
第三方 Skill 前，请先检查源码和所需权限。

## 安全

每个 Skill 都会说明自己的范围和兼容性。使用前先阅读对应 README，不要把凭据和真实
用户数据放入提示词或压缩包；遇到未验证或阻断结果时，应先复核而不是视为成功。

## 维护者

- 每个 Skill 独立维护自己的 `SKILL.md`、版本、README 语言镜像，以及需要的 reference
  或测试。
- Skill 发生变化时，同步用户可见声明、兼容性和根目录版本索引。
- 合并或发布前运行
  [`.github/workflows/validate-skills.yml`](.github/workflows/validate-skills.yml) 中的仓库校验。
- 贡献和发布背景请参考对应 Skill README 及集合的[变更记录](CHANGELOG.md)。

## 许可证

本集合及其中的 Skill 均采用 [MIT 许可证](LICENSE)。

## 联系

如果你对 B 端产品、AI 产品开发、供应链数字化或 Shadow 系列产品感兴趣，可以联系我：

- **X（Twitter）**：[@Gollumgulu](https://x.com/Gollumgulu)
- **微信公众号** — ![微信公众号二维码](https://cdn.jsdelivr.net/gh/WardLu/mypic/images%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7.jpg)
- **小红书 / 微博 / 抖音**：全网同名「Ward的AI产品实战」—— [小红书](https://xhslink.cn/m/4W1NWyRrxv5) · [微博](https://weibo.com/u/8344390431) · [抖音](https://v.douyin.com/1y06PMohfoE/)
- **Email**：[wardlu@126.com](mailto:wardlu@126.com)
