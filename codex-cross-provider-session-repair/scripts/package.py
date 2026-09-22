#!/usr/bin/env python3
"""Create a distributable .skill archive using only the standard library."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


# "dist" is the documented `--output` directory, so it must never be packaged:
# building into it would otherwise nest the previous archive inside the new one.
EXCLUDED_DIRS = {"__pycache__", ".git", "evals", "dist"}
EXCLUDED_NAMES = {".DS_Store"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    name = root.name
    output = (args.output or root.parent).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{name}.skill"
    # When the archive is written inside the skill directory (the documented
    # `--output ./dist` usage), exclude everything under the output directory
    # and the archive itself, otherwise each build nests the previous archive.
    archive_resolved = archive.resolve()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in EXCLUDED_DIRS for part in relative.parts) or path.name in EXCLUDED_NAMES:
                continue
            resolved = path.resolve()
            if resolved == archive_resolved or output in resolved.parents:
                continue
            handle.write(path, Path(name) / relative)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
