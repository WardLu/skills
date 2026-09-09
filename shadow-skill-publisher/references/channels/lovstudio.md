# LovStudio channel contract

Use these public LovStudio references as the contract source:

## Official entry points

- Catalog entry: `https://lovstudio.ai/skills`
- Public detail page pattern: `https://lovstudio.ai/skills/<catalog-slug>`
- CLI contract: `https://github.com/lovstudio/cli`

Use only the listed catalog and CLI references. Do not infer undocumented
fields or copy behavior from unrelated repositories.

## Required prepared fields

LovStudio staging prepares these deterministic fields before artifact packaging and submission planning:

- `name`
- `title`
- `concise_description`
- `version`
- `license`
- `source_url`
- `support_url`
- `install_command`
- `permissions`
- `risks`
- `limitations`

Field rules:

- `name` stays bound to the frozen `SourceSnapshot.name`.
- `title` is a display title derived from the install/catalog slug.
- `concise_description` stays bound to the frozen source description.
- `version` stays bound to the frozen source version.
- `license` prefers an explicit dossier fact and otherwise falls back to the first non-empty license line.
- `source_url` must come from an explicit dossier fact or provenance record. Missing public source evidence is contract drift, not a fallback case.
- `support_url` uses the dossier support link and falls back to `source_url` when no separate support page is declared.
- `install_command` uses the current LovStudio CLI path: `npx -y lovstudio@latest skills add <catalog-slug>`.

## Public evidence and live rule

The public detail page currently exposes the signals this adapter relies on:

- a visible current version label on the skill detail page;
- an install command block using `npx -y lovstudio@latest skills add <catalog-slug>`;
- a source link to the public repository;
- a compatibility / permissions / license section.

`live` evidence requires both:

1. the public detail page for the target skill shows the target version; and
2. the visible install path resolves to the same skill being published.

If either signal is missing, mismatched, or points at another slug, stop automated completion and record `channel_contract_unverified`.

## Catalog slug boundary

The adapter does not guess or normalize catalog slugs. By default it uses the frozen `SourceSnapshot.name` exactly for the install command and display-title input. If a future verified contract introduces a separate catalog-slug field, that value must be consumed exactly as documented rather than inferred by prefix stripping or other rewrite rules.

## Status mapping

Documented public strings currently mapped by the adapter:

- `Not published yet` -> `draft`
- `Published` -> `live`
- `Ready to install` -> `live`

Unknown status text must remain unmapped.

## Drift boundary

Do not encode automatic pricing, bundled entitlement behavior, or
LovStudio-specific brand copy from live pages into the adapter. Those behaviors
may change independently of the deterministic submission fields above.
