"""Evidence loading and trusted command execution for publisher checks."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping, Sequence

from .models import CommandEvidence, EvidenceBundle, EvidenceItem, ExecutionPlan, SourceSnapshot
from .redaction import redact_text


class EvidenceProfileError(ValueError):
    """Raised when a profile declares malformed evidence configuration."""


class ExecutionAuthorizationError(ValueError):
    """Raised when a trusted command plan is executed without matching approval."""


_ALLOWED_PROVENANCE = {"source", "command", "user", "official_page"}
_TIMEOUT_RETURN_CODE = 124
_MISSING_EXECUTABLE_RETURN_CODE = 127


def load_evidence(profile: Mapping[str, object], snapshot: SourceSnapshot) -> EvidenceBundle:
    """Load source-declared capabilities into a structured evidence bundle."""

    capabilities = profile.get("capabilities", ())
    if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes)):
        raise EvidenceProfileError("capabilities must be a sequence")

    core: list[EvidenceItem] = []
    optional: list[EvidenceItem] = []
    commands: list[CommandEvidence] = []
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, Mapping):
            raise EvidenceProfileError(f"capabilities[{index}] must be a mapping")
        capability_id = str(capability.get("id", "")).strip()
        if not capability_id:
            raise EvidenceProfileError(f"capabilities[{index}].id is required")
        evidence = capability.get("evidence")
        if not isinstance(evidence, Mapping):
            raise EvidenceProfileError(f"capabilities[{index}].evidence must be a mapping")

        evidence_type = str(evidence.get("type", "")).strip()
        if evidence_type not in _ALLOWED_PROVENANCE:
            raise EvidenceProfileError(f"capabilities[{index}].evidence.type is unsupported")
        if evidence_type == "command":
            command = _validate_declared_command(evidence, index)
            commands.append(
                CommandEvidence(
                    command=command,
                    returncode=-1,
                    stdout="",
                    stderr="",
                )
            )

        item = EvidenceItem(
            evidence_id=f"{capability_id}:{evidence_type}",
            capability=capability_id,
            core=bool(capability.get("core", False)),
            passed=_initial_pass_state(snapshot, evidence_type, evidence),
            provenance=evidence_type,
        )
        if item.core:
            core.append(item)
        else:
            optional.append(item)

    return EvidenceBundle(core=tuple(core), optional=tuple(optional), commands=tuple(commands))


def build_execution_plan(
    snapshot: SourceSnapshot,
    commands: Sequence[Sequence[str]],
    cwd: Path,
    timeout_seconds: int,
    permitted_env_names: Sequence[str],
) -> ExecutionPlan:
    """Build a source-bound execution plan with a deterministic approval digest."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    canonical_commands: list[tuple[str, ...]] = []
    for index, command in enumerate(commands):
        if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
            raise ValueError(f"commands[{index}] must be a sequence")
        parts = tuple(str(part) for part in command)
        if not parts or any(not part for part in parts):
            raise ValueError(f"commands[{index}] must contain non-empty strings")
        canonical_commands.append(parts)
    if not canonical_commands:
        raise ValueError("at least one command is required")

    resolved_cwd = Path(cwd).expanduser().resolve()
    if not resolved_cwd.is_dir():
        raise ValueError("cwd must resolve to an existing directory")

    env_names = tuple(str(name) for name in permitted_env_names)
    if any(not name or "=" in name for name in env_names):
        raise ValueError("permitted_env_names must contain non-empty variable names")

    digest = _execution_digest(
        snapshot.source_digest,
        tuple(canonical_commands),
        resolved_cwd,
        timeout_seconds,
        env_names,
    )
    return ExecutionPlan(
        source_digest=snapshot.source_digest,
        commands=tuple(canonical_commands),
        cwd=resolved_cwd,
        timeout_seconds=timeout_seconds,
        permitted_env_names=env_names,
        digest=digest,
    )


