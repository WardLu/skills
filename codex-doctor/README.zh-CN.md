# Codex Doctor

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`codex-doctor` 分析本地 Codex 会话 telemetry，把反复出现的模式转化为少量有证据
支持的工作流改进。默认使用仅 telemetry 模式，不会调用模型。

[English](README.md) · [简体中文](README.zh-CN.md)

## 适用场景

- 上下文膨胀或会话异常过长；
- 探索或验证没有收敛；
- 没有改变假设却反复失败和重试；
- 按选定时间范围观察趋势，而不是只看单个会话。

## 使用

将 Skill 安装到受支持的 agent：

```bash
npx skills add https://github.com/wardlu/skills --skill codex-doctor
```

工作区中必须已有 Codex Doctor 分析器，或由你提供其路径。安装后，让 agent 分析指定
时间范围，并说明使用仅 telemetry 还是 AI 辅助解读。

例如：

```text
请以仅 telemetry 模式分析我最近的 Codex 会话，并给出不超过三条工作流改进建议。
```

## 结果与隐私

报告会区分测量到的 telemetry、解读和建议；JSON 用于事实读取，HTML 用于人类阅读。
只有在明确请求时才会运行 AI 解读，并可能消耗模型用量。

Skill 不会扫描整个主目录、无理由安装依赖，也不会把原始指标和私有路径写入全局规则。
不要把真实会话数据或凭据放入公开 Issue 或压缩包。

<details>
<summary>维护者</summary>

保持仅 telemetry 为默认模式，示例只使用合成数据；报告契约或隐私边界变化时，请复核
`SKILL.md`。

</details>

## 许可证

MIT，详见 [LICENSE](../LICENSE)。
