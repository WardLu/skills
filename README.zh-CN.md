<div align="center">

# WardLu Skills

面向 AI agent 工作流的专注型、可版本管理、开源 Skill 集合。

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

> 小而专注、可组合的 Skill，让重复工作更可靠，同时保留清晰的安全边界、离线测试和可发布版本。

## 这是一个什么仓库

这是一个面向 AI agent 和开发者工作流的自包含 Skill 集合。每个 Skill 都位于独立的 kebab-case 目录中，并包含自己的 `SKILL.md`；脚本、测试、references、文档、许可证和版本元数据按需要加入。不同 Skill 可以只支持某一个 agent，也可以跨多个 agent 使用；具体兼容性请以各 Skill 的 `SKILL.md` 和直接引用的资源为准。

当前集合包含 Codex 工作流 Skill、GitHub 仓库国际化 Skill、公开仓库/Release 闸门，以及一个跨框架的测试范围路由 Skill。

| Skill | 用途 | 版本 | 文档 |
| --- | --- | --- | --- |
| [`codex-cross-provider-session-repair`](codex-cross-provider-session-repair/) | 在不删除 Codex 目录的前提下，诊断并修复供应商不一致，以及远程上下文压缩出现 `404 Item with id 'rs_...' not found` 的问题。 | `0.7.5` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |
| [`codex-doctor`](codex-doctor/) | 分析本地 Codex 会话 telemetry，并生成隐私安全的效率改进建议。 | `0.1.1` | [SKILL.md](codex-doctor/SKILL.md) |
| [`github-repo-i18n`](github-repo-i18n/) | 在英文默认入口和用户指定语言之间同步 GitHub 仓库文档、描述与 Topics，并提供 parity 检查和 Markdown 预览。 | `0.1.0` | [SKILL.md](github-repo-i18n/SKILL.md) |
| [`public-release-gate`](public-release-gate/) | 审核公开仓库的 Release、最终产物、第三方许可证、部署响应头和 GitHub Release 附件。 | `0.1.1` | [SKILL.md](public-release-gate/SKILL.md) |
| [`public-repo-git-gate`](public-repo-git-gate/) | 覆盖 commit、push 和 Pull Request 的公开内容、分支、远程仓库和 PR 状态检查。 | `0.1.1` | [SKILL.md](public-repo-git-gate/SKILL.md) |
| [`test-scope-routing`](test-scope-routing/) | 根据改动风险和受影响边界选择验证范围，避免默认运行全量测试。 | `0.1.1` | [SKILL.md](test-scope-routing/SKILL.md) |

## 安装

### 推荐使用 `npx skills`

每个 Skill 目录只要包含有效的 `SKILL.md` 就可以安装；Skill 根目录的
`README.md` 是可选的人类说明文档，不是 CLI 的安装要求。为受支持的 agent
全局安装指定 Skill（下面以 `codex-doctor` 为例）：

~~~bash
npx skills add WardLu/skills --skill codex-doctor --global --agent codex --yes
~~~

将 `codex-doctor` 替换为下面任意一个 Skill 名称：

~~~text
codex-cross-provider-session-repair
codex-doctor
github-repo-i18n
public-release-gate
public-repo-git-gate
test-scope-routing
~~~

为 Codex 安装整个集合：

~~~bash
npx skills add WardLu/skills --skill '*' --global --agent codex --yes
~~~

安装命令适用于 Windows、macOS 和 Linux，但需要先安装 Node.js/npm。`skills` CLI 会安装选定的 `SKILL.md`，并可继续使用同一工具管理：

~~~bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
~~~

安装到其他受支持的 agent 时替换 `--agent codex`。仓库合并到 `main` 后，`WardLu/skills` 命令才能解析新 Skill。

### 当前 Codex Skill 的手动安装

Windows PowerShell：

~~~powershell
git clone https://github.com/WardLu/skills.git
Set-Location .\skills\codex-cross-provider-session-repair
.\scripts\install.ps1 -Destination "$env:USERPROFILE\.codex\skills"
~~~

macOS/Linux：

~~~bash
git clone https://github.com/WardLu/skills.git
cd skills/codex-cross-provider-session-repair
./scripts/install.sh "$HOME/.codex/skills"
~~~

