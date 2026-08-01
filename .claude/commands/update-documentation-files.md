---
name: update-documentation-files
description: Workflow command scaffold for update-documentation-files in skills.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /update-documentation-files

Use this workflow when working on **update-documentation-files** in `skills`.

## Goal

Updates documentation files for the repository or a specific skill, including README, CHANGELOG, and related markdown files.

## Common Files

- `README.md`
- `codex-cross-provider-session-repair/README.md`
- `codex-cross-provider-session-repair/README.zh-CN.md`
- `codex-cross-provider-session-repair/CHANGELOG.md`
- `codex-cross-provider-session-repair/SKILL.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or add content to README.md at the root or within a skill directory
- Optionally update or add language-specific README files (e.g., README.zh-CN.md)
- Update CHANGELOG.md and/or SKILL.md as needed
- Commit changes with a docs-related message

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.