# Changelog

All released collection-level changes are documented here. Individual skills
may keep a more detailed changelog in their own directory.

## [0.4.0] - 2026-09-09

### Added

- Added agent-privacy-check v0.1.0 for read-only, plain-language audits of
  agent access, data egress, untrusted content, and the Secret Source +
  External Sink + Untrusted Content combination across Codex, Claude Code, and
  generic agent runtimes.

### Changed

- Added a four-level Low, Medium, High, and Critical operational risk rubric
  with evidence labels, worst-case explanations, and ordered remediation.

## [0.3.0] - 2026-09-09

### Added

- Added `shadow-skill-publisher` v0.2.0 for local Skill validation, channel
  packaging, confirmation-bound handoff, and publication status tracking.
- Added bilingual public README entry points for independently installable
  Skills.

### Changed

- Made the Publisher's first local check profile-free for prompt-only Skills;
  missing channel facts are reported without creating remote or browser state.
- Clarified browser-neutral manual handoff and maintainer-facing documentation
  across the collection.
- Synchronized individual Skill versions, README indexes, and public Git gates.

## [0.2.0] - 2026-09-02

### Added

- Added `codex-doctor` for local Codex session telemetry analysis and
  privacy-safe workflow recommendations.
- Added `github-repo-i18n` for scoped GitHub repository documentation and
  metadata localization, locale parity checks, and Markdown previews.
- Added public repository commit, push, and pull-request gates.
- Added public release artifact, license, deployment, and GitHub Release gates.
- Added framework-agnostic test-scope routing.
- Added collection-level `npx skills` installation instructions for individual
  skills and the complete collection.

### Changed

- Rewrote the `public-release-gate` and `public-repo-git-gate` entry documents
  in English.
- Updated the `codex-doctor` and `test-scope-routing` AI-facing descriptions in
  English.
- Synchronized the English and Simplified Chinese root indexes with current
  skill and collection versions.
- Preserved explicit locale documents, multilingual fixtures, and intentional
  bilingual runtime output as non-English content.
- Corrected the collection release sequence and aligned root version documents,
  repository tags, and GitHub Release names.

### Fixed

- Replaced invalid PNG placeholders in the `github-repo-i18n` fixtures with
  valid PNG files and added a regression check for their signatures.
- Corrected localized README naming guidance to use `README.<locale>.md`.

## [0.1.0] - 2026-08-05

### Added

- Established the collection with the Codex cross-provider session repair
  skill, bilingual repository navigation, offline validation, and platform
  installation guidance.
- Published the initial `codex-cross-provider-session-repair` Skill release at
  version `0.4.0`.
