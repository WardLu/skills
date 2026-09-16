# Codex Doctor

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`codex-doctor` analyzes local Codex session telemetry and turns recurring
patterns into a small set of evidence-backed workflow improvements. It uses
telemetry-only analysis by default and does not invoke a model.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it helps with

- context bloat and unusually long sessions;
- exploration or validation that does not converge;
- repeated failures and retries without a changed hypothesis;
- trends across a selected date range rather than one isolated session.

## Use it

Install the Skill for a supported agent:

```bash
npx skills add WardLu/skills --skill codex-doctor
```

An existing Codex Doctor analyzer must be available in the workspace or at a
path you provide. After installation, ask your agent to analyze a selected
period and state whether you want telemetry-only or AI-assisted interpretation.

For example:

```text
Analyze my recent Codex sessions in telemetry-only mode and suggest up to three workflow improvements.
```

## Results and privacy

The report separates measured telemetry, interpretation, and recommendations.
It preserves JSON for facts and HTML for human-readable presentation. AI
interpretation runs only when explicitly requested and may consume model usage.

The Skill does not scan the whole home directory, install dependencies without
a reason, or place raw metrics and private paths into global rules. Keep real
session data and credentials out of public issues and archives.

<details>
<summary>For maintainers</summary>

Keep telemetry-only mode as the default, preserve synthetic examples, and
review `SKILL.md` whenever the report contract or privacy boundary changes.

</details>

## License

MIT. See [LICENSE](../LICENSE).
