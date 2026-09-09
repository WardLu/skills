# Optional private workspace configuration

The publisher can start without a user-authored profile. `check` builds an
in-memory profile from deterministic source facts. For prompt-only Skills, the
frozen `SKILL.md` is valid core source evidence; scripted Skills still need
execution or other verifiable evidence.

When `prepare` cannot infer a channel fact safely, it returns a classified
missing-input group. `needs_browser_observation` means the agent should read
the visible signed-in creator page and update the private profile. It should not
ask the user to type account aliases or platform fields. `user_confirmation_required`
means the agent may draft the value but the user must approve the final choice.
A stored profile is optional and exists to make later runs repeatable, not as a
prerequisite for the first check.

When `--profile` is supplied, that exact file is used. Otherwise the publisher
looks for `config/profile.json` under the resolved private workspace. Workspace
resolution order is:

1. The command's explicit `--home` value.
2. `SHADOW_SKILL_PUBLISHER_HOME`.
3. `~/.shadow-skill-publisher`.

The publisher never changes or repurposes `HOME`. The resolved workspace uses
this layout:

```text
config/profile.json
state/publisher.sqlite3
runs/<run-id>/{reports,dossiers,artifacts,plans,reviews,evidence}/
```

Path helpers only calculate locations. Commands create directories only when a
write is actually requested. A read-only `check --json` invocation does not
create the workspace or run directories.

Reports and evidence must pass through deterministic redaction before leaving
the private workspace. Redaction covers access tokens, API keys, database URL
passwords, private keys, cookie values, QR payloads, platform home paths, and
caller-supplied private values.

Example evidence profile:

```json
{
  "schema_version": 1,
  "author": {"display_name": "Example Author", "source_url": "https://example.com/source"},
  "capabilities": [
    {"id": "scan-staged-content", "core": true, "evidence": {"type": "command", "command": ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]}}
  ],
  "commercial": {"mode": "free", "currency": null, "price": null},
  "accounts": {"workbuddy": "primary"}
}
```

Generated profiles never invent identity or live channel verification. Typical
browser-observable fields include:

- `accounts.<channel>` for the visible account alias;
- creator identity, agreement, price-format, and form-contract observations for
  SkillPay.

The agent may derive or draft `description_zh` and `allowed_tools`
from the public source and channel contract, then ask only for final approval
when the value is not deterministic. Author ownership and commercial decisions
remain explicit user confirmations.

Visible account and form facts may be observed in any user-controlled browser.
Do not copy passwords, cookies, tokens, QR payloads, or browser storage into the
profile.

`author.display_name` and `author.source_url` become first-class Release Dossier facts. Keep channel-specific human copy outside the canonical Skill. `profile.json` may contain a private `channel_edits` mapping keyed by channel, for example `{"channel_edits": {"workbuddy": {"description": "Approved human copy"}}}`. Only safe text fields (`title`, descriptions, summaries, applicability, workflow, risks, and limitations) are accepted; generated identity, version, digest, permission, account, package, and price fields are rejected. `prepare` stores redacted `FrozenFields` bound to the source, channel, and attempt, reapplies the copy on later prepares for the same source/channel, and reports any changed generated facts separately. Generated fact hashes remain local metadata and are never inserted into channel-facing fields.

For WorkBuddy marketplace branding, the private profile may also provide
`display_name`, `description_zh`, `description_en`, `examples_zh`, and
`examples_en`. The WorkBuddy adapter keeps the executable `SKILL.md` contract
separate from the market metadata and writes the localized example arrays to
`_skillhub_meta.json`. These values are listing copy, not evidence claims; keep
them accurate and do not place credentials or private paths in them.

For non-command capability evidence, fail closed unless the profile records
explicit proof. `source` evidence needs a safe relative `path`, the current
`source_digest`, and a non-empty proof/summary. `user` and `official_page`
evidence need a non-empty observation summary plus an auditable `source_url`
or `record_id`.
