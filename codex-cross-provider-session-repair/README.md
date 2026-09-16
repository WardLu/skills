# Codex Cross-Provider Session Repair

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.7.6](https://img.shields.io/badge/version-0.7.6-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`codex-cross-provider-session-repair` is a backup-first Skill for recovering
an old Codex Desktop conversation after a provider switch, import, or fork.
Repairs are limited to the selected session; the Skill does not replace a
provider globally or delete the Codex home.

[English](README.md) · [简体中文](README.zh-CN.md)

## When to use it

Use it when an existing conversation cannot continue because:

- the saved session still points to an unavailable provider;
- remote compaction reports `404 Item with id 'rs_...' not found`; or
- an imported session uses a model unsupported by the current account.

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
