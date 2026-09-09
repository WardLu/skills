"""Validation and persistence for imported AI review findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
import re

from .models import AIReview, Finding, GateSeverity, SourceSnapshot
from .redaction import redact_text


class AIReviewError(ValueError):
    """Raised when an imported AI review file is invalid."""


_MAX_REVIEW_BYTES = 64 * 1024
_MAX_FINDINGS = 128
_PRIVATE_PATH = re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z]:[\\/]Users[\\/][^\\/\s]+)")


def load_ai_review(path: Path, snapshot: SourceSnapshot) -> AIReview:
    """Read and validate a source-bound AI review payload."""

    review_path = Path(path)
    payload = review_path.read_bytes()
    if len(payload) > _MAX_REVIEW_BYTES:
        raise AIReviewError("review_too_large")

    try:
        document = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise AIReviewError("invalid_utf8") from exc
    except json.JSONDecodeError as exc:
        raise AIReviewError("invalid_json") from exc

    if not isinstance(document, Mapping):
        raise AIReviewError("invalid_payload")

    if document.get("schema_version") != 1:
        raise AIReviewError("unsupported_schema_version")

    if document.get("source_digest") != snapshot.source_digest:
        raise AIReviewError("source_digest_mismatch")

    raw_findings = document.get("findings", ())
    if not isinstance(raw_findings, list):
        raise AIReviewError("invalid_findings")
    if len(raw_findings) > _MAX_FINDINGS:
        raise AIReviewError("too_many_findings")

    findings = tuple(_parse_finding(index, item) for index, item in enumerate(raw_findings))
    return AIReview(schema_version=1, source_digest=snapshot.source_digest, findings=findings)


def persist_ai_review(review: AIReview, attempt_dir: Path) -> Path:
    """Persist a validated review inside the private attempt evidence tree."""

    output_path = Path(attempt_dir) / "reviews" / "ai-review.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": review.schema_version,
        "source_digest": review.source_digest,
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity.value,
                "message": redact_text(finding.message),
                "path": None if finding.path is None else redact_text(finding.path),
                "claim": None if finding.claim is None else redact_text(finding.claim),
                "provenance": finding.provenance,
            }
            for finding in review.findings
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _parse_finding(index: int, item: Any) -> Finding:
    if not isinstance(item, Mapping):
        raise AIReviewError(f"findings[{index}] must be a mapping")

    code = _required_string(item, "code", index)
    message = _required_string(item, "message", index)
    _ensure_no_private_path(message)
    severity_text = _required_string(item, "severity", index)
    if severity_text not in {"warn", "block"}:
        raise AIReviewError("invalid_severity")

    provenance = _required_string(item, "provenance", index)
    if provenance != "ai_inference":
        raise AIReviewError("invalid_provenance")

    path = item.get("path")
    if path is not None:
        if not isinstance(path, str):
            raise AIReviewError("invalid_path")
        _ensure_no_private_path(path)

    claim = item.get("claim")
    if claim is not None:
        if not isinstance(claim, str):
            raise AIReviewError("invalid_claim")
        _ensure_no_private_path(claim)

    return Finding(
        code=code,
        severity=GateSeverity(severity_text),
        message=message,
        path=path,
        claim=claim,
        provenance="ai_inference",
    )


def _required_string(item: Mapping[str, object], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AIReviewError(f"findings[{index}].{key} is required")
    return value.strip()

def _ensure_no_private_path(value: str) -> None:
    if _PRIVATE_PATH.search(value):
        raise AIReviewError("private_absolute_path")
