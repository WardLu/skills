# Shadow Skill Publisher

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.6.4](https://img.shields.io/badge/version-0.6.4-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`shadow-skill-publisher` 用于在发布 Agent Skill 前完成检查，并为选定渠道分别准备
发布包、上架信息、可恢复交接和状态记录。它不会绕过登录、协议或最终提交确认。

[English](README.md) · [简体中文](README.zh-CN.md)

## 能做什么

- 检查 Skill 的结构、版本、许可证、隐私和压缩包内容；
- 自动提取安全的本地事实，首次检查不要求用户手写 profile；
- 生成各渠道独立的 ZIP 和上架所需字段；
- 分开记录上传、提交和发布状态，便于后续跟踪。
- 用 `batch` 一次准备多个 Skill/渠道，并生成绑定摘要的批次确认范围；
- 用 `resume` 恢复准确下一步，用 `monitor` 只在真实状态变化时入账；
- 自动刷新 `state/publishing-ledger.md`，无需靠聊天截图补记；
- 发布前校验渠道文案长度、头像/封面摘要和渠道裁剪策略。

当前可为扣子技能商店、WorkBuddy、SkillPay 和小红书 Red Skill 准备发布包。知乎 AI Works 在其
创作者表单可观察并完成验证前暂不可用。

平台登录、CAPTCHA/二维码和最终提交仍由用户掌控。本地工作流不需要浏览器；只有在
渠道没有可验证的 API/CLI、且用户明确授权时，才需要浏览器交接。

如果准备阶段需要浏览器观察，agent 可以使用当前已登录浏览器读取可见的账号和表单信息，
填写准确计划并上传准确 ZIP，然后停在最终提交前等待用户确认。

## 安装

使用 `skills` CLI 将 Skill 安装到受支持的 agent：

```bash
npx skills add WardLu/skills --skill shadow-skill-publisher --global --agent <agent-name> --yes
```

将 `<agent-name>` 替换为你使用的 agent。安装后，直接让该 agent 检查并准备要发布
的 Skill 即可。

## 示例

例如：

```text
请检查并准备 /path/to/my-skill，目标渠道为 WorkBuddy 和 SkillPay。
```

Skill 会返回校验结果、各渠道发布包、上架字段，以及下一步确认或交接动作。如果渠道
需要无法安全推断的身份、文案或实时表单信息，agent 只会询问这些缺项，并在补齐前保持
该渠道阻断。

## 安全

- 不要把密码、Cookie、Token、二维码内容、私有路径或真实用户数据放入 Skill 源码、
  压缩包或聊天中。
- 每个发布包都绑定准确的源、版本、渠道和账号；无法验证的变更会暂停流程并等待复核。
- 上传与提交需要分开的明确确认；单独发送“同意”等聊天回复不能绕过这些确认。

<details>
<summary>维护者</summary>

运行离线测试并查看命令入口：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/publisher.py --help
```

渠道差异应维护在 `references/` 中；不要把凭据、私有路径或真实用户数据加入测试
fixture 或示例。

</details>
