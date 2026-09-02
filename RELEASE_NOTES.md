# WardLu Skills Release Notes

本文档汇总 WardLu Skills（面向 AI Agent 工作流的专注型开源 Skill 集合工程）历史版本发布说明。

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
