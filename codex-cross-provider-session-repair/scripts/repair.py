#!/usr/bin/env python3
"""Diagnose and repair one Codex session without touching unrelated sessions.

The script deliberately uses only Python's standard library so it can run on a
fresh machine. It is dry-run by default; pass --apply to write changes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STALE_ITEM_RE = re.compile(r"Item with id ['\"](rs_[^'\"]+)['\"] not found")
PROVIDER_RE = re.compile(r"^\s*model_provider\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def resolve_codex_home(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        profile = os.environ.get("USERPROFILE")
        if profile:
            return (Path(profile) / ".codex").resolve()
    return (Path.home() / ".codex").resolve()


def find_rollout(codex_home: Path, session_id: str) -> Path:
    sessions = codex_home / "sessions"
    if not sessions.is_dir():
        raise FileNotFoundError(f"sessions directory not found: {sessions}")

    exact = sorted(sessions.rglob(f"rollout-*-{session_id}.jsonl"))
    if exact:
        return exact[0]

    # Filename conventions have changed across Codex versions, so fall back to
    # checking session_meta records without reading any other Codex artifacts.
    for candidate in sorted(sessions.rglob("rollout-*.jsonl")):
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = item.get("payload", {})
                    if item.get("type") == "session_meta" and payload.get("id") == session_id:
                        return candidate
        except OSError:
            continue
    raise FileNotFoundError(f"rollout for session {session_id} not found under {sessions}")


def read_jsonl(path: Path) -> tuple[list[str], list[dict[str, Any] | None], list[int]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    records: list[dict[str, Any] | None] = []
    errors: list[int] = []
    for number, line in enumerate(lines, 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append(None)
            errors.append(number)
    return lines, records, errors


def read_global_provider(codex_home: Path) -> str | None:
    config = codex_home / "config.toml"
    if not config.is_file():
        return None
    match = PROVIDER_RE.search(config.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def read_thread_row(database: Path, session_id: str) -> dict[str, Any] | None:
    if not database.is_file():
        return None
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA query_only = ON")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "threads" not in tables:
            return None
        columns = [row[1] for row in connection.execute("PRAGMA table_info(threads)")]
        wanted = [name for name in ("id", "model_provider", "model", "cwd", "archived") if name in columns]
        if "id" not in wanted:
            return None
        row = connection.execute(
            f"SELECT {', '.join(wanted)} FROM threads WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(zip(wanted, row)) if row else None
    except sqlite3.Error as exc:
        return {"error": f"SQLite read failed: {exc}"}
    finally:
        try:
            if connection is not None:
                connection.close()
        except Exception:
            pass


def read_stale_ids(database: Path, session_id: str) -> list[str]:
    if not database.is_file():
        return []
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA query_only = ON")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "logs" not in tables:
            return []
        rows = connection.execute(
            "SELECT feedback_log_body FROM logs WHERE thread_id = ?", (session_id,)
        ).fetchall()
        found: set[str] = set()
        for (body,) in rows:
            found.update(STALE_ITEM_RE.findall(body or ""))
        return sorted(found)
    except sqlite3.Error:
        return []
    finally:
        try:
            if connection is not None:
                connection.close()
        except Exception:
            pass


def inspect_session(codex_home: Path, session_id: str) -> dict[str, Any]:
    rollout = find_rollout(codex_home, session_id)
    lines, records, parse_errors = read_jsonl(rollout)
    session_meta: list[dict[str, Any]] = []
    reasoning_ids: list[str] = []
    for record in records:
        if not record:
            continue
        payload = record.get("payload") or {}
        if record.get("type") == "session_meta":
            session_meta.append({
                "id": payload.get("id"),
                "model_provider": payload.get("model_provider"),
                "cwd": payload.get("cwd"),
            })
        if record.get("type") == "response_item" and payload.get("type") == "reasoning":
            if payload.get("id"):
                reasoning_ids.append(payload["id"])

    root_db = codex_home / "state_5.sqlite"
    stale_ids = read_stale_ids(codex_home / "logs_2.sqlite", session_id)
    reasoning_set = set(reasoning_ids)
    target_meta = [item for item in session_meta if item.get("id") == session_id]
    return {
        "session_id": session_id,
        "codex_home": str(codex_home),
        "rollout_path": str(rollout),
        "line_count": len(lines),
        "json_parse_errors": parse_errors,
        "session_meta": session_meta,
        "target_session_meta": target_meta,
        "global_provider": read_global_provider(codex_home),
        "root_thread": read_thread_row(root_db, session_id),
        "stale_remote_item_ids": stale_ids,
        "stale_ids_present_as_reasoning": sorted(set(stale_ids) & reasoning_set),
        "reasoning_item_count": len(reasoning_ids),
        "reasoning_item_ids": reasoning_ids,
        "child_database_present": (codex_home / "sqlite" / "state_5.sqlite").is_file(),
    }


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_file(path: Path, label: str) -> Path:
    destination = path.with_name(f"{path.name}.bak-{label}-{timestamp()}")
    shutil.copy2(path, destination)
    return destination


def rewrite_session(
    report: dict[str, Any],
    provider: str | None,
    fix_provider: bool,
    remove_reasoning: str,
) -> tuple[Path | None, int, int]:
    path = Path(report["rollout_path"])
    lines, records, parse_errors = read_jsonl(path)
    if parse_errors:
        raise ValueError(f"refusing to rewrite malformed JSONL; lines: {parse_errors[:10]}")

    stale = set(report["stale_ids_present_as_reasoning"])
    backup = backup_file(path, "session-repair")
    output: list[str] = []
    removed = 0
    provider_updates = 0
    for original, record in zip(lines, records):
        assert record is not None
        payload = record.get("payload") or {}
        if record.get("type") == "response_item" and payload.get("type") == "reasoning":
            item_id = payload.get("id")
            if remove_reasoning == "all" or (remove_reasoning == "stale" and item_id in stale):
                removed += 1
                continue
        if (
            fix_provider
            and provider
            and record.get("type") == "session_meta"
            and payload.get("id") == report["session_id"]
            and payload.get("model_provider") != provider
        ):
            payload["model_provider"] = provider
            record["payload"] = payload
            provider_updates += 1
            output.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            continue
        output.append(original)

    temporary = path.with_name(f".{path.name}.repair-{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write("".join(output))
    try:
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return backup, removed, provider_updates


def update_thread_provider(codex_home: Path, session_id: str, provider: str) -> Path | None:
    database = codex_home / "state_5.sqlite"
    row = read_thread_row(database, session_id)
    if not row or row.get("error") or "model_provider" not in row:
        return None
    if row["model_provider"] == provider:
        return None
    backup = backup_file(database, "session-repair")
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(database) + suffix)
        if sidecar.is_file():
            shutil.copy2(sidecar, Path(str(backup) + suffix))
    connection = sqlite3.connect(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE threads SET model_provider = ? WHERE id = ?", (provider, session_id)
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return backup


def print_report(report: dict[str, Any], as_json: bool) -> None:
    safe = dict(report)
    # The full reasoning ID list is useful for local debugging but noisy in the
    # normal report. Keep the count and the exact stale IDs only.
    safe.pop("reasoning_item_ids", None)
    if as_json:
        print(json.dumps(safe, ensure_ascii=False, indent=2))
        return
    print(f"Session: {safe['session_id']}")
    print(f"Rollout: {safe['rollout_path']}")
    print(f"JSONL: {safe['line_count']} lines; parse errors={len(safe['json_parse_errors'])}")
    print(f"Global provider: {safe['global_provider'] or '(not found)'}")
    print(f"Target session_meta: {safe['target_session_meta']}")
    print(f"Root threads row: {safe['root_thread'] or '(not found)'}")
    print(f"Remote stale IDs: {safe['stale_remote_item_ids']}")
    print(f"Stale IDs present as local reasoning: {safe['stale_ids_present_as_reasoning']}")
    print(f"Local reasoning records: {safe['reasoning_item_count']}")
    print(f"Child sqlite database present: {safe['child_database_present']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True, help="Target Codex session UUID")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--provider", help="Current provider to write when --fix-provider is used")
    parser.add_argument("--fix-provider", action="store_true", help="Repair target session_meta and DB provider")
    parser.add_argument(
        "--remove-reasoning",
        choices=("none", "stale", "all"),
        default="none",
        help="Remove exact stale reasoning IDs, or all internal reasoning records",
    )
    parser.add_argument("--apply", action="store_true", help="Write the requested repair; default is dry-run")
    parser.add_argument("--json", action="store_true", help="Print the diagnostic report as JSON")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        codex_home = resolve_codex_home(args.codex_home)
        report = inspect_session(codex_home, args.session_id)
        print_report(report, args.json)
        if not args.apply:
            print("Dry run only. Re-run with --apply after fully quitting Codex Desktop.")
            return 0
        if report["json_parse_errors"]:
            raise ValueError("refusing to apply: JSONL has parse errors")
        if args.fix_provider and not args.provider:
            raise ValueError("--fix-provider requires --provider")
        if args.remove_reasoning == "stale" and not report["stale_ids_present_as_reasoning"]:
            print("No stale local reasoning IDs matched; no session rewrite needed.")
        session_backup = None
        removed = 0
        provider_updates = 0
        if args.remove_reasoning != "none" or args.fix_provider:
            session_backup, removed, provider_updates = rewrite_session(
                report, args.provider, args.fix_provider, args.remove_reasoning
            )
        db_backup = None
        if args.fix_provider and args.provider:
            db_backup = update_thread_provider(codex_home, args.session_id, args.provider)
        print(f"Applied: removed_reasoning={removed}, session_meta_provider_updates={provider_updates}")
        if session_backup:
            print(f"Session backup: {session_backup}")
        if db_backup:
            print(f"Database backup: {db_backup}")
        print("Post-repair report:")
        print_report(inspect_session(codex_home, args.session_id), args.json)
        return 0
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
