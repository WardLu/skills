# Zhihu AI Works channel contract

Use the public Zhihu AI Works entry point:
`https://www.zhihu.com/project-square`.

## Discovery result

Discovery is read-only until a creator contract is verified.

- The public entry point currently reaches a login or human-verification wall
  before AI Works creation fields become visible.
- No stable creator surface was available for read-only inspection.
- No draft was created.
- No file was uploaded.
- No field was submitted.

Because the required-field view is not observable without a signed-in creator
session, the adapter keeps the contract unverified and blocks with
`channel_contract_unverified`.

## Verified source boundary

The only verified first-party source is the public project-square URL above. No
stable creator form labels, accepted file types, length constraints, or
review-status strings are recorded until they can be observed without crossing
the login or verification wall.

## State boundary

When Zhihu discovery resumes, the workflow must keep these evidence categories separate:

- draft creation
- submission
- review outcome
- public AI Works page visibility

None of the states above may stand in for another one.

## Manual discovery handoff

To verify a future Zhihu contract, use a signed-in browser session and stop at the current AI Works creation surface before any write action. Record only what is visibly required on that page:

1. the exact required labels;
2. the accepted artifact type;
3. any visible title or description length limits; and
4. the separate page text or signals for draft creation, submission, review, and public visibility.

If any item above is blocked by login, verification, or UI drift, keep `channel_contract_unverified` and finish the publication manually without inventing hidden fields or selectors.
