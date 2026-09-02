# Changelog

All released collection-level changes are documented here. Individual skills
may keep a more detailed changelog in their own directory.

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
