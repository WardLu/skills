# Test Scope Routing

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`test-scope-routing` 根据改动范围和风险选择最小但足够的验证范围，让本地反馈保持快速，
同时把集成、发布和生产检查留给真正需要它们的边界。

[English](README.md) · [简体中文](README.zh-CN.md)

## 适用场景

在规划或复核改动时，用它决定：

- 应运行哪些项目定义的命令；
- 代码、UI、数据、认证、构建或发布风险分别需要哪些检查；
- 哪些检查可以跳过，以及如何记录这个决定。

## 验证层级

| 层级 | 典型职责 |
| --- | --- |
| L0 | 静态、格式、策略和文档检查 |
| L1 | 快速、确定性的逻辑和状态检查 |
| L2 | 针对性的 UI 渲染和交互 |
| L3 | 集成、数据、认证、同步和外部边界检查 |
| L4 | 完整的合并、发布、安全或生产边界 |

## 使用

将 Skill 安装到受支持的 agent：

```bash
npx skills add WardLu/skills --skill test-scope-routing --global --agent <agent-name> --yes
```

例如：

```text
请为这次改动选择最小但足够的检查，并记录仍未验证的内容。
```

## 结果与边界

Skill 会返回选定层级、项目定义的命令、需记录的证据、跳过的检查和残余风险。它以项目
自己的测试与发布配置为准，不会臆造全局命令，也不会用生产写入代替验证。

<details>
<summary>维护者</summary>

准确命令和环境前置条件应维护在项目文档中。此 Skill 负责范围路由和证据记录，不替代
项目测试、CI、发布门禁或生产验收。

</details>

## 许可证

MIT，详见 [LICENSE](../LICENSE)。
