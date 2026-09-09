# Shadow Skill Publisher

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.3.0](https://img.shields.io/badge/version-0.3.0-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`shadow-skill-publisher` helps you check an Agent Skill before publication and
prepare a separate package, listing information, and status record for each
selected channel. It does not log in to platforms or publish on your behalf.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it does

- checks the Skill's structure, version, license, privacy, and package contents;
- derives safe local facts automatically instead of requiring a hand-written
  profile for the first check;
- prepares channel-specific ZIP files and the fields needed for a listing;
- keeps upload, submission, and publication status separate for later tracking.

Packages can currently be prepared for WorkBuddy, SkillPay, and Xiaohongshu Red
Skill. Zhihu AI Works is not available until its creator form can be observed
and verified.

Platform login, CAPTCHA/QR steps, and final submission remain user-controlled.
The local workflow needs no browser; a browser handoff is optional only when a
channel has no verified API or CLI and the user explicitly authorizes it.

When preparation needs browser observation, the agent can use the current
signed-in browser to read visible account/form facts, fill the exact plan, and
upload the exact ZIP. It stops before the final submit action for the user's
confirmation.

## Install

Install the Skill for a supported agent with the `skills` CLI:

```bash
npx skills add WardLu/skills --skill shadow-skill-publisher --global --agent <agent-name> --yes
```

Replace `<agent-name>` with the agent you use. After installation, ask that
agent to check and prepare the Skill you want to publish.

## Example

For example:

```text
Check and prepare /path/to/my-skill for WorkBuddy and SkillPay.
```

The Skill returns the validation result, channel packages, listing fields, and
the next confirmation or handoff step. When a channel needs identity, copy, or
live-form facts that cannot be inferred safely, the agent asks only for those
missing inputs and keeps the channel blocked until they are supplied.

## Safety

- Do not put passwords, cookies, tokens, QR payloads, private paths, or real
  user data in the Skill source, archive, or chat.
- Each package is tied to the selected source, version, channel, and account;
  changes that cannot be verified stop the workflow for review.
- Upload and submission require separate, explicit confirmations. A chat reply
  such as “agree” does not bypass those confirmations.

<details>
<summary>For maintainers</summary>

Run the offline checks and inspect the command surface with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/publisher.py --help
```

Keep channel-specific behavior in `references/` and never add credentials,
private paths, or real user data to fixtures or examples.

</details>
