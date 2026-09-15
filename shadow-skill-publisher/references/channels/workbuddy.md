# WorkBuddy channel contract

Use the official WorkBuddy Open Platform Skill documentation:
`https://open.workbuddy.cn/en/docs/skill`.

## Official entry point

The adapter uses this page as the contract source for WorkBuddy packaging,
frontmatter, marketplace placement, and resource-directory structure.

## Marketplace and evidence boundaries

The official page documents these user-visible steps and signals:

- Skills appear in the WorkBuddy marketplace under `Experts · Skills · Connectors -> Skills`.
- Users install a listed skill from the marketplace with the plus button in the upper-right corner of a skill card.
- Skill creation starts from `Add Skill -> Create Skill`.
- ZIP parsing may fail during creation; the same page tells operators to compare the package against the documented Skill structure before escalating.

Keep these evidence categories separate:

- `zip_parsed`: the uploaded ZIP is accepted without the documented parsing failure.
- `review_submitted`: the draft was submitted for review.
- `approved`: review approval was observed.
- `marketplace_visible`: the skill is visible in the marketplace as the expected listing.
- `installed_in_conversation`: the marketplace plus-button flow installs a usable skill in a conversation.

Before publishing the first approved Skill, verify the account-level developer
profile. WorkBuddy blocks publication until the public avatar, globally unique
nickname, introduction, and at least one contact method are saved. The observed
2026-09-13 form accepted JPG/PNG avatars up to 100 KB, introductions up to 120
characters, and one to five contact methods. Store only a boolean verification
receipt and hashes of public values in private publisher state; do not put the
profile or local avatar path into Skill packages.

Approval produces the separate `待发布` state. Publishing then requires an
explicit mode choice:

- `public`: visible to all users in the WorkBuddy marketplace;
- `dedicated`: visible only inside Buddy applications under the same account.

Never rely on the dialog default. Bind the selected mode into the submission
digest and wait until the card reads `已发布 · 公开` or the exact dedicated
equivalent. Email is only a reason to refresh status, not approval evidence.

An observed update withdrawal does not release its version number. WorkBuddy
continues to require the next uploaded `SKILL.md` version to be greater than
the withdrawn version, even when the marketplace card still shows the older
published version. Treat every accepted upload version as consumed and
preflight the next version before rebuilding listing fields or assets.

None of the states above may stand in for another one. Uploading a ZIP does not prove review submission. Review submission does not prove approval. Approval does not prove marketplace visibility. Marketplace visibility does not prove installation in a conversation.

## Required staged package shape

The official Skill page shows this package structure:

```text
skills/
└── {skill-name}/
    ├── SKILL.md
    ├── references/
    ├── scripts/
    └── templates/
```

The adapter stages a WorkBuddy package view rooted at `<skill-name>/`,
with `<skill-name>/SKILL.md` as the canonical staged definition path.

The final ZIP contains exactly one root entry: the `<skill-name>/` runtime tree.
It does not place sibling files beside that directory. `LICENSE` and
`_skillhub_meta.json` therefore live inside `<skill-name>/` alongside
`SKILL.md`. This is required by the WorkBuddy desktop installer: it descends
into a single root directory, then requires `SKILL.md` in the resolved source
directory.

## Frontmatter contract

The official page documents these WorkBuddy Skill frontmatter fields:

- `description` (required)
- `description_zh` (required)
- `description_en` (required)
- `display_name` (required)
- `display_name_en` (required)
- `version` (required)
- `author` (required)
- `allowed-tools` (optional, comma-separated)

The page also shows `name` in the example Skill definition; the adapter binds
it to the frozen `SourceSnapshot.name`.

The adapter preserves the source Markdown body and injects only WorkBuddy
metadata into staging. The staged frontmatter must include:

- frozen `name`
- derived or verified `display_name`
- derived or verified `display_name_en`
- frozen `description`
- verified `description_zh`
- verified `description_en`
- frozen `version`
- verified `author`
- verified `allowed-tools`
- staged-only WorkBuddy package metadata:
  - `workbuddy-package-root`
  - `workbuddy-skill-path`
  - `workbuddy-resource-directories`

The adapter does not rewrite the source repository copy of `SKILL.md`.

The official documentation does not define a frontmatter field for the
marketplace's `试试这样问我` quick prompts. WorkBuddy's installed marketplace
packages use a separate `_skillhub_meta.json` alongside the resolved
`SKILL.md`, with `examples_zh` and
`examples_en` arrays; the adapter emits those fields when the private profile
provides them. A live Create Skill contract check on 2026-09-09 showed that the
upload parser does not expose this metadata in the draft preview, so a preview
value of `-` is not proof that the eventual marketplace metadata was omitted.
Keep upload parsing, review submission, and marketplace visibility as separate
evidence gates.

## Resource-directory rule

The official page documents the semantic role of these optional subdirectories:

- `references/`: supplementary documents read as execution context
- `scripts/`: executable scripts invoked by the Bash tool
- `templates/`: reusable template files

The adapter records the present top-level resource directories from the frozen
source snapshot and mirrors those files into the staged package view.

## Drift boundary

The Open Platform UI observed on 2026-09-13 exposed `审核中`, `待发布`, and
`已发布` plus the publication scope `公开`. These live labels remain browser
evidence rather than an official API contract, so `map_status()` remains empty.

## Manual fallback

If automation cannot trust the WorkBuddy package or the platform flow drifts:

1. Upload the exact artifact ZIP for the target attempt with the intended WorkBuddy account alias through `Add Skill -> Create Skill`.
2. If parsing fails, inspect the ZIP and verify that `<skill-name>/SKILL.md` exists at the package root and that its staged frontmatter still contains the documented fields.
3. Record separate evidence for `zip_parsed`, `review_submitted`, `approved`, `marketplace_visible`, and `installed_in_conversation`, including the exact observed page text or error text for each state.

The fallback is intentionally specific; “upload manually” alone is not sufficient evidence.
