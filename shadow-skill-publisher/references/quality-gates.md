# Quality Gates

The publisher evaluates a local Skill through six layers that stay deterministic
until the workflow reaches an explicitly authorized external write.

## 1. Source contract

- The source root must already load as a valid `SourceSnapshot`.
- Required metadata, an in-scope license, and in-root resources remain blocking.
- Internal/private workspace directories are never publishable source content.

## 2. Functional evidence

- Every `core` capability in the local profile needs verified evidence before
  upload is allowed.
- Unsupported `optional` claims are removed from the publishable dossier before
  they become warnings, so they cannot silently ship as unverified marketing.
- Profile-declared command evidence starts as unevidenced until an approved
  execution plan has run.
- Non-command evidence also fails closed until it carries explicit, auditable
  proof. `source` evidence must bind a safe in-snapshot relative `path`, the
  current `source_digest`, and a non-empty proof/summary. `user` and
  `official_page` evidence must include a non-empty observation summary plus an
  auditable `source_url` or `record_id`.

## 3. Security and privacy

- Deterministic scanning blocks likely secrets, credential-bearing URLs, and
  private personal paths.
- Binary files remain visible as warnings for manual review.
- Command evidence that implies destructive writes or network access must be
  disclosed and explicitly authorized before use.

## 4. Source-bound execution authorization

- Every local command runs through an `ExecutionPlan`.
- The execution digest binds the current `source_digest`, exact argument arrays,
  resolved working directory, timeout, and permitted environment-variable names.
- `check` without `--exec-digest` prints the current plan only. Execution is
  allowed later only when the caller supplies the exact freshly recomputed
  digest.
- `prepare` applies the same rule. Command-backed core evidence remains blocked
  unless `prepare --exec-digest` matches the plan freshly recomputed from that
  invocation; a match executes the commands in that same process before the
  quality decision and artifact preparation.
- Commands always execute as argument arrays with a minimal inherited
  environment and captured redacted output. `shell=True` is forbidden.

## 5. AI review import

- Imported AI review must be UTF-8 JSON with `schema_version: 1`, the exact
  `source_digest`, and bounded findings whose provenance is `ai_inference`.
- AI findings may add warnings or blocks, but they can never remove or weaken
  deterministic findings.
- `check --ai-review FILE` validates and reads the AI review in read-only mode
  without writing into the private workspace.
- `prepare --ai-review FILE` stores a validated, redacted copy under the
  private attempt evidence tree at `runs/<run-id>/reviews/ai-review.json`.

## 6. Final artifact verification

- `prepare` verifies each final ZIP and sidecar manifest before creating a
  ledger attempt or confirmation plan.
- Any blocking archive finding produces a channel-local blocked result and the
  unverified ZIP and manifest are discarded from the private run tree.
- A blocked channel does not erase a successfully prepared channel attempt.
