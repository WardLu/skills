# Public Release Gate

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.4](https://img.shields.io/badge/version-0.1.4-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`public-release-gate` reviews a public repository release as a complete
deliverable. It checks the source, final artifacts, release page, and deployed
state instead of treating a passing commit or CI job as release approval.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it checks

- version, tag, README, changelog, and release-note consistency;
- final build artifacts and archives;
- secrets, personal data, internal material, and third-party licenses;
- deployment response headers, production state, and release attachments.

## Use it

Install the Skill for a supported agent:

```bash
npx skills add WardLu/skills --skill public-release-gate
```

Then ask the agent to review a specific version, tag, artifact set, and
production URL. For example:

```text
Audit release v1.2.3, its final archive, and the deployed URL before publication.
```

## Results and boundaries

The result is `PASS`, `BLOCKED`, or `FAILED`, with evidence and skipped checks.
The review is read-only by default. A passing gate does not authorize creating a
tag or Release, uploading attachments, changing production configuration, or
deploying.

Use `public-repo-git-gate` for commit, push, and pull request checks. Keep
project-specific commands and release configuration in the project itself.

<details>
<summary>For maintainers</summary>

Build and inspect the exact final artifacts before release, and keep third-party
source, license, and checksum records alongside the release evidence.

</details>

## License

MIT. See [LICENSE](../LICENSE).
