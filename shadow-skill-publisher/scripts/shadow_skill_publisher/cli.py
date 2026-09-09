"""Command-line interface for the local Shadow Skill Publisher workflow."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Optional, Sequence

from .adapters import ChannelContractError, ChannelPolicyError
from .ai_review import AIReviewError, load_ai_review, persist_ai_review
from .archive import build_artifact, verify_artifact
from .channels import CHANNEL_KEYS, get_channel_adapter
from .confirmations import SubmissionPlanIncomplete, finalize_submission_plan
from .dossier import DossierError, apply_channel_edits, build_dossier, render_dossier_json, render_dossier_markdown, validate_channel_edits
from .evidence import (
    EvidenceProfileError,
    ExecutionAuthorizationError,
    build_execution_plan,
    load_evidence,
    run_trusted_commands,
)
from .ledger import AuthorizationRequired, InvalidTransition, Ledger, RecoveryBlocked
from .models import (
    AIReview,
    Artifact,
    CommandEvidence,
    EvidenceBundle,
    EvidenceItem,
    Finding,
    FrozenFields,
    GateReport,
    GateSeverity,
    PublishState,
    SubmissionPlan,
)
from .paths import attempt_root, resolve_publisher_home, source_id as build_source_id
from .profile_builder import (
    GENERATED_PROFILE_ORIGIN,
    PROVIDED_PROFILE_ORIGIN,
    STORED_PROFILE_ORIGIN,
    apply_source_defaults,
    build_generated_profile,
    missing_generated_profile_inputs,
)
from .quality import run_quality
from .redaction import redact_text
from .source import SourceContractError, SourceSnapshot, load_source


VERSION = "0.2.0"
COMMANDS = ("check", "prepare", "finalize", "authorize", "record", "status", "export")

_BLOCK_EXIT = 1
_ERROR_EXIT = 2
_SUBMISSION_UNKNOWN_EXIT = 3
_DEFAULT_TIMEOUT_SECONDS = 300
_FINAL_ACTIONS = ("submit_review", "publish")
_REMOTE_WRITE_STATES = frozenset(
    (
        PublishState.UPLOADED,
        PublishState.PARSING,
        PublishState.SUBMISSION_UNKNOWN,
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
_EVENT_TO_STATE = {
    "upload_completed": PublishState.UPLOADED,
    "zip_parsed": PublishState.PARSING,
    "submission_unknown": PublishState.SUBMISSION_UNKNOWN,
    "review_submitted": PublishState.SUBMITTED,
    "publish": PublishState.SUBMITTED,
    "under_review": PublishState.UNDER_REVIEW,
    "changes_requested": PublishState.CHANGES_REQUESTED,
    "rejected": PublishState.REJECTED,
    "approved": PublishState.APPROVED,
    "live": PublishState.LIVE,
    "superseded": PublishState.SUPERSEDED,
    "delisted": PublishState.DELISTED,
}
_EVIDENCE_REQUIRED_EVENTS = frozenset(("review_submitted", "publish", "under_review", "approved", "live"))
_BLOCKER_EVENTS = frozenset(
    (
        "remote_drift",
        "qualification_required",
        "quota_exhausted",
        "channel_contract_unverified",
    )
)
_RESOLUTION_EVENTS = {
    "remote_drift_resolved": "remote_drift",
    "qualification_resolved": "qualification_required",
    "quota_resolved": "quota_exhausted",
    "channel_contract_verified": "channel_contract_unverified",
    "retry_exhausted_resolved": "retry_exhausted",
}
_OWNERSHIP_EVENTS = frozenset(("ownership_handoff", "ownership_cancelled"))
_ORPHAN_OWNERSHIP_CANCEL_EVENT = "ownership_claim_cancelled"


class ArtifactPreparationBlocked(ValueError):
    """Raised when the built channel archive fails its mandatory final verification."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publisher.py",
        description="Validate, package, submit, publish, or track a local Agent Skill.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    check_parser = subparsers.add_parser("check", help="Validate local source and evidence.")
    check_parser.add_argument("source")
    check_parser.add_argument("--home")
    check_parser.add_argument("--profile")
    check_parser.add_argument("--ai-review")
    check_parser.add_argument("--exec-digest")
    check_parser.add_argument("--json", action="store_true")
    check_parser.set_defaults(_handler=_handle_check, _command_parser=check_parser)

    prepare_parser = subparsers.add_parser("prepare", help="Build local artifacts and submission plans.")
    prepare_parser.add_argument("source")
    prepare_parser.add_argument("--home")
    prepare_parser.add_argument("--profile")
    prepare_parser.add_argument("--channels", nargs="+", required=True)
    prepare_parser.add_argument("--ai-review")
    prepare_parser.add_argument("--exec-digest")
    prepare_parser.add_argument("--json", action="store_true")
    prepare_parser.set_defaults(_handler=_handle_prepare, _command_parser=prepare_parser)

    finalize_parser = subparsers.add_parser("finalize", help="Persist verified observed fields and finalize a plan.")
    finalize_parser.add_argument("run_id")
    finalize_parser.add_argument("channel")
    finalize_parser.add_argument("--home")
    finalize_parser.add_argument("--platform-id", required=True)
    finalize_parser.add_argument("--observed-fields", required=True)
    finalize_parser.add_argument("--final-action", choices=_FINAL_ACTIONS, required=True)
    finalize_parser.add_argument("--json", action="store_true")
    finalize_parser.set_defaults(_handler=_handle_finalize, _command_parser=finalize_parser)

    authorize_parser = subparsers.add_parser("authorize", help="Record a digest-bound authorization event.")
    authorize_parser.add_argument("run_id")
    authorize_parser.add_argument("channel")
    authorize_parser.add_argument("--home")
    authorize_parser.add_argument("--kind", choices=("upload", "submission"), required=True)
    authorize_parser.add_argument("--digest", required=True)
    authorize_parser.add_argument("--confirmed-at")
    authorize_parser.add_argument("--json", action="store_true")
    authorize_parser.set_defaults(_handler=_handle_authorize, _command_parser=authorize_parser)

    record_parser = subparsers.add_parser("record", help="Record a documented lifecycle event from evidence.")
    record_parser.add_argument("run_id")
    record_parser.add_argument("channel")
    record_parser.add_argument("--home")
    record_parser.add_argument("--event", required=True)
    record_parser.add_argument("--evidence", required=True)
    record_parser.add_argument("--json", action="store_true")
    record_parser.set_defaults(_handler=_handle_record, _command_parser=record_parser)

    status_parser = subparsers.add_parser("status", help="Read the current local attempt status.")
    status_parser.add_argument("run_id", nargs="?")
    status_parser.add_argument("channel", nargs="?")
    status_parser.add_argument("--home")
    status_parser.add_argument("--source")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(_handler=_handle_status, _command_parser=status_parser)

    export_parser = subparsers.add_parser("export", help="Export redacted local status rows.")
    export_parser.add_argument("--home")
    export_parser.add_argument("--format", choices=("json", "markdown", "md", "csv"), required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--source-id")
    export_parser.add_argument("--source")
    export_parser.set_defaults(_handler=_handle_export, _command_parser=export_parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    command_parser = getattr(args, "_command_parser", None)
    if handler is None:
        if command_parser is not None:
            command_parser.print_help()
        else:
            parser.print_help()
        return 0
    return handler(args)


def _handle_check(args: argparse.Namespace) -> int:
    try:
        snapshot, profile, evidence, ai_review, profile_origin = _load_local_inputs(
            Path(args.source),
            _resolve_home(args.home),
            args.ai_review,
            args.profile,
        )
        execution_plan = _build_execution_plan_from_profile(snapshot, profile, evidence.commands)
        command_results: tuple[CommandEvidence, ...] = ()
        if args.exec_digest:
            if execution_plan is None:
                raise ValueError("check has no declared command evidence to execute")
            command_results = run_trusted_commands(execution_plan, args.exec_digest)
            evidence = _apply_command_results(evidence, command_results)
        report = run_quality(snapshot, evidence, ai_findings=ai_review.findings if ai_review else ())
        payload = {
            "source": _serialize_snapshot(snapshot),
            "report": _serialize_report(report),
            "profile": _serialize_profile(profile_origin),
            "execution_plan": None if execution_plan is None else _serialize_execution_plan(execution_plan),
            "command_results": [_serialize_command_evidence(item) for item in command_results],
        }
        _emit(args.json, payload, _render_check_text(payload))
        return 0 if report.allowed else _BLOCK_EXIT
    except (
        SourceContractError,
        EvidenceProfileError,
        DossierError,
        AIReviewError,
        ExecutionAuthorizationError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_prepare(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        snapshot, profile, evidence, ai_review, profile_origin = _load_local_inputs(
            Path(args.source), home, args.ai_review, args.profile
        )
        execution_plan = _build_execution_plan_from_profile(snapshot, profile, evidence.commands)
        if args.exec_digest:
            if execution_plan is None:
                raise ValueError("prepare has no declared command evidence to execute")
            evidence = _apply_command_results(evidence, run_trusted_commands(execution_plan, args.exec_digest))
            if load_source(snapshot.root).source_digest != snapshot.source_digest:
                raise ExecutionAuthorizationError("source_changed_after_execution")
        report = run_quality(snapshot, evidence, ai_findings=ai_review.findings if ai_review else ())
        if not report.allowed:
            payload = {
                "source": _serialize_snapshot(snapshot),
                "report": _serialize_report(report),
                "profile": _serialize_profile(profile_origin),
                "attempts": [],
            }
            _emit(args.json, payload, _render_prepare_text(payload))
            return _BLOCK_EXIT

        selected_channels = _normalize_channels(args.channels)
        missing_inputs = (
            missing_generated_profile_inputs(profile, selected_channels)
            if profile_origin == GENERATED_PROFILE_ORIGIN
            else ()
        )
        if missing_inputs:
            payload = {
                "source": _serialize_snapshot(snapshot),
                "report": _serialize_report(report),
                "profile": _serialize_profile(profile_origin, missing_inputs),
                "attempts": [_serialize_missing_input_channel(item) for item in missing_inputs],
            }
            _emit(args.json, payload, _render_prepare_text(payload))
            return _BLOCK_EXIT
        for channel_key in selected_channels:
            validate_channel_edits(_channel_edits(profile, channel_key))
        dossier = _augment_dossier(build_dossier(snapshot, report, profile), profile)
        attempts: list[dict[str, Any]] = []
        blocked = False
        ledger: Optional[Ledger] = _open_ledger(home, create=False) if _state_db_path(home).is_file() else None
        for channel_key in selected_channels:
            adapter = get_channel_adapter(channel_key)
            artifact: Optional[Artifact] = None
            ownership_claim_ref: Optional[str] = None
            try:
                account_alias = _account_alias(profile, channel_key)
                staging = adapter.build_staging(snapshot, dossier)
                prior = ledger.load_frozen_fields(snapshot.root, channel_key) if ledger is not None else None
                fields, frozen = apply_channel_edits(dossier, staging.fields, _channel_edits(profile, channel_key), prior)
                staging = replace(staging, fields=fields)
                _validate_local_preview_config(adapter, profile, staging.fields)
                if ledger is None:
                    ledger = _open_ledger(home, create=True)
                owner, acquired = ledger.claim_ownership(snapshot, channel_key)
                if not acquired:
                    recovery_commands = _ownership_recovery_commands(owner, channel_key)
                    blocked = True
                    attempts.append(_serialize_concurrent_attempt(channel_key, owner, recovery_commands))
                    continue
                ownership_claim_ref = owner.claim_ref
                artifact = _build_attempt_artifact(home, snapshot, channel_key, staging.files)
                plan = adapter.build_plan(staging, artifact, account_alias)
                local_preview_plan = _build_local_preview_plan(adapter, profile, plan, artifact)
            except (ChannelContractError, ChannelPolicyError, ArtifactPreparationBlocked) as exc:
                if artifact is not None:
                    _discard_artifact(home, artifact)
                if ledger is not None and ownership_claim_ref is not None:
                    ledger.release_ownership_claim(ownership_claim_ref)
                blocked = True
                attempts.append(_serialize_blocked_channel(channel_key, exc, tuple(adapter.manual_fallback)))
                continue
            except ValueError:
                if artifact is not None:
                    _discard_artifact(home, artifact)
                if ledger is not None and ownership_claim_ref is not None:
                    ledger.release_ownership_claim(ownership_claim_ref)
                raise

            attempt_id = ledger.create_attempt(snapshot, channel_key, account_alias, adapter.contract_version, artifact)
            ledger.bind_ownership(ownership_claim_ref, attempt_id)
            existing_attempt = ledger.get_attempt(attempt_id)
            if existing_attempt.state != PublishState.DRAFT:
                attempts.append(
                    _serialize_attempt_status(
                        existing_attempt,
                        ledger.load_submission_plan(attempt_id),
                        ledger.load_frozen_fields_for_attempt(attempt_id),
                        ledger,
                    )
                )
                continue
            attempt_dir = _ensure_attempt_layout(home, attempt_id)
            ledger.save_submission_plan(attempt_id, plan)
            ledger.save_frozen_fields(attempt_id, frozen)
            current_plan = plan
            if local_preview_plan is not None:
                ledger.save_submission_plan(attempt_id, local_preview_plan)
                current_plan = local_preview_plan
            _write_prepare_artifacts(attempt_dir, dossier, report, plan, frozen)
            if ai_review is not None:
                persist_ai_review(ai_review, attempt_dir)
            _write_plan_snapshot(attempt_dir, current_plan)
            _transition_prepare_attempt(ledger, attempt_id, local_preview_plan)
            current_attempt = ledger.get_attempt(attempt_id)
            attempts.append(_serialize_attempt_status(current_attempt, ledger.load_submission_plan(attempt_id), frozen, ledger))
        payload = {
            "source": _serialize_snapshot(snapshot),
            "report": _serialize_report(report),
            "profile": _serialize_profile(profile_origin),
            "attempts": attempts,
        }
        _emit(args.json, payload, _render_prepare_text(payload))
        return _BLOCK_EXIT if blocked else 0
    except (SourceContractError, EvidenceProfileError, DossierError, AIReviewError, ExecutionAuthorizationError) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)
    except (FileNotFoundError, KeyError, SubmissionPlanIncomplete, ValueError) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_finalize(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        ledger = _open_ledger(home, create=False)
        attempt, plan = _load_attempt_and_plan(ledger, args.run_id, args.channel)
        ledger.require_no_active_blockers(args.run_id)
        adapter = get_channel_adapter(args.channel)
        requested_platform_id = str(args.platform_id).strip()
        expected_preview_id = adapter.local_preview_id(plan.artifact)
        is_local_preview = requested_platform_id == expected_preview_id
        if requested_platform_id.startswith("local-preview:"):
            if (
                not is_local_preview
                or getattr(adapter, "no_prior_write_contract", False) is not True
                or getattr(adapter, "contract_verified", False) is not True
            ):
                raise AuthorizationRequired("local preview requires a verified adapter no_prior_write_contract opt-in")
        elif not is_local_preview:
            ledger.require_authorization(args.run_id, "upload", plan.upload_confirmation_digest)
        observed_fields = _load_json_mapping(Path(args.observed_fields), "observed_fields")
        adapter.ensure_contract_fields(observed_fields)
        finalized_plan = finalize_submission_plan(plan, requested_platform_id, observed_fields, args.final_action)
        ledger.save_submission_plan(args.run_id, finalized_plan)
        _write_plan_snapshot(_ensure_attempt_layout(home, args.run_id), finalized_plan)
        _transition_to_submission_confirmation(ledger, attempt, finalized_plan)
        updated_attempt = ledger.get_attempt(args.run_id)
        updated_plan = ledger.load_submission_plan(args.run_id)
        payload = _serialize_attempt_status(updated_attempt, updated_plan, ledger.load_frozen_fields_for_attempt(args.run_id), ledger)
        _emit(args.json, payload, _render_status_text(payload))
        return 0
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        ChannelContractError,
        AuthorizationRequired,
        InvalidTransition,
        RecoveryBlocked,
    ) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_authorize(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        ledger = _open_ledger(home, create=False)
        attempt, plan = _load_attempt_and_plan(ledger, args.run_id, args.channel)
        del attempt
        expected = plan.upload_confirmation_digest if args.kind == "upload" else plan.submission_confirmation_digest
        if not expected:
            raise AuthorizationRequired(f"{args.kind} authorization requires the current persisted plan digest")
        if args.digest != expected:
            raise AuthorizationRequired(f"{args.kind} authorization must match the current persisted plan digest")
        confirmed_at = args.confirmed_at or "local-confirmation"
        ledger.add_authorization(args.run_id, args.kind, args.digest, confirmed_at)
        updated_attempt = ledger.get_attempt(args.run_id)
        updated_plan = ledger.load_submission_plan(args.run_id)
        payload = _serialize_attempt_status(updated_attempt, updated_plan, ledger.load_frozen_fields_for_attempt(args.run_id), ledger)
        payload["authorized_kind"] = args.kind
        payload["authorized_digest"] = args.digest
        _emit(args.json, payload, _render_status_text(payload))
        return 0
    except (FileNotFoundError, KeyError, AuthorizationRequired, RecoveryBlocked, ValueError) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_record(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        ledger = _open_ledger(home, create=False)
        event_name = str(args.event).strip().lower()
        evidence_payload = _read_evidence_payload(Path(args.evidence))
        if event_name == _ORPHAN_OWNERSHIP_CANCEL_EVENT:
            ledger.release_orphaned_ownership(args.run_id, args.channel, evidence_payload)
            payload = {
                "run_id": args.run_id,
                "channel": args.channel,
                "recorded_event": event_name,
                "ownership_released": True,
            }
            _emit(args.json, payload, "{0} {1}".format(args.channel, event_name))
            return 0
        attempt, plan = _load_attempt_and_plan(ledger, args.run_id, args.channel)
        blocked_result = False
        if event_name in _BLOCKER_EVENTS:
            commands = _recovery_commands_from_evidence(evidence_payload)
            _validate_blocker_evidence(event_name, evidence_payload)
            ledger.record_blocker(args.run_id, event_name, evidence_payload, commands)
        elif event_name == "attempt_failed":
            commands = _recovery_commands_from_evidence(evidence_payload)
            streak = ledger.record_failure(args.run_id, str(evidence_payload.get("failure_signature", "")), evidence_payload, commands)
            evidence_payload = {**dict(evidence_payload), "failure_signature": streak.failure_signature}
            blocked_result = streak.consecutive_count >= 3
        elif event_name == "readback_recovered":
            ledger.reset_failure_streak(args.run_id, evidence_payload)
        elif event_name in _RESOLUTION_EVENTS:
            if _RESOLUTION_EVENTS[event_name] == "retry_exhausted":
                ledger.reset_failure_streak(args.run_id, evidence_payload)
            else:
                ledger.resolve_blocker(args.run_id, _RESOLUTION_EVENTS[event_name], evidence_payload)
        elif event_name in _OWNERSHIP_EVENTS:
            ledger.release_ownership(args.run_id)
            ledger.resolve_blocker(args.run_id, "concurrent_attempt", evidence_payload)
        else:
            target = _EVENT_TO_STATE.get(event_name)
            if target is None:
                raise ValueError("record only accepts documented lifecycle events or recovery events")
            _validate_record_evidence(attempt, plan, event_name, evidence_payload)
            if target == PublishState.AWAITING_SUBMISSION_CONFIRMATION and attempt.state == PublishState.AWAITING_UPLOAD_CONFIRMATION:
                raise InvalidTransition("finalize the current plan before recording submission readiness")
            ledger.transition(args.run_id, target, event_name, evidence_payload)
        _persist_record_evidence(_ensure_attempt_layout(home, args.run_id), event_name, evidence_payload)
        updated_attempt = ledger.get_attempt(args.run_id)
        updated_plan = ledger.load_submission_plan(args.run_id)
        payload = _serialize_attempt_status(updated_attempt, updated_plan, ledger.load_frozen_fields_for_attempt(args.run_id), ledger)
        payload["recorded_event"] = event_name
        _emit(args.json, payload, _render_status_text(payload))
        if event_name == "submission_unknown":
            return _SUBMISSION_UNKNOWN_EXIT
        return _BLOCK_EXIT if blocked_result else 0
    except (FileNotFoundError, KeyError, AuthorizationRequired, RecoveryBlocked, InvalidTransition, ValueError) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_status(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        if args.source is not None:
            if args.run_id is not None or args.channel is not None:
                raise ValueError("status accepts either RUN_ID CHANNEL or --source SOURCE")
            source_identifier = _resolve_source_id(args.source)
            ledger = _open_ledger(home, create=False, read_only=True)
            payload = {"attempts": json.loads(ledger.export(source_identifier, "json"))}
            _emit(args.json, payload, _render_source_status_text(payload))
            return 0
        if args.run_id is None or args.channel is None:
            raise ValueError("status requires RUN_ID CHANNEL or --source SOURCE")
        ledger = _open_ledger(home, create=False, read_only=True)
        attempt, plan = _load_attempt_and_plan(ledger, args.run_id, args.channel)
        payload = _serialize_attempt_status(attempt, plan, ledger.load_frozen_fields_for_attempt(args.run_id), ledger)
        _emit(args.json, payload, _render_status_text(payload))
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return _emit_error(args.json, exc, _ERROR_EXIT)


def _handle_export(args: argparse.Namespace) -> int:
    try:
        home = _resolve_home(args.home)
        ledger = _open_ledger(home, create=False)
        if args.source_id is not None and args.source is not None:
            raise ValueError("export accepts either --source-id or --source")
        source_identifier = args.source_id if args.source is None else _resolve_source_id(args.source)
        exported = redact_text(ledger.export(source_identifier, args.format))
        output_path = Path(args.output).expanduser().resolve()
        _write_atomic(output_path, exported)
        print(redact_text(str(output_path)))
        return 0
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(False, exc, _ERROR_EXIT)


def _load_local_inputs(
    source_root: Path,
    home: Path,
    ai_review_path: Optional[str],
    profile_path: Optional[str] = None,
) -> tuple[SourceSnapshot, Mapping[str, object], EvidenceBundle, Optional[AIReview], str]:
    snapshot = load_source(source_root)
    profile, profile_origin = _load_profile(home, snapshot, profile_path)
    evidence = load_evidence(profile, snapshot)
    ai_review = load_ai_review(Path(ai_review_path), snapshot) if ai_review_path else None
    return snapshot, profile, evidence, ai_review, profile_origin


def _load_profile(
    home: Path, snapshot: SourceSnapshot, explicit_path: Optional[str] = None
) -> tuple[Mapping[str, object], str]:
    if explicit_path is None:
        profile_path = home / "config" / "profile.json"
        if not profile_path.is_file():
            return build_generated_profile(snapshot), GENERATED_PROFILE_ORIGIN
        origin = STORED_PROFILE_ORIGIN
    else:
        profile_path = Path(explicit_path).expanduser().resolve()
        origin = PROVIDED_PROFILE_ORIGIN
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(redact_text(f"missing profile: {profile_path}")) from exc
    except UnicodeDecodeError as exc:
        raise ValueError("profile.json must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("profile.json must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("profile.json must decode to a mapping")
    return apply_source_defaults(payload, snapshot), origin


def _augment_dossier(dossier, profile: Mapping[str, object]):
    excluded = {"schema_version", "capabilities", "channel_edits", "commercial", "pricing", "claims", "core_claims"}
    merged_facts = dict(dossier.facts)
    for key, value in profile.items():
        if key in excluded:
            continue
        if key == "author" and isinstance(value, Mapping):
            display_name = value.get("display_name") or value.get("name")
            if display_name is not None and str(display_name).strip():
                merged_facts["author"] = str(display_name).strip()
            continue
        merged_facts[str(key)] = value
    return replace(dossier, facts=merged_facts)


def _build_execution_plan_from_profile(
    snapshot: SourceSnapshot,
    profile: Mapping[str, object],
    commands: Sequence[CommandEvidence],
):
    if not commands:
        return None
    execution = profile.get("execution", {})
    if execution is None:
        execution = {}
    if not isinstance(execution, Mapping):
        raise ValueError("execution config must be a mapping")
    timeout_seconds = int(execution.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
    permitted_env_names = execution.get("permitted_env_names", ())
    if isinstance(permitted_env_names, (str, bytes)):
        permitted_env_names = (str(permitted_env_names),)
    if not isinstance(permitted_env_names, Sequence):
        raise ValueError("permitted_env_names must be a sequence")
    return build_execution_plan(
        snapshot,
        tuple(item.command for item in commands),
        snapshot.root,
        timeout_seconds,
        tuple(str(name) for name in permitted_env_names),
    )


def _apply_command_results(bundle: EvidenceBundle, results: Sequence[CommandEvidence]) -> EvidenceBundle:
    command_iter = iter(results)

    def _apply(items: Sequence[EvidenceItem]) -> tuple[EvidenceItem, ...]:
        updated: list[EvidenceItem] = []
        for item in items:
            if item.provenance != "command":
                updated.append(item)
                continue
            result = next(command_iter)
            updated.append(replace(item, passed=result.returncode == 0))
        return tuple(updated)

    return EvidenceBundle(core=_apply(bundle.core), optional=_apply(bundle.optional), commands=tuple(results))


def _normalize_channels(raw_channels: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in raw_channels:
        for candidate in str(raw).split(","):
            key = candidate.strip()
            if not key:
                continue
            if key not in CHANNEL_KEYS:
                raise ValueError(f"unknown channel: {key}")
            if key not in normalized:
                normalized.append(key)
    if not normalized:
        raise ValueError("at least one channel is required")
    return tuple(normalized)


def _account_alias(profile: Mapping[str, object], channel_key: str) -> str:
    accounts = profile.get("accounts", {})
    if not isinstance(accounts, Mapping):
        raise ValueError("profile.accounts must be a mapping")
    alias = accounts.get(channel_key)
    if alias is None or not str(alias).strip():
        raise ValueError(f"profile.accounts.{channel_key} is required")
    return str(alias).strip()


def _channel_edits(profile: Mapping[str, object], channel_key: str) -> Mapping[str, str]:
    raw_edits = profile.get("channel_edits", {})
    if raw_edits is None:
        return {}
    if not isinstance(raw_edits, Mapping):
        raise ValueError("profile.channel_edits must be a mapping")
    channel_edits = raw_edits.get(channel_key, {})
    if channel_edits is None:
        return {}
    if not isinstance(channel_edits, Mapping):
        raise ValueError("profile.channel_edits.{0} must be a mapping".format(channel_key))
    return {str(key): "" if value is None else str(value) for key, value in channel_edits.items()}


def _resolve_home(explicit: Optional[str]) -> Path:
    return resolve_publisher_home(None if explicit is None else Path(explicit), os.environ)


def _resolve_source_id(source: str) -> str:
    source_root = Path(source).expanduser().resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(redact_text(f"missing source: {source_root}"))
    return build_source_id(source_root)


def _state_db_path(home: Path) -> Path:
    return home / "state" / "publisher.sqlite3"


def _open_ledger(home: Path, *, create: bool, read_only: bool = False) -> Ledger:
    path = _state_db_path(home)
    if not create and not path.is_file():
        raise FileNotFoundError(redact_text(f"missing ledger: {path}"))
    if read_only:
        return Ledger.open_readonly(path)
    return Ledger.open(path)


def _build_attempt_artifact(home: Path, snapshot: SourceSnapshot, channel: str, staging_files: Mapping[str, bytes]) -> Artifact:
    scratch_root = home / ".scratch-artifacts"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as temp_dir:
        try:
            temp_artifact = build_artifact(snapshot, channel, staging_files, Path(temp_dir))
        except ValueError as exc:
            raise ArtifactPreparationBlocked("artifact_build_failed", str(exc)) from exc
        findings = verify_artifact(temp_artifact, temp_artifact.files)
        blocking = tuple(finding for finding in findings if finding.severity == GateSeverity.BLOCK)
        if blocking:
            first = blocking[0]
            raise ArtifactPreparationBlocked(first.code, first.message)
        attempt_id = _attempt_id(snapshot, channel, temp_artifact.sha256)
        output_dir = _ensure_attempt_layout(home, attempt_id) / "artifacts"
        archive_path = output_dir / temp_artifact.path.name
        manifest_source = temp_artifact.path.with_name(temp_artifact.path.name + ".manifest.json")
        manifest_path = archive_path.with_name(archive_path.name + ".manifest.json")
        os.replace(temp_artifact.path, archive_path)
        os.replace(manifest_source, manifest_path)
        return replace(temp_artifact, path=archive_path)


def _attempt_id(snapshot: SourceSnapshot, channel: str, artifact_sha256: str) -> str:
    seed = "::".join((snapshot.source_digest, snapshot.version, channel, artifact_sha256))
    return __import__("hashlib").sha256(seed.encode("utf-8")).hexdigest()[:32]


def _discard_artifact(home: Path, artifact: Artifact) -> None:
    path = Path(artifact.path)
    for target in (path, path.with_name(path.name + ".manifest.json")):
        try:
            target.unlink()
        except FileNotFoundError:
            pass
    run_root = path.parent.parent
    for name in ("reports", "dossiers", "artifacts", "plans", "reviews", "evidence"):
        try:
            (run_root / name).rmdir()
        except OSError:
            pass
    try:
        run_root.rmdir()
    except OSError:
        pass


def _ensure_attempt_layout(home: Path, run_id: str) -> Path:
    root = attempt_root(home, run_id)
    for name in ("reports", "dossiers", "artifacts", "plans", "reviews", "evidence"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _write_prepare_artifacts(
    attempt_dir: Path,
    dossier,
    report: GateReport,
    plan: SubmissionPlan,
    frozen: FrozenFields,
) -> None:
    (attempt_dir / "dossiers" / "dossier.json").write_text(render_dossier_json(dossier), encoding="utf-8")
    (attempt_dir / "dossiers" / "dossier.md").write_text(render_dossier_markdown(dossier), encoding="utf-8")
    (attempt_dir / "reports" / "quality.json").write_text(
        json.dumps(_serialize_report(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_plan_snapshot(attempt_dir, plan)
    (attempt_dir / "dossiers" / "frozen-fields.json").write_text(
        json.dumps(_serialize_frozen_fields(frozen), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_plan_snapshot(attempt_dir: Path, plan: SubmissionPlan) -> None:
    (attempt_dir / "plans" / "submission-plan.json").write_text(
        json.dumps(_serialize_plan(plan), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _transition_prepare_attempt(
    ledger: Ledger,
    attempt_id: str,
    local_preview_plan: Optional[SubmissionPlan],
) -> None:
    _move_to_state(ledger, attempt_id, PublishState.CHECKED, "quality_passed", {"next_action": "prepare_channel_artifact"})
    _move_to_state(
        ledger,
        attempt_id,
        PublishState.PREPARED,
        "artifact_prepared",
        {"next_action": "choose_upload_or_finalize"},
    )
    if local_preview_plan is None:
        _move_to_state(
            ledger,
            attempt_id,
            PublishState.AWAITING_UPLOAD_CONFIRMATION,
            "upload_confirmation_ready",
            {"next_action": "confirm_upload"},
        )
        return
    _move_to_state(
        ledger,
        attempt_id,
        PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        "local_preview_finalized",
        {"product_id": local_preview_plan.platform_id, "next_action": "confirm_submit"},
    )


def _build_local_preview_plan(
    adapter,
    profile: Mapping[str, object],
    plan: SubmissionPlan,
    artifact: Artifact,
) -> Optional[SubmissionPlan]:
    preview = profile.get("local_preview")
    if preview is None:
        return None
    if not isinstance(preview, Mapping):
        raise ValueError("local_preview must be a mapping")
    if preview.get("enabled") is not True:
        return None
    _validate_local_preview_config(adapter, profile, plan.fields)
    observed_fields = {str(key): "" if value is None else str(value) for key, value in preview.get("observed_fields", plan.fields).items()}
    final_action = str(preview.get("final_action", "submit_review"))
    return finalize_submission_plan(plan, adapter.local_preview_id(artifact), observed_fields, final_action)  # type: ignore[arg-type]


def _validate_local_preview_config(adapter, profile: Mapping[str, object], fields: Mapping[str, str]) -> None:
    preview = profile.get("local_preview")
    if preview is None:
        return
    if not isinstance(preview, Mapping):
        raise ValueError("local_preview must be a mapping")
    if preview.get("enabled") is not True:
        return
    if getattr(adapter, "no_prior_write_contract", False) is not True or getattr(adapter, "contract_verified", False) is not True:
        raise ValueError("local_preview requires adapter no_prior_write_contract opt-in")
    observed_fields_raw = preview.get("observed_fields", fields)
    if not isinstance(observed_fields_raw, Mapping):
        raise ValueError("local_preview.observed_fields must be a mapping")
    observed_fields = {str(key): "" if value is None else str(value) for key, value in observed_fields_raw.items()}
    try:
        adapter.ensure_contract_fields(observed_fields)
    except ChannelContractError as exc:
        raise ValueError(str(exc)) from exc
    if observed_fields != {str(key): str(value) for key, value in fields.items()}:
        raise ValueError("local_preview.observed_fields must exactly match current plan fields")


def _move_to_state(ledger: Ledger, attempt_id: str, target: PublishState, event: str, evidence: Mapping[str, Any]) -> None:
    current = ledger.get_attempt(attempt_id).state
    if current == target:
        return
    ledger.transition(attempt_id, target, event, evidence)


def _load_attempt_and_plan(ledger: Ledger, run_id: str, channel: str):
    attempt = ledger.get_attempt(run_id)
    if attempt.channel != channel:
        raise ValueError("run_id does not match the requested channel")
    return attempt, ledger.load_submission_plan(run_id)


def _transition_to_submission_confirmation(ledger: Ledger, attempt, plan: SubmissionPlan) -> None:
    current = attempt.state
    if current in (PublishState.AWAITING_UPLOAD_CONFIRMATION, PublishState.AWAITING_SUBMISSION_CONFIRMATION):
        ledger.transition(
            attempt.attempt_id,
            PublishState.PREPARED,
            "finalize_reopened",
            {"next_action": "re_finalize_current_plan"},
        )
        current = PublishState.PREPARED
    if current not in (
        PublishState.PREPARED,
        PublishState.UPLOADED,
        PublishState.PARSING,
    ):
        raise InvalidTransition(f"{current.value} cannot be finalized")
    event = "local_preview_finalized" if str(plan.platform_id).startswith("local-preview:") else "prefill_verified"
    ledger.transition(
        attempt.attempt_id,
        PublishState.AWAITING_SUBMISSION_CONFIRMATION,
        event,
        {"product_id": plan.platform_id, "next_action": "confirm_submit"},
    )


def _load_json_mapping(path: Path, label: str) -> Mapping[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must decode to a mapping")
    normalized = {}
    for key, value in payload.items():
        text_key = str(key).strip()
        if not text_key:
            raise ValueError(f"{label} keys must be non-empty strings")
        normalized[text_key] = "" if value is None else str(value)
    return normalized


def _read_evidence_payload(path: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as exc:
        raise ValueError("evidence file must be UTF-8") from exc
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return {"note": redact_text(text)}
    if not isinstance(payload, Mapping):
        raise ValueError("evidence file must contain a JSON object")
    return {str(key): value for key, value in payload.items()}


def _validate_record_evidence(attempt, plan: SubmissionPlan, event_name: str, evidence: Mapping[str, Any]) -> None:
    if event_name not in _EVIDENCE_REQUIRED_EVENTS and event_name != "submission_unknown":
        return
    raw_status = str(evidence.get("raw_status", "")).strip()
    product_id = str(evidence.get("product_id", "")).strip()
    source_version = str(evidence.get("source_version", "")).strip()
    if not raw_status:
        raise ValueError(f"{event_name} evidence requires non-empty raw_status")
    if not product_id or product_id != str(plan.platform_id or ""):
        raise ValueError(f"{event_name} evidence product_id must match the finalized plan")
    if not source_version or source_version != attempt.source_version:
        raise ValueError(f"{event_name} evidence source_version must match the attempt")
    if event_name == "live" and not str(evidence.get("public_url", "")).strip():
        raise ValueError("live evidence requires non-empty public_url")
    if event_name == "review_submitted" and plan.final_action != "submit_review":
        raise ValueError("review_submitted must match finalized plan final_action=submit_review")
    if event_name == "publish" and plan.final_action != "publish":
        raise ValueError("publish must match finalized plan final_action=publish")
    if event_name == "submission_unknown" and str(evidence.get("final_action", "")).strip() != plan.final_action:
        raise ValueError("submission_unknown evidence final_action must match the finalized plan")


def _persist_record_evidence(attempt_dir: Path, event_name: str, payload: Mapping[str, Any]) -> None:
    evidence_path = attempt_dir / "evidence" / f"{event_name}.json"
    sanitized = _redact_jsonable(payload)
    evidence_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _recovery_commands_from_evidence(evidence: Mapping[str, Any]) -> tuple[tuple[str, ...], ...]:
    raw_commands = evidence.get("recovery_commands")
    if not isinstance(raw_commands, Sequence) or isinstance(raw_commands, (str, bytes)):
        raise ValueError("blocking evidence requires recovery_commands argument arrays")
    commands: list[tuple[str, ...]] = []
    for command in raw_commands:
        if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
            raise ValueError("recovery_commands must be argument arrays, not shell strings")
        values = tuple(str(value) for value in command)
        if not values or any(not value.strip() for value in values):
            raise ValueError("recovery command arguments must be non-empty")
        commands.append(values)
    if not commands:
        raise ValueError("blocking evidence requires recovery_commands")
    return tuple(commands)


def _validate_blocker_evidence(event_name: str, evidence: Mapping[str, Any]) -> None:
    if event_name == "remote_drift":
        if not isinstance(evidence.get("local_fields"), Mapping) or not isinstance(evidence.get("remote_fields"), Mapping):
            raise ValueError("remote_drift evidence requires local_fields and remote_fields mappings")
        if dict(evidence["local_fields"]) == dict(evidence["remote_fields"]):
            raise ValueError("remote_drift evidence requires a local/remote difference")


def _ownership_recovery_commands(owner, channel: str) -> tuple[tuple[str, ...], ...]:
    if owner.owner_attempt_id:
        return (
            (
                "python3",
                "scripts/publisher.py",
                "record",
                owner.owner_attempt_id,
                channel,
                "--event",
                "ownership_handoff",
                "--evidence",
                "ownership-handoff.json",
            ),
        )
    return (
        (
            "python3",
            "scripts/publisher.py",
            "record",
            owner.claim_ref,
            channel,
            "--event",
            _ORPHAN_OWNERSHIP_CANCEL_EVENT,
            "--evidence",
            "ownership-claim-cancelled.json",
        ),
    )


def _serialize_snapshot(snapshot: SourceSnapshot) -> dict[str, Any]:
    return {
        "name": snapshot.name,
        "version": snapshot.version,
        "kind": snapshot.kind,
        "source_digest": snapshot.source_digest,
        "files": list(snapshot.files),
        "git_commit": snapshot.git_commit,
        "git_branch": snapshot.git_branch,
        "git_dirty": snapshot.git_dirty,
        "untracked_files": list(snapshot.untracked_files),
    }


def _serialize_report(report: GateReport) -> dict[str, Any]:
    return {
        "allowed": report.allowed,
        "removed_claims": list(report.removed_claims),
        "findings": [_serialize_finding(item) for item in report.findings],
    }


def _serialize_finding(finding: Finding) -> dict[str, Any]:
    return {
        "code": finding.code,
        "severity": finding.severity.value if isinstance(finding.severity, GateSeverity) else str(finding.severity),
        "message": finding.message,
        "path": finding.path,
        "claim": finding.claim,
        "provenance": finding.provenance,
    }


def _serialize_execution_plan(plan) -> dict[str, Any]:
    return {
        "source_digest": plan.source_digest,
        "commands": [list(command) for command in plan.commands],
        "cwd": str(plan.cwd),
        "timeout_seconds": plan.timeout_seconds,
        "permitted_env_names": list(plan.permitted_env_names),
        "digest": plan.digest,
    }


def _serialize_command_evidence(item: CommandEvidence) -> dict[str, Any]:
    return {
        "command": list(item.command),
        "returncode": item.returncode,
        "stdout": item.stdout,
        "stderr": item.stderr,
    }


def _serialize_plan(plan: SubmissionPlan) -> dict[str, Any]:
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
        "disclosure": _json_safe(plan.disclosure),
        "upload_confirmation_digest": plan.upload_confirmation_digest,
        "platform_id": plan.platform_id,
        "observed_fields": dict(plan.observed_fields),
        "final_action": plan.final_action,
        "submission_confirmation_digest": plan.submission_confirmation_digest,
        "manual_fallback": list(plan.manual_fallback),
    }


def _serialize_attempt_status(
    attempt,
    plan: SubmissionPlan,
    frozen: Optional[FrozenFields] = None,
    ledger: Optional[Ledger] = None,
) -> dict[str, Any]:
    payload = {
        "run_id": attempt.attempt_id,
        "channel": attempt.channel,
        "state": attempt.state.value,
        "raw_status": attempt.raw_status or "",
        "account_alias": attempt.account_alias,
        "product_id": attempt.product_id or "",
        "public_url": attempt.public_url or "",
        "artifact_sha256": attempt.artifact_sha256,
        "upload_confirmation_digest": plan.upload_confirmation_digest,
        "submission_confirmation_digest": plan.submission_confirmation_digest,
        "remote_write_recorded": _remote_write_recorded(attempt.state, plan),
        "plan": _serialize_plan(plan),
    }
    if frozen is not None:
        payload["frozen_fields"] = _serialize_frozen_fields(frozen)
    if ledger is not None:
        payload["blocking_flags"] = [
            {
                "flag": blocker.flag,
                "evidence": dict(blocker.evidence),
                "recovery_commands": [list(command) for command in blocker.recovery_commands],
                "created_at": blocker.created_at,
            }
            for blocker in ledger.active_blockers(attempt.attempt_id)
        ]
        streak = ledger.failure_streak(attempt.attempt_id)
        payload["failure_streak"] = {
            "failure_signature": streak.failure_signature,
            "consecutive_count": streak.consecutive_count,
        }
    return _redact_jsonable(payload)


def _serialize_frozen_fields(frozen: FrozenFields) -> dict[str, Any]:
    return {
        "human_edits": dict(frozen.values),
        "drifted_fields": list(frozen.drifted_fields),
        "generated_facts": dict(frozen.generated_facts),
    }


def _serialize_profile(
    origin: str, missing_inputs: Sequence[Mapping[str, object]] = ()
) -> dict[str, Any]:
    return {
        "origin": origin,
        "missing_inputs": [
            {
                "channel": str(item["channel"]),
                "fields": [str(field) for field in item.get("fields", ())],
            }
            for item in missing_inputs
        ],
    }


def _serialize_missing_input_channel(item: Mapping[str, object]) -> dict[str, Any]:
    channel = str(item["channel"])
    fields = tuple(str(field) for field in item.get("fields", ()))
    field_list = ", ".join(fields)
    return {
        "run_id": "",
        "channel": channel,
        "state": PublishState.BLOCKED.value,
        "error_code": "missing_user_input",
        "error": "Channel preparation needs non-secret facts that cannot be inferred safely.",
        "missing_inputs": list(fields),
        "manual_fallback": [
            "Provide or observe only these fields: {0}.".format(field_list),
            "Use any browser for visible account or form checks; do not share passwords, cookies, tokens, QR payloads, or browser storage.",
        ],
        "remote_write_recorded": False,
    }


def _serialize_blocked_channel(channel: str, exc: Exception, manual_fallback: Sequence[str]) -> dict[str, Any]:
    code = str(getattr(exc, "code", "channel_blocked"))
    error = redact_text(str(getattr(exc, "message", str(exc))))
    fallback = tuple(getattr(exc, "manual_fallback", ())) or tuple(manual_fallback)
    return {
        "run_id": "",
        "channel": channel,
        "state": PublishState.BLOCKED.value,
        "error_code": code,
        "error": error,
        "manual_fallback": [redact_text(str(item)) for item in fallback],
        "remote_write_recorded": False,
    }


def _serialize_concurrent_attempt(channel: str, owner, recovery_commands: Sequence[Sequence[str]]) -> dict[str, Any]:
    return _redact_jsonable(
        {
            "run_id": "",
            "channel": channel,
            "state": PublishState.BLOCKED.value,
            "error_code": "concurrent_attempt",
            "error": "an active local owner already holds this source/version/channel scope",
            "wait": True,
            "owner": {
                "run_id": owner.owner_attempt_id or "",
                "claim_ref": owner.claim_ref,
                "created_at": owner.created_at,
                "source_id": owner.source_id,
                "source_version": owner.source_version,
                "channel": owner.channel,
            },
            "blocking_flags": [
                {
                    "flag": "concurrent_attempt",
                    "recovery_commands": [list(command) for command in recovery_commands],
                }
            ],
            "recovery_commands": [list(command) for command in recovery_commands],
            "remote_write_recorded": False,
        }
    )


def _remote_write_recorded(state: PublishState, plan: SubmissionPlan) -> bool:
    if state in _REMOTE_WRITE_STATES:
        return True
    if state == PublishState.AWAITING_SUBMISSION_CONFIRMATION:
        platform_id = str(plan.platform_id or "")
        return not platform_id.startswith("local-preview:")
    return False


def _emit(json_mode: bool, payload: Mapping[str, Any], text: str) -> None:
    if json_mode:
        print(json.dumps(_redact_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(text)


def _emit_error(json_mode: bool, exc: Exception, exit_code: int) -> int:
    message = redact_text(str(exc))
    if json_mode:
        print(json.dumps({"error": message}, ensure_ascii=False, sort_keys=True))
    else:
        print(message)
    return exit_code


def _render_check_text(payload: Mapping[str, Any]) -> str:
    report = payload["report"]
    lines = [
        "allowed={0}".format("yes" if report["allowed"] else "no"),
        "findings={0}".format(len(report["findings"])),
    ]
    profile = payload.get("profile")
    if isinstance(profile, Mapping):
        lines.append("profile_origin={0}".format(profile.get("origin", "unknown")))
        groups = profile.get("missing_inputs", ())
        missing_count = sum(
            len(item.get("fields", ()))
            for item in groups
            if isinstance(item, Mapping)
        )
        lines.append("missing_inputs={0}".format(missing_count))
    execution_plan = payload.get("execution_plan")
    if execution_plan is not None:
        lines.append("execution_digest={0}".format(execution_plan["digest"]))
    return "\n".join(lines)


def _render_prepare_text(payload: Mapping[str, Any]) -> str:
    if not payload["attempts"]:
        return _render_check_text(payload)
    lines: list[str] = []
    for item in payload["attempts"]:
        line = "{channel} {state} {run_id}".format(
            channel=item["channel"],
            state=item["state"],
            run_id=item.get("run_id", ""),
        ).rstrip()
        missing = item.get("missing_inputs", ())
        if missing:
            line += " missing_inputs={0}".format(",".join(str(field) for field in missing))
        lines.append(line)
    return "\n".join(lines)


def _render_status_text(payload: Mapping[str, Any]) -> str:
    return "{channel} {state} {run_id}".format(
        channel=payload["channel"],
        state=payload["state"],
        run_id=payload["run_id"],
    )


def _render_source_status_text(payload: Mapping[str, Any]) -> str:
    attempts = payload["attempts"]
    if not attempts:
        return "no local attempts"
    return "\n".join(
        "{channel} {status}".format(channel=item["channel"], status=item["status"])
        for item in attempts
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _redact_jsonable(value: Any, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {str(child_key): _redact_jsonable(child, str(child_key)) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_redact_jsonable(item, key) for item in value]
    if isinstance(value, tuple):
        return [_redact_jsonable(item, key) for item in value]
    if isinstance(value, str):
        lowered = key.lower()
        if lowered != "account_alias" and ("account" in lowered or "email" in lowered):
            return "[REDACTED_ACCOUNT]"
        if any(marker in lowered for marker in ("token", "secret", "password", "passwd", "cookie", "qr")):
            return "[REDACTED_PRIVATE]"
        return redact_text(value)
    return value


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)
