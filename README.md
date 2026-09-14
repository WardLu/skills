<div align="center">

# WardLu Skills

Focused, versioned, open-source skills for agent workflows.

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml)
[![Collection version 0.4.0](https://img.shields.io/badge/collection%20version-0.4.0-2563eb.svg)](VERSION)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md) · [Changelog](CHANGELOG.md) · [Issues](https://github.com/WardLu/skills/issues)

</div>

Small, composable Skills for repeatable agent work, with clear safety
boundaries and independently versioned packages.

## Skills

Choose a Skill by the task you want to complete:

| Skill | Use it for | Version | Documentation |
| --- | --- | --- | --- |
| `agent-privacy-check` | Audit what an agent can access, where data can leave, and the plain-language privacy risk. | `0.1.0` | [English](agent-privacy-check/README.md) · [简体中文](agent-privacy-check/README.zh-CN.md) |
| `codex-cross-provider-session-repair` | Recover an old Codex Desktop conversation after a provider, import, or fork problem. | `0.7.6` | [English](codex-cross-provider-session-repair/README.md) · [简体中文](codex-cross-provider-session-repair/README.zh-CN.md) |
| `codex-doctor` | Analyze local Codex session telemetry and find evidence-backed workflow improvements. | `0.1.2` | [English](codex-doctor/README.md) · [简体中文](codex-doctor/README.zh-CN.md) |
| `github-repo-i18n` | Keep selected repository documentation aligned across locales. | `0.1.1` | [English](github-repo-i18n/README.md) · [简体中文](github-repo-i18n/README.zh-CN.md) |
| `public-release-gate` | Review release metadata, artifacts, licenses, deployment state, and attachments. | `0.1.2` | [English](public-release-gate/README.md) · [简体中文](public-release-gate/README.zh-CN.md) |
| `public-repo-git-gate` | Check public content and Git boundaries before commit, push, or pull request. | `0.1.2` | [English](public-repo-git-gate/README.md) · [简体中文](public-repo-git-gate/README.zh-CN.md) |
| `shadow-skill-publisher` | Validate, package, and track a local Agent Skill before manual publication. | `0.2.0` | [English](shadow-skill-publisher/README.md) · [简体中文](shadow-skill-publisher/README.zh-CN.md) |
| `test-scope-routing` | Select the smallest sufficient validation scope for a change. | `0.1.2` | [English](test-scope-routing/README.md) · [简体中文](test-scope-routing/README.zh-CN.md) |

## Install

Install one Skill for a supported agent:

```bash
npx skills add WardLu/skills --skill <skill-name> --global --agent <agent-name> --yes
```

Replace `<skill-name>` and `<agent-name>` with the values for your task and
agent. To install the whole collection, use `--skill '*'`. The command requires
Node.js/npm.

Manage installed Skills with the same CLI:

```bash
npx skills list
npx skills update <skill-name>
npx skills remove <skill-name>
```

## Safety

Each Skill documents its own scope and compatibility. Read its README before
use, keep credentials and real user data out of prompts and packages, and treat
an unverified or blocked result as a request for review rather than success.

## For maintainers

- Each Skill owns its `SKILL.md`, version, README locales, and any required
  references or tests.
- Keep user-facing claims, compatibility, and version indexes synchronized
  when a Skill changes.
- Run the repository validation workflow in
  [`.github/workflows/validate-skills.yml`](.github/workflows/validate-skills.yml)
  before merging or releasing.
- Use the relevant Skill README and the collection [CHANGELOG](CHANGELOG.md)
  for contribution and release context.

## License

The collection and its Skills are released under the [MIT License](LICENSE).

## Contact

Interested in B2B products, AI product development, supply-chain digitalization,
or the Shadow product line? Feel free to reach out:

- **X (Twitter)** — [@Gollumgulu](https://x.com/Gollumgulu)
- **WeChat Official Account** — ![WeChat Official Account QR code](https://cdn.jsdelivr.net/gh/WardLu/mypic/images%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7.jpg)
- **Xiaohongshu (RED) / Weibo / Douyin** — same handle「Ward的AI产品实战」across platforms: [Xiaohongshu (RED)](https://xhslink.cn/m/4W1NWyRrxv5) · [Weibo](https://weibo.com/u/8344390431) · [Douyin](https://v.douyin.com/1y06PMohfoE/)
- **Email** — [wardlu@126.com](mailto:wardlu@126.com)
