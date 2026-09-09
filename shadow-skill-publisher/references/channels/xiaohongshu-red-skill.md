# Xiaohongshu Red Skill channel contract

Use the official Xiaohongshu creator entry point:
`https://creator.xiaohongshu.com/`.

## Scope boundary

The adapter covers only Red Skill packaging and submission. It excludes all
note-oriented behavior:

- no `note_content`
- no note creation
- no note publishing
- no note-to-Skill mounting

The adapter therefore binds only Skill-surface metadata and evidence, not note text or note-distribution actions.

## Required prepared fields

Red Skill staging prepares these deterministic fields before artifact packaging and upload planning:

- `skill_identity`
- `skill_version`
- `functionality`
- `applicability`
- `dependencies`
- `required_permissions`
- `third_party_apis_models`
- `workflow_summary`
- `data_handling`
- `limitations`
- `risk_disclosure`
- `license`
- `agreement_id`
- `rights_declaration`

Field rules:

- `skill_identity` stays bound to the frozen `SourceSnapshot.name`.
- `skill_version` stays bound to the frozen source version.
- `functionality` stays bound to the frozen source description.
- `applicability`, `dependencies`, `required_permissions`, `third_party_apis_models`, `data_handling`, `limitations`, and `risk_disclosure` render directly from dossier facts without inferring note behavior.
- `workflow_summary` records the Red Skill flow only: upload and registration, review submission, approval, install-prompt resolution, and live verification.
- `license` prefers an explicit dossier fact and otherwise falls back to the first non-empty license line.
- `agreement_id` is recorded in staging and currently defaults to `ZXXY20260518001` unless a newly observed agreement identifier is supplied for the attempt.
- `rights_declaration` must stay bound to the same `agreement_id`, so an agreement change changes the confirmation payload and requires a fresh confirmation.

## Agreement and confirmation boundary

The default agreement identifier is `ZXXY20260518001`.

The adapter keeps agreement handling conservative:

- the agreement identifier is part of the staged fields;
- the rights declaration repeats the same agreement identifier;
- the upload confirmation digest therefore changes whenever the agreement identifier changes.

This means an agreement change is never silently reused under an older confirmation.

## Evidence separation

Keep these evidence categories separate:

- `upload_completed`
- `registration_acknowledged`
- `review_submitted`
- `approved`
- `install_prompt_resolved_to_target_version`
- `live`

None of the states above may stand in for another one.

- Uploading a package does not prove Skill registration.
- Upload completion does not prove registration acknowledgement.
- Registration does not prove review submission.
- Review submission does not prove approval.
- Approval does not prove the install prompt resolves to the target version.
- An install prompt is evidence only after it resolves to the target version.
- A resolved install prompt does not prove the Skill is already live.

## Drift boundary

If the creator flow shows a different agreement, required field set, or
install-prompt behavior than this contract, stop guessing and record
`channel_contract_unverified`.

Manual completion remains limited to the Red Skill surface. Operators must not expand the run into note creation, note publishing, or note-to-Skill mounting just to work around contract drift.
