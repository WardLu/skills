# Release Checklist

> This file is the fixed, human-readable release entry for an independently releasable project. Keep it at `docs/release-checklist.md` relative to that project's root. Copy this structure into the project and replace every template status before using it as release evidence.

## Release identity

- Project: `[project name]`
- Version / tag: `[version and tag]`
- Release commit SHA: `[full SHA]`
- Release mode: `code_only` | `migration_only` | `release_only` | `full_release`
- Owner / UTC timestamp: `[owner / YYYY-MM-DDTHH:MM:SSZ]`
- Evidence index: `[local path or durable URL; never include secrets]`

## Status contract

Every item below must contain exactly one of these statuses:

- `completed` — the item was executed and includes evidence that another person can inspect.
- `N/A` — the item does not apply to this release and includes a concrete reason.
- `blocked` — the item cannot yet be completed and includes the blocker plus the next action or owner.

Do not use `pending`, `skipped`, `passed`, `failed`, or an empty checkbox as a substitute status. A release with any `blocked` item is not ready to pass the Release gate. A `completed` item without evidence, or an `N/A` item without a reason, is incomplete.

## 1. Scope, version, and release inputs

- Scope and release mode are recorded. Status: `blocked` — reason: template only; next: replace with the release-specific classification; owner: release owner.
- Version sources, changelog, release notes, and target tag agree. Status: `blocked` — reason: template only; next: inspect the project's configured version sources; owner: release owner.
- The final commit and intended release target are fixed. Status: `blocked` — reason: template only; next: record the exact SHA and tag before proceeding; owner: release owner.

## 2. Code, tests, and build artifacts

- Required code and focused tests have run using project-defined commands. Status: `blocked` — reason: template only; next: record commands, results, and artifact paths; owner: release owner.
- Required full verification, build, packaging, or security checks have run for this release mode. Status: `blocked` — reason: template only; next: record exact results or mark `N/A` with a reason; owner: release owner.
- Final artifacts were inspected, including archives, generated files, and checksums where applicable. Status: `blocked` — reason: template only; next: record paths and SHA-256 values; owner: release owner.
- Publicity and sensitive-data scan found no secrets, personal/customer data, internal material, or unnecessary public files. Status: `blocked` — reason: template only; next: record the scan scope and result; owner: release owner.
- Third-party code, models, WASM, fonts, and media have matching source, license, redistribution terms, and SHA-256 evidence. Status: `blocked` — reason: template only; next: record notices or mark `N/A` with a reason; owner: release owner.

## 3. Database migrations

- Migration order, application state, schema/functions/RLS checks, and business smoke evidence are recorded. Status: `blocked` — reason: template only; next: use the project's safe migration procedure or mark `N/A` with a reason; owner: release owner.
- Production migration is separately confirmed, or explicitly held behind its authorization gate. Status: `blocked` — reason: template only; next: do not treat CI or Preview as production evidence; owner: release owner.

## 4. Functions and data repair

- Edge/server Functions changed by this release were tested and their deployed version is identified. Status: `blocked` — reason: template only; next: record function names, version/SHA, and test evidence or mark `N/A` with a reason; owner: release owner.
- Data repair, backfill, or entitlement correction was executed and verified, or is explicitly not applicable. Status: `blocked` — reason: template only; next: never use real user data in local validation; owner: release owner.

## 5. Configuration and CDN

- Environment/configuration changes are identified, reviewed, and applied only in the authorized environment. Status: `blocked` — reason: template only; next: record the non-secret variable/config names and evidence or mark `N/A` with a reason; owner: release owner.
- CDN, cache, Service Worker, static resource, and invalidation behavior is verified where applicable. Status: `blocked` — reason: template only; next: record URLs, headers, cache state, or mark `N/A` with a reason; owner: release owner.

## 6. Preview

- The exact Preview deployment, commit SHA, and environment are identified. Status: `blocked` — reason: template only; next: record the deployment URL and SHA or mark `N/A` with a reason; owner: release owner.
- Critical Preview journeys and release-specific checks pass with inspectable evidence. Status: `blocked` — reason: template only; next: record the journey, viewport/device where relevant, and result; owner: release owner.

## 7. Production

- Production deployment or promotion is separately authorized and identified. Status: `blocked` — reason: template only; next: obtain separate authorization and identify the deployment; owner: release owner.
- Production health, headers, critical routes, data boundaries, and release behavior are verified. Status: `blocked` — reason: template only; next: record timestamps, URLs, response evidence, and operator; owner: release owner.

## 8. Rollback and recovery

- Rollback target, trigger conditions, owner, and exact recovery command/procedure are recorded. Status: `blocked` — reason: template only; next: record the known-good SHA/tag and safe procedure; owner: release owner.
- Rollback readiness was tested or is marked `N/A` with a concrete reason and residual risk. Status: `blocked` — reason: template only; next: do not claim readiness from a plan alone; owner: release owner.

## 9. Evidence and final decision

- Evidence is complete, durable, redacted, and linked from this file. Status: `blocked` — reason: template only; next: do not include tokens, personal data, backups, or private logs; owner: release owner.
- Existing project `release:check`, CI, and Release Watcher results are attached or marked `N/A` with reasons. Status: `blocked` — reason: template only; next: reuse existing automation and do not create a new controller or state store; owner: release owner.
- Tag, Release page, and every attachment match the scanned final artifacts and recorded hashes, or are marked `N/A` with a reason. Status: `blocked` — reason: template only; next: do not create or edit a Release as part of local validation; owner: release owner.
- Final Release gate decision is recorded as `PASS`, `BLOCKED`, or `FAILED` with residual risks. Status: `blocked` — reason: template only; next: `PASS` requires every applicable item to be `completed` or justified `N/A`; owner: release owner.

## Notes

- This checklist is a human-readable receipt, not a Release Manifest, state machine, controller, or cross-project database.
- Git commit/push/PR checks remain the responsibility of `public-repo-git-gate`; Tag, artifact, deployment, and Release attachment checks remain the responsibility of `public-release-gate`.
- A local implementation, Preview result, pending CI check, or HTTP `200` alone is not production evidence.
