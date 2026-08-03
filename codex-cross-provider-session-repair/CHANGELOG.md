# Changelog

All notable changes to this skill are documented here.

## [0.3.0] - 2026-08-03

### Added

- Gemini model-turn compaction detection and repair: `--fix-model-turn` removes
  `thread_rolled_back` events that hide the trailing user turn and appends a
  dummy user message when the effective history still ends with an assistant
  turn, fixing HTTP 400 "Requests ending with a model turn are not supported".
- End-to-end user interaction flow documentation in `SKILL.md` so users only
  need to provide a session ID in a new Codex conversation.

### Changed

- Dry-run report now includes a `Model-turn compaction` line with risk status,
  last effective role/line, and effective message/turn counts.

## [Unreleased]

### Added

- Added a Simplified Chinese README for the repository root.

### Changed

- Clarified that the repository is a general-purpose agent skills collection; the current session-repair skill is specifically for Codex Desktop.
- Simplified the root README language navigation label.
- Added paired `English` and `简体中文` links to both language versions of the root and current-skill READMEs.

## [0.2.0] - 2026-08-01

### Added

- Bilingual English and Simplified Chinese README documentation with quick navigation links.
- `npx skills` installation, listing, update, and removal instructions.
- Explicit Windows, macOS, and Linux support matrix and platform installer guidance.
- Executable POSIX helper scripts for macOS/Linux installations.

## [0.1.0] - 2026-08-01

### Added

- Read-only diagnostics across `config.toml`, session JSONL, root `state_5.sqlite`, and `logs_2.sqlite`.
- Target-only provider repair with SQLite and JSONL backups.
- One-pass cleanup for repeated non-persisted `response_item` reasoning records.
- Windows and POSIX installers, offline tests, eval prompts, and MIT licensing.
