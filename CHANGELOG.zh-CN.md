# 变更记录

所有已经发布的集合级变更记录在此。单个 Skill 可以在自己的目录中维护更详细的变更记录。

[English](CHANGELOG.md) · [简体中文](CHANGELOG.zh-CN.md)

## [0.3.0] - 2026-09-09

### 新增

- 新增 `shadow-skill-publisher` v0.2.0，用于本地 Skill 校验、渠道打包、确认式交接和发布状态跟踪。
- 为可独立安装的 Skill 新增中英文公开 README 入口。

### 变更

- 让 Publisher 首次本地检查无需 profile 即可支持纯提示词 Skill；缺失的渠道事实会被报告，而不会创建远程或浏览器状态。
- 明确跨浏览器的手动交接方式，并完善集合中的维护者文档。
- 同步单个 Skill 版本、README 索引和公开 Git 闸门。

## [0.2.0] - 2026-09-02

### 新增

- 新增 `codex-doctor`，用于分析本地 Codex 会话 telemetry，并提供隐私安全的工作流建议。
- 新增 `github-repo-i18n`，用于限定范围的 GitHub 仓库文档和元数据国际化、locale parity 检查及 Markdown 预览。
- 新增公开仓库 commit、push 和 Pull Request 闸门。
- 新增公开 Release 产物、许可证、部署和 GitHub Release 闸门。
- 新增框架无关的测试范围路由。
- 新增针对单个 Skill 和完整集合的 `npx skills` 安装说明。

### 变更

- 重写 `public-release-gate` 和 `public-repo-git-gate` 的英文入口文档。
- 更新 `codex-doctor` 和 `test-scope-routing` 的 AI-facing 英文描述。
- 同步当前 Skill 和集合版本的中英文根索引。
- 保留明确的 locale 文档、多语言 fixture 以及有意保留的双语运行时输出。
- 修正集合发布顺序，并对齐根版本文档、仓库 Tag 和 GitHub Release 名称。

### 修复

- 将 `github-repo-i18n` fixture 中无效的 PNG 占位文件替换为有效 PNG，并增加签名回归检查。
- 修正本地化 README 命名说明，统一使用 `README.<locale>.md`。

## [0.1.0] - 2026-08-05

### 新增

- 建立包含 Codex 跨供应商会话修复 Skill、双语仓库导航、离线验证和平台安装说明的集合。
- 发布初始 `codex-cross-provider-session-repair` Skill，版本为 `0.4.0`。
