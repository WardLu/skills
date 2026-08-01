# WardLu Skills

Open-source Codex skills maintained by Ward Lu. Each skill is self-contained in a kebab-case directory with its own `SKILL.md`, version metadata, tests, and license.

## Available skills

- [`codex-cross-provider-session-repair`](codex-cross-provider-session-repair/) — diagnose and repair Codex Desktop sessions that fail after provider switches, imports, or forks. Read the [English guide](codex-cross-provider-session-repair/README.md) or [简体中文指南](codex-cross-provider-session-repair/README.zh-CN.md).

## Install a skill

Recommended cross-platform installation:

```bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair --global --agent codex --yes
```

Clone this repository, enter the skill directory, and run its installer. The default destination is the current user's `.agents/skills`; pass your client-specific skills directory when needed. Restart the client after installation or upgrade.

## Maintenance policy

Skills use Semantic Versioning. Each skill owns its `VERSION` and `CHANGELOG.md`. Changes should include offline tests and preserve the MIT license. Do not commit real Codex homes, session logs, backups, or credentials.

## License

Each skill declares its license. The collection's repository license is MIT.
