# GitHub Repository i18n

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.1](https://img.shields.io/badge/version-0.1.1-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`github-repo-i18n` keeps the user-facing language layer of a GitHub repository
aligned across an English default and explicitly requested locales. It can
translate or audit selected documentation without silently changing unrelated
repository content.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it covers

- README files and other selected documentation;
- release notes and changelogs when included in the requested scope;
- repository description and topics as separate, optional metadata surfaces;
- language links, code blocks, images, versions, and local references.

## Use it

Install the Skill for a supported agent:

```bash
npx skills add WardLu/skills --skill github-repo-i18n --global --agent <agent-name> --yes
```

Tell the agent exactly which files or metadata surfaces and which locales to
handle. For example:

```text
Audit README.md and README.zh-CN.md for parity, then show local and GitHub-style previews.
```

## Results and boundaries

The Skill returns a scope matrix, locale mirrors, parity findings, and separate
preview evidence. English remains the default entry unless you choose another
documented strategy. Code, links, images, versions, and factual limitations are
preserved.

It does not translate product UI, invent project claims, scan GitHub remotely,
or commit, push, release, deploy, or update repository metadata without
explicit authorization.

<details>
<summary>For maintainers</summary>

Keep project facts in the selected source documents, run the repository's
offline checks before release, and review the linked references when changing
locale or preview behavior.

</details>

## License

MIT. See [LICENSE](../LICENSE).
