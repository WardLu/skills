# WardLu Skills Release Notes

Release notes for WardLu Skills, a focused open-source skill collection for AI
agent workflows.

[English](RELEASE_NOTES.md) · [简体中文](RELEASE_NOTES.zh-CN.md)

---

## v0.4.2 - 2026-09-22

> **Type**: Documentation layer, release-notes parity, and audit fix
>
> **GitHub Release**: [v0.4.2](https://github.com/WardLu/skills/releases/tag/v0.4.2)

### Added

- Root README visual layer: a hero and a four-step release workflow diagram in
  English and Simplified Chinese, as pure SVG with accessible text contrast.

### Changed

- **`github-repo-i18n` → v0.1.2**: the parity audit now compares a linked document
  from another locale family by its locale-neutral path, so a correct locale
  pair is no longer a false mismatch.
- Release notes are bilingual: `RELEASE_NOTES.md` is the English default and
  `RELEASE_NOTES.zh-CN.md` preserves the Chinese content, both linked from the
  root READMEs.

### Fixed

- Backfilled the missing v0.3.0 and v0.4.0 release-notes entries.

---

## v0.4.1 - 2026-09-22

> **Type**: Collection patch release (single-skill fix and upgrade)
>
> **GitHub Release**: [v0.4.1](https://github.com/WardLu/skills/releases/tag/v0.4.1)

### Skill upgrade

- **codex-cross-provider-session-repair v0.7.7**: fixes sessions that could not
  continue after a remote-compaction contract failure. The diagnostic now reads
  the rollout's `task_complete` records as well as `logs_2.sqlite` (which usually
  keeps only the generic line), reports the `remote_compaction_v2` feature stage,
  and refuses to write an ineffective config key once that flag is a tombstone.
  An offline repair runner and a loopback compaction shim repair one over-limit
  session without editing `config.toml`.

### Fixed

- Corrected `scripts/package.py`: building with the documented
  `--output ./dist` no longer nests the previous `.skill` file inside the new
  archive.

### Release metadata

- The interim single-skill tag `codex-cross-provider-session-repair-v0.7.7` was
  retired and now maps to this collection release.

---

## v0.4.0 - 2026-09-16

> **Type**: New skill and skill upgrades
>
> **GitHub Release**: [v0.4.0](https://github.com/WardLu/skills/releases/tag/v0.4.0)

### New skill

- **`agent-privacy-check` (v0.1.0)**: read-only, plain-language audits of the
  data an agent can reach, where data can leave, untrusted content, and the
  resulting compound privacy risk across Codex, Claude Code, and generic agent
  runtimes.

### Skill upgrades

- **`shadow-skill-publisher` → v0.6.3**: digest-bound batch workflows, resumable
  handoffs, read-only monitoring, Coze Skill Store support, reusable listing
  assets, and corrected single-root WorkBuddy archives.
- **`public-release-gate` → v0.1.4**: corrected WorkBuddy packaging. v0.1.3 was
  consumed by a withdrawn marketplace review and was never published.
- **`codex-cross-provider-session-repair`**: synchronized its metadata with the
  existing v0.7.6 VERSION and README files, and removed the unverified LovStudio
  channel contract.

### Verification

- Independent review passed after all Critical and Important findings were resolved.
- GitHub validation CI passed on the final PR heads.
- 192 shadow-skill-publisher tests and 9 agent-privacy-check tests passed locally.
- All 8 skills were discovered and installed in an isolated Codex target, and the
  final source archive passed ZIP integrity and public-content checks.

---

## v0.3.0 - 2026-09-09

> **Type**: Publishing workflow and documentation
>
> **GitHub Release**: [v0.3.0](https://github.com/WardLu/skills/releases/tag/v0.3.0)

### Highlights

- Added `shadow-skill-publisher` v0.2.0 for local Skill validation, channel
  packaging, confirmation-bound handoff, and publication status tracking.
- Added bilingual public README entry points for independently installable Skills.
- Made the Publisher's first local check profile-free for prompt-only Skills;
  missing channel facts are reported without creating remote or browser state.
- Clarified browser-neutral manual handoff and maintainer-facing documentation
  across the collection, and synchronized individual Skill versions, README
  indexes, and public Git gates.

### Included skill versions

- `codex-cross-provider-session-repair` v0.7.6
- `codex-doctor` v0.1.2
- `github-repo-i18n` v0.1.1
- `public-release-gate` v0.1.2
- `public-repo-git-gate` v0.1.2
- `shadow-skill-publisher` v0.2.0
- `test-scope-routing` v0.1.2

This is a source collection release; no custom binary attachments are included.

---

## v0.2.0 - 2026-09-02

> **Type**: Large capability expansion and CLI distribution ecosystem
>
> **GitHub Release**: [v0.2.0](https://github.com/WardLu/skills/releases/tag/v0.2.0)

### New skills

1. **`codex-doctor` (v0.1.1)**: analyzes local Codex session telemetry and produces privacy-safe workflow and prompt improvement recommendations.
2. **`github-repo-i18n` (v0.1.0)**: keeps GitHub repository documentation, metadata, and topics aligned between the English default entry and the target locales, with parity checks and live previews.
3. **`public-release-gate` (v0.1.1)**: release review gate for public repositories, covering artifacts, open-source license compliance, deployment security response headers, and GitHub Release attachments.
4. **`public-repo-git-gate` (v0.1.1)**: public-repository gate for Git commit, push, and pull request branch state, untracked files, and sensitive-information leakage.
5. **`test-scope-routing` (v0.1.1)**: framework-agnostic change-risk grading and test-scope routing instead of blind full test runs.

### Engineering and distribution

- **Native `npx skills` distribution**: install any single skill or the whole collection through the standard CLI:
  - Single skill: `npx skills add WardLu/skills --skill <name> --global --agent codex --yes`
  - Whole collection: `npx skills add WardLu/skills --skill '*' --global --agent codex --yes`
- **Documentation standardization**: rebuilt the bilingual documentation entry points and strictly standardized `README.<locale>.md` naming.

---

## v0.1.0 - 2026-08-05

> **Type**: Initial release
>
> **GitHub Release**: [v0.1.0](https://github.com/WardLu/skills/releases/tag/v0.1.0)

### Core features

- **Initial skill release**: published `codex-cross-provider-session-repair` (v0.4.0), the first skill to fully repair provider inconsistency and remote context compaction `404 Item with id 'rs_...' not found` crashes while preserving the Codex directory.
- **Self-contained architecture**: established per-skill directories, independent `SKILL.md` files, offline test cases, and lightweight dependencies.
