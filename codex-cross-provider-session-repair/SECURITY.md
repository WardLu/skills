# Security policy

## Local data

Codex rollout files and SQLite databases can contain prompts, source code, tool output, paths, and authentication-adjacent metadata. Do not commit your real `%USERPROFILE%\\.codex` directory, generated backups, or diagnostic reports to GitHub.

The bundled tool is target-scoped and backup-first. It does not print full JSONL records or token values. Review a dry-run report before applying any change.

## Reporting a vulnerability

Please open a private security report through GitHub if possible. Do not include access tokens, refresh tokens, API keys, or unredacted Codex session content in an issue.
