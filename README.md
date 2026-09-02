<div align="center">

# WardLu Skills

Focused, versioned, open-source skills for agent workflows.

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![Collection version 0.1.0](https://img.shields.io/badge/collection%20version-0.1.0-2563eb.svg)](VERSION)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [Changelog](CHANGELOG.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

> Small, composable skills for repeatable work — with explicit safety boundaries, offline tests, and releaseable versions.

## What this repository is

This repository is a collection of self-contained skills for AI agents and developer workflows. Each skill lives in its own kebab-case directory and includes a `SKILL.md`; scripts, tests, references, documentation, licenses, and version metadata are added when the skill needs them. Individual skills may target one agent or work across several agents; their compatibility is documented in each skill's `SKILL.md` and any linked references.

The collection currently includes Codex workflow skills, GitHub repository internationalization, public repository/release gates, and a framework-agnostic test-scope routing skill.

| Skill | Purpose | Version | Documentation |
| --- | --- | --- | --- |
| [`codex-cross-provider-session-repair`](codex-cross-provider-session-repair/) | Diagnose and repair provider mismatches and remote compaction `404 Item with id 'rs_...' not found` errors without deleting the Codex home. | `0.7.5` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |
| [`codex-doctor`](codex-doctor/) | Analyze local Codex session telemetry and produce privacy-safe efficiency recommendations. | `0.1.1` | [SKILL.md](codex-doctor/SKILL.md) |
| [`github-repo-i18n`](github-repo-i18n/) | Synchronize explicitly selected GitHub repository documentation, descriptions, and topics across an English default and requested locales with parity checks and Markdown previews. | `0.1.0` | [SKILL.md](github-repo-i18n/SKILL.md) |
| [`public-release-gate`](public-release-gate/) | Review public repository releases, final artifacts, third-party notices, deployment headers, and GitHub Release attachments. | `0.1.1` | [SKILL.md](public-release-gate/SKILL.md) |
| [`public-repo-git-gate`](public-repo-git-gate/) | Check public repository content and branch/remote/PR state across commit, push, and pull request workflows. | `0.1.1` | [SKILL.md](public-repo-git-gate/SKILL.md) |
| [`test-scope-routing`](test-scope-routing/) | Route validation by change risk and affected boundaries instead of defaulting to the full test suite. | `0.1.1` | [SKILL.md](test-scope-routing/SKILL.md) |

## Install

### Recommended: `npx skills`

Each skill is installable when its directory contains a valid `SKILL.md`; a
per-skill `README.md` is optional and is not required by the CLI. Install one
skill globally for a supported agent with this example:

~~~bash
npx skills add WardLu/skills --skill codex-doctor --global --agent codex --yes
~~~

Replace `codex-doctor` with any available skill name:

~~~text
codex-cross-provider-session-repair
codex-doctor
github-repo-i18n
public-release-gate
public-repo-git-gate
test-scope-routing
~~~

To install the whole collection for Codex:

~~~bash
npx skills add WardLu/skills --skill '*' --global --agent codex --yes
~~~

The command works on Windows, macOS, and Linux with Node.js/npm installed. The `skills` CLI installs the selected `SKILL.md` bundle and keeps the skill manageable through the same tool:

~~~bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
~~~

For another supported agent, replace `--agent codex` with that agent name. This repository must be merged to `main` before the `WardLu/skills` command can resolve newly added skills.

### Manual installation for the current Codex skill

Windows PowerShell:

~~~powershell
git clone https://github.com/WardLu/skills.git
Set-Location .\skills\codex-cross-provider-session-repair
.\scripts\install.ps1 -Destination "$env:USERPROFILE\.codex\skills"
~~~

macOS/Linux:

~~~bash
git clone https://github.com/WardLu/skills.git
cd skills/codex-cross-provider-session-repair
./scripts/install.sh "$HOME/.codex/skills"
~~~

Restart the target agent after installing or upgrading so the new skill metadata is loaded.

## Current skill: platform support

The current session-repair skill targets Codex Desktop and supports:

| Platform | Codex home fallback | Installer | Runtime |
| --- | --- | --- | --- |
| Windows | `%USERPROFILE%\.codex` | `scripts/install.ps1` | Python 3.9+ standard library |
| macOS | `~/.codex` | `scripts/install.sh` | Python 3.9+ standard library |
| Linux | `~/.codex` | `scripts/install.sh` | Python 3.9+ standard library |

Set `CODEX_HOME` when Codex uses a non-default home. The repair scripts do not require third-party Python packages. Future skills may document a different compatibility matrix.

## Safety-first workflow

For the session repair skill:

1. Stop Codex Desktop completely, including its tray process.
2. Run a dry-run diagnosis with the exact session UUID.
3. Review the provider and stale-reasoning findings.
4. Apply only the smallest target-scoped repair; backups are created before writes.
5. Relaunch Codex and send a short smoke-test prompt before resuming the original task.

The skill preserves visible messages and tool history. It does not delete the whole Codex home, refresh expired credentials, or recover records that the remote service never persisted.

## Repository layout

~~~text
.
├── .github/workflows/validate-skills.yml
├── CHANGELOG.md
├── VERSION
├── codex-cross-provider-session-repair/
│   ├── SKILL.md
│   ├── README.md
│   ├── README.zh-CN.md
│   ├── scripts/
│   ├── tests/
│   ├── evals/
│   ├── VERSION
│   ├── CHANGELOG.md
│   ├── CONTRIBUTING.md
│   ├── SECURITY.md
│   └── LICENSE
├── codex-doctor/
│   ├── SKILL.md
│   ├── agents/
│   └── VERSION
├── github-repo-i18n/
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── VERSION
├── public-release-gate/
│   ├── SKILL.md
│   ├── agents/
│   └── VERSION
├── public-repo-git-gate/
│   ├── SKILL.md
│   ├── agents/
│   ├── assets/
│   ├── references/
│   ├── scripts/
│   ├── tests/
│   └── VERSION
├── test-scope-routing/
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   └── VERSION
├── LICENSE
└── README.md
~~~

## Development and releases

From a skill directory:

~~~bash
python -m unittest discover -s tests -v
python scripts/repair.py --help
python scripts/package.py --output ./dist
~~~

Skills follow [Semantic Versioning](https://semver.org/). The canonical version is stored in `VERSION` and mirrored in `SKILL.md`. User-visible changes should update `CHANGELOG.md`; release tags use `vMAJOR.MINOR.PATCH`.

See the contribution rules in [`codex-cross-provider-session-repair/CONTRIBUTING.md`](codex-cross-provider-session-repair/CONTRIBUTING.md).

## Security and license

Do not commit real user data, session logs, backups, tokens, or API keys. For the current Codex-specific skill, read [`SECURITY.md`](codex-cross-provider-session-repair/SECURITY.md) before filing a bug with diagnostic data.

This collection and its skills are released under the [MIT License](LICENSE).


## Contact

Interested in B2B products, AI product development, supply-chain digitalization, or the Shadow product line? Feel free to reach out:

- **X (Twitter)** — [@Gollumgulu](https://x.com/Gollumgulu)
- **WeChat Official Account** — ![WeChat Official Account QR code](https://cdn.jsdelivr.net/gh/WardLu/mypic/images%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7.jpg)
- **Xiaohongshu (RED) / Weibo / Douyin** — same handle「Ward的AI产品实战」across platforms: [Xiaohongshu (RED)](https://xhslink.cn/m/4W1NWyRrxv5) · [Weibo](https://weibo.com/u/8344390431) · [Douyin](https://v.douyin.com/1y06PMohfoE/)
- **Email** — [wardlu@126.com](mailto:wardlu@126.com)

> Available for 1:1 consulting and project coaching: product diagnosis · AI implementation · workflow / Skill · system customization