安装或升级后，请重启目标 agent，使新的 Skill 元数据生效。

## 当前 Skill：平台支持

当前的会话修复 Skill 面向 Codex Desktop，支持：

| 平台 | Codex 目录回退位置 | 安装器 | 运行时 |
| --- | --- | --- | --- |
| Windows | `%USERPROFILE%\.codex` | `scripts/install.ps1` | Python 3.9+ 标准库 |
| macOS | `~/.codex` | `scripts/install.sh` | Python 3.9+ 标准库 |
| Linux | `~/.codex` | `scripts/install.sh` | Python 3.9+ 标准库 |

如果 Codex 使用非默认目录，请设置 `CODEX_HOME`。修复脚本不需要第三方 Python 依赖。后续 Skill 可以声明不同的兼容性矩阵。

## 安全优先的工作流程

对于当前的会话修复 Skill：

1. 完全退出 Codex Desktop，包括托盘进程。
2. 使用准确的会话 UUID 执行预览诊断。
3. 检查供应商和过期推理记录的诊断结果。
4. 只应用范围最小的目标修复；写入前会创建备份。
5. 重新启动 Codex，发送简短的烟雾测试提示后，再继续原任务。

该 Skill 会保留用户可见消息和工具历史。它不会删除整个 Codex 目录、刷新过期凭据，也无法恢复远程服务从未持久化的记录。

## 仓库结构

~~~text
.
├── .github/workflows/validate-skills.yml
├── codex-cross-provider-session-repair/
│   ├── SKILL.md
│   ├── README.md
│   ├── README.zh-CN.md
│   ├── scripts/
│   ├── tests/
│   ├── evals/
│   ├── VERSION
│   ├── CHANGELOG.md
│   ├── CONTRIBUTING.md
│   ├── SECURITY.md
│   └── LICENSE
├── codex-doctor/
│   ├── SKILL.md
│   ├── agents/
│   └── VERSION
├── github-repo-i18n/
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── VERSION
├── public-release-gate/
│   ├── SKILL.md
│   ├── agents/
│   └── VERSION
├── public-repo-git-gate/
│   ├── SKILL.md
│   ├── agents/
│   ├── assets/
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── VERSION
├── test-scope-routing/
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   └── VERSION
├── LICENSE
├── README.md
└── README.zh-CN.md
~~~

## 开发与发布

进入某个 Skill 目录后运行：

~~~bash
python -m unittest discover -s tests -v
python scripts/repair.py --help
python scripts/package.py --output ./dist
~~~

所有 Skill 遵循[语义化版本](https://semver.org/)。规范版本存放在 `VERSION`，并同步写入 `SKILL.md`。面向用户的变更应更新 `CHANGELOG.md`；发布标签使用 `vMAJOR.MINOR.PATCH`。

贡献规则请参阅 [`codex-cross-provider-session-repair/CONTRIBUTING.md`](codex-cross-provider-session-repair/CONTRIBUTING.md)。

## 安全与许可证

不要提交真实用户数据、会话日志、备份、令牌或 API 密钥。对于当前 Codex 专用 Skill，请在提交诊断数据前阅读 [`SECURITY.md`](codex-cross-provider-session-repair/SECURITY.md)。

本集合及其中的 Skill 均采用 [MIT 许可证](LICENSE)。


## 联系我

如果你对 B 端产品、AI 产品开发、供应链数字化或 Shadow 系列产品感兴趣，可以联系我：

- **X（Twitter）**：[@Gollumgulu](https://x.com/Gollumgulu)
- **微信公众号** — ![微信公众号二维码](https://cdn.jsdelivr.net/gh/WardLu/mypic/images%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7.jpg)
- **小红书 / 微博 / 抖音**：全网同名「Ward的AI产品实战」—— [小红书](https://xhslink.cn/m/4W1NWyRrxv5) · [微博](https://weibo.com/u/8344390431) · [抖音](https://v.douyin.com/1y06PMohfoE/)
- **Email**：[wardlu@126.com](mailto:wardlu@126.com)

> 可接 1v1 咨询和项目陪跑：产品诊断 · AI 实施 · 工作流 / Skill · 系统定制
