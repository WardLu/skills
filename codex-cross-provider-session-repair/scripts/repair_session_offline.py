#!/usr/bin/env python3
"""Repair one over-limit session while Codex Desktop is fully quit.

Use this when a session cannot continue because remote compaction keeps
failing and the failure cannot be fixed from ``config.toml`` (see
``compaction_shim.py`` for the protocol and for builds where
``remote_compaction_v2`` is a removed flag).

The runner never edits ``config.toml``. It starts the shim on a loopback port,
then drives one turn through ``codex exec resume`` with temporary ``-c``
overrides so the turn is routed through the shim. The compaction result is
written back into the session's rollout, after which the conversation resumes
normally through the ordinary provider URL.

Safety properties:

* dry-run by default; ``--apply`` performs the run;
* timestamped backup of the rollout and the root state database before writing;
* refuses to run when a rollout has JSON parse errors;
* pins the session model for the repair turn, because ``codex exec resume``
  otherwise rewrites the session's model to the current config default;
* reports an actionable blocker when Codex still holds the thread writer lock
  (``already has an active writer``), instead of retrying blindly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import repair  # noqa: E402  (bundled sibling module)

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 5098
DEFAULT_PROMPT = "Reply with OK only. Do not call any tools."
RESUME_TIMEOUT_SECONDS = 1800
WRITER_CONFLICT_MARKERS = (
    "already has an active writer",
    "thread-store conflict",
)


def read_global_provider_name(codex_home: Path) -> str | None:
    return repair.read_global_provider(codex_home)


def read_provider_base_url(config_text: str, provider: str) -> str | None:
    """Return ``base_url`` for ``[model_providers.<provider>]``.

    Prefers ``tomllib`` (Python 3.11+) and falls back to a section-scoped regex
    so the script keeps working on Python 3.9 without third-party packages.
    """
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

    if tomllib is not None:
        try:
            data = tomllib.loads(config_text)
        except Exception:
            data = None
        if isinstance(data, dict):
            providers = data.get("model_providers")
            if isinstance(providers, dict):
                entry = providers.get(provider)
                if isinstance(entry, dict) and isinstance(entry.get("base_url"), str):
                    return entry["base_url"]

    section = re.search(
        rf"^\[model_providers\.(?:\"{re.escape(provider)}\"|{re.escape(provider)})\]\s*$",
        config_text,
        re.MULTILINE,
    )
    if not section:
        return None
    tail = config_text[section.end():]
    next_section = re.search(r"^\[", tail, re.MULTILINE)
    body = tail[: next_section.start()] if next_section else tail
    match = re.search(r'^\s*base_url\s*=\s*"([^"]+)"', body, re.MULTILINE)
    return match.group(1) if match else None


def derive_shim_base_url(original_base_url: str, listen_port: int, listen_host: str = DEFAULT_LISTEN_HOST) -> str:
    """Point ``original_base_url`` at the shim while preserving its path prefix."""
    parsed = urllib.parse.urlsplit(original_base_url)
    path = parsed.path or ""
    return f"http://{listen_host}:{listen_port}{path}"


def upstream_host_port(base_url: str) -> tuple[str, int]:
    parsed = urllib.parse.urlsplit(base_url)
    host = parsed.hostname or DEFAULT_LISTEN_HOST
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def free_port(host: str = DEFAULT_LISTEN_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def session_model(records: list[dict[str, Any] | None], thread_row: dict[str, Any] | None) -> str | None:
    """Prefer the desktop's thread snapshot, then the newest structured setting."""
    if thread_row and isinstance(thread_row.get("model"), str):
        return thread_row["model"]
    models = repair.read_structured_models(records)
    return models[-1] if models else None


def count_compacted_records(records: list[dict[str, Any] | None]) -> int:
    return sum(1 for record in records if record and record.get("type") == "compacted")


def last_task_complete_error(records: list[dict[str, Any] | None]) -> Any:
    for record in reversed(records):
        if not record or record.get("type") != "event_msg":
            continue
        payload = record.get("payload") or {}
        if payload.get("type") == "task_complete":
            return payload.get("error")
    return None


def classify_run_output(output: str) -> str:
    """Return ``"writer-conflict"``, ``"compaction-error"`` or ``"ok"``."""
    lowered = output.lower()
    for marker in WRITER_CONFLICT_MARKERS:
        if marker in lowered:
            return "writer-conflict"
    if repair.REMOTE_COMPACTION_ERROR_RE.search(output):
        return "compaction-error"
    return "ok"


def session_cwd(records: list[dict[str, Any] | None], fallback: Path) -> Path:
    for record in records:
        if not record or record.get("type") != "session_meta":
            continue
        cwd = (record.get("payload") or {}).get("cwd")
        if isinstance(cwd, str) and cwd:
            candidate = Path(cwd)
            if candidate.is_dir():
                return candidate
    return fallback


