<div align="center">

# WardLu Skills

Focused, versioned, open-source skills for agent workflows.

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

> Small, composable skills for repeatable work — with explicit safety boundaries, offline tests, and releaseable versions.

## What this repository is

This repository is a collection of self-contained skills for AI agents and developer workflows. Each skill lives in its own kebab-case directory and includes its instructions, scripts, tests, documentation, license, and version metadata. Individual skills may target one agent or work across several agents; their compatibility is documented in each skill's README and `SKILL.md`.

The first skill in the collection is Codex-specific: it helps recover an old Codex Desktop conversation after a provider switch, import, or fork.

| Skill | Purpose | Version | Documentation |
| --- | --- | --- | --- |
| [`codex-cross-provider-session-repair`](codex-cross-provider-session-repair/) | Diagnose and repair provider mismatches and remote compaction `404 Item with id 'rs_...' not found` errors without deleting the Codex home. | `0.4.0` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |

## Install

### Recommended: `npx skills`

Install a skill globally for a supported agent. The example below installs the current Codex-specific skill:

~~~bash
npx skills add WardLu/skills --skill codex-cross-provider-session-repair --global --agent codex --yes
~~~

The command works on Windows, macOS, and Linux with Node.js/npm installed. The `skills` CLI installs the selected `SKILL.md` bundle and keeps the skill manageable through the same tool:

~~~bash
npx skills list
npx skills update codex-cross-provider-session-repair
npx skills remove codex-cross-provider-session-repair
~~~

To install the full collection, omit `--skill`. For another skill, replace the skill name; for another supported agent, replace `--agent codex` with that agent name. This repository must be merged to `main` before the `WardLu/skills` command can resolve the new skill.

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
├── codex-cross-provider-session-repair/
│   ├── SKILL.md
│   ├── README.md
│   ├── README.zh-CN.md
│   ├── scripts/
│   ├── tests/
│   ├── evals/
│   ├── VERSION
│   ├── CHANGELOG.md
│   ├── SECURITY.md
│   └── LICENSE
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