def run_trusted_commands(plan: ExecutionPlan, authorized_digest: str) -> tuple[CommandEvidence, ...]:
    """Execute a previously approved command plan with a minimal environment."""

    actual_digest = _execution_digest(
        plan.source_digest,
        plan.commands,
        plan.cwd,
        plan.timeout_seconds,
        plan.permitted_env_names,
    )
    if actual_digest != plan.digest or actual_digest != authorized_digest:
        raise ExecutionAuthorizationError("execution_digest_mismatch")

    env = {name: os.environ[name] for name in plan.permitted_env_names if name in os.environ}
    evidence: list[CommandEvidence] = []
    for command in plan.commands:
        try:
            result = subprocess.run(
                list(command),
                cwd=plan.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=plan.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            evidence.append(
                CommandEvidence(
                    command=command,
                    returncode=_TIMEOUT_RETURN_CODE,
                    stdout=redact_text(exc.stdout or ""),
                    stderr=redact_text((exc.stderr or "") + f"timed out after {plan.timeout_seconds} seconds"),
                )
            )
            continue
        except FileNotFoundError as exc:
            evidence.append(
                CommandEvidence(
                    command=command,
                    returncode=_MISSING_EXECUTABLE_RETURN_CODE,
                    stdout="",
                    stderr=redact_text(str(exc)),
                )
            )
            continue

        evidence.append(
            CommandEvidence(
                command=command,
                returncode=result.returncode,
                stdout=redact_text(result.stdout),
                stderr=redact_text(result.stderr),
            )
        )

    return tuple(evidence)


def _initial_pass_state(snapshot: SourceSnapshot, evidence_type: str, evidence: Mapping[str, object]) -> bool:
    if evidence_type == "command":
        return False
    if "passed" in evidence and not bool(evidence.get("passed")):
        return False
    if evidence_type == "source":
        return _has_valid_source_evidence(snapshot, evidence)
    if evidence_type in {"user", "official_page"}:
        return _has_valid_observed_evidence(evidence)
    return False


def _validate_declared_command(evidence: Mapping[str, object], index: int) -> tuple[str, ...]:
    command = evidence.get("command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
        raise EvidenceProfileError(f"capabilities[{index}].evidence.command must be a sequence")
    parts = tuple(str(part) for part in command)
    if not parts or any(not part for part in parts):
        raise EvidenceProfileError(f"capabilities[{index}].evidence.command must contain non-empty strings")
    return parts


def _has_valid_source_evidence(snapshot: SourceSnapshot, evidence: Mapping[str, object]) -> bool:
    relative = _non_empty_text(evidence.get("path"))
    if relative is None:
        return False
    if _unsafe_relative_path(relative):
        return False
    if _non_empty_text(evidence.get("source_digest")) != snapshot.source_digest:
        return False
    if relative not in snapshot.files:
        return False
    try:
        resolved = (snapshot.root / PurePosixPath(relative)).resolve(strict=True)
        resolved.relative_to(snapshot.root.resolve())
    except (FileNotFoundError, ValueError):
        return False
    return _has_summary_or_proof(evidence)


def _has_valid_observed_evidence(evidence: Mapping[str, object]) -> bool:
    if not _has_summary_or_proof(evidence):
        return False
    return _non_empty_text(evidence.get("source_url")) is not None or _non_empty_text(evidence.get("record_id")) is not None


def _has_summary_or_proof(evidence: Mapping[str, object]) -> bool:
    return any(
        _non_empty_text(evidence.get(key)) is not None
        for key in ("summary", "proof", "excerpt", "observation")
    )


def _unsafe_relative_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.is_absolute() or ".." in path.parts or relative.strip() in {"", "."}


def _non_empty_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _execution_digest(
    source_digest: str,
    commands: tuple[tuple[str, ...], ...],
    cwd: Path,
    timeout_seconds: int,
    permitted_env_names: tuple[str, ...],
) -> str:
    payload = {
        "source_digest": source_digest,
        "commands": [list(command) for command in commands],
        "cwd": str(cwd),
        "timeout_seconds": timeout_seconds,
        "permitted_env_names": list(permitted_env_names),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
