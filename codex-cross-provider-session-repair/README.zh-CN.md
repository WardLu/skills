# Codex 跨供应商旧会话修复

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.7.5](https://img.shields.io/badge/version-0.7.5-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`codex-cross-provider-session-repair` 是一个以备份优先为原则的 Codex Skill，用于修复切换模型供应商、导入或分叉旧会话后无法继续的问题。

[English](README.md) · [简体中文](README.zh-CN.md) · [快速安装](#推荐使用-npx-skills) · [使用方法](#使用方法) · [开发测试](#开发测试) · [版本与升级](#版本与升级) · [安全说明](SECURITY.md) · [变更记录](CHANGELOG.md)

它处理三类在界面上很相似的故障：

1. 已保存的会话或根目录 `state_5.sqlite` 中的线程仍指向不可用的供应商；
2. 远程上下文压缩返回 `404 Item with id 'rs_...' not found`，原因是本地推理记录以 `store=false` 发送后并未被服务持久化；
3. 导入的会话固定使用当前 ChatGPT 账号不支持的模型，例如 `ark-code-latest`。

修复范围严格限定在指定会话，不会全局替换供应商，也不会删除整个 Codex 目录。

## 安装

### 推荐使用 `npx skills`

仓库合并到 `main` 后，可只为 Codex 全局安装此 Skill：

~~~bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair --global --agent codex --yes
~~~

同一条命令适用于 Windows、macOS 和 Linux，但需要先安装 Node.js/npm（提供 `npx`）。省略 `--skill` 可安装整个 Skill 集合；将 `--agent codex` 替换为其他受支持的 agent 名称，可安装到其他客户端。

常用的生命周期命令：

~~~bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
~~~

也可以直接从 Skill 子目录安装：

~~~bash
npx skills add https://github.com/WardLu/skills/tree/main/codex-cross-provider-session-repair --global --agent codex --yes
~~~

`skills` CLI 会为选定的 agent 安装 `SKILL.md` 及其资源；随 Skill 一起提供的 Python 修复脚本仍位于安装后的 Skill 目录中。

### 手动安装

克隆集合仓库并在此目录运行安装器：

~~~powershell
git clone https://github.com/WardLu/skills.git
Set-Location .\skills\codex-cross-provider-session-repair
.\scripts\install.ps1
~~~

默认安装到 `%USERPROFILE%\.agents\skills`。如果你的 Codex 使用 `%USERPROFILE%\.codex\skills`，请显式传入目标目录：

~~~powershell
.\scripts\install.ps1 -Destination "$env:USERPROFILE\.codex\skills"
~~~

macOS/Linux：

~~~bash
git clone https://github.com/WardLu/skills.git
cd skills/codex-cross-provider-session-repair
./scripts/install.sh
~~~

平台支持矩阵：

| 平台 | Codex 目录查找顺序 | 安装器 |
| --- | --- | --- |
| Windows | `CODEX_HOME`，然后 `%USERPROFILE%\\.codex` | `scripts/install.ps1` |
| macOS | `CODEX_HOME`，然后 `~/.codex` | `scripts/install.sh` |
| Linux | `CODEX_HOME`，然后 `~/.codex` | `scripts/install.sh` |

修复逻辑只使用 Python 3.9+ 标准库（`json`、`sqlite3`、`pathlib`、`shutil`），不需要安装平台专属 Python 依赖。安装或升级后请重启客户端，使新的 Skill 元数据生效。

## 使用方法

把受影响的会话 UUID 和界面中的错误交给 Codex。Skill 应先执行只读诊断，并在写入前要求你完全退出 Codex Desktop。

只读诊断：

~~~powershell
python .\scripts\repair.py `
  --session-id 019fb8f5-5fcc-74c0-8341-61f83f2126ce `
  --codex-home "$env:USERPROFILE\.codex"
~~~

当远程压缩反复返回 404，且报告确认错误 ID 对应本地推理记录时，请先完全退出 Codex Desktop：

~~~powershell
python .\scripts\repair.py `
  --session-id 019fb8f5-5fcc-74c0-8341-61f83f2126ce `
  --codex-home "$env:USERPROFILE\.codex" `
  --remove-reasoning all --apply
~~~

执行完成后，再运行同一条命令但去掉 `--apply`。真正决定是否成功的是：
`Stale IDs present as local reasoning: []` 和
`Local reasoning records: 0`。报告里的历史日志 ID 可能仍然存在，它们会被明确标记为历史记录。

推荐给普通用户的流程是：用户同意修复后，立即启动下面这条命令。macOS 会自动打开一个可见的「终端」窗口，显示最终结果；用户按回车后，启动器会按会话 ID 关闭本次修复的窗口：

~~~bash
python3 scripts/start_repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --remove-reasoning stale
~~~

启动后，当前会话应立即提醒用户：“修复任务已启动，最多等待 300 秒；请完全退出 Codex。”用户可以直接退出 Codex，不需要再回复“已退出”。如果 Codex 已经退出，这条命令也能继续执行安全检查。macOS 会打开一个可读的 120 列、36 行 Terminal 标签页/窗口，并通过短 runner 隐藏很长的命令参数；屏幕只显示分段状态。终端会先显示等待上限，并在约 60、180、240 秒再次提醒；状态使用双语：`Waiting / 等待中`、`Applying / 修复中`、`Verified / 已验证`、`Failed / 失败`。只有看到 `Verified / 已验证` 才能重新打开 Codex。最终按回车后，启动器会关闭带有该会话 ID 且只包含修复标签页的目标窗口；如果 macOS 尚未授予 Terminal 自动化权限，脚本会退出，但用户需要手动按 `Command+W` 关闭已完成的窗口。超时会明确说明未修改文件，并要求保持 Codex 关闭。

高级用户也可以在 Codex Desktop 仍打开时，从独立的「终端」启动底层等待器：

~~~bash
python3 scripts/wait_and_repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --remove-reasoning all \
  --status-file "/tmp/codex-session-repair-<UUID>.json"
~~~

然后完全退出 Codex Desktop。该工具会显示配置的最长等待时间，并在等待期间周期提醒；如果 Codex 重新出现，等待超过上限，或等待期间会话文件发生变化，就会停止写入并显示 `Failed / 失败`。只有修复和二次诊断都通过后才会显示 `Verified / 已验证`。

如果是供应商不一致，请传入当前供应商，并显式启用仅目标会话的更新：

~~~powershell
python .\scripts\repair.py `
  --session-id <UUID> `
  --codex-home "$env:USERPROFILE\.codex" `
  --provider custom --fix-provider --apply
~~~

不带 `--apply` 时始终是预览模式。每次应用修复都会创建带时间戳的 JSONL 备份；只有目标 `threads.model_provider` 行发生变化时才会备份数据库，并同时复制 WAL/SHM 伴随文件。不要只依据后台进程退出或返回码判断成功，必须看到备份和 `verified` 状态。

如果是会话保存的模型不受当前账号支持，请把目标会话的结构化模型设置和根目录线程快照对齐到当前模型。显式使用 `none`，确保不会删除本地推理记录：

~~~bash
python3 scripts/repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --model <current-model> --fix-model \
  --remove-reasoning none --apply
~~~

该命令不会修改全局 `config.toml`，也不会影响其他会话。验证时应确认目标 `threads.model`、JSONL 中的结构化模型设置都已变为指定模型，并且生成了新的 JSONL/数据库备份。

手动执行并验证完成后，再重新启动 Codex Desktop；使用等待器时，状态变为
`verified` 后即可重开。刷新页面不会清除桌面进程缓存的会话事件流。先发送一条简短的确认提示，确认成功后再继续原项目任务。

无需额外依赖即可生成可分发的 `.skill` 压缩包：

~~~bash
python scripts/package.py --output ./dist
~~~

## 开发测试

修复工具没有第三方运行时依赖：

~~~bash
python -m unittest discover -s tests -v
python scripts/repair.py --help
python scripts/wait_and_repair.py --help
python scripts/start_repair.py --help
~~~

`evals/evals.json` 包含真实的触发条件和行为提示词。标准 Skill 打包器不会把 `evals` 目录放入可分发的 `.skill` 包。

## 版本与升级

本 Skill 遵循语义化版本。规范版本位于 `VERSION`，并同步写入 `SKILL.md` 的 metadata。

~~~bash
git pull --ff-only origin main
git fetch --tags
~~~

拉取更新后，请重新安装当前检出的版本。发布时应使用 `vMAJOR.MINOR.PATCH` 标签，同时更新 `CHANGELOG.md` 并创建 GitHub Release。改变默认修复范围或 `--remove-reasoning all` 含义，属于不兼容变更。

## 安全说明与限制

本 Skill 只修复本地 Codex 会话状态。它无法恢复远程服务从未持久化的记录、刷新过期登录令牌、修复供应商宕机，或在没有可用备份时修复损坏的 SQLite 数据库。它会保留用户可见历史，不会尝试重新生成缺失的模型推理轨迹。

请勿把真实 Codex 目录、会话日志、令牌或 API 密钥提交到仓库。详见 [SECURITY.md](SECURITY.md)。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