def build_resume_command(
    codex_bin: str,
    session_id: str,
    provider: str,
    shim_base_url: str,
    model: str | None,
    prompt: str,
    compact_token_limit: int | None,
) -> list[str]:
    command = [codex_bin, "exec", "resume", "--skip-git-repo-check"]
    command += ["-c", f'model_providers.{provider}.base_url="{shim_base_url}"']
    if model:
        command += ["-c", f"model={model}"]
    if compact_token_limit:
        command += ["-c", f"model_auto_compact_token_limit={compact_token_limit}"]
    command += [session_id, prompt]
    return command


def wait_for_listener(host: str, port: int, deadline_seconds: float = 10.0) -> bool:
    end = time.time() + deadline_seconds
    while time.time() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.2)
    return False


def backup_session(codex_home: Path, rollout: Path) -> list[Path]:
    """Back up the rollout and root state database next to their originals.

    Backups stay beside the source file (the convention used by the rest of
    this skill) so a backup can never be mistaken for a live rollout by path
    globs that look for ``rollout-*.jsonl``.
    """
    backups = [repair.backup_file(rollout, "session-repair")]
    for name in ("state_5.sqlite", "state_5.sqlite-wal", "state_5.sqlite-shm"):
        source = codex_home / name
        if source.is_file():
            try:
                backups.append(repair.backup_file(source, "session-repair"))
            except OSError:
                pass
    return backups


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session-id", required=True, help="Target Codex session UUID")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--codex-bin", help="Codex CLI path (auto-detected when omitted)")
    parser.add_argument("--model", help="Pin the repair turn to this model "
                                        "(default: the session's recorded model)")
    parser.add_argument("--provider", help="Provider key to re-point at the shim "
                                           "(default: the global model_provider)")
    parser.add_argument("--upstream-host", help="Backend the shim forwards to "
                                                "(default: from the provider base_url)")
    parser.add_argument("--upstream-port", type=int, help="Backend port "
                                                          "(default: from the provider base_url)")
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST)
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT,
                        help="Shim port; 0 picks a free port")
    parser.add_argument("--compact-token-limit", type=int,
                        help="Temporarily lower the auto-compaction threshold so the "
                             "repair turn definitely compacts")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT,
                        help="Prompt for the repair turn; keep it a no-op confirmation")
    parser.add_argument("--apply", action="store_true", help="Perform the repair; default is a dry run")
    parser.add_argument("--json", action="store_true", help="Print the result summary as JSON")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    codex_home = repair.resolve_codex_home(args.codex_home)
    result: dict[str, Any] = {"session_id": args.session_id, "codex_home": str(codex_home)}
    try:
        rollout = repair.find_rollout(codex_home, args.session_id)
        lines, records, parse_errors = repair.read_jsonl(rollout)
        if parse_errors:
            raise ValueError(f"refusing to run: rollout has parse errors on lines {parse_errors[:5]}")

        config_path = codex_home / "config.toml"
        config_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
        provider = args.provider or repair.read_global_provider(codex_home)
        if not provider:
            raise ValueError("cannot determine the provider; pass --provider")
        base_url = read_provider_base_url(config_text, provider)
        if not base_url:
            raise ValueError(f"cannot read base_url for provider {provider!r}; check config.toml")
        default_host, default_port = upstream_host_port(base_url)
        upstream_host = args.upstream_host or default_host
        upstream_port = args.upstream_port or default_port
        listen_port = args.listen_port or free_port(args.listen_host)

        codex_bin = repair.find_codex_binary(codex_home, args.codex_bin)
        if not codex_bin:
            raise ValueError("cannot find the Codex CLI; pass --codex-bin")

        thread_row = repair.read_thread_row(codex_home / "state_5.sqlite", args.session_id)
        model = args.model or session_model(records, thread_row)
        shim_base_url = derive_shim_base_url(base_url, listen_port, args.listen_host)
        shim_script = Path(__file__).resolve().parent / "compaction_shim.py"
        if not shim_script.is_file():
            raise ValueError(f"compaction_shim.py not found next to this script: {shim_script}")

        before_compacted = count_compacted_records(records)
        before_error = last_task_complete_error(records)
        cwd = session_cwd(records, Path.home())
        command = build_resume_command(
            codex_bin, args.session_id, provider, shim_base_url, model, args.prompt,
            args.compact_token_limit,
        )

        result.update({
            "rollout": str(rollout),
            "line_count": len(lines),
            "provider": provider,
            "upstream": f"{upstream_host}:{upstream_port}",
            "shim_base_url": shim_base_url,
            "model": model,
            "compacted_before": before_compacted,
            "last_error_before": before_error,
            "cwd": str(cwd),
        })

        if not args.apply:
            result["dry_run"] = True
            _print_result(result, args.json, command=command, shim_script=shim_script)
            return 0

        backups = backup_session(codex_home, rollout)
        result["backups"] = [str(path) for path in backups]

        shim_env = dict(os.environ)
        shim = subprocess.Popen(
            [sys.executable, str(shim_script), "--listen-host", args.listen_host,
             "--listen-port", str(listen_port), "--upstream-host", upstream_host,
             "--upstream-port", str(upstream_port)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=shim_env,
        )
        run_output = ""
        try:
            if not wait_for_listener(args.listen_host, listen_port):
                raise ValueError(f"the compaction shim did not start on port {listen_port}")
            env = dict(os.environ)
            env["NO_PROXY"] = "127.0.0.1,localhost"
            env["no_proxy"] = "127.0.0.1,localhost"
            # The resume run must target the same home that was diagnosed, even
            # when --codex-home differs from the ambient CODEX_HOME.
            env["CODEX_HOME"] = str(codex_home)
            completed = subprocess.run(
                command, cwd=str(cwd), capture_output=True, text=True,
                timeout=RESUME_TIMEOUT_SECONDS, env=env,
            )
            run_output = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired:
            run_output = "timed out waiting for the repair turn"
        finally:
            shim.terminate()
            try:
                shim.wait(timeout=10)
            except subprocess.TimeoutExpired:
                shim.kill()
            shim_log = ""
            if shim.stdout is not None:
                try:
                    shim_log = shim.stdout.read() or ""
                except (OSError, ValueError):
                    shim_log = ""
                finally:
                    try:
                        shim.stdout.close()
                    except OSError:
                        pass
            result["shim_log"] = shim_log

        outcome = classify_run_output(run_output)
        result["run_outcome"] = outcome
        result["run_tail"] = run_output.strip().splitlines()[-12:]

        _, after_records, _ = repair.read_jsonl(rollout)
        after_compacted = count_compacted_records(after_records)
        after_error = last_task_complete_error(after_records)
        after_thread_row = repair.read_thread_row(codex_home / "state_5.sqlite", args.session_id)
        after_models = repair.read_structured_models(after_records)
        result.update({
            "compacted_after": after_compacted,
            "last_error_after": after_error,
            "thread_model_after": (after_thread_row or {}).get("model"),
            "last_structured_model_after": after_models[-1] if after_models else None,
        })
        result["verified"] = bool(
            after_compacted > before_compacted
            and outcome == "ok"
            and not after_error
            and (not model or all(
                value is None or value == model
                for value in ((after_thread_row or {}).get("model"), after_models[-1] if after_models else None)
            ))
        )
        if outcome == "writer-conflict":
            result["blocker"] = ("Codex still holds this thread's writer lock. Fully quit Codex "
                                 "(Cmd+Q) and confirm no codex app-server process remains, then retry.")
        _print_result(result, args.json)
        return 0 if result["verified"] else 1
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _print_result(result: dict[str, Any], as_json: bool, command: list[str] | None = None,
                  shim_script: Path | None = None) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if result.get("dry_run"):
        print("Dry run only. Re-run with --apply after fully quitting Codex Desktop.")
        print(f"Session: {result['session_id']}")
        print(f"Rollout: {result['rollout']} ({result['line_count']} lines)")
        print(f"Provider: {result['provider']} -> shim {result['shim_base_url']} -> "
              f"{result['upstream']}")
        print(f"Model pinned for the repair turn: {result['model'] or '(config default)'}")
        print(f"Existing compacted records: {result['compacted_before']}")
        print(f"Last task_complete error: {result['last_error_before']}")
        if shim_script:
            print(f"Shim script: {shim_script}")
        if command:
            print("Command that would run:")
            print("  " + " ".join(command))
        return
    print(f"Session: {result['session_id']}")
    for path in result.get("backups") or []:
        print(f"Backup: {path}")
    print(f"Run outcome: {result.get('run_outcome')}")
    print(f"Compacted records: {result.get('compacted_before')} -> {result.get('compacted_after')}")
    print(f"Last task_complete error: {result.get('last_error_before')} -> "
          f"{result.get('last_error_after')}")
    print(f"Thread model after run: {result.get('thread_model_after')}")
    for line in result.get("run_tail") or []:
        print(f"  | {line}")
    if result.get("shim_log"):
        print("Shim log:")
        for line in result["shim_log"].strip().splitlines():
            print(f"  | {line}")
    if result.get("blocker"):
        print(f"BLOCKED: {result['blocker']}")
    if result.get("verified"):
        print("Verified: the session compacted successfully. Reopen Codex and continue the thread.")
    else:
        print("Not verified: send the output above back to the agent before retrying.")


if __name__ == "__main__":
    raise SystemExit(main())
