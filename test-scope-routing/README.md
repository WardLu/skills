# Test Scope Routing

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`test-scope-routing` selects the smallest sufficient validation scope from the
changed surface and its risk. It helps keep local feedback fast while
reserving integration, release, and production checks for the boundaries that
need them.

[English](README.md) · [简体中文](README.zh-CN.md)

## When to use it

Use it when planning or reviewing a change and you need to decide:

- which project-defined commands to run;
- which checks are required by code, UI, data, auth, build, or release risk;
- which checks can be skipped and how to record that decision.

## Validation tiers

| Tier | Typical responsibility |
| --- | --- |
| L0 | Static, formatting, policy, and documentation checks |
| L1 | Fast deterministic logic and state checks |
| L2 | Targeted UI rendering and interaction |
| L3 | Integration, data, auth, sync, and external-boundary checks |
| L4 | Full merge, release, security, or production boundary |

## Use it

Install the Skill for a supported agent:

```bash
npx skills add https://github.com/wardlu/skills --skill test-scope-routing
```

For example:

```text
Route the smallest sufficient checks for this change and record what remains unverified.
```

## Results and boundaries

The Skill returns the selected tier, project-defined commands, evidence to
record, skipped checks, and residual risk. It reads the project's own test and
release configuration; it does not invent global command names or substitute a
production write for validation.

<details>
<summary>For maintainers</summary>

Keep exact commands and environment prerequisites in project documentation.
Use this Skill for routing and evidence, not as a replacement for project
tests, CI, release gates, or production acceptance.

</details>

## License

MIT. See [LICENSE](../LICENSE).
