# Contributing

1. Create a feature branch from `main`.
2. Keep the repair target-scoped and backup-first.
3. Add or update an offline test for every behavior change.
4. Run `python -m unittest discover -s tests -v` and the skill validator before opening a pull request.
5. Update `VERSION` and `CHANGELOG.md` for user-visible changes.
6. Keep the root and per-skill `README.md` / `README.zh-CN.md` pairs structurally synchronized, including language navigation, install, and upgrade commands.

Never use real Codex homes, tokens, or unredacted session files in tests or commits. Synthetic JSONL and SQLite fixtures are sufficient.
