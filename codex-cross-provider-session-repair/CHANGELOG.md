# Changelog

All notable changes to this skill are documented here.

## [0.7.5] - 2026-08-15

### Fixed

- Close the dedicated Terminal repair window after the final Enter prompt. The
  previous implementation sent `close` to a Terminal tab object, which macOS
  Terminal rejects with error `-1708`; the new path matches the window title
  and closes it only when it contains one tab.

## [0.7.4] - 2026-08-15

### Fixed

- Give each macOS repair tab a session-specific custom title and close only
  that tab after the final Enter prompt, instead of relying on the Terminal
  profile's completed-window behavior.
- Use Terminal's raw `do script` event for launcher compatibility and keep a
  shell-exit fallback when Terminal automation is unavailable.

## [0.7.3] - 2026-08-15

### Fixed

- Make the macOS Terminal launcher exit its outer shell after the final Enter
  prompt, so the Terminal tab/window actually closes instead of leaving an
  idle shell open.

## [0.7.2] - 2026-08-14

### Changed

- Reworked the macOS Terminal launcher to use a readable 120×36 Terminal
  tab/window and run
  the worker through a short temporary runner, so long shell arguments no
  longer wrap into an unreadable block.
- Added a separated bilingual header and final result panel around the worker
  output.

## [0.7.1] - 2026-08-14

### Added

- Added a bilingual wait-limit announcement and reminders at approximately 60,
  180, and 240 seconds during the default 300-second Codex shutdown wait.
- Added `wait_timeout_seconds`, `wait_phase`, `conversation_notice`, and
  `wait_timed_out` status fields so the current conversation and Terminal can
  explain the same state.
- Added an explicit timeout message that says no files were changed and Codex
  must remain closed before retrying.

## [0.7.0] - 2026-08-13

### Added

- Added `scripts/start_repair.py` as the recommended consent-to-repair entry
  point. It opens a visible Terminal on macOS, keeps the final result visible,
  and safely handles Codex being closed before or after the worker starts.
- Added bilingual terminal and JSON status fields, including
  `Verified / 已验证`, `can_reopen`, and `next_action`.
- Added explicit support for starting the approved repair job after Codex is
  already stopped, while retaining a stable process-free safety window.

## [0.6.0] - 2026-08-12

### Added

- Added target-scoped repair for sessions pinned to an unsupported saved model,
  including structured rollout settings and the root `threads.model` snapshot.
- Added `--remove-reasoning none` to the process-aware wrapper and independent
  verification that model repairs agree in both JSONL and SQLite.
- Added detection for the bundled `codex` app-server and Codex Framework service
  processes, which can keep the rollout and SQLite WAL open after the main window exits.

## [0.5.0] - 2026-08-10

### Added

- Added `scripts/wait_and_repair.py`, a process-aware wrapper that waits for a
  stable Codex Desktop shutdown, detects rollout races, applies the existing
  target-scoped repair, and independently verifies the result.
- Added atomic JSON status reporting with `diagnosed`, `waiting`, `stopped`,
  `applying`, `verified`, and `failed` states.
- Added offline tests for process restart races, rollout changes, status files,
  and end-to-end apply/verify behavior.

### Changed

- Made the documented order explicit: quit Codex before writing, and reopen it
  only after verification.
- Labeled log-derived stale IDs as historical so they are not confused with
  local reasoning items that would still be submitted.

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

## [0.4.0] - 2026-08-05

### Fixed

- `--fix-model-turn` now appends the dummy user message based on the effective
  history after `thread_rolled_back` events are stripped, instead of the raw
  JSONL tail. This fixes sessions where an unfinished or rolled-back turn left a
  trailing user message while the effective history still ended with an
  assistant turn.

### Added

- Diagnose Codex remote-compaction-v2 failures (`remote compaction v2 expected
  exactly one compaction output item, got 0 from N output items`). The report
  now prints a user-friendly hint: disable remote compaction or switch to a
  provider/model that supports it. New `--disable-remote-compaction` flag
  (requires `--apply` and explicit user approval) writes
  `remote_compaction_v2 = false` under `[features]` in config.toml with a backup.
- Tests for the model-turn regression and remote-compaction diagnostics.
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
