# WardLu Skills Release Notes

本文档汇总 WardLu Skills（面向 AI Agent 工作流的专注型开源 Skill 集合工程）历史版本发布说明。

[English](RELEASE_NOTES.md) · [简体中文](RELEASE_NOTES.zh-CN.md)

---

## v0.4.1 - 2026-09-22

> **类型**: 集合级补丁发布（单技能修复与升级）
>
> **GitHub Release**: [v0.4.1](https://github.com/WardLu/skills/releases/tag/v0.4.1)

### 技能升级

- **codex-cross-provider-session-repair v0.7.7**：修复「远程压缩契约失败导致会话无法继续」的问题。
  诊断改为同时读取 rollout 的 `task_complete` 记录（`logs_2.sqlite` 常只剩概括行），
  读取 `remote_compaction_v2` 的特性阶段，并在该开关已是墓碑项时拒绝写入无效配置；
  新增离线修复执行器与环回压缩 shim，可在不修改 `config.toml` 的前提下修复单个超限会话。

### 修复

- 修正 `scripts/package.py`：按文档使用 `--output ./dist` 构建时，归档不再把上一版
  `.skill` 文件嵌套进新归档。

### 发布元数据

- 单技能临时 Tag `codex-cross-provider-session-repair-v0.7.7` 已退役，映射到本集合发布。

---

## v0.4.0 - 2026-09-16

> **类型**: 新增 Skill 与多项技能升级
>
> **GitHub Release**: [v0.4.0](https://github.com/WardLu/skills/releases/tag/v0.4.0)

### 核心新增 Skill
- **`agent-privacy-check` (v0.1.0)**：以只读、平实语言审查 agent 可访问的数据、数据出境路径与不可信内容，并给出覆盖 Codex、Claude Code 与通用 agent 运行时的复合隐私风险结论。

### 技能升级
- **`shadow-skill-publisher` → v0.6.3**：摘要绑定的批量工作流、可续接的交接、只读监控、Coze Skill Store 支持、可复用上架素材，以及修正后的单根目录 WorkBuddy 归档。
- **`public-release-gate` → v0.1.4**：修正 WorkBuddy 打包。v0.1.3 因一次撤回的市场审核而被消耗，未发布。
- **`codex-cross-provider-session-repair`**：将其元数据与既有的 v0.7.6 VERSION 和 README 文件同步一致，并移除未经核实的 LovStudio 渠道契约。

### 验证
- 独立评审在所有 Critical 与 Important 问题解决后通过。
- GitHub 校验 CI 在最终 PR HEAD 上通过。
- 本地通过 shadow-skill-publisher 192 项、agent-privacy-check 9 项测试。
- 全部 8 个 Skill 在隔离的 Codex 目标中被发现并安装，最终源码归档通过 ZIP 完整性与公开内容检查。

---

## v0.3.0 - 2026-09-09

> **类型**: 发布工作流与文档建设
>
> **GitHub Release**: [v0.3.0](https://github.com/WardLu/skills/releases/tag/v0.3.0)

### 主要内容
- 新增 `shadow-skill-publisher` v0.2.0，用于本地 Skill 校验、渠道打包、需确认的交接与发布状态跟踪。
- 为可独立安装的 Skill 增加双语公开 README 入口。
- Publisher 的首个本地检查不再依赖 profile，仅对 prompt-only Skill 生效；缺失的渠道事实会被报告，而不会创建远程或浏览器状态。
- 统一澄清与浏览器无关的手工交接流程与维护者文档，并同步各 Skill 版本、README 索引与公开 Git 门禁。

### 本版包含的 Skill 版本
- `codex-cross-provider-session-repair` v0.7.6
- `codex-doctor` v0.1.2
- `github-repo-i18n` v0.1.1
- `public-release-gate` v0.1.2
- `public-repo-git-gate` v0.1.2
- `shadow-skill-publisher` v0.2.0
- `test-scope-routing` v0.1.2

本版为源码集合发布，不包含自定义二进制附件。

---

## v0.2.0 - 2026-09-02

> **类型**: 大规模能力扩充与 CLI 分发生态建立
>
> **GitHub Release**: [v0.2.0](https://github.com/WardLu/skills/releases/tag/v0.2.0)

### 核心新增 Skill
1. **`codex-doctor` (v0.1.1)**：分析本地 Codex 会话 telemetry，生成隐私安全的工作流与提示词优化建议。
2. **`github-repo-i18n` (v0.1.0)**：在英文默认入口和目标语言之间精准同步 GitHub 仓库文档、元数据与 Topics，提供 parity 校验与实时预览。
3. **`public-release-gate` (v0.1.1)**：公开仓库 Release 产物、开源许可证合规、部署安全响应头与 GitHub Release 附件自动化审查门禁。
4. **`public-repo-git-gate` (v0.1.1)**：公开仓库 Git commit、push 和 PR 分支状态、未跟踪文件与敏感信息防泄露门禁。
5. **`test-scope-routing` (v0.1.1)**：框架无关的改动风险分级测试范围路由，杜绝盲目跑全量测试。

### 工程与分发改进
- **`npx skills` 原生分发支持**：支持通过标准 CLI 一键安装任意单项能力或全套集合：
  - 单技能安装：`npx skills add WardLu/skills --skill <name> --global --agent codex --yes`
  - 全集合安装：`npx skills add WardLu/skills --skill '*' --global --agent codex --yes`
- **文档体系标准化**：重构双语文档入口，严格规范 `README.<locale>.md` 命名。

---

## v0.1.0 - 2026-08-05

> **类型**: 初始版本发布
>
> **GitHub Release**: [v0.1.0](https://github.com/WardLu/skills/releases/tag/v0.1.0)

### 核心特性
- **初始 Skill 发布**：发布 `codex-cross-provider-session-repair`（v0.4.0），首创在保留 Codex 目录的前提下，彻底修复供应商不一致以及远程上下文压缩 `404 Item with id 'rs_...' not found` 崩溃。
- **自包含架构确立**：确立每个 Skill 独立目录、独立 `SKILL.md`、离线测试用例与轻量化依赖的规范。
