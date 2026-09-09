# Channel Contract

Every first-party publishing adapter must satisfy this shared contract before any browser automation or external write is allowed.

## Shared adapter surface

- `build_staging(snapshot, dossier)` returns a deterministic `ChannelStaging` with:
  - the exact CLI channel key;
  - a verified `contract_version`;
  - channel-scoped staged files only;
  - required semantic fields rendered from the frozen `SourceSnapshot` and `Dossier`;
  - disclosure metadata that records permissions, external services, claims, risks, limitations, and commercial settings;
  - a manual fallback sequence for contract drift or unsupported automation.
- `build_plan(staging, artifact, account_alias)` returns an unfinalized `SubmissionPlan` whose `upload_confirmation_digest` is canonical and whose `platform_id`, `observed_fields`, `final_action`, and `submission_confirmation_digest` are all empty.
- `map_status(raw_status)` only maps documented platform status strings to the shared `PublishState` enum. Unknown text returns `None`.

## Shared remote-execution boundary

- Browser or remote execution is allowed only after local observation has produced the current `SubmissionPlan`.
- Upload-facing actions such as prefill, upload, and registration must stay bound to the current plan's exact `channel`, `account_alias`, artifact SHA-256, and upload digest.
- Submission-facing actions such as `submit_review` and `publish` require a finalized plan, a submission digest derived from that finalized plan, and a second authorization distinct from the upload authorization.
- The submission or unknown-submission ledger boundary rechecks both the current upload digest authorization and the current submission digest authorization. The recorded action must equal the finalized plan's `final_action`.
- The common observe -> authorize -> act -> verify -> record -> handoff sequence is mandatory for every channel. Unknown state at any step remains unknown until read-back evidence resolves it.

## Confirmation digests

- Upload confirmation uses canonical UTF-8 JSON with sorted keys and compact separators.
- The upload digest binds:
  - `channel`;
  - `contract_version`;
  - `account_alias`;
  - artifact `channel`, `sha256`, `size_bytes`, and file list;
  - declared `permissions`;
  - declared `external_services`;
  - a disclosure summary of staged fields, claims, data handling, risks, and limitations.
- Submission confirmation is unavailable until the plan is finalized.
- Finalization requires:
  - the platform draft/product ID, or an adapter-defined local preview ID when the contract has no prior remote write;
  - the exact observed/rendered fields confirmed on the target platform;
  - the final action, either `submit_review` or `publish`.
- The submission digest binds the upload payload plus:
  - `platform_id`;
  - `observed_fields`;
  - `final_action`;
  - `commercial_mode`;
  - `price`.

## Handoff packet

- Manual or browser handoff must be built from the current plan only.
- The handoff packet must include:
  - the verified target URL from the channel reference;
  - the exact `channel` and `account_alias`;
  - the exact artifact path, SHA-256, and staged file list;
  - every staged field and value;
  - the current upload digest;
  - the expected intermediate state and channel-specific fallback instructions.
- After finalization, the handoff packet must also include the exact `platform_id`, exact `observed_fields`, selected `final_action`, and current submission digest.
- Handoff must never require credentials, cookies, tokens, QR payloads, or undocumented platform storage to be copied into chat.

## Drift handling

- Adapters must declare:
  - `key`;
  - `contract_version`;
  - official source URLs;
  - required semantic fields;
  - optional semantic fields;
  - allowed commercial modes;
  - documented status mappings;
  - public verification signals.
- `build_staging()` may also emit channel-scoped files through `render_files(snapshot, dossier)`, which defaults to an empty mapping in the base adapter.
- If required fields are missing or unknown fields appear outside the declared required plus optional sets, the adapter must raise `ChannelContractError` with code `channel_contract_unverified`.
- On `channel_contract_unverified`, the workflow must stop guessing selectors or submit actions and fall back to the adapter's manual instructions.
- If the live surface reaches login, CAPTCHA, QR scan, a platform confirmation wall, user takeover, or an inactive browser space, the workflow must pause and hand off instead of continuing heuristically.

## Status evidence boundary

- Each adapter documents its own evidence categories and public signals. Shared logic must not invent extra platform-specific fields or statuses.
- `map_status()` may return only documented states. Unknown raw text must remain unmapped and cannot be reported as success.
- Read-back evidence must preserve the exact visible status text, exact platform identifier, and exact rendered fields used to justify a state transition.
- `review_submitted`, `under_review`, `approved`, and `live` records require non-empty raw status, the finalized target identifier, and the matching frozen source version. `live` additionally requires a non-empty public URL.
- Parsing, registration, review submission, approval, publication, marketplace visibility, and installability remain distinct states unless the channel reference explicitly proves otherwise.

## Registry

The registry is keyed by the five CLI channel names:

- `lovstudio`
- `workbuddy`
- `skillpay`
- `zhihu-ai-works`
- `xiaohongshu-red-skill`

- Verified channel adapters currently exist for:
  - `lovstudio`
  - `workbuddy`
  - `skillpay`
  - `xiaohongshu-red-skill`
- `zhihu-ai-works` remains an explicit unverified placeholder that must block automation with `channel_contract_unverified` instead of inventing runtime behavior.
