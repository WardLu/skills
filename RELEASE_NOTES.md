# WardLu Skills Release Notes

This document summarizes the historical releases of WardLu Skills, a focused
open-source collection for AI agent workflows.

[English](RELEASE_NOTES.md) · [简体中文](RELEASE_NOTES.zh-CN.md)

---

## v0.2.0 - 2026-09-02

> **Type**: Major capability expansion and CLI distribution ecosystem
> **GitHub Release**: [v0.2.0](https://github.com/WardLu/skills/releases/tag/v0.2.0)

### Core new Skills
1. **`codex-doctor` (v0.1.1)**: Analyze local Codex session telemetry and produce privacy-safe workflow and prompt optimization recommendations.
2. **`github-repo-i18n` (v0.1.0)**: Synchronize GitHub repository documentation, metadata, and Topics between an English default and target locales, with parity checks and live previews.
3. **`public-release-gate` (v0.1.1)**: Review public repository Release artifacts, open-source license compliance, deployment security headers, and GitHub Release attachments.
4. **`public-repo-git-gate` (v0.1.1)**: Protect public repositories across Git commit, push, and PR branch state, untracked files, and sensitive information.
5. **`test-scope-routing` (v0.1.1)**: Route validation by change risk in a framework-agnostic way instead of blindly running the full suite.

### Engineering and distribution improvements
- **Native `npx skills` distribution**: Install any individual Skill or the complete collection through the standard CLI:
  - Individual Skill: `npx skills add WardLu/skills --skill <name> --global --agent codex --yes`
  - Complete collection: `npx skills add WardLu/skills --skill '*' --global --agent codex --yes`
- **Documentation standardization**: Restructure bilingual documentation entry points and standardize the `README.<locale>.md` naming convention.

---

## v0.1.0 - 2026-08-05

> **Type**: Initial release
> **GitHub Release**: [v0.1.0](https://github.com/WardLu/skills/releases/tag/v0.1.0)

### Core features
- **Initial Skill release**: Released `codex-cross-provider-session-repair` (v0.4.0), repairing provider mismatches and remote context compaction `404 Item with id 'rs_...' not found` failures while preserving the Codex directory.
- **Self-contained architecture**: Established the convention that each Skill has its own directory and `SKILL.md`, offline tests, and lightweight dependencies.
