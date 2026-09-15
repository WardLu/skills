"""Deterministic confirmation digests for channel upload and submission gates."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any, Iterable, Literal, Mapping, Optional

from .models import Authorization, SubmissionPlan

_FINAL_ACTIONS = frozenset(("submit_review", "publish"))
_UPLOAD_ACTIONS = frozenset(("prefill", "upload", "register", "registration"))


class SubmissionPlanIncomplete(ValueError):
    """Raised when submission confirmation is requested before finalization."""


def upload_digest(plan: SubmissionPlan) -> str:
    """Return the canonical upload authorization digest for a plan."""

    return _digest_payload(_upload_payload(plan))


def finalize_submission_plan(
    plan: SubmissionPlan,
    platform_id: str,
    observed_fields: Mapping[str, str],
    final_action: Literal["submit_review", "publish"],
) -> SubmissionPlan:
    """Bind the observed platform state and final action into a new plan."""

    normalized_platform_id = _require_text(platform_id, "platform_id")
    normalized_action = _normalize_final_action(final_action)
    normalized_fields = _string_mapping(observed_fields, "observed_fields")
    if not normalized_fields:
        raise SubmissionPlanIncomplete("observed_fields must not be empty")
    finalized = replace(
        plan,
        platform_id=normalized_platform_id,
        observed_fields=normalized_fields,
        final_action=normalized_action,
        submission_confirmation_digest=None,
    )
    digest = _submission_digest_payload(finalized)
    return replace(finalized, submission_confirmation_digest=_digest_payload(digest))


def submission_digest(plan: SubmissionPlan) -> str:
    """Return the canonical submission authorization digest for a finalized plan."""

    if not plan.submission_confirmation_digest:
        raise SubmissionPlanIncomplete("submission plan has not been finalized")
    return _digest_payload(_submission_digest_payload(plan))


def can_execute_remote_action(
    plan: SubmissionPlan,
    action: str,
    authorizations: Iterable[Authorization] = (),
) -> bool:
    """Return whether the current plan has the exact recorded authorization for a remote action."""

    try:
        normalized_action = str(action).strip().lower()
        if plan.channel != plan.artifact.channel:
            return False
        upload_confirmation = _current_upload_digest(plan)
        if normalized_action in _UPLOAD_ACTIONS:
            return _has_matching_authorization(authorizations, "upload", upload_confirmation)
        if normalized_action in _FINAL_ACTIONS:
            if _normalize_final_action(plan.final_action) != normalized_action:
                return False
            submission_confirmation = _current_submission_digest(plan)
            if submission_confirmation is None:
                return False
            return _has_matching_authorization(
                authorizations,
                "upload",
                upload_confirmation,
            ) and _has_matching_authorization(
                authorizations,
                "submission",
                submission_confirmation,
            )
        return False
    except Exception:
        return False


def _current_upload_digest(plan: SubmissionPlan) -> str:
    try:
        digest = upload_digest(plan)
        persisted = _optional_text(plan.upload_confirmation_digest)
    except Exception:
        return ""
    if persisted is not None and persisted != digest:
        return ""
    return digest


def _current_submission_digest(plan: SubmissionPlan) -> Optional[str]:
    try:
        persisted = _optional_text(plan.submission_confirmation_digest)
    except Exception:
        return None
    if persisted is None:
        return None
    try:
        digest = submission_digest(plan)
    except Exception:
        return None
    if persisted != digest:
        return None
    return digest


def _has_matching_authorization(authorizations: Iterable[Authorization], kind: str, digest: str) -> bool:
    if not digest:
        return False
    try:
        for authorization in authorizations:
            if authorization.kind == kind and authorization.digest == digest:
                return True
    except Exception:
        return False
    return False


def _upload_payload(plan: SubmissionPlan) -> dict[str, Any]:
    return {
        "scope": "upload_confirmation",
        "channel": _require_text(plan.channel, "channel"),
        "contract_version": _require_text(plan.contract_version, "contract_version"),
        "account_alias": _require_text(plan.account_alias, "account_alias"),
        "artifact": {
            "channel": _require_text(plan.artifact.channel, "artifact.channel"),
            "sha256": _require_text(plan.artifact.sha256, "artifact.sha256"),
            "size_bytes": int(plan.artifact.size_bytes),
            "files": _string_sequence(plan.artifact.files),
        },
        "permissions": _string_sequence(_mapping_value(plan.disclosure, "permissions", ())),
        "external_services": _string_sequence(_mapping_value(plan.disclosure, "external_services", ())),
        "artifact_policy": _canonicalize(_mapping_value(plan.disclosure, "artifact_policy", {})),
        "listing_asset_receipts": _canonicalize(
            _mapping_value(plan.disclosure, "listing_asset_receipts", ())
        ),
        "channel_contract_checks": _canonicalize(
            {
                str(key): value
                for key, value in plan.disclosure.items()
                if str(key).endswith("_contract_checks")
            }
        ),
        "disclosure_summary": {
            "fields": _string_mapping(plan.fields, "fields"),
            "claims": _string_sequence(_mapping_value(plan.disclosure, "claims", ())),
            "removed_claims": _string_sequence(_mapping_value(plan.disclosure, "removed_claims", ())),
            "data_handling": _string_sequence(_mapping_value(plan.disclosure, "data_handling", ())),
            "risks": _string_sequence(_mapping_value(plan.disclosure, "risks", ())),
            "limitations": _string_sequence(_mapping_value(plan.disclosure, "limitations", ())),
            "disclosure": _canonicalize(_mapping_value(plan.disclosure, "disclosure_summary", {})),
        },
    }


def _submission_digest_payload(plan: SubmissionPlan) -> dict[str, Any]:
    platform_id = _require_text(plan.platform_id, "platform_id")
    final_action = _normalize_final_action(plan.final_action)
    observed_fields = _string_mapping(plan.observed_fields, "observed_fields")
    if not observed_fields:
        raise SubmissionPlanIncomplete("observed_fields must not be empty")
    return {
        "scope": "submission_confirmation",
        "upload": _upload_payload(plan),
        "platform_id": platform_id,
        "observed_fields": observed_fields,
        "final_action": final_action,
        "commercial_mode": _optional_text(_mapping_value(plan.disclosure, "commercial_mode", None)),
        "price": _optional_text(_mapping_value(plan.disclosure, "price", None)),
    }


def _digest_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_canonicalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return [_canonicalize(item) for item in sorted((str(item) for item in value), key=str)]
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mapping_value(mapping: Mapping[str, object], key: str, default: object) -> object:
    if not isinstance(mapping, Mapping):
        return default
    return mapping.get(key, default)


def _string_mapping(value: Mapping[str, str], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise SubmissionPlanIncomplete(f"{label} must be a mapping")
    normalized = {}
    for key, item in value.items():
        text_key = _require_text(key, f"{label}.key")
        normalized[text_key] = "" if item is None else str(item)
    return normalized


def _string_sequence(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [str(value)]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return [str(value)]
    return sorted((str(item) for item in value), key=str)


def _normalize_final_action(value: Optional[str]) -> str:
    text = _require_text(value, "final_action")
    if text not in _FINAL_ACTIONS:
        raise SubmissionPlanIncomplete("final_action must be submit_review or publish")
    return text


def _require_text(value: Optional[str], label: str) -> str:
    if value is None:
        raise SubmissionPlanIncomplete(f"{label} is required")
    text = str(value).strip()
    if not text:
        raise SubmissionPlanIncomplete(f"{label} is required")
    return text


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
