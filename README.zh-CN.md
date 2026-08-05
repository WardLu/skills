<div align="center">

# WardLu Skills

面向 AI agent 工作流的专注型、可版本管理、开源 Skill 集合。

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

> 小而专注、可组合的 Skill，让重复工作更可靠，同时保留清晰的安全边界、离线测试和可发布版本。

## 这是一个什么仓库

这是一个面向 AI agent 和开发者工作流的自包含 Skill 集合。每个 Skill 都位于独立的 kebab-case 目录中，并包含自己的指令、脚本、测试、文档、许可证和版本元数据。不同 Skill 可以只支持某一个 agent，也可以跨多个 agent 使用；具体兼容性请以各 Skill 的 README 和 `SKILL.md` 为准。

当前集合中的第一个 Skill 专门用于 Codex：它可以修复切换模型供应商、导入或分叉旧会话后无法继续的 Codex Desktop 对话。

| Skill | 用途 | 版本 | 文档 |
| --- | --- | --- | --- |
| [`codex-cross-provider-session-repair`](codex-cross-provider-session-repair/) | 在不删除 Codex 目录的前提下，诊断并修复供应商不一致，以及远程上下文压缩出现 `404 Item with id 'rs_...' not found` 的问题。 | `0.4.0` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |

## 安装

### 推荐使用 `npx skills`

为受支持的 agent 全局安装 Skill。下面以当前这个 Codex 专用 Skill 为例：

~~~bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair --global --agent codex --yes
~~~

安装命令适用于 Windows、macOS 和 Linux，但需要先安装 Node.js/npm。`skills` CLI 会安装选定的 `SKILL.md`，并可继续使用同一工具管理：

~~~bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
~~~

省略 `--skill` 可以安装整个集合；安装其他 Skill 时替换 Skill 名称；安装到其他受支持的 agent 时替换 `--agent codex`。仓库合并到 `main` 后，`WardLu/skills` 命令才能解析新 Skill。

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
│   ├── SECURITY.md
│   └── LICENSE
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
