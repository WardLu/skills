# Codex Cross-Provider Session Repair

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.7.7](https://img.shields.io/badge/version-0.7.7-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`codex-cross-provider-session-repair` is a backup-first Skill for recovering
an old Codex Desktop conversation after a provider switch, import, or fork.
Repairs are limited to the selected session; the Skill does not replace a
provider globally or delete the Codex home.

[English](README.md) · [简体中文](README.zh-CN.md)

## When to use it

Use it when an existing conversation cannot continue because:

- the saved session still points to an unavailable provider;
- remote compaction reports `404 Item with id 'rs_...' not found`; or
- an imported session uses a model unsupported by the current account; or
- the backend does not implement Codex remote compaction v2, so an over-limit
  session aborts with `remote compaction v2 expected exactly one compaction
  output item, got 0 from N output items`.

## Install

Install it for Codex with the `skills` CLI:

```bash
npx skills add https://github.com/wardlu/skills --skill codex-cross-provider-session-repair
```

The command requires Node.js/npm. After installation, ask Codex to diagnose
the affected session and include the visible error and session UUID.

## Safe recovery

The Skill diagnoses first and asks you to fully quit Codex Desktop before any
write. It creates backups before applying a repair and reports a verified state
only after a second diagnostic succeeds.

For a read-only diagnostic, run the bundled command with your own session ID:

```bash
python3 scripts/repair.py \
  --session-id <SESSION_UUID> \
  --codex-home "$HOME/.codex"
```

Use the agent workflow for provider/model-specific repairs and any process-aware
waiting step. Do not apply a repair to a different session or while Codex is
running.

## When the backend cannot compact

Remote compaction v2 is a server-side feature. When the backend answers a
compaction request with an ordinary assistant message, Codex sees zero
compaction items and aborts the turn. On builds where `codex features list`
reports `remote_compaction_v2` as `removed` the flag is a tombstone: there is no
config switch, no local fallback, and the diagnostic refuses
`--disable-remote-compaction` instead of writing a key that does nothing.

Two target-scoped tools are bundled for that case:

- `scripts/compaction_shim.py` — a loopback shim that answers compaction
  requests on the backend's behalf and expands replayed compaction items back
  into readable context. It must stay in the request path while it is in use.
- `scripts/repair_session_offline.py` — runs that shim for one session while
  Codex is fully quit, then writes the compaction result into the session
  rollout. It never edits `config.toml` and leaves no process behind.

```bash
# preview (writes nothing)
python3 scripts/repair_session_offline.py \
  --session-id <SESSION_UUID> --codex-home "$HOME/.codex"

# apply, with Codex fully quit
python3 scripts/repair_session_offline.py \
  --session-id <SESSION_UUID> --codex-home "$HOME/.codex" --apply
```

Run it only while Codex is quit: the desktop app holds a writer lock on the
thread (`<CODEX_HOME>/thread-writer-locks/<uuid>.lock`) that makes
`codex exec resume` fail with `already has an active writer`. The runner backs
up the rollout and the root state database beside their originals and reports
`verified: true` only when the `compacted` record count grew, the last
`task_complete` error is null, and the session model is unchanged.

## Limits and privacy

This Skill cannot recover data that the remote service never persisted, refresh
expired credentials, fix a provider outage, or repair a corrupt database with
no usable backup. It preserves visible history and does not regenerate missing
model traces.

Keep session logs, tokens, backups, and real user data out of issues and public
archives. See [SECURITY.md](SECURITY.md) for reporting guidance.

<details>
<summary>For maintainers</summary>

Run the offline checks and build a distributable archive with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package.py --output ./dist
```

Keep the public version in `VERSION`, document user-visible changes in
`CHANGELOG.md`, and review [CONTRIBUTING.md](CONTRIBUTING.md) before changing
the repair scope or safety contract.

</details>

## License

MIT. See [LICENSE](LICENSE).
