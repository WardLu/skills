"""Deterministic, private Skill channel artifact construction and verification."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Mapping, Optional, Sequence
import zipfile

from .models import Artifact, Finding, GateSeverity, SourceSnapshot

_FIXED_DATE = (1980, 1, 1, 0, 0, 0)
_FILE_MODE = (stat.S_IFREG | 0o644) << 16
_MAX_MEMBER_BYTES = 10 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
_SECRET = re.compile(r"(?:-----BEGIN .*PRIVATE KEY-----|(?:token|api[_-]?key|secret|password)\s*[:=]|\bgh[pousr]_)", re.I)
_PRIVATE_PATH = re.compile(r"(?:/(?:Users|home)/[^/\s]+|[A-Za-z]:[\\/]Users[\\/][^\\/\s]+)", re.I)
_ALLOWED_ROOTS = {"SKILL.md", "LICENSE", "VERSION"}
_ALLOWED_DIRS = {"scripts", "references", "assets", "templates"}
_EXCLUDED_NAMES = {"README.md", "README.txt", "CHANGELOG.md", "RELEASE_NOTES.md"}
_EXCLUDED_COMPONENTS = {"private", "internal", "tests", "__pycache__"}
_EXCLUDED_BASENAMES = {"readme", "changelog", "release_notes"}


def build_artifact(
    snapshot: SourceSnapshot,
    channel: str,
    staging_files: Mapping[str, bytes],
    output_dir: Path,
) -> Artifact:
    """Build a reproducible ZIP in ``output_dir`` without changing source files."""

    if not isinstance(channel, str) or not channel.strip() or "/" in channel or "\\" in channel:
        raise ValueError("channel must be a non-empty name")
    if not isinstance(staging_files, Mapping):
        raise TypeError("staging_files must be a mapping")

    files: dict[str, bytes] = {}
    # Snapshot files are the source of truth; staging is an intentional,
    # channel-scoped overlay (for example, generated metadata).
    if channel != "workbuddy":
        for name in snapshot.files:
            if _is_allowed(name, channel=channel, snapshot_name=snapshot.name):
                files[name] = _read_source_file(snapshot, name)
    for name, payload in staging_files.items():
        _validate_member_name(name)
        if not isinstance(payload, bytes):
            raise TypeError(f"staging file {name!r} must contain bytes")
        if channel == "workbuddy" and not name.startswith(f"skills/{snapshot.name}/"):
            if name != "LICENSE":
                raise ValueError("workbuddy_package_path_invalid")
        if not _is_allowed(name, channel=channel, snapshot_name=snapshot.name):
            if channel == "workbuddy" and name.startswith("skills/"):
                raise ValueError("workbuddy_package_path_invalid")
        else:
            files[name] = payload

    license_bytes = Path(snapshot.license_path).read_bytes()
    if "LICENSE" in files and files["LICENSE"] != license_bytes:
        raise ValueError("license_mismatch")
    files["LICENSE"] = license_bytes
    required_skill_path = f"skills/{snapshot.name}/SKILL.md" if channel == "workbuddy" else "SKILL.md"
    if required_skill_path not in files:
        raise ValueError("missing_skill_md")

    ordered = tuple(sorted(files))
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"{snapshot.name}-{snapshot.version}-{channel}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ordered:
            info = zipfile.ZipInfo(name, _FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = _FILE_MODE
            info.extra = b""
            info.comment = b""
            archive.writestr(info, files[name])

    digest = _sha256_file(archive_path)
    manifest = {
        "schema_version": 1,
        "channel": channel,
        "source_digest": snapshot.source_digest,
        "sha256": digest,
        "size_bytes": archive_path.stat().st_size,
        "files": list(ordered),
    }
    archive_path.with_name(archive_path.name + ".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return Artifact(channel=channel, path=archive_path, sha256=digest, size_bytes=archive_path.stat().st_size, files=ordered)


def verify_artifact(artifact: Artifact, expected_files: Sequence[str]) -> tuple[Finding, ...]:
    """Verify an artifact's digest, manifest, ZIP safety, and file allowlist."""

    findings: list[Finding] = []
    path = Path(artifact.path)
    if not path.is_file():
        return (_finding("artifact_missing", "Artifact ZIP does not exist."),)
    actual_digest = _sha256_file(path)
    if actual_digest != artifact.sha256:
        findings.append(_finding("artifact_digest_mismatch", "Artifact SHA-256 does not match metadata."))
    if path.stat().st_size != artifact.size_bytes:
        findings.append(_finding("artifact_size_mismatch", "Artifact size does not match metadata."))
    expected = tuple(expected_files)
    workbuddy_prefix = _workbuddy_prefix(expected) if artifact.channel == "workbuddy" else None
    for name in expected:
        try:
            _validate_member_name(name)
        except ValueError:
            findings.append(_finding("archive_path_escape", "Expected file contains an unsafe path.", name))

    names: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            if path.stat().st_size > _MAX_ARCHIVE_BYTES:
                findings.append(_finding("archive_too_large", "Archive exceeds the maximum size."))
            for info in archive.infolist():
                try:
                    _validate_member_name(info.filename)
                except ValueError:
                    findings.append(_finding("archive_path_escape", "Archive contains an unsafe member path.", info.filename))
                    continue
                if info.filename in names:
                    findings.append(_finding("archive_duplicate_member", "Archive contains a duplicate member.", info.filename))
                    continue
                names.append(info.filename)
                if info.compress_type != zipfile.ZIP_DEFLATED:
                    findings.append(_finding("archive_compression_unsupported", "Archive uses unsupported compression.", info.filename))
                if stat.S_ISLNK(info.external_attr >> 16):
                    findings.append(_finding("archive_symlink", "Archive contains a symlink.", info.filename))
                if info.file_size > _MAX_MEMBER_BYTES:
                    findings.append(_finding("archive_member_too_large", "Archive member exceeds the maximum size.", info.filename))
                    continue
                if not info.is_dir():
                    payload = archive.read(info)
                    try:
                        text = payload.decode("utf-8")
                    except UnicodeDecodeError:
                        findings.append(_finding("archive_invalid_utf8", "Archive member is not valid UTF-8.", info.filename))
                        text = ""
                    if _SECRET.search(text):
                        findings.append(_finding("possible_secret", "Possible secret detected in archive content.", info.filename))
                    if _PRIVATE_PATH.search(text):
                        findings.append(_finding("personal_data", "Private local path detected in archive content.", info.filename))
                    if not _is_allowed(info.filename, channel=artifact.channel, package_prefix=workbuddy_prefix):
                        findings.append(_finding("archive_unexpected_file", "Archive member is outside the runtime allowlist.", info.filename))
    except (zipfile.BadZipFile, OSError) as exc:
        findings.append(_finding("archive_invalid", f"Archive cannot be read safely: {exc}"))
        return tuple(findings)

    actual_files = tuple(sorted(names))
    if actual_files != tuple(sorted(expected)):
        findings.append(_finding("archive_file_manifest_mismatch", "Archive file list differs from expected files."))
    manifest_path = path.with_name(path.name + ".manifest.json")
    if not manifest_path.is_file():
        findings.append(_finding("artifact_manifest_missing", "Artifact manifest is missing."))
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("sha256") != actual_digest
                or manifest.get("size_bytes") != path.stat().st_size
                or tuple(manifest.get("files", ())) != actual_files
            ):
                findings.append(_finding("artifact_manifest_mismatch", "Artifact manifest does not match the ZIP."))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            findings.append(_finding("artifact_manifest_invalid", "Artifact manifest is invalid."))
    return tuple(findings)


