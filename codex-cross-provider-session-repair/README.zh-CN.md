# Codex 跨供应商旧会话修复

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.7.6](https://img.shields.io/badge/version-0.7.6-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`codex-cross-provider-session-repair` 是一个以备份优先为原则的 Skill，用于修复切换
供应商、导入或分叉后无法继续的 Codex Desktop 旧会话。修复严格限定在指定会话，
不会全局替换供应商，也不会删除 Codex 目录。

[English](README.md) · [简体中文](README.zh-CN.md)

## 适用场景

当已有会话无法继续，且原因可能是以下情况时使用：

- 已保存的会话仍指向不可用的供应商；
- 远程压缩返回 `404 Item with id 'rs_...' not found`；
- 导入的会话使用了当前账号不支持的模型。

## 安装

使用 `skills` CLI 将它安装到 Codex：

```bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair
```

该命令需要 Node.js/npm。安装后，把受影响的会话 UUID 和界面中的错误交给 Codex，
让它先完成诊断。

## 安全修复

Skill 会先执行只读诊断，并在写入前要求你完全退出 Codex Desktop。应用修复前会创建
备份，只有二次诊断成功后才会报告已验证状态。

只读诊断可以使用下面的命令，并将占位符替换为实际会话 ID：

```bash
python3 scripts/repair.py \
  --session-id <SESSION_UUID> \
  --codex-home "$HOME/.codex"
```

供应商/模型专项修复和等待 Codex 退出的流程，请让 agent 按 Skill 工作流处理。不要
对其他会话执行修复，也不要在 Codex 运行时写入文件。

## 限制与隐私

本 Skill 无法恢复远程服务从未持久化的数据、刷新过期凭据、修复供应商故障，或在没有
可用备份时修复损坏的数据库。它会保留可见历史，不会重新生成缺失的模型推理记录。

不要把会话日志、令牌、备份或真实用户数据放入 Issue 或公开压缩包。详见
[SECURITY.md](SECURITY.md)。

<details>
<summary>维护者</summary>

运行离线测试并生成可分发压缩包：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package.py --output ./dist
```

版本维护在 `VERSION`，面向用户的变更记录在 `CHANGELOG.md`。修改修复范围或安全契约前，
请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

</details>

## 许可证

MIT，详见 [LICENSE](LICENSE)。
