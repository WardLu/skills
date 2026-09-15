# Browser Execution and Human Handoff

Use this reference when a verified channel contract requires a human-operated browser step or when automation must pause. It defines the minimum packet that may leave the local publisher context without expanding scope into credential handling or undocumented platform behavior.

The browser path is optional. The publisher's local checks, packaging, confirmations, and status tracking do not require Ego or another browser runtime. Manual handoff works with any user-controlled browser, including Chrome or Safari. A host agent may use a verified browser tool when available, but this Skill does not install it, manage its login state, copy browser sessions, or treat its presence as proof of a platform contract.

## Execution priority

1. Prefer the channel's verified official API or CLI when the channel reference documents one.
2. Use a verified browser tool available to the host agent, or hand off to any user-controlled browser, only when no verified API or CLI exists and the browser surface itself is part of the verified contract. Ego is one optional provider.
3. Pause immediately when the flow hits login, CAPTCHA, QR scan, platform confirmation, user takeover, or an inactive browser space.

Do not request, paste, or store passwords, session cookies, tokens, QR payloads, or copied browser storage in chat.

## Browser-assisted preparation

When `prepare` returns `needs_browser_observation`, the agent should complete the
following loop:

1. Open the channel's documented creator or upload page in the host-controlled
   browser. Prefer the user's current signed-in tab when the host provides that
   capability; use Ego for an isolated signed-in space when available; otherwise
   hand off to the user's Chrome, Safari, or other browser.
2. Confirm the visible account identity. If the page is logged out, return
   `login_required` and ask the user to log in in that browser; never ask for
   credentials or extract the browser session.
3. Read only the visible account, agreement, price-format, and form-contract
   facts already required by the channel reference. Update the private profile
   with those observations and rerun `prepare`.
4. After the exact plan and ZIP exist, open the same target page, fill only the
   plan fields, upload the exact artifact, and read back every rendered value.
5. Stop at the final review/submit page. Return the visible account, fields,
   artifact, and current status for the user's final confirmation.

For account-level prerequisites such as a public developer profile, resolve the
profile once before iterating approved items. Cache only non-secret verification
facts. After an email or notification, refresh the full item list because more
than one item may transition while the batch is running. Execute account-bound
publishing serially and read back every item card after each delayed response.

The browser session remains owned by the browser. Publisher evidence may retain
redacted observations and timestamps, but never cookies, tokens, passwords,
QR payloads, or browser storage.

## Required handoff packet

Before any browser action, provide a bounded packet that matches the current `SubmissionPlan` exactly:

- `target_url`: the verified creator or upload URL from the selected channel reference.
- `channel`: the exact CLI channel key.
- `account_alias`: the exact plan account alias.
- `artifact_path`: the exact ZIP path on disk.
- `artifact_sha256`: the exact ZIP SHA-256 from the plan.
- `artifact_files`: the exact staged file list from the artifact.
- `upload_digest`: the current upload confirmation digest.
- `fields`: every staged field as exact `key=value` content from `plan.fields`.
- `expected_intermediate_state`: the next state the operator should observe before returning control.
- `manual_fallback`: the channel-specific fallback instructions from the current plan.

If the plan has already been finalized, also include:

- `platform_id`: the exact draft, product, or adapter-defined local preview ID.
- `observed_fields`: every exact read-back field/value pair used for finalization.
- `final_action`: `submit_review` or `publish`.
- `submission_digest`: the current finalized submission digest.

## Allowed browser actions

The browser operator may only:

- open the verified `target_url`;
- confirm the visible account matches `account_alias`;
- read the visible fields needed to resolve `needs_browser_observation`;
- upload the exact artifact identified by `artifact_path` and `artifact_sha256`;
- prefill or register only the exact field/value pairs already present in the plan;
- read back the visible draft ID, product ID, rendered fields, and raw status text;
- stop before the final submit or publish action.

The browser operator must not:

- invent selectors, hidden fields, or undocumented submit flows;
- switch to another account, artifact, or channel;
- infer success from navigation alone, a toast alone, or a pending screen;
- continue past a verification wall or platform confirmation without pausing.

## Evidence to return

When control returns from a human-operated browser step, capture evidence as exact observed facts:

- the final visited URL after the action;
- the visible account identifier or alias text, if the platform shows one;
- the uploaded artifact filename and any visible digest, checksum, or file-size confirmation;
- the exact raw status text shown by the platform;
- the exact draft or product ID, if shown;
- the exact rendered field/value pairs visible on the page;
- the exact blocker text if the flow paused for login, CAPTCHA, QR, confirmation, takeover, inactivity, or contract drift.

If the platform does not show one of the items above, report it as unavailable. Do not replace missing evidence with inference.

## Contract drift

If the live surface asks for a field that is not already declared in the verified channel contract, or if a required documented field is missing, stop and report `channel_contract_unverified`. The fallback is to return the observed drift and complete the platform action manually outside this Skill, not to guess the missing behavior.