def _validate_member_name(name: str) -> None:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("archive_path_escape")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "." in path.parts or name.endswith("/"):
        raise ValueError("archive_path_escape")


def _is_allowed(
    name: str,
    *,
    channel: Optional[str] = None,
    snapshot_name: Optional[str] = None,
    package_prefix: Optional[str] = None,
) -> bool:
    if not isinstance(name, str):
        return False
    parts = PurePosixPath(name).parts
    if (
        name in _EXCLUDED_NAMES
        or any(part.startswith(".") for part in parts)
        or any(part.lower() in _EXCLUDED_COMPONENTS for part in parts)
        or any(_is_excluded_document(part) for part in parts)
    ):
        return False
    if name in _ALLOWED_ROOTS or (len(parts) >= 2 and parts[0] in _ALLOWED_DIRS):
        return True
    prefix = package_prefix
    if channel == "workbuddy" and snapshot_name:
        prefix = f"skills/{snapshot_name}/"
    if not prefix or not name.startswith(prefix) or len(name) <= len(prefix):
        return False
    nested = name[len(prefix):]
    nested_parts = PurePosixPath(nested).parts
    if any(part.startswith(".") for part in nested_parts):
        return False
    if any(part.lower() in _EXCLUDED_COMPONENTS for part in nested_parts):
        return False
    if any(_is_excluded_document(part) for part in nested_parts):
        return False
    if nested == "SKILL.md":
        return True
    return len(nested_parts) >= 2 and nested_parts[0] in _ALLOWED_DIRS


def _is_excluded_document(part: str) -> bool:
    """Reject excluded document names with locale/version suffixes at any depth."""

    basename = Path(part).name.lower()
    return any(
        basename == excluded
        or basename.startswith(excluded + ".")
        or basename.startswith(excluded + "-")
        or basename.startswith(excluded + "_")
        for excluded in _EXCLUDED_BASENAMES
    )


def _workbuddy_prefix(expected_files: Sequence[str]) -> Optional[str]:
    prefixes = {
        f"skills/{PurePosixPath(name).parts[1]}/"
        for name in expected_files
        if len(PurePosixPath(name).parts) >= 3 and PurePosixPath(name).parts[0] == "skills"
    }
    return prefixes.pop() if len(prefixes) == 1 else None


def _read_source_file(snapshot: SourceSnapshot, name: str) -> bytes:
    root = Path(snapshot.root).resolve()
    candidate = root / name
    # Check every component before resolving: a symlinked directory can hide
    # an otherwise apparently in-root leaf from a simple leaf check.
    current = root
    for component in PurePosixPath(name).parts:
        current /= component
        if current.is_symlink():
            raise ValueError("invalid_source_member")
    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("resource_outside_root") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid_source_member")
    return path.read_bytes()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finding(code: str, message: str, path: Optional[str] = None) -> Finding:
    return Finding(code=code, severity=GateSeverity.BLOCK, message=message, path=path)
