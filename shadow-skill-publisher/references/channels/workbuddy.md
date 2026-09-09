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

The adapter stages a WorkBuddy package view rooted at `skills/<skill-name>/`,
with `skills/<skill-name>/SKILL.md` as the canonical staged definition path.

The final ZIP contains that single `skills/<skill-name>/` runtime tree. It does not duplicate `SKILL.md`, `references/`, `scripts/`, or `templates/` at the ZIP root. A root `LICENSE` may remain so the distributed package carries the applicable license text.

## Frontmatter contract

The official page documents these WorkBuddy Skill frontmatter fields:

- `description` (required)
- `description_zh` (required)
- `description_en` (required)
- `version` (required)
- `author` (required)
- `allowed-tools` (optional, comma-separated)

The page also shows `name` in the example Skill definition; the adapter binds
it to the frozen `SourceSnapshot.name`.

The adapter preserves the source Markdown body and injects only WorkBuddy
metadata into staging. The staged frontmatter must include:

- frozen `name`
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

## Resource-directory rule

The official page documents the semantic role of these optional subdirectories:

- `references/`: supplementary documents read as execution context
- `scripts/`: executable scripts invoked by the Bash tool
- `templates/`: reusable template files

The adapter records the present top-level resource directories from the frozen
source snapshot and mirrors those files into the staged package view.

## Drift boundary

The official Skill page does not document a stable textual contract for
review-status or approval-status labels. `map_status()` therefore remains empty
for WorkBuddy; future UI status strings are unverified until documented.

## Manual fallback

If automation cannot trust the WorkBuddy package or the platform flow drifts:

1. Upload the exact artifact ZIP for the target attempt with the intended WorkBuddy account alias through `Add Skill -> Create Skill`.
2. If parsing fails, inspect the ZIP and verify that `skills/<skill-name>/SKILL.md` exists and that its staged frontmatter still contains the documented fields.
3. Record separate evidence for `zip_parsed`, `review_submitted`, `approved`, `marketplace_visible`, and `installed_in_conversation`, including the exact observed page text or error text for each state.

The fallback is intentionally specific; “upload manually” alone is not sufficient evidence.
