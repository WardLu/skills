"""Five-layer quality gate for publisher source, evidence, and AI review."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Optional, Sequence

from .models import CommandEvidence, EvidenceBundle, Finding, GateReport, GateSeverity, SourceSnapshot
from .redaction import redact_text


BLOCKING_CODES = {
    "source_contract_invalid",
    "core_not_evidenced",
    "possible_secret",
    "personal_data",
    "resource_outside_root",
    "license_missing",
    "license_scope_unknown",
    "dangerous_write_undisclosed",
    "network_access_undisclosed",
}

_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_SECRET_ASSIGNMENT = re.compile(
    r"(?:token|api[_-]?key|secret|password|passwd|access[_-]?token)\s*[:=]\s*[^\s]+",
    re.IGNORECASE,
)
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_\-]{10,}|github_pat_[A-Za-z0-9_\-]{10,}|"
    r"sk_(?:live|test)_[A-Za-z0-9]{8,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})\b"
)
_CREDENTIAL_URL = re.compile(
    r"\b(?:https?|postgres(?:ql)?|mysql|mariadb|redis)://[^/\s:@]+:[^/\s@]+@",
    re.IGNORECASE,
)
_UNIX_HOME = re.compile(r"(?<![\w])/(?:Users|home)/[^/\s\\]+", re.IGNORECASE)
_WINDOWS_HOME = re.compile(r"(?<![\w])[A-Za-z]:[\\/]Users[\\/][^\\/\s]+")
_PRIVATE_DIR_NAMES = {".git", ".shadow-skill-publisher", "internal", "private"}
_PACKAGE_EXCLUDED_DIR_NAMES = {"tests", "__pycache__"}
_NETWORK_COMMANDS = {"curl", "wget", "ping", "ssh", "scp", "rsync"}
_DANGEROUS_WRITE_COMMANDS = {"rm", "mv", "dd", "mkfs", "chmod", "chown"}
_GIT_NETWORK_SUBCOMMANDS = {"push", "pull", "fetch", "clone", "remote", "submodule", "ls-remote"}
_GIT_DESTRUCTIVE_SUBCOMMANDS = {"clean", "reset"}


def run_quality(
    snapshot: SourceSnapshot,
    evidence: EvidenceBundle,
    ai_findings: Sequence[Finding] = (),
) -> GateReport:
    """Evaluate the deterministic and advisory quality gates for a source snapshot."""

    findings: list[Finding] = []
    findings.extend(_validate_snapshot(snapshot))

    removed_claims = tuple(item.capability for item in evidence.optional if not item.passed)
    if not evidence.core or any(not item.passed for item in evidence.core):
        findings.append(
            Finding(
                code="core_not_evidenced",
                severity=GateSeverity.NOT_EVIDENCED,
                message="At least one core capability lacks verified evidence.",
            )
        )

    for capability in removed_claims:
        findings.append(
            Finding(
                code="optional_claim_removed",
                severity=GateSeverity.WARN,
                message=f"Removed unsupported optional claim: {capability}",
                claim=capability,
            )
        )

    findings.extend(_scan_source(snapshot))
    findings.extend(_scan_commands(evidence.commands))
    findings.extend(_validate_ai_findings(ai_findings))

    allowed = not any(finding.severity in {GateSeverity.BLOCK, GateSeverity.NOT_EVIDENCED} for finding in findings)
    return GateReport(allowed=allowed, findings=tuple(findings), removed_claims=removed_claims)


def _validate_snapshot(snapshot: SourceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    if not snapshot.name or not snapshot.description or not snapshot.version or not snapshot.source_digest:
        findings.append(
            Finding(
                code="source_contract_invalid",
                severity=GateSeverity.BLOCK,
                message="Source snapshot is missing required contract fields.",
            )
        )
    if len(snapshot.source_digest) != 64 or any(char not in "0123456789abcdef" for char in snapshot.source_digest.lower()):
        findings.append(
            Finding(
                code="source_contract_invalid",
                severity=GateSeverity.BLOCK,
                message="Source snapshot digest must be a 64-character hex string.",
            )
        )

    license_path = Path(snapshot.license_path)
    if not license_path.is_file():
        findings.append(
            Finding(
                code="license_missing",
                severity=GateSeverity.BLOCK,
                message="Source license file is missing.",
                path=redact_text(str(license_path)),
            )
        )
    elif not _license_in_scope(snapshot.root.resolve(), license_path.resolve()):
        findings.append(
            Finding(
                code="license_scope_unknown",
                severity=GateSeverity.BLOCK,
                message="License file must live in the source root or its immediate parent.",
                path=redact_text(str(license_path)),
            )
        )

    for relative in snapshot.files:
        path_issue = _path_issue(relative)
        if path_issue is not None:
            findings.append(path_issue)
            continue
        if _contains_private_dir(relative):
            findings.append(
                Finding(
                    code="private_workspace_content",
                    severity=GateSeverity.BLOCK,
                    message="Source includes internal or private workspace content.",
                    path=relative,
                )
            )
    return findings


def _scan_source(snapshot: SourceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    root = snapshot.root.resolve()
    for relative in snapshot.files:
        if _path_issue(relative) is not None:
            continue
        if any(part.lower() in _PACKAGE_EXCLUDED_DIR_NAMES for part in PurePosixPath(relative).parts):
            continue
        file_path = root / relative
        try:
            resolved = file_path.resolve(strict=True)
            resolved.relative_to(root)
            payload = resolved.read_bytes()
        except FileNotFoundError:
            findings.append(
                Finding(
                    code="source_contract_invalid",
                    severity=GateSeverity.BLOCK,
                    message="Snapshot references a file that no longer exists.",
                    path=relative,
                )
            )
            continue
        except ValueError:
            findings.append(
                Finding(
                    code="resource_outside_root",
                    severity=GateSeverity.BLOCK,
                    message="Snapshot references content outside the source root.",
                    path=relative,
                )
            )
            continue

        if _looks_binary(payload):
            findings.append(
                Finding(
                    code="binary_file_present",
                    severity=GateSeverity.WARN,
                    message="Binary files need manual verification before publishing.",
                    path=relative,
                )
            )
            continue

        text = payload.decode("utf-8")
        if _contains_secret(text):
            findings.append(
                Finding(
                    code="possible_secret",
                    severity=GateSeverity.BLOCK,
                    message="Possible secret or credential detected in source content.",
                    path=relative,
                )
            )
        if _contains_personal_data(text):
            findings.append(
                Finding(
                    code="personal_data",
                    severity=GateSeverity.BLOCK,
                    message="Personal data or private local paths detected in source content.",
                    path=relative,
                )
            )
    return findings


def _scan_commands(commands: Sequence[CommandEvidence]) -> list[Finding]:
    findings: list[Finding] = []
    for evidence in commands:
        if _is_network_command(evidence.command):
            findings.append(
                Finding(
                    code="network_access_undisclosed",
                    severity=GateSeverity.BLOCK,
                    message="Network-capable command requires explicit disclosure and authorization.",
                    path=" ".join(evidence.command),
                )
            )
        if _is_dangerous_write_command(evidence.command):
            findings.append(
                Finding(
                    code="dangerous_write_undisclosed",
                    severity=GateSeverity.BLOCK,
                    message="Destructive or state-changing command requires explicit disclosure and authorization.",
                    path=" ".join(evidence.command),
                )
            )
    return findings


def _validate_ai_findings(ai_findings: Sequence[Finding]) -> list[Finding]:
    findings: list[Finding] = []
    for finding in ai_findings:
        if finding.provenance != "ai_inference":
            raise ValueError("AI findings must use provenance=ai_inference")
        if finding.severity not in {GateSeverity.WARN, GateSeverity.BLOCK}:
            raise ValueError("AI findings may only use warn or block severities")
        findings.append(
            Finding(
                code=finding.code,
                severity=finding.severity,
                message=redact_text(finding.message),
                path=None if finding.path is None else redact_text(finding.path),
                claim=None if finding.claim is None else redact_text(finding.claim),
                provenance="ai_inference",
            )
        )
    return findings


def _license_in_scope(root: Path, license_path: Path) -> bool:
    try:
        license_path.relative_to(root)
        return True
    except ValueError:
        pass
    return license_path.parent == root.parent


def _path_issue(relative: str) -> Optional[Finding]:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        return Finding(
            code="resource_outside_root",
            severity=GateSeverity.BLOCK,
            message="Source file paths must remain within the source root.",
            path=relative,
        )
    return None


def _contains_private_dir(relative: str) -> bool:
    return any(part.lower() in _PRIVATE_DIR_NAMES for part in PurePosixPath(relative).parts)


def _looks_binary(payload: bytes) -> bool:
    if b"\0" in payload:
        return True
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _contains_secret(text: str) -> bool:
    return bool(
        _PRIVATE_KEY.search(text)
        or _SECRET_ASSIGNMENT.search(text)
        or _KNOWN_TOKEN.search(text)
        or _CREDENTIAL_URL.search(text)
    )


def _contains_personal_data(text: str) -> bool:
    return bool(_UNIX_HOME.search(text) or _WINDOWS_HOME.search(text))


def _is_network_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    if executable in _NETWORK_COMMANDS:
        return True
    if executable == "git" and len(command) > 1 and command[1] in _GIT_NETWORK_SUBCOMMANDS:
        return True
    return False


def _is_dangerous_write_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    if executable in _DANGEROUS_WRITE_COMMANDS:
        return True
    if executable == "git" and len(command) > 1 and command[1] in _GIT_DESTRUCTIVE_SUBCOMMANDS:
        return True
    return False
