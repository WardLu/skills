# GitHub Repository i18n

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.1](https://img.shields.io/badge/version-0.1.1-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`github-repo-i18n` 用于让 GitHub 仓库的用户可见语言层在英文默认入口和用户明确指定的
语言之间保持一致。它可以翻译或审计选定文档，不会静默修改无关仓库内容。

[English](README.md) · [简体中文](README.zh-CN.md)

## 覆盖范围

- README 和其他明确选定的文档；
- 请求范围包含时的发布说明和变更记录；
- 可单独选择的仓库描述和 Topics 元数据；
- 语言链接、代码块、图片、版本和本地引用。

## 使用

将 Skill 安装到受支持的 agent：

```bash
npx skills add https://github.com/wardlu/skills --skill github-repo-i18n
```

告诉 agent 准确的文件或元数据范围，以及要处理的语言。例如：

```text
请审计 README.md 和 README.zh-CN.md 的一致性，并展示本地及 GitHub 风格预览。
```

## 结果与边界

Skill 会返回范围矩阵、语言镜像、一致性发现和分开的预览证据。除非选择了其他有记录的
策略，否则 README.md 保持英文默认入口；代码、链接、图片、版本和事实限制会被保留。

它不会翻译产品 UI、编造项目声明、远程扫描 GitHub，也不会在没有明确授权时 commit、
push、发布、部署或更新仓库元数据。

<details>
<summary>维护者</summary>

项目事实应以选定的源文档为准；发布前运行仓库离线检查，修改语言或预览行为时复核相关
reference。

</details>

## 许可证

MIT，详见 [LICENSE](../LICENSE)。
