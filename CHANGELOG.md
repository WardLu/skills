# Changelog

All released collection-level changes are documented here. Individual skills
may keep a more detailed changelog in their own directory.

## [0.4.1] - 2026-09-22

### Added

- Added an offline repair path and a loopback compaction shim to
  codex-cross-provider-session-repair, so one over-limit session can be repaired
  without editing `config.toml`.

### Changed

- Upgraded codex-cross-provider-session-repair to v0.7.7. Sessions that aborted
  with `remote compaction v2 expected exactly one compaction output item, got 0
  from N output items` can now be repaired: the diagnostic reads the failure
  from the rollout as well as `logs_2.sqlite`, reports the
  `remote_compaction_v2` feature stage, and refuses `--disable-remote-compaction`
  on builds where that flag is a removed tombstone.

### Fixed

- Fixed codex-cross-provider-session-repair's `scripts/package.py` so the
  documented `--output ./dist` build no longer nests the previous `.skill`
  archive inside the new one.

### Release metadata

- Released as tag and release name `v0.4.1`. The interim skill-scoped tag
  `codex-cross-provider-session-repair-v0.7.7` was retired and now maps to this
  collection release.

## [0.4.0] - 2026-09-16

### Added

- Added agent-privacy-check v0.1.0 for read-only, plain-language audits of
  agent access, data egress, untrusted content, and the Secret Source +
  External Sink + Untrusted Content combination across Codex, Claude Code, and
  generic agent runtimes.

### Changed

- Added a four-level Low, Medium, High, and Critical operational risk rubric
  with evidence labels, worst-case explanations, and ordered remediation.
- Upgraded shadow-skill-publisher to v0.6.3 with digest-bound batch workflows,
  resumable handoffs, read-only monitoring, Coze Skill Store support, reusable
  listing assets, and corrected single-root WorkBuddy archives.
- Upgraded public-release-gate to v0.1.4 for its corrected WorkBuddy package;
  v0.1.3 was consumed by a withdrawn marketplace review and was not published.
- Synchronized codex-cross-provider-session-repair frontmatter metadata with
  its existing v0.7.6 VERSION and README files.
- Removed the unverified LovStudio channel contract from
  shadow-skill-publisher.

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
