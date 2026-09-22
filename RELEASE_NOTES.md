# WardLu Skills Release Notes

本文档汇总 WardLu Skills（面向 AI Agent 工作流的专注型开源 Skill 集合工程）历史版本发布说明。

---

## v0.4.1 - 2026-09-22

> **类型**: 集合级补丁发布（单技能修复与升级）
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

## v0.2.0 - 2026-09-02

> **类型**: 大规模能力扩充与 CLI 分发生态建立  
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
> **GitHub Release**: [v0.1.0](https://github.com/WardLu/skills/releases/tag/v0.1.0)

### 核心特性
- **初始 Skill 发布**：发布 `codex-cross-provider-session-repair`（v0.4.0），首创在保留 Codex 目录的前提下，彻底修复供应商不一致以及远程上下文压缩 `404 Item with id 'rs_...' not found` 崩溃。
- **自包含架构确立**：确立每个 Skill 独立目录、独立 `SKILL.md`、离线测试用例与轻量化依赖的规范。
