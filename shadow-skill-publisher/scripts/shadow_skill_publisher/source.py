"""Read and validate a Skill source tree into an immutable snapshot."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import subprocess
from typing import Mapping, Optional

from .models import SourceSnapshot
from .redaction import redact_text


try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised via import stub test
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_EXCLUDED_NAMES = {".git", ".DS_Store", "__pycache__", ".shadow-skill-publisher"}
_LICENSE_FILES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    "COPYING.md",
    "COPYING.txt",
)


class SourceContractError(ValueError):
    """Raised when a local Skill source violates the publisher contract."""

    def __init__(self, code: str, message: str, path: Optional[Path] = None):
        self.code = code
        self.message = message
        self.path = path
        detail = f"{code}: {message}"
        if path is not None:
            detail = f"{detail} ({redact_text(str(path))})"
        super().__init__(detail)


def load_source(root: Path) -> SourceSnapshot:
    """Validate ``root`` and capture its immutable source provenance."""

    _require_yaml_dependency()

    canonical_root = Path(root).expanduser().resolve()
    if not canonical_root.is_dir():
        raise SourceContractError(
            "invalid_root",
            "source root must be an existing directory",
            canonical_root,
        )

    skill_path = canonical_root / "SKILL.md"
    if not skill_path.is_file():
        raise SourceContractError(
            "missing_skill_md",
            "source root must contain SKILL.md",
            skill_path,
        )

    skill_md_text, document = _load_frontmatter(skill_path)
    name = _required_string(document, "name", skill_path, "invalid_name")
    if _NAME_RE.fullmatch(name) is None:
        raise SourceContractError(
            "invalid_name",
            "skill name must use kebab-case",
            skill_path,
        )

    description = _required_string(
        document,
        "description",
        skill_path,
        "missing_description",
    )
    if not description:
        raise SourceContractError(
            "missing_description",
            "description must be non-empty",
            skill_path,
        )

    version = _resolve_version(canonical_root, skill_path, document)
    license_path = _resolve_license(canonical_root, document)
    files = tuple(_collect_files(canonical_root))
    source_digest = _hash_source(canonical_root, files)
    git_commit, git_branch, git_dirty, untracked_files = _read_git_facts(canonical_root)
    kind = _infer_kind(files)

    return SourceSnapshot(
        root=canonical_root,
        name=name,
        description=description,
        version=version,
        source_digest=source_digest,
        files=files,
        license_path=license_path,
        kind=kind,
        skill_md_text=skill_md_text,
        git_commit=git_commit,
        git_branch=git_branch,
        git_dirty=git_dirty,
        untracked_files=untracked_files,
    )


def _require_yaml_dependency() -> None:
    if yaml is None:
        raise SourceContractError(
            "missing_dependency",
            "PyYAML>=6.0,<7 is required to parse SKILL.md frontmatter",
        ) from _YAML_IMPORT_ERROR


def _load_frontmatter(skill_path: Path) -> tuple[str, Mapping[str, object]]:
    try:
        text = skill_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SourceContractError(
            "invalid_utf8",
            "SKILL.md must be UTF-8 encoded",
            skill_path,
        ) from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SourceContractError(
            "invalid_frontmatter",
            "SKILL.md must start with YAML frontmatter",
            skill_path,
        )

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise SourceContractError(
            "invalid_frontmatter",
            "SKILL.md frontmatter must end with a closing delimiter",
            skill_path,
        )

    payload = "\n".join(lines[1:end_index])
    try:
        document = yaml.safe_load(payload) or {}
    except yaml.YAMLError as exc:
        raise SourceContractError(
            "invalid_frontmatter",
            "SKILL.md frontmatter must be valid YAML",
            skill_path,
        ) from exc
    if not isinstance(document, dict):
        raise SourceContractError(
            "invalid_frontmatter",
            "SKILL.md frontmatter must decode to a mapping",
            skill_path,
        )
    return text, document


def _required_string(
    document: Mapping[str, object],
    key: str,
    path: Path,
    error_code: str,
) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise SourceContractError(error_code, f"{key} is required", path)
    return value.strip()


def _resolve_version(root: Path, skill_path: Path, document: Mapping[str, object]) -> str:
    metadata = document.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise SourceContractError(
            "invalid_frontmatter",
            "metadata must be a mapping when present",
            skill_path,
        )

    candidates: list[tuple[str, str, Path]] = []
    version_file = root / "VERSION"
    if version_file.is_file():
        candidates.append(("VERSION", version_file.read_text(encoding="utf-8").strip(), version_file))

    top_level = document.get("version")
    if top_level is not None:
        candidates.append(("version", str(top_level).strip(), skill_path))

    if isinstance(metadata, dict) and metadata.get("version") is not None:
        candidates.append(("metadata.version", str(metadata["version"]).strip(), skill_path))

    present = [(origin, value, path) for origin, value, path in candidates if value]
    if not present:
        raise SourceContractError(
            "missing_version",
            "source must declare a SemVer version",
            skill_path,
        )

    for origin, value, path in present:
        if _SEMVER_RE.fullmatch(value) is None:
            raise SourceContractError(
                "invalid_version",
                f"{origin} must be a valid SemVer value",
                path,
            )

    distinct_values = {value for _, value, _ in present}
    if len(distinct_values) > 1:
        raise SourceContractError(
            "version_conflict",
            "VERSION, version, and metadata.version must match",
            skill_path,
        )
    return present[0][1]


def _resolve_license(root: Path, document: Mapping[str, object]) -> Path:
    explicit = document.get("license")
    if isinstance(explicit, str) and explicit.strip():
        explicit_path = Path(explicit.strip())
        if not explicit_path.is_absolute():
            candidate = (root / explicit_path).resolve()
            if candidate.is_file() and _license_path_in_scope(root, candidate):
                return candidate

    for candidate_root in (root, root.parent):
        for name in _LICENSE_FILES:
            candidate = candidate_root / name
            if candidate.is_file():
                return candidate.resolve()

    raise SourceContractError(
        "missing_license",
        "source must include a clearly applicable license",
        root,
    )


def _license_path_in_scope(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return candidate.parent == root.parent


def _collect_files(root: Path) -> list[str]:
    return _walk_dir(root, root, Path())


def _walk_dir(root: Path, current: Path, relative: Path) -> list[str]:
    files: list[str] = []
    for child in sorted(current.iterdir(), key=lambda path: path.name):
        if child.name in _EXCLUDED_NAMES:
            continue

        relative_child = relative / child.name
        if child.is_symlink():
            resolved = child.resolve()
            _ensure_inside_root(root, resolved, child)
            if resolved.is_dir():
                files.extend(_walk_dir(root, resolved, relative_child))
            elif resolved.is_file():
                files.append(relative_child.as_posix())
            else:
                raise SourceContractError(
                    "invalid_resource",
                    "symlink must point to a file or directory",
                    child,
                )
            continue

        if child.is_dir():
            files.extend(_walk_dir(root, child, relative_child))
            continue

        if child.is_file():
            child.resolve(strict=True)
            files.append(relative_child.as_posix())

    return files


def _hash_source(root: Path, files: tuple[str, ...]) -> str:
    digest = sha256()
    for relative in files:
        resolved = (root / relative).resolve(strict=True)
        _ensure_inside_root(root, resolved, root / relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(resolved.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _read_git_facts(root: Path) -> tuple[Optional[str], Optional[str], bool, tuple[str, ...]]:
    try:
        repo_root = Path(_git(root, "rev-parse", "--show-toplevel"))
    except SourceContractError as exc:
        if "not a git repository" in exc.message.lower():
            return None, None, False, ()
        raise

    commit = _git(root, "rev-parse", "HEAD") or None
    branch = _git(root, "branch", "--show-current") or None
    relative_root = root.relative_to(repo_root)
    porcelain = _git(
        repo_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        relative_root.as_posix(),
    )
    untracked_files = tuple(
        sorted(
            _relative_to_source_root(_parse_porcelain_path(line[3:]), relative_root)
            for line in porcelain.splitlines()
            if line.startswith("?? ")
        )
    )
    return commit, branch, bool(porcelain.strip()), untracked_files


def _infer_kind(files: tuple[str, ...]) -> str:
    for relative in files:
        if relative.startswith("scripts/"):
            return "scripted"
    return "prompt"


def _parse_porcelain_path(raw_path: str) -> str:
    value = raw_path.strip()
    if value.startswith('"') and value.endswith('"'):
        value = bytes(value[1:-1], "utf-8").decode("unicode_escape")
    return Path(value).as_posix()


def _relative_to_source_root(path_text: str, relative_root: Path) -> str:
    path = Path(path_text)
    return path.relative_to(relative_root).as_posix()


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
        raise SourceContractError("git_error", message, root) from exc
    return result.stdout.strip()


def _ensure_inside_root(root: Path, resolved: Path, original: Path) -> None:
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SourceContractError(
            "resource_outside_root",
            "source resources must stay within the source root",
            original,
        ) from exc
