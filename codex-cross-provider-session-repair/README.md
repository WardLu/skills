# Codex Cross-Provider Session Repair

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.7.5](https://img.shields.io/badge/version-0.7.5-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`codex-cross-provider-session-repair` is a small, backup-first Codex Skill for recovering an old Codex Desktop conversation after a provider switch, import, or fork.

[English](README.md) · [简体中文](README.zh-CN.md) · [Install](#install) · [Usage](#usage) · [Development](#development) · [Versioning and upgrades](#versioning-and-upgrades) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

It addresses three failure modes that look similar in the UI:

1. the saved session or its root `state_5.sqlite` thread row still points at an unavailable provider;
2. remote context compaction returns `404 Item with id 'rs_...' not found` because local reasoning items were sent with `store=false` and were never persisted by the service; and
3. an imported session is pinned to a model unsupported by the current ChatGPT account, such as `ark-code-latest`.

The repair is session-scoped. It never performs a global provider replacement or deletes the Codex home.

## Install

### Recommended: `npx skills`

After this repository is merged to `main`, install only this skill globally for Codex:

```bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair --global --agent codex --yes
```

The same command works on Windows, macOS, and Linux. It requires Node.js/npm (for `npx`). To install the whole collection, omit `--skill`; to target another supported agent, replace `--agent codex` with that agent name.

Useful lifecycle commands:

```bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
```

To install directly from the skill directory instead of selecting it from the collection:

```bash
npx skills add https://github.com/WardLu/skills/tree/main/codex-cross-provider-session-repair --global --agent codex --yes
```

The `skills` CLI installs the `SKILL.md` bundle for the selected agent; the bundled Python repair script remains available inside the installed skill directory.

### Manual installation

Clone the skills collection and run the installer from this directory:

```powershell
git clone https://github.com/WardLu/skills.git
Set-Location .\skills\codex-cross-provider-session-repair
.\scripts\install.ps1
```

The default destination is `%USERPROFILE%\.agents\skills`. For a Codex installation that reads `%USERPROFILE%\.codex\skills`, pass it explicitly:

```powershell
.\scripts\install.ps1 -Destination "$env:USERPROFILE\.codex\skills"
```

On macOS/Linux:

```bash
git clone https://github.com/WardLu/skills.git
cd skills/codex-cross-provider-session-repair
./scripts/install.sh
```

The platform matrix is:

| Platform | Codex home discovery | Installer |
| --- | --- | --- |
| Windows | `CODEX_HOME`, then `%USERPROFILE%\\.codex` | `scripts/install.ps1` |
| macOS | `CODEX_HOME`, then `~/.codex` | `scripts/install.sh` |
| Linux | `CODEX_HOME`, then `~/.codex` | `scripts/install.sh` |

The repair logic uses Python 3.9+ standard-library modules only (`json`, `sqlite3`, `pathlib`, and `shutil`), so no platform-specific Python packages are required.

Restart the client after installing or upgrading a skill so its metadata is reloaded.

## Usage

Give Codex the affected session UUID and the visible error. The skill should diagnose first and ask you to quit Codex Desktop before applying a repair.

For a direct, read-only diagnostic:

```powershell
python .\scripts\repair.py `
  --session-id 019fb8f5-5fcc-74c0-8341-61f83f2126ce `
  --codex-home "$env:USERPROFILE\.codex"
```

For a repeated remote-compaction 404 where the report maps stale IDs to local reasoning records, fully quit Codex Desktop first:

```powershell
python .\scripts\repair.py `
  --session-id 019fb8f5-5fcc-74c0-8341-61f83f2126ce `
  --codex-home "$env:USERPROFILE\.codex" `
  --remove-reasoning all --apply
```

Run the same command without `--apply` afterward. The decisive verification
fields are `Stale IDs present as local reasoning: []` and
`Local reasoning records: 0`. Log-derived IDs are labeled as historical and may
remain in the report.

Recommended user-facing run: after the user approves the repair, start this
command immediately. On macOS it opens a visible Terminal window, shows the
final result, and closes the uniquely titled repair window after the user
presses Enter:

```bash
python3 scripts/start_repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --remove-reasoning stale
```

The worker can safely start before or after Codex is closed. The current
conversation should immediately tell the user that the repair may wait up to
300 seconds and that Codex must be fully quit. The Terminal announces the wait
limit and reminds the user at about 60, 180, and 240 seconds. On macOS it opens
a readable 120-column by 36-row Terminal tab/window and hides the long worker
command behind a short temporary runner. It shows
bilingual states such as `Waiting / 等待中`, `Applying / 修复中`,
`Verified / 已验证`, and `Failed / 失败`. Only `Verified / 已验证` means it is
safe to reopen Codex; after pressing Enter on the final prompt, the launcher
closes the exact repair window identified by the session ID when it contains
only the repair tab. If Terminal automation permission is unavailable, the
shell still exits and the finished window can be closed with Command+W. A
timeout explicitly says that no files were changed.

For advanced use, run the lower-level worker from an independent Terminal while
Codex Desktop is still open:

```bash
python3 scripts/wait_and_repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --remove-reasoning all \
  --status-file "/tmp/codex-session-repair-<UUID>.json"
```

Then fully quit Codex Desktop. The wrapper announces the configured wait limit,
prints periodic reminders, waits for a stable process-free window, refuses to
write if Codex reappears or the rollout changes, and ends with
`Verified / 已验证` only after the repair and a second diagnostic succeed.

For a provider mismatch, pass the known current provider and opt into the target-only database/session update:

```powershell
python .\scripts\repair.py `
  --session-id <UUID> `
  --codex-home "$env:USERPROFILE\.codex" `
  --provider custom --fix-provider --apply
```

The command is dry-run unless `--apply` is present. Every apply run creates a timestamped JSONL backup. A database backup is created only when the target `threads.model_provider` row changes; WAL/SHM sidecars are copied alongside it. Do not treat a background process exit as proof of completion unless a backup and `verified` status are visible.

For an unsupported saved model, align the target rollout settings and root
thread snapshot with the current configured model. Use `none` explicitly so
this repair preserves local reasoning records:

```bash
python3 scripts/repair.py \
  --session-id <UUID> \
  --codex-home "$HOME/.codex" \
  --model <current-model> --fix-model \
  --remove-reasoning none --apply
```

The command does not change the global `config.toml` or unrelated sessions.
Verification must show the target `threads.model` and structured rollout model
settings using the requested model, plus the new JSONL/database backups.

After the manual apply and verification, relaunch Codex Desktop. For the
process-aware wrapper, it is already safe to relaunch once the status reaches
`verified`. A page refresh does not unload the cached rollout. Test with a
short confirmation prompt before resuming the original project task.

To build a portable `.skill` archive without extra dependencies:

```bash
python scripts/package.py --output ./dist
```

## Development

The repair tool has no third-party runtime dependencies:

```bash
python -m unittest discover -s tests -v
python scripts/repair.py --help
python scripts/wait_and_repair.py --help
python scripts/start_repair.py --help
```

The `evals/evals.json` file contains realistic trigger and behavior prompts. The `evals` directory is intentionally excluded from distributable `.skill` packages by the standard skill packager.

## Versioning and upgrades

This skill follows Semantic Versioning. The canonical version is in `VERSION` and mirrored in `SKILL.md` metadata.

```bash
git pull --ff-only origin main
git fetch --tags
```

Install the checked-out version again after pulling. Releases should be tagged `vMAJOR.MINOR.PATCH`, with a `CHANGELOG.md` entry and a GitHub release. Backward-incompatible changes include changing the default repair scope or the meaning of `--remove-reasoning all`.

## Scope and limitations

This skill repairs local Codex session state. It cannot recover an item that the remote service never persisted, refresh an expired login token, fix a provider outage, or repair a corrupt SQLite database with no usable backup. It deliberately preserves visible history rather than trying to regenerate missing model traces.

## License

MIT. See [LICENSE](LICENSE).
