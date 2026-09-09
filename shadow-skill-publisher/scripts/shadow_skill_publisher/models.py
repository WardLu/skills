"""Stable value objects shared by publisher workflow stages."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Mapping, Optional, Protocol


class GateSeverity(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    NOT_EVIDENCED = "not_evidenced"


class PublishState(str, Enum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    CHECKED = "checked"
    PREPARED = "prepared"
    AWAITING_UPLOAD_CONFIRMATION = "awaiting_upload_confirmation"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    AWAITING_SUBMISSION_CONFIRMATION = "awaiting_submission_confirmation"
    SUBMISSION_UNKNOWN = "submission_unknown"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    APPROVED = "approved"
    LIVE = "live"
    SUPERSEDED = "superseded"
    DELISTED = "delisted"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: GateSeverity
    message: str
    path: Optional[str] = None
    claim: Optional[str] = None
    provenance: Literal["deterministic", "ai_inference"] = "deterministic"


@dataclass(frozen=True)
class GateReport:
    allowed: bool
    findings: tuple[Finding, ...]
    removed_claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceSnapshot:
    root: Path
    name: str
    description: str
    version: str
    source_digest: str
    files: tuple[str, ...]
    license_path: Path
    kind: Literal["prompt", "scripted"]
    skill_md_text: str
    git_commit: Optional[str]
    git_branch: Optional[str]
    git_dirty: bool
    untracked_files: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    source_digest: str
    commands: tuple[tuple[str, ...], ...]
    cwd: Path
    timeout_seconds: int
    permitted_env_names: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    capability: str
    core: bool
    passed: bool
    provenance: Literal["source", "command", "user", "official_page", "ai_inference"]


@dataclass(frozen=True)
class CommandEvidence:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class EvidenceBundle:
    core: tuple[EvidenceItem, ...]
    optional: tuple[EvidenceItem, ...]
    commands: tuple[CommandEvidence, ...] = ()


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Dossier:
    identity: Mapping[str, str]
    claims: tuple[Claim, ...]
    removed_claims: tuple[str, ...]
    commercial_mode: Literal["free", "one_time"]
    price: Optional[str]
    facts: Mapping[str, object]


@dataclass(frozen=True)
class FrozenFields:
    values: Mapping[str, str]
    drifted_fields: tuple[str, ...] = ()
    generated_facts: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelStaging:
    channel: str
    contract_version: str
    files: Mapping[str, bytes]
    fields: Mapping[str, str]
    disclosure: Mapping[str, object]
    manual_fallback: tuple[str, ...]


@dataclass(frozen=True)
class Artifact:
    channel: str
    path: Path
    sha256: str
    size_bytes: int
    files: tuple[str, ...]


@dataclass(frozen=True)
class SubmissionPlan:
    channel: str
    contract_version: str
    account_alias: str
    artifact: Artifact
    fields: Mapping[str, str]
    disclosure: Mapping[str, object]
    upload_confirmation_digest: str
    platform_id: Optional[str]
    observed_fields: Mapping[str, str]
    final_action: Optional[Literal["submit_review", "publish"]]
    submission_confirmation_digest: Optional[str]
    manual_fallback: tuple[str, ...]


@dataclass(frozen=True)
class AIReview:
    schema_version: int
    source_digest: str
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class Authorization:
    kind: Literal["upload", "submission"]
    digest: str


class ChannelAdapter(Protocol):
    key: str
    contract_version: str

    def build_staging(self, snapshot: SourceSnapshot, dossier: Dossier) -> ChannelStaging: ...

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan: ...

    def map_status(self, raw_status: str) -> Optional[PublishState]: ...
