"""Local SQLite ledger for publisher lifecycle state."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Optional

from .models import Artifact, FrozenFields, PublishState, SourceSnapshot, SubmissionPlan
from .paths import source_id as build_source_id
from .redaction import redact_text
from .state import can_transition


SCHEMA_VERSION = 1
_DEFAULT_RUN_ID = "local"
_FINAL_ACTIONS = {"submit_review", "publish"}
_EVENT_ACTIONS = {"review_submitted": "submit_review", "publish": "publish"}
_BLOCKING_FLAGS = frozenset(
    (
        "remote_drift",
        "qualification_required",
        "quota_exhausted",
        "channel_contract_unverified",
        "retry_exhausted",
        "concurrent_attempt",
    )
)
_RECOVERY_RECORD_EVENTS = frozenset(
    (
        "remote_drift_resolved",
        "qualification_resolved",
        "quota_resolved",
        "channel_contract_verified",
        "retry_exhausted_resolved",
        "ownership_handoff",
        "ownership_cancelled",
        "ownership_claim_cancelled",
    )
)
_BLOCKER_RECOVERY_EVENTS = {
    "remote_drift": "remote_drift_resolved",
    "qualification_required": "qualification_resolved",
    "quota_exhausted": "quota_resolved",
    "channel_contract_unverified": "channel_contract_verified",
    "retry_exhausted": "retry_exhausted_resolved",
    "concurrent_attempt": frozenset(("ownership_handoff", "ownership_cancelled")),
}
_TIMESTAMP_COLUMNS = {
    PublishState.SUBMITTED: "submitted_at",
    PublishState.SUBMISSION_UNKNOWN: "submitted_at",
    PublishState.APPROVED: "approved_at",
    PublishState.LIVE: "published_at",
}
_VERIFIED_STATES = frozenset(
    (
        PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        PublishState.SUBMITTED,
        PublishState.UNDER_REVIEW,
        PublishState.CHANGES_REQUESTED,
        PublishState.REJECTED,
        PublishState.APPROVED,
        PublishState.LIVE,
        PublishState.SUPERSEDED,
        PublishState.DELISTED,
    )
)
_ROW_COLUMNS = (
    "run_id",
    "status",
    "raw_status",
    "source_id",
    "skill_name",
    "version",
    "channel",
    "contract_version",
    "account_alias",
    "product_id",
    "public_url",
    "artifact_sha256",
    "created_at",
    "submitted_at",
    "approved_at",
    "published_at",
    "last_verified_at",
    "evidence_summary",
    "next_action",
    "final_action",
)


class InvalidTransition(ValueError):
    """Raised when a requested state mutation violates the PRD graph."""


class AuthorizationRequired(ValueError):
    """Raised when an external-write state change lacks matching authorization."""


class RecoveryBlocked(ValueError):
    """Raised when local recovery metadata blocks automated continuation."""


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    source_id: str
    source_digest: str
    source_version: str
    skill_name: str
    channel: str
    contract_version: str
    account_alias: str
    artifact_sha256: str
    state: PublishState
    raw_status: Optional[str]
    product_id: Optional[str]
    public_url: Optional[str]
    created_at: str
    submitted_at: Optional[str]
    approved_at: Optional[str]
    published_at: Optional[str]
    last_verified_at: Optional[str]


@dataclass(frozen=True)
class BlockerRecord:
    flag: str
    evidence: Mapping[str, Any]
    recovery_commands: tuple[tuple[str, ...], ...]
    created_at: str


@dataclass(frozen=True)
class FailureStreak:
    failure_signature: str
    consecutive_count: int


@dataclass(frozen=True)
class OwnershipRecord:
    source_id: str
    source_digest: str
    source_version: str
    channel: str
    claim_ref: str
    owner_attempt_id: Optional[str]
    created_at: str


class Ledger:
    """Persist attempt state and evidence in a local SQLite database."""

    def __init__(self, path: Path, connection: sqlite3.Connection):
        self.path = Path(path)
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: Path) -> "Ledger":
        database_path = Path(path).expanduser().resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        ledger = cls(database_path, connection)
        ledger._initialize()
        return ledger

    @classmethod
    def open_readonly(cls, path: Path) -> "Ledger":
        database_path = Path(path).expanduser().resolve()
        connection = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return cls(database_path, connection)

    def close(self) -> None:
        self._connection.close()

    def create_attempt(
        self,
        snapshot: SourceSnapshot,
        channel: str,
        account_alias: str,
        contract_version: str,
        artifact: Artifact,
    ) -> str:
        with self._immediate_transaction():
            existing = self._connection.execute(
                """
                SELECT attempt_id
                FROM attempts
                WHERE source_digest = ? AND source_version = ? AND channel = ? AND artifact_sha256 = ?
                """,
                (snapshot.source_digest, snapshot.version, channel, artifact.sha256),
            ).fetchone()
            if existing is not None:
                return str(existing["attempt_id"])

            attempt_id = _attempt_id(snapshot, channel, artifact)
            created_at = _utcnow()
            source_identifier = build_source_id(snapshot.root)
            artifact_path = str(Path(artifact.path).expanduser().resolve())
            artifact_files = _dump_json(list(artifact.files))
            self._connection.execute(
                """
                INSERT OR IGNORE INTO artifacts (
                    artifact_sha256, channel, path, size_bytes, files_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.sha256,
                    artifact.channel,
                    artifact_path,
                    artifact.size_bytes,
                    artifact_files,
                    created_at,
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO attempts (
                    attempt_id, run_id, source_id, source_digest, source_version, skill_name,
                    channel, contract_version, account_alias, artifact_sha256,
                    state, raw_status, product_id, public_url,
                    created_at, submitted_at, approved_at, published_at, last_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    attempt_id,
                    _DEFAULT_RUN_ID,
                    source_identifier,
                    snapshot.source_digest,
                    snapshot.version,
                    snapshot.name,
                    channel,
                    contract_version,
                    account_alias,
                    artifact.sha256,
                    PublishState.DRAFT.value,
                    created_at,
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO events (
                    attempt_id, from_state, to_state, event, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    None,
                    PublishState.DRAFT.value,
                    "attempt_created",
                    _dump_json(
                        {
                            "source_digest": snapshot.source_digest,
                            "source_version": snapshot.version,
                            "artifact_sha256": artifact.sha256,
                        }
                    ),
                    created_at,
                ),
            )
        return attempt_id

    def get_attempt(self, attempt_id: str) -> AttemptRecord:
        row = self._connection.execute(
            """
            SELECT attempt_id, source_id, source_digest, source_version, skill_name, channel,
                   contract_version, account_alias, artifact_sha256, state, raw_status,
                   product_id, public_url, created_at, submitted_at, approved_at,
                   published_at, last_verified_at
            FROM attempts
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return AttemptRecord(
            attempt_id=row["attempt_id"],
            source_id=row["source_id"],
            source_digest=row["source_digest"],
            source_version=row["source_version"],
            skill_name=row["skill_name"],
            channel=row["channel"],
            contract_version=row["contract_version"],
            account_alias=row["account_alias"],
            artifact_sha256=row["artifact_sha256"],
            state=PublishState(row["state"]),
            raw_status=row["raw_status"],
            product_id=row["product_id"],
            public_url=row["public_url"],
            created_at=row["created_at"],
            submitted_at=row["submitted_at"],
            approved_at=row["approved_at"],
            published_at=row["published_at"],
            last_verified_at=row["last_verified_at"],
        )

    def find_platform_item(self, source_root: Path, channel: str, account_alias: str) -> Optional[Mapping[str, str]]:
        """Return the latest known remote identity for create-vs-update routing."""
        row = self._connection.execute(
            """
            SELECT product_id, public_url, source_version, state
            FROM attempts
            WHERE source_id = ? AND channel = ? AND account_alias = ?
              AND product_id IS NOT NULL AND TRIM(product_id) != ''
            ORDER BY COALESCE(last_verified_at, created_at) DESC, created_at DESC
            LIMIT 1
            """,
            (build_source_id(Path(source_root)), str(channel), str(account_alias)),
        ).fetchone()
        if row is None:
            return None
        return {
            "platform_id": str(row["product_id"]),
            "public_url": str(row["public_url"] or ""),
            "source_version": str(row["source_version"]),
            "state": str(row["state"]),
        }

    def save_submission_plan(self, attempt_id: str, plan: SubmissionPlan) -> None:
        attempt = self.get_attempt(attempt_id)
        if plan.channel != attempt.channel:
            raise ValueError("submission plan channel must match attempt channel")
        if plan.artifact.channel != attempt.channel:
            raise ValueError("submission plan artifact channel must match attempt channel")
        if plan.contract_version != attempt.contract_version:
            raise ValueError("submission plan contract version must match attempt")
        if plan.artifact.sha256 != attempt.artifact_sha256:
            raise ValueError("submission plan artifact must match attempt")
        if plan.final_action is not None and plan.final_action not in _FINAL_ACTIONS:
            raise ValueError("unsupported final action")

        with self._immediate_transaction():
            revision_row = self._connection.execute(
                "SELECT COALESCE(MAX(revision), 0) AS max_revision FROM submission_plans WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            revision = int(revision_row["max_revision"]) + 1
            saved_at = _utcnow()
            self._connection.execute(
                """
                INSERT INTO submission_plans (
                    attempt_id, revision, saved_at, plan_json, upload_digest, submission_digest
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    revision,
                    saved_at,
                    _dump_json(_sanitize_plan_dict(_plan_to_dict(plan))),
                    plan.upload_confirmation_digest,
                    plan.submission_confirmation_digest,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO events (
                    attempt_id, from_state, to_state, event, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    attempt.state.value,
                    attempt.state.value,
                    "submission_plan_saved",
                    _dump_json(
                        {
                            "revision": revision,
                            "upload_confirmation_digest": plan.upload_confirmation_digest,
                            "submission_confirmation_digest": plan.submission_confirmation_digest,
                            "account_alias": plan.account_alias,
                        }
                    ),
                    saved_at,
                ),
            )

    def load_submission_plan(self, attempt_id: str) -> SubmissionPlan:
        row = self._connection.execute(
            """
            SELECT plan_json
            FROM submission_plans
            WHERE attempt_id = ?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return _plan_from_dict(json.loads(row["plan_json"]))

    def save_frozen_fields(self, attempt_id: str, frozen: FrozenFields) -> None:
        """Append private, redacted channel-copy metadata for one attempt."""

        attempt = self.get_attempt(attempt_id)
        values = {str(key): str(value) for key, value in frozen.values.items()}
        generated_facts = {str(key): str(value) for key, value in frozen.generated_facts.items()}
        drifted_fields = tuple(str(value) for value in frozen.drifted_fields)
        timestamp = _utcnow()
        with self._immediate_transaction():
            self._connection.execute(
                """
                INSERT INTO frozen_fields (
                    attempt_id, source_id, source_digest, source_version, channel,
                    values_json, generated_facts_json, drifted_fields_json, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    attempt.source_id,
                    attempt.source_digest,
                    attempt.source_version,
                    attempt.channel,
                    _dump_json(_sanitize_for_storage(values)),
                    _dump_json(_sanitize_for_storage(generated_facts)),
                    _dump_json(_sanitize_for_storage(list(drifted_fields))),
                    timestamp,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO events (
                    attempt_id, from_state, to_state, event, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    attempt.state.value,
                    attempt.state.value,
                    "frozen_fields_saved",
                    _dump_json(
                        {
                            "field_names": sorted(values),
                            "generated_fact_names": sorted(generated_facts),
                            "drifted_fields": list(drifted_fields),
                        }
                    ),
                    timestamp,
                ),
            )

    def load_frozen_fields(self, source_root: Path, channel: str) -> Optional[FrozenFields]:
        """Return the latest private copy for a source/channel regeneration."""

        source_identifier = build_source_id(Path(source_root))
        row = self._connection.execute(
            """
            SELECT values_json, generated_facts_json, drifted_fields_json
            FROM frozen_fields
            WHERE source_id = ? AND channel = ?
            ORDER BY frozen_field_id DESC
            LIMIT 1
            """,
            (source_identifier, channel),
        ).fetchone()
        return _frozen_fields_from_row(row)

    def load_frozen_fields_for_attempt(self, attempt_id: str) -> Optional[FrozenFields]:
        row = self._connection.execute(
            """
            SELECT values_json, generated_facts_json, drifted_fields_json
            FROM frozen_fields
            WHERE attempt_id = ?
            ORDER BY frozen_field_id DESC
            LIMIT 1
            """,
            (attempt_id,),
        ).fetchone()
        return _frozen_fields_from_row(row)

    def transition(
        self,
        attempt_id: str,
        target: PublishState,
        event: str,
        evidence: Mapping[str, Any],
    ) -> None:
        if not isinstance(event, str) or not event.strip():
            raise ValueError("event must be a non-empty string")
        attempt = self.get_attempt(attempt_id)
        current = attempt.state
        if not can_transition(current, target):
            raise InvalidTransition(f"{current.value} -> {target.value} is not allowed")
        clear_retry_exhausted = event != "submission_unknown"
        self.require_no_active_blockers(attempt_id)
        if current == PublishState.SUBMISSION_UNKNOWN and target in (
            PublishState.SUBMITTED,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        ):
            if not event.startswith("readback_"):
                raise InvalidTransition("submission_unknown can only advance via readback")

        plan = self.load_submission_plan(attempt_id)
        if target == PublishState.UPLOADED:
            self._require_authorization(attempt_id, "upload", plan.upload_confirmation_digest)
        if current == PublishState.AWAITING_SUBMISSION_CONFIRMATION and target in (
            PublishState.SUBMITTED,
            PublishState.SUBMISSION_UNKNOWN,
        ):
            self._require_authorization(attempt_id, "upload", plan.upload_confirmation_digest)
            digest = plan.submission_confirmation_digest
            if not digest:
                raise AuthorizationRequired("submission requires a finalized plan digest")
            self._require_authorization(attempt_id, "submission", digest)
            requested_action = _EVENT_ACTIONS.get(event.strip()) or _string_or_none(evidence.get("final_action"))
            if requested_action != plan.final_action:
                raise InvalidTransition("submission event final_action must match the finalized plan")

        sanitized_evidence = _sanitize_for_storage(evidence)
        timestamp = _utcnow()
        raw_status = _string_or_none(sanitized_evidence.get("raw_status")) or attempt.raw_status
        product_id = _string_or_none(sanitized_evidence.get("product_id")) or attempt.product_id
        public_url = _string_or_none(sanitized_evidence.get("public_url")) or attempt.public_url
        submitted_at = attempt.submitted_at
        approved_at = attempt.approved_at
        published_at = attempt.published_at
        last_verified_at = attempt.last_verified_at

        timestamp_column = _TIMESTAMP_COLUMNS.get(target)
        if timestamp_column == "submitted_at":
            submitted_at = timestamp
        elif timestamp_column == "approved_at":
            approved_at = timestamp
        elif timestamp_column == "published_at":
            published_at = timestamp
        if target in _VERIFIED_STATES or event.startswith("readback_"):
            last_verified_at = timestamp

        with self._immediate_transaction():
            self._connection.execute(
                """
                UPDATE attempts
                SET state = ?, raw_status = ?, product_id = ?, public_url = ?,
                    submitted_at = ?, approved_at = ?, published_at = ?, last_verified_at = ?
                WHERE attempt_id = ?
                """,
                (
                    target.value,
                    raw_status,
                    product_id,
                    public_url,
                    submitted_at,
                    approved_at,
                    published_at,
                    last_verified_at,
                    attempt_id,
                ),
            )
            if clear_retry_exhausted:
                self._clear_retry_exhaustion_in_transaction(attempt_id, {"reason": "successful_lifecycle", "event": event.strip()}, timestamp)
            self._connection.execute(
                """
                INSERT INTO events (
                    attempt_id, from_state, to_state, event, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    current.value,
                    target.value,
                    event.strip(),
                    _dump_json(sanitized_evidence),
                    timestamp,
                ),
            )

    def add_authorization(
        self,
        attempt_id: str,
        kind: str,
        digest: str,
        confirmed_at: str,
    ) -> None:
        if kind not in {"upload", "submission"}:
            raise ValueError("kind must be upload or submission")
        if not isinstance(digest, str) or not digest:
            raise ValueError("digest must be non-empty")
        if not isinstance(confirmed_at, str) or not confirmed_at:
            raise ValueError("confirmed_at must be non-empty")
        self.get_attempt(attempt_id)
        self.require_no_active_blockers(attempt_id)
        plan = self.load_submission_plan(attempt_id)
        expected_digest = plan.upload_confirmation_digest if kind == "upload" else plan.submission_confirmation_digest
        if not expected_digest:
            raise AuthorizationRequired(f"{kind} authorization requires the current persisted plan digest")
        if digest != expected_digest:
            raise AuthorizationRequired(f"{kind} authorization must match the current persisted plan digest")
        timestamp = _utcnow()
        with self._immediate_transaction():
            self._connection.execute(
                """
                INSERT INTO authorizations (
                    attempt_id, kind, digest, confirmed_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (attempt_id, kind, digest, confirmed_at, timestamp),
            )
            self._connection.execute(
                """
                INSERT INTO events (
                    attempt_id, from_state, to_state, event, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    None,
                    None,
                    "authorization_added",
                    _dump_json({"kind": kind, "digest": digest, "confirmed_at": confirmed_at}),
                    timestamp,
                ),
            )

    def add_authorizations(self, entries: Iterable[tuple[str, str, str, str]]) -> None:
        """Validate a complete batch first, then persist every authorization atomically."""

        normalized = tuple((str(a), str(k), str(d), str(c)) for a, k, d, c in entries)
        if not normalized:
            raise ValueError("authorization batch must not be empty")
        timestamp = _utcnow()
        with self._immediate_transaction():
            for attempt_id, kind, digest, confirmed_at in normalized:
                if kind not in {"upload", "submission"}:
                    raise ValueError("kind must be upload or submission")
                if not digest or not confirmed_at:
                    raise ValueError("digest and confirmed_at must be non-empty")
                self.get_attempt(attempt_id)
                self.require_no_active_blockers(attempt_id)
                plan = self.load_submission_plan(attempt_id)
                expected = plan.upload_confirmation_digest if kind == "upload" else plan.submission_confirmation_digest
                if not expected or digest != expected:
                    raise AuthorizationRequired(f"{kind} authorization must match the current persisted plan digest")
            for attempt_id, kind, digest, confirmed_at in normalized:
                self._connection.execute(
                    "INSERT INTO authorizations (attempt_id, kind, digest, confirmed_at, created_at) VALUES (?, ?, ?, ?, ?)",
                    (attempt_id, kind, digest, confirmed_at, timestamp),
                )
                self._connection.execute(
                    "INSERT INTO events (attempt_id, from_state, to_state, event, evidence_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (attempt_id, None, None, "authorization_added", _dump_json({"kind": kind, "digest": digest, "confirmed_at": confirmed_at}), timestamp),
                )

    def require_authorization(self, attempt_id: str, kind: str, digest: str) -> None:
        """Require an exact current authorization without mutating ledger state."""

        if kind not in {"upload", "submission"}:
            raise ValueError("kind must be upload or submission")
        self._require_authorization(attempt_id, kind, digest)

    def active_blockers(self, attempt_id: str) -> tuple[BlockerRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT flag, evidence_json, recovery_commands_json, created_at
            FROM blocker_flags
            WHERE attempt_id = ?
              AND blocker_id IN (
                  SELECT MAX(blocker_id) FROM blocker_flags WHERE attempt_id = ? GROUP BY flag
              )
              AND active = 1
            ORDER BY blocker_id ASC
            """,
            (attempt_id, attempt_id),
        ).fetchall()
        return tuple(
            BlockerRecord(
                flag=str(row["flag"]),
                evidence=dict(json.loads(row["evidence_json"])),
                recovery_commands=tuple(
                    tuple(str(item) for item in command)
                    for command in json.loads(row["recovery_commands_json"])
                ),
                created_at=str(row["created_at"]),
            )
            for row in rows
        )

    def require_no_active_blockers(self, attempt_id: str, ignored_flags: Iterable[str] = ()) -> None:
        ignored = frozenset(str(flag) for flag in ignored_flags)
        blockers = tuple(blocker for blocker in self.active_blockers(attempt_id) if blocker.flag not in ignored)
        if blockers:
            raise RecoveryBlocked("active blocking flags: " + ", ".join(blocker.flag for blocker in blockers))

    def record_blocker(
        self,
        attempt_id: str,
        flag: str,
        evidence: Mapping[str, Any],
        recovery_commands: Iterable[Iterable[str]],
    ) -> None:
        if flag not in _BLOCKING_FLAGS:
            raise ValueError("unsupported blocking flag")
        attempt = self.get_attempt(attempt_id)
        commands = _validate_recovery_commands(
            recovery_commands,
            _BLOCKER_RECOVERY_EVENTS[flag],
            attempt_id,
            attempt.channel,
        )
        timestamp = _utcnow()
        with self._immediate_transaction():
            self._connection.execute(
                """
                INSERT INTO blocker_flags (
                    attempt_id, flag, active, evidence_json, recovery_commands_json, created_at
                ) VALUES (?, ?, 1, ?, ?, ?)
                """,
                (
                    attempt_id,
                    flag,
                    _dump_json(_sanitize_for_storage(evidence)),
                    _dump_json(_sanitize_for_storage([list(command) for command in commands])),
                    timestamp,
                ),
            )

    def resolve_blocker(self, attempt_id: str, flag: str, evidence: Mapping[str, Any]) -> None:
        if flag not in _BLOCKING_FLAGS:
            raise ValueError("unsupported blocking flag")
        self.get_attempt(attempt_id)
        timestamp = _utcnow()
        with self._immediate_transaction():
            self._connection.execute(
                """
                INSERT INTO blocker_flags (
                    attempt_id, flag, active, evidence_json, recovery_commands_json, created_at
                ) VALUES (?, ?, 0, ?, '[]', ?)
                """,
                (attempt_id, flag, _dump_json(_sanitize_for_storage(evidence)), timestamp),
            )

    def record_failure(self, attempt_id: str, failure_signature: str, evidence: Mapping[str, Any], recovery_commands: Iterable[Iterable[str]]) -> FailureStreak:
        raw_signature = str(failure_signature).strip()
        if not raw_signature:
            raise ValueError("attempt_failed evidence requires failure_signature")
        attempt = self.get_attempt(attempt_id)
        commands = _validate_recovery_commands(
            recovery_commands,
            "retry_exhausted_resolved",
            attempt_id,
            attempt.channel,
        )
        signature = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()
        timestamp = _utcnow()
        with self._immediate_transaction():
            prior = self._connection.execute(
                """
                SELECT failure_signature, consecutive_count FROM failure_streak_current
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
            count = min(3, int(prior["consecutive_count"]) + 1) if prior is not None and prior["failure_signature"] == signature else 1
            self._connection.execute("UPDATE failure_streaks SET consecutive_count = 0, updated_at = ? WHERE attempt_id = ?", (timestamp, attempt_id))
            self._connection.execute(
                """
                INSERT INTO failure_streaks (attempt_id, failure_signature, consecutive_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(attempt_id, failure_signature) DO UPDATE SET consecutive_count = excluded.consecutive_count, updated_at = excluded.updated_at
                """,
                (attempt_id, signature, count, timestamp),
            )
            self._connection.execute(
                """
                INSERT INTO failure_streak_current (attempt_id, failure_signature, consecutive_count, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    failure_signature = excluded.failure_signature,
                    consecutive_count = excluded.consecutive_count,
                    updated_at = excluded.updated_at
                """,
                (attempt_id, signature, count, timestamp),
            )
        if count >= 3:
            self.record_blocker(
                attempt_id,
                "retry_exhausted",
                {**dict(evidence), "failure_signature": signature, "consecutive_count": count},
                commands,
            )
        else:
            self.resolve_blocker(attempt_id, "retry_exhausted", {"reason": "failure_signature_changed"})
        return FailureStreak(signature, count)

    def failure_streak(self, attempt_id: str) -> FailureStreak:
        row = self._connection.execute(
            """
            SELECT failure_signature, consecutive_count FROM failure_streak_current
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if row is None:
            return FailureStreak("", 0)
        return FailureStreak(str(row["failure_signature"]), int(row["consecutive_count"]))

    def reset_failure_streak(self, attempt_id: str, evidence: Mapping[str, Any]) -> FailureStreak:
        self.get_attempt(attempt_id)
        with self._immediate_transaction():
            timestamp = _utcnow()
            self._clear_retry_exhaustion_in_transaction(
                attempt_id,
                {"reason": "successful_readback", **dict(evidence)},
                timestamp,
            )
        return self.failure_streak(attempt_id)

    def _clear_retry_exhaustion_in_transaction(
        self,
        attempt_id: str,
        evidence: Mapping[str, Any],
        timestamp: str,
    ) -> None:
        self._connection.execute("UPDATE failure_streaks SET consecutive_count = 0, updated_at = ? WHERE attempt_id = ?", (timestamp, attempt_id))
        self._connection.execute("UPDATE failure_streak_current SET consecutive_count = 0, updated_at = ? WHERE attempt_id = ?", (timestamp, attempt_id))
        self._connection.execute(
            """
            INSERT INTO blocker_flags (
                attempt_id, flag, active, evidence_json, recovery_commands_json, created_at
            ) VALUES (?, 'retry_exhausted', 0, ?, '[]', ?)
            """,
            (attempt_id, _dump_json(_sanitize_for_storage(evidence)), timestamp),
        )

    def claim_ownership(self, snapshot: SourceSnapshot, channel: str) -> tuple[OwnershipRecord, bool]:
        source_identifier = build_source_id(snapshot.root)
        with self._immediate_transaction():
            existing = self._connection.execute(
                """
                SELECT source_id, source_digest, source_version, channel, owner_token, owner_attempt_id, created_at
                FROM ownership_claims
                WHERE source_id = ? AND source_version = ? AND channel = ? AND active = 1
                ORDER BY ownership_id DESC LIMIT 1
                """,
                (source_identifier, snapshot.version, channel),
            ).fetchone()
            if existing is not None:
                return _ownership_from_row(existing), False
            timestamp = _utcnow()
            sequence = self._connection.execute("SELECT COALESCE(MAX(ownership_id), 0) AS current_id FROM ownership_claims").fetchone()
            cursor = self._connection.execute(
                """
                INSERT INTO ownership_claims (
                    source_id, source_digest, source_version, channel, owner_token, owner_attempt_id, active, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, 1, ?)
                """,
                (source_identifier, snapshot.source_digest, snapshot.version, channel, "claim-pending-{0}".format(int(sequence["current_id"]) + 1), timestamp),
            )
            claim_ref = "claim-{0}".format(cursor.lastrowid)
            self._connection.execute("UPDATE ownership_claims SET owner_token = ? WHERE ownership_id = ?", (claim_ref, cursor.lastrowid))
            return OwnershipRecord(source_identifier, snapshot.source_digest, snapshot.version, channel, claim_ref, None, timestamp), True

    def bind_ownership(self, claim_ref: str, attempt_id: str) -> None:
        self.get_attempt(attempt_id)
        with self._immediate_transaction():
            self._connection.execute(
                "UPDATE ownership_claims SET owner_attempt_id = ? WHERE owner_token = ? AND active = 1",
                (attempt_id, claim_ref),
            )

    def release_ownership(self, attempt_id: str) -> None:
        with self._immediate_transaction():
            self._connection.execute(
                "UPDATE ownership_claims SET active = 0 WHERE owner_attempt_id = ? AND active = 1",
                (attempt_id,),
            )

    def release_ownership_claim(self, claim_ref: str) -> None:
        with self._immediate_transaction():
            self._connection.execute(
                "UPDATE ownership_claims SET active = 0 WHERE owner_token = ? AND active = 1",
                (claim_ref,),
            )

    def release_orphaned_ownership(self, claim_ref: str, channel: str, evidence: Mapping[str, Any]) -> None:
        with self._immediate_transaction():
            row = self._connection.execute(
                """
                SELECT ownership_id, source_id, source_version, channel FROM ownership_claims
                WHERE owner_token = ? AND channel = ? AND owner_attempt_id IS NULL AND active = 1
                """,
                (claim_ref, channel),
            ).fetchone()
            if row is None:
                raise ValueError("active orphaned ownership claim not found")
            if (
                str(evidence.get("source_id", "")) != str(row["source_id"])
                or str(evidence.get("source_version", "")) != str(row["source_version"])
                or str(evidence.get("channel", "")) != str(row["channel"])
            ):
                raise ValueError("ownership_claim_cancelled evidence must match the claim source_id, source_version, and channel")
            self._connection.execute("UPDATE ownership_claims SET active = 0 WHERE ownership_id = ?", (row["ownership_id"],))
            self._connection.execute(
                """
                INSERT INTO ownership_events (ownership_id, event, evidence_json, created_at)
                VALUES (?, 'ownership_claim_cancelled', ?, ?)
                """,
                (row["ownership_id"], _dump_json(_sanitize_for_storage(evidence)), _utcnow()),
            )

    def export(self, source_id: Optional[str], format: str) -> str:
        rows = self._export_rows(source_id)
        format_name = format.lower()
        if format_name == "json":
            return json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if format_name == "csv":
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=_ROW_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return stream.getvalue()
        if format_name in {"markdown", "md"}:
            lines = [
                "# Skill publishing ledger",
                "",
                "| Run ID | Status | Raw Status | Skill | Version | Channel | Alias | Product ID | Public URL | Artifact | Created At | Submitted At | Approved At | Published At | Last Verified At | Next Action |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
            for row in rows:
                lines.append(
                    "| {run_id} | {status} | {raw_status} | {skill_name} | {version} | {channel} | {account_alias} | {product_id} | {public_url} | {artifact_sha256} | {created_at} | {submitted_at} | {approved_at} | {published_at} | {last_verified_at} | {next_action} |".format(
                        **{key: row.get(key, "") or "" for key in row}
                    )
                )
                lines.append("")
                lines.append("Evidence: `{}`".format(row["evidence_summary"]))
                lines.append("")
            return "\n".join(lines).rstrip() + "\n"
        raise ValueError("format must be json, csv, or markdown")

    def _export_rows(self, source_identifier: Optional[str]) -> list[dict[str, str]]:
        query = """
            SELECT a.attempt_id, a.state, a.raw_status, a.source_id, a.skill_name, a.source_version,
                   a.channel, a.contract_version, a.account_alias, a.product_id, a.public_url,
                   a.artifact_sha256, a.created_at, a.submitted_at, a.approved_at,
                   a.published_at, a.last_verified_at,
                   sp.plan_json,
                   e.event, e.evidence_json
            FROM attempts AS a
            LEFT JOIN submission_plans AS sp
              ON sp.attempt_id = a.attempt_id
             AND sp.revision = (
                 SELECT MAX(revision) FROM submission_plans WHERE attempt_id = a.attempt_id
             )
            LEFT JOIN events AS e
              ON e.event_id = (
                 SELECT event_id FROM events WHERE attempt_id = a.attempt_id ORDER BY event_id DESC LIMIT 1
             )
        """
        params: tuple[Any, ...] = ()
        if source_identifier is not None:
            query += " WHERE a.source_id = ?"
            params = (source_identifier,)
        query += " ORDER BY a.created_at ASC, a.attempt_id ASC"
        raw_rows = self._connection.execute(query, params).fetchall()
        rows: list[dict[str, str]] = []
        for row in raw_rows:
            latest_plan = json.loads(row["plan_json"]) if row["plan_json"] else None
            evidence_payload = json.loads(row["evidence_json"]) if row["evidence_json"] else {}
            next_action = _string_or_none(evidence_payload.get("next_action"))
            if next_action is None:
                next_action = _default_next_action(PublishState(row["state"]))
            final_action = None
            if latest_plan is not None:
                final_action = _string_or_none(latest_plan.get("final_action"))
            exported = {
                "run_id": row["attempt_id"],
                "status": row["state"],
                "raw_status": row["raw_status"] or "",
                "source_id": row["source_id"],
                "skill_name": row["skill_name"],
                "version": row["source_version"],
                "channel": row["channel"],
                "contract_version": row["contract_version"],
                "account_alias": row["account_alias"],
                "product_id": row["product_id"] or "",
                "public_url": row["public_url"] or "",
                "artifact_sha256": row["artifact_sha256"],
                "created_at": row["created_at"],
                "submitted_at": row["submitted_at"] or "",
                "approved_at": row["approved_at"] or "",
                "published_at": row["published_at"] or "",
                "last_verified_at": row["last_verified_at"] or "",
                "evidence_summary": _summarize_evidence(evidence_payload),
                "next_action": next_action or "",
                "final_action": final_action or "",
            }
            rows.append({key: redact_text(str(exported[key])) for key in _ROW_COLUMNS})
        return rows

    def _require_authorization(self, attempt_id: str, kind: str, digest: str) -> None:
        row = self._connection.execute(
            """
            SELECT authorization_id
            FROM authorizations
            WHERE attempt_id = ? AND kind = ? AND digest = ?
            ORDER BY authorization_id DESC
            LIMIT 1
            """,
            (attempt_id, kind, digest),
        ).fetchone()
        if row is None:
            raise AuthorizationRequired(f"{kind} authorization for the current digest is required")

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_sha256 TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    files_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    source_id TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    contract_version TEXT NOT NULL,
                    account_alias TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL REFERENCES artifacts(artifact_sha256),
                    state TEXT NOT NULL,
                    raw_status TEXT,
                    product_id TEXT,
                    public_url TEXT,
                    created_at TEXT NOT NULL,
                    submitted_at TEXT,
                    approved_at TEXT,
                    published_at TEXT,
                    last_verified_at TEXT,
                    UNIQUE(source_digest, source_version, channel, artifact_sha256)
                );

                CREATE TABLE IF NOT EXISTS submission_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    revision INTEGER NOT NULL,
                    saved_at TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    upload_digest TEXT NOT NULL,
                    submission_digest TEXT,
                    UNIQUE(attempt_id, revision)
                );

                CREATE TABLE IF NOT EXISTS authorizations (
                    authorization_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    kind TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    from_state TEXT,
                    to_state TEXT,
                    event TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS frozen_fields (
                    frozen_field_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    source_id TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    generated_facts_json TEXT NOT NULL,
                    drifted_fields_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS blocker_flags (
                    blocker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    flag TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    evidence_json TEXT NOT NULL,
                    recovery_commands_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS failure_streaks (
                    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
                    failure_signature TEXT NOT NULL,
                    consecutive_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(attempt_id, failure_signature)
                );

                CREATE TABLE IF NOT EXISTS failure_streak_current (
                    attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
                    failure_signature TEXT NOT NULL,
                    consecutive_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ownership_claims (
                    ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    owner_token TEXT NOT NULL UNIQUE,
                    owner_attempt_id TEXT,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ownership_events (
                    ownership_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ownership_id INTEGER NOT NULL REFERENCES ownership_claims(ownership_id),
                    event TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            version_row = self._connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if version_row is None:
                self._connection.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            elif int(version_row["version"]) != SCHEMA_VERSION:
                raise RuntimeError("unsupported schema version")
            self._connection.execute(
                "INSERT OR IGNORE INTO runs(run_id, created_at) VALUES (?, ?)",
                (_DEFAULT_RUN_ID, _utcnow()),
            )

    @contextmanager
    def _immediate_transaction(self) -> Iterable[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()


def _attempt_id(snapshot: SourceSnapshot, channel: str, artifact: Artifact) -> str:
    seed = "::".join((snapshot.source_digest, snapshot.version, channel, artifact.sha256))
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _ownership_from_row(row: sqlite3.Row) -> OwnershipRecord:
    return OwnershipRecord(
        source_id=str(row["source_id"]),
        source_digest=str(row["source_digest"]),
        source_version=str(row["source_version"]),
        channel=str(row["channel"]),
        claim_ref=str(row["owner_token"]),
        owner_attempt_id=_string_or_none(row["owner_attempt_id"]),
        created_at=str(row["created_at"]),
    )


def _validate_recovery_commands(
    commands: Iterable[Iterable[str]],
    expected_events: object,
    attempt_id: str,
    channel: str,
) -> tuple[tuple[str, ...], ...]:
    if isinstance(expected_events, str):
        expected = frozenset((expected_events,))
    else:
        expected = frozenset(str(event) for event in expected_events)
    validated: list[tuple[str, ...]] = []
    for command in commands:
        if isinstance(command, (str, bytes)):
            raise ValueError("recovery_commands must be argument arrays, not shell strings")
        values = tuple(str(value) for value in command)
        if not values or any(not value.strip() for value in values):
            raise ValueError("recovery command arguments must be non-empty")
        if (
            len(values) != 9
            or values[0:3] != ("python3", "scripts/publisher.py", "record")
            or values[3] != attempt_id
            or values[4] != channel
            or values[5] != "--event"
            or values[6] not in expected
            or values[7] != "--evidence"
            or not values[8].strip()
        ):
            raise ValueError("recovery commands must be complete local publisher record argument arrays")
        if any(any(marker in value.lower() for marker in ("token", "secret", "password", "cookie", "qr")) for value in values):
            raise ValueError("recovery commands must not contain credentials, cookies, or QR payloads")
        validated.append(values)
    if not validated:
        raise ValueError("blocking evidence requires recovery_commands")
    return tuple(validated)


def _plan_to_dict(plan: SubmissionPlan) -> dict[str, Any]:
    return {
        "channel": plan.channel,
        "contract_version": plan.contract_version,
        "account_alias": plan.account_alias,
        "artifact": {
            "channel": plan.artifact.channel,
            "path": str(plan.artifact.path),
            "sha256": plan.artifact.sha256,
            "size_bytes": plan.artifact.size_bytes,
            "files": list(plan.artifact.files),
        },
        "fields": dict(plan.fields),
        "disclosure": dict(plan.disclosure),
        "upload_confirmation_digest": plan.upload_confirmation_digest,
        "platform_id": plan.platform_id,
        "observed_fields": dict(plan.observed_fields),
        "final_action": plan.final_action,
        "submission_confirmation_digest": plan.submission_confirmation_digest,
        "manual_fallback": list(plan.manual_fallback),
    }


def _frozen_fields_from_row(row: Optional[sqlite3.Row]) -> Optional[FrozenFields]:
    if row is None:
        return None
    return FrozenFields(
        values={str(key): str(value) for key, value in dict(json.loads(row["values_json"])).items()},
        drifted_fields=tuple(str(value) for value in json.loads(row["drifted_fields_json"])),
        generated_facts={str(key): str(value) for key, value in dict(json.loads(row["generated_facts_json"])).items()},
    )


def _sanitize_plan_dict(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_for_storage(payload)
    return dict(sanitized)


def _plan_from_dict(payload: Mapping[str, Any]) -> SubmissionPlan:
    artifact_payload = payload["artifact"]
    artifact = Artifact(
        channel=str(artifact_payload["channel"]),
        path=Path(str(artifact_payload["path"])),
        sha256=str(artifact_payload["sha256"]),
        size_bytes=int(artifact_payload["size_bytes"]),
        files=tuple(str(item) for item in artifact_payload.get("files", ())),
    )
    final_action = payload.get("final_action")
    if final_action is not None:
        final_action = str(final_action)
    return SubmissionPlan(
        channel=str(payload["channel"]),
        contract_version=str(payload["contract_version"]),
        account_alias=str(payload["account_alias"]),
        artifact=artifact,
        fields={str(key): str(value) for key, value in dict(payload.get("fields", {})).items()},
        disclosure=dict(payload.get("disclosure", {})),
        upload_confirmation_digest=str(payload["upload_confirmation_digest"]),
        platform_id=_string_or_none(payload.get("platform_id")),
        observed_fields={str(key): str(value) for key, value in dict(payload.get("observed_fields", {})).items()},
        final_action=final_action,
        submission_confirmation_digest=_string_or_none(payload.get("submission_confirmation_digest")),
        manual_fallback=tuple(str(item) for item in payload.get("manual_fallback", ())),
    )


def _sanitize_for_storage(value: Any, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {str(child_key): _sanitize_for_storage(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_storage(item, key) for item in value]
    if isinstance(value, str):
        lowered = key.lower()
        if lowered != "account_alias" and ("account" in lowered or "email" in lowered):
            return "[REDACTED_ACCOUNT]"
        if any(marker in lowered for marker in ("token", "secret", "password", "passwd", "cookie", "qr")):
            return "[REDACTED_PRIVATE]"
        return redact_text(value)
    return value


def _default_next_action(state: PublishState) -> str:
    mapping = {
        PublishState.DRAFT: "run_quality_checks",
        PublishState.BLOCKED: "fix_blockers",
        PublishState.CHECKED: "prepare_channel_artifact",
        PublishState.PREPARED: "choose_upload_or_finalize",
        PublishState.AWAITING_UPLOAD_CONFIRMATION: "confirm_upload",
        PublishState.UPLOADED: "wait_for_parsing",
        PublishState.PARSING: "readback_parsing_status",
        PublishState.AWAITING_SUBMISSION_CONFIRMATION: "confirm_submit",
        PublishState.SUBMISSION_UNKNOWN: "readback_submission_status",
        PublishState.SUBMITTED: "wait_for_review",
        PublishState.UNDER_REVIEW: "refresh_review_status",
        PublishState.CHANGES_REQUESTED: "revise_and_prepare",
        PublishState.REJECTED: "decide_resubmission",
        PublishState.APPROVED: "verify_public_listing",
        PublishState.LIVE: "monitor_public_version",
        PublishState.SUPERSEDED: "track_newer_version",
        PublishState.DELISTED: "review_takedown_or_restore",
    }
    return mapping[state]


def _summarize_evidence(payload: Mapping[str, Any]) -> str:
    if not payload:
        return ""
    hidden = {"raw_status", "next_action", "product_id", "public_url", "account_alias"}
    trimmed = {key: value for key, value in payload.items() if key not in hidden}
    return redact_text(json.dumps(trimmed, ensure_ascii=False, sort_keys=True)) if trimmed else ""


def _dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
