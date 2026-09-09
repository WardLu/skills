"""Private, deterministic paths used by the publisher.

These helpers deliberately only calculate paths.  Callers decide when a write
is appropriate and are responsible for creating the returned directories.
"""

from hashlib import sha256
from os import PathLike
from pathlib import Path
import re
from typing import Mapping, Optional, Union


PathInput = Union[str, PathLike[str]]
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def resolve_publisher_home(
    explicit: Optional[Path], env: Mapping[str, str]
) -> Path:
    """Resolve the private workspace using explicit, environment, then default.

    ``HOME`` is intentionally never read or changed.  An empty environment
    value is treated as unset so it cannot produce the current directory.
    """

    candidate: Optional[PathInput] = explicit
    if candidate is None:
        configured = env.get("SHADOW_SKILL_PUBLISHER_HOME")
        if configured:
            candidate = configured
    if candidate is None:
        candidate = "~/.shadow-skill-publisher"
    return Path(candidate).expanduser().resolve()


def source_id(root: Path) -> str:
    """Return an opaque, stable identifier for a source root.

    The absolute path is hashed rather than returned, preventing reports from
    leaking the user's private directory name while retaining stable identity.
    """

    canonical = str(Path(root).expanduser().resolve())
    return sha256(canonical.encode("utf-8")).hexdigest()[:16]


def attempt_root(home: Path, run_id: str) -> Path:
    """Return the private run directory for ``run_id`` without creating it."""

    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must contain only letters, digits, '.', '_' or '-'")
    return Path(home).expanduser().resolve() / "runs" / run_id
