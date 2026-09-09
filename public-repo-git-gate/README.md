# Public Repository Git Gate

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`public-repo-git-gate` checks what a public repository is about to expose at
the commit, push, and pull request boundaries. It inspects actual Git scope,
not just `.gitignore` or a file summary.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it checks

| Stage | Main question |
| --- | --- |
| Commit | Are the staged paths, secrets, and public contents safe to commit? |
| Push | Does the branch change target the intended remote and base? |
| Pull request | Does the final head satisfy the repository's CI and review gates? |

## Use it

Install the Skill for a supported agent:

```bash
npx skills add WardLu/skills --skill public-repo-git-gate --global --agent <agent-name> --yes
```

For example:

```text
Check this repository before I commit these changes or open a pull request.
```

## Results and boundaries

The Skill reports the checked scope, findings, required project checks, and
remaining gates. It is read-only by default. Passing a check does not authorize
commit, push, PR creation, or remote-branch updates.

It does not replace the separate release gate for final archives, licenses,
deployment, or GitHub Release attachments. Keep internal plans, credentials,
customer data, and unnecessary private configuration out of public history.

<details>
<summary>For maintainers</summary>

Run the offline tests with:

```bash
python3 -m unittest discover -s tests -v
```

Keep project-specific exceptions in a narrowly scoped gate configuration and
review the full staged diff before release.

</details>

## License

MIT. See [LICENSE](../LICENSE).
