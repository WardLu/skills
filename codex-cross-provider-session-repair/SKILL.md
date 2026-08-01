---
name: codex-cross-provider-session-repair
description: Repair Codex Desktop sessions that fail after switching model providers or importing/forking old conversations. Use this skill whenever a user mentions an old Codex session becoming invalid, “model provider not found”, “Codex cannot load config.toml”, remote context compaction 404s, “Item with id rs_... not found”, repeated reconnecting during resume, or a migrated Codex conversation that cannot continue—even when the user only asks to inspect or explain the failure. Diagnose the target session across its JSONL rollout, root state_5.sqlite, config.toml, and logs_2.sqlite, then make a target-scoped backup-first repair with verification and restart instructions.
license: MIT
compatibility: Requires Python 3.9+ with the standard library; Windows, macOS, and Linux Codex homes are supported. Stop Codex Desktop before applying file or database changes.
metadata:
  version: "0.1.0"
  repository: "https://github.com/WardLu/codex-cross-provider-session-repair"
  maintainer: "Ward Lu"
---

# Codex cross-provider session repair

Use this skill for a damaged or incompatible *saved Codex session*, not for ordinary model/API troubleshooting. The goal is to make one existing conversation resumable while keeping its user-visible history and avoiding broad cache deletion.

## What this skill fixes

Codex stores continuation state in several layers:

1. the global `config.toml` (current provider defaults);
2. a dated `sessions/**/rollout-*.jsonl` file (the conversation event stream);
3. the root `state_5.sqlite` `threads` row (the desktop index and provider snapshot); and
4. `logs_2.sqlite` (diagnostic evidence).

After a provider switch, an old thread can retain a provider in layers 2 or 3 even when the global config is correct. Separately, an imported/forked long thread can contain `response_item` reasoning records that were sent with `store=false` and never persisted by the service. Remote compaction then fails with HTTP 404: `Item with id 'rs_...' not found`.

The second failure is not fixed by changing the provider, deleting `config.toml`, or clearing browser cache. If multiple different `rs_...` IDs fail in succession, remove the non-user-visible local reasoning items in one pass; deleting one ID at a time only exposes the next stale reference.

## Safety contract

- Work on the requested session ID only. Do not update every thread or every session by default.
- Start with a dry run. Before any write, make a timestamped backup of the JSONL; back up the root SQLite database (including WAL/SHM sidecars) only when changing its provider row.
- Ask the user to fully quit Codex Desktop, including the tray process, before applying changes. A live process can cache old events or hold a file lock.
- Never delete the whole Codex home, all sessions, `config.toml`, auth tokens, caches, or databases as a generic “reset”.
- Preserve every user message, visible assistant message, tool call, tool result, and `event_msg`. Only remove `response_item` records whose payload type is `reasoning`, and only when the diagnosis supports the stale-compaction repair.
- Do not print auth tokens, refresh tokens, API keys, or complete session contents. Redact paths and secrets in reports.
- If the target rollout cannot be found, JSON parsing fails, or a backup cannot be created, stop and report the blocker instead of guessing.

## Workflow

### 1. Identify the target and Codex home

Use the exact session UUID supplied by the user. Resolve `CODEX_HOME` first; on Windows fall back to `%USERPROFILE%\\.codex`, and on macOS/Linux to `$HOME/.codex`. Do not repurpose common environment variables in shell snippets.

Locate the rollout by filename suffix and then confirm its first `session_meta` record contains the requested ID. Do not trust a title or current working directory alone; imported files can contain more than one `session_meta` record.

### 2. Diagnose read-only

Run the bundled script in dry-run mode:

```text
python scripts/repair.py --session-id <UUID> --codex-home <CODEX_HOME>
```

The report should include:

- the exact rollout path and line count;
- JSON parse errors (must be zero before repair);
- target `session_meta` provider values;
- the global provider from `config.toml`;
- the target `threads.model_provider` from root `state_5.sqlite` (the important database, when present);
- distinct `rs_...` IDs extracted from target-thread log errors; and
- how many of those IDs are actual local `response_item` reasoning records.

Use Python's built-in `sqlite3` module; do not require the optional `sqlite3` CLI. Treat a missing `sqlite/` child database as normal and do not invent one.

### 3. Select the smallest justified repair

**Provider mismatch.** If the current provider is known and the target session or target DB row still names an old provider, apply a target-only provider repair:

```text
python scripts/repair.py --session-id <UUID> --codex-home <CODEX_HOME> \
  --provider <current-provider> --fix-provider --apply
```

Update only the target session's `session_meta` payload and the target `threads` row. Never run a global `UPDATE ... WHERE model_provider=...` for a shared Codex home.

**Stale remote compaction.** If logs show `Item with id 'rs_...' not found` and the IDs map to local `response_item` records with `payload.type == "reasoning"`, use:

```text
python scripts/repair.py --session-id <UUID> --codex-home <CODEX_HOME> \
  --remove-reasoning stale --apply
```

This removes only the exact stale IDs. If the user has already seen two or more different stale IDs from the same imported/migrated session, or a retry reveals another ID immediately, use the one-pass cleanup:

```text
python scripts/repair.py --session-id <UUID> --codex-home <CODEX_HOME> \
  --remove-reasoning all --apply
```

`all` means all local `response_item` records whose payload type is `reasoning`; it does not remove `event_msg.agent_reasoning`, visible messages, tool calls, or tool outputs. This is appropriate because those reasoning items are internal model traces and the service has already confirmed that they were not persisted.

Provider repair and reasoning cleanup can be combined in one invocation after the dry-run report confirms both conditions.

### 4. Verify the file and database

Run the script again without `--apply`, or use its `--verify` output. Confirm:

- every remaining JSONL line parses;
- zero stale IDs remain as local reasoning items;
- provider values agree with the chosen current provider when provider repair was requested;
- the backup path is reported; and
- no unrelated session was changed.

The raw `rs_...` text may still occur inside a historical `task_complete` error event. That text is not a `response_item` submitted for compaction and does not need to be deleted.

### 5. Reload and test

Tell the user to fully quit and relaunch Codex Desktop, then open the exact session. A page refresh is insufficient because the desktop process caches the event stream. A safe smoke test is a short prompt that asks for a confirmation only; do not resume the user's old project task automatically.

If compaction succeeds and the error changes to authentication, transport, or provider availability, stop treating it as a session-file problem and diagnose that separate issue. If a new stale ID appears after a clean reload, re-run the dry-run report before changing anything else.

## Bundled tools

- `scripts/repair.py` — deterministic, backup-first diagnosis and target-scoped repair.
- `tests/test_repair.py` — offline tests using temporary fake Codex homes and SQLite databases.
- `README.md` — installation, upgrade, release, and troubleshooting guide.

## Report format

Give the user a concise result with: root cause, exact target session, files changed, backup paths, verification counts, whether an independent smoke test reached `Context compacted`, and the one required restart step. Never include credentials or full JSONL lines.

