---
name: add-or-enhance-skill-package
description: Workflow command scaffold for add-or-enhance-skill-package in skills.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-enhance-skill-package

Use this workflow when working on **add-or-enhance-skill-package** in `skills`.

## Goal

Adds a new skill package or enhances an existing one by updating code, scripts, tests, and documentation within the skill directory.

## Common Files

- `codex-cross-provider-session-repair/README.md`
- `codex-cross-provider-session-repair/SKILL.md`
- `codex-cross-provider-session-repair/CHANGELOG.md`
- `codex-cross-provider-session-repair/scripts/install.sh`
- `codex-cross-provider-session-repair/scripts/package.py`
- `codex-cross-provider-session-repair/scripts/repair.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create or update the skill directory with necessary files (README, SKILL.md, scripts, tests, etc.)
- Add or update scripts (e.g., install.sh, package.py, repair.py)
- Update or add tests in the tests/ subdirectory
- Update documentation files within the skill (README.md, CHANGELOG.md, SKILL.md, etc.)
- Commit all changes together

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.