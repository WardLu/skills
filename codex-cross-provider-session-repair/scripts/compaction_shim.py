#!/usr/bin/env python3
"""Supply Codex remote-compaction-v2 on behalf of a non-OpenAI backend.

Codex remote compaction v2 is an OpenAI-server-side feature. The client side of
the contract is:

* a compaction request is an ordinary ``POST /responses`` call whose
  ``client_metadata["x-codex-turn-metadata"]`` carries
  ``"request_kind": "compaction"`` (the header ``x-codex-beta-features``
  contains ``remote_compaction_v2``), with ``tools: []`` and an input ending in
  the *CONTEXT CHECKPOINT COMPACTION* prompt;
* the reply must contain exactly one output item of
  ``{"type": "compaction", "encrypted_content": "<string>"}``;
* Codex base64-decodes ``encrypted_content``, builds a handoff message from it,
  records a ``compacted`` entry in the rollout, and adds its own ``id``
  (``cmp_...``) to the item.

A third-party backend answers that prompt with an ordinary assistant message,
so Codex observes zero compaction items and aborts the turn with
``remote compaction v2 expected exactly one compaction output item, got 0 from
N output items``.

This shim sits between Codex and such a backend and supplies the missing half:

* compaction request -> forward as-is (the prompt already asks for a handoff
  summary), then re-wrap the model's text as a ``compaction`` item whose
  ``encrypted_content`` is this shim's own base64 encoding;
* normal turn -> stream through unchanged, except that any replayed
  ``compaction`` item in the input is expanded back into a readable message so
  the upstream model actually sees the compacted context.

The shim must stay in the request path for as long as the session may need to
compact; if it is not running, every request through the configured provider
base URL fails. See ``README.md`` for the supported topologies and for the
offline repair runner in ``repair_session_offline.py``.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import http.server
import json
import sys
import time
from pathlib import Path
from typing import Any

HOP_HEADERS = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
})

REMOTE_COMPACTION_BETA = "remote_compaction_v2"
COMPACTION_PROMPT_MARKER = "CONTEXT CHECKPOINT COMPACTION"

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 5098
DEFAULT_UPSTREAM_HOST = "127.0.0.1"
DEFAULT_UPSTREAM_PORT = 5000

CHUNK_BYTES = 16384
UPSTREAM_TIMEOUT_SECONDS = 900


def _iter_sse_events(raw: bytes):
    """Yield decoded JSON objects from a raw Server-Sent-Events body."""
    for block in raw.split(b"\n\n"):
        data: bytes | None = None
        for line in block.split(b"\n"):
            if line.startswith(b"data:"):
                data = line[5:].strip()
        if not data or data == b"[DONE]":
            continue
        try:
            event = json.loads(data)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def sse_event(payload: dict[str, Any]) -> bytes:
    return (
        f"event: {payload['type']}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    ).encode("utf-8")


def parse_turn_metadata(headers: Any) -> dict[str, Any]:
    """Return the decoded ``x-codex-turn-metadata`` object, or an empty dict."""
    raw = headers.get("x-codex-turn-metadata") if headers else None
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def detect_request_kind(headers: Any, body: bytes, allow_prompt_marker: bool = False) -> str:
    """Classify a ``/responses`` body as ``"compaction"`` or ``"turn"``.

    ``client_metadata["x-codex-turn-metadata"]["request_kind"]`` is authoritative.
    The ``x-codex-beta-features`` header alone is not sufficient on its own for
    every build, so it is only a secondary signal. The prompt marker is opt-in
    because a normal conversation can legitimately quote that text.
    """
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        parsed = None

    if isinstance(parsed, dict):
        metadata = parsed.get("client_metadata")
        if isinstance(metadata, dict):
            turn_metadata = metadata.get("x-codex-turn-metadata")
            if isinstance(turn_metadata, str):
                try:
                    turn_metadata = json.loads(turn_metadata)
                except ValueError:
                    turn_metadata = None
            if isinstance(turn_metadata, dict) and turn_metadata.get("request_kind") == "compaction":
                return "compaction"

    beta = headers.get("x-codex-beta-features") if headers else None
    if isinstance(beta, str) and REMOTE_COMPACTION_BETA in beta:
        return "compaction"

    if allow_prompt_marker and COMPACTION_PROMPT_MARKER.encode("utf-8") in body:
        return "compaction"
    return "turn"


def encode_summary(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def decode_summary(payload: Any) -> str | None:
    if not isinstance(payload, str):
        return None
    try:
        return base64.b64decode(payload, validate=True).decode("utf-8")
    except (ValueError, TypeError):
        return None


def expand_compaction_items(body: bytes) -> bytes:
    """Replace replayed ``compaction`` inputs with readable messages.

    Codex normally turns a compaction item into a handoff message itself, so
    this is a safety net for items this shim did not produce (for example after
    an operator switched backends) and for builds that replay the raw item.
    """
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return body
    if not isinstance(parsed, dict) or not isinstance(parsed.get("input"), list):
        return body

    changed = False
    rewritten: list[Any] = []
    for item in parsed["input"]:
        if isinstance(item, dict) and item.get("type") == "compaction":
            summary = decode_summary(item.get("encrypted_content"))
            if summary is None:
                summary = "(compacted conversation context is not readable by this backend)"
            rewritten.append({
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": "<compacted-context>\n" + summary + "\n</compacted-context>",
                }],
            })
            changed = True
        else:
            rewritten.append(item)

    if not changed:
        return body
    parsed["input"] = rewritten
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def extract_compaction_result(raw: bytes) -> tuple[str, dict[str, Any] | None, str]:
    """Return ``(assistant_text, usage, response_id)`` from an upstream SSE body.

    Text is taken from streamed deltas when present, otherwise from
    ``response.output_item.done`` items, otherwise from the final
    ``response.completed.output`` array. The three sources are mutually
    exclusive so the summary is never duplicated.
    """
    delta_parts: list[str] = []
    item_parts: list[str] = []
    final_parts: list[str] = []
    usage: dict[str, Any] | None = None
    response_id = "resp_shim"
    for event in _iter_sse_events(raw):
        event_type = event.get("type")
        if event_type == "response.completed":
            response = event.get("response")
            if isinstance(response, dict):
                if isinstance(response.get("usage"), dict):
                    usage = response["usage"]
                if isinstance(response.get("id"), str):
                    response_id = response["id"]
                for item in response.get("output") or []:
                    if isinstance(item, dict) and item.get("type") == "message":
                        for content in item.get("content") or []:
                            if isinstance(content, dict) and content.get("type") in (
                                "output_text", "text"
                            ):
                                final_parts.append(content.get("text") or "")
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "message":
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                    item_parts.append(content.get("text") or "")
        delta = event.get("delta")
        if isinstance(delta, str) and isinstance(event_type, str) and event_type.endswith(
            "output_text.delta"
        ):
            delta_parts.append(delta)
    parts = delta_parts or item_parts or final_parts
    return "".join(parts), usage, response_id


def build_compaction_sse(summary: str, usage: dict[str, Any] | None, response_id: str) -> bytes:
    """Build the SSE body Codex expects for a compaction request."""
    item = {"type": "compaction", "encrypted_content": encode_summary(summary)}
    response = {
        "id": response_id,
        "status": "completed",
        "output": [item],
        "usage": usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    return b"".join((
        sse_event({"type": "response.created",
                   "response": {"id": response_id, "status": "in_progress"}}),
        sse_event({"type": "response.output_item.done",
                   "output_index": 0, "item": item}),
        sse_event({"type": "response.completed", "response": response}),
    ))


class CompactionShimHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    upstream_host = DEFAULT_UPSTREAM_HOST
    upstream_port = DEFAULT_UPSTREAM_PORT
    log_file: Path | None = None
    log_bodies = False
    allow_prompt_marker = False

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _upstream_headers(self, body: bytes) -> dict[str, str]:
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        headers["Host"] = f"{self.upstream_host}:{self.upstream_port}"
        headers["Content-Length"] = str(len(body))
        return headers

    def _record(self, kind: str, body: bytes) -> None:
        if self.log_file is None:
            return
        entry: dict[str, Any] = {
            "ts": time.time(),
            "kind": kind,
            "method": self.command,
            "path": self.path,
            "bytes": len(body),
        }
        if self.log_bodies:
            entry["body"] = body.decode("utf-8", "replace")
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _forward_buffered(self, body: bytes) -> tuple[int, list[tuple[str, str]], bytes]:
        connection = http.client.HTTPConnection(
            self.upstream_host, self.upstream_port, timeout=UPSTREAM_TIMEOUT_SECONDS
        )
        try:
            connection.request(self.command, self.path, body=body,
                               headers=self._upstream_headers(body))
            response = connection.getresponse()
            raw = response.read()
            headers = [(k, v) for k, v in response.getheaders() if k.lower() not in HOP_HEADERS]
            return response.status, headers, raw
        finally:
            try:
                connection.close()
            except Exception:
                pass

    def _forward_streamed(self, body: bytes) -> None:
        connection = http.client.HTTPConnection(
            self.upstream_host, self.upstream_port, timeout=UPSTREAM_TIMEOUT_SECONDS
        )
        try:
            connection.request(self.command, self.path, body=body,
                               headers=self._upstream_headers(body))
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            try:
                connection.close()
            except Exception:
                pass

    def _relay_error(self, status: int, headers: list[tuple[str, str]], raw: bytes) -> None:
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def _handle(self) -> None:
        body = self._read_body()
        path = self.path.split("?")[0]
        is_responses = self.command.upper() == "POST" and path.rstrip("/").endswith("/responses")
        kind = detect_request_kind(self.headers, body, self.allow_prompt_marker) if is_responses else "turn"
        self._record(kind, body)

        if is_responses and kind == "compaction":
            try:
                status, headers, raw = self._forward_buffered(body)
            except Exception as exc:  # noqa: BLE001 - report upstream failure to the client
                self.send_error(502, f"upstream request failed: {exc}")
                return
            if status != 200:
                self._relay_error(status, headers, raw)
                return
            summary, usage, response_id = extract_compaction_result(raw)
            if not summary.strip():
                summary = "(compaction produced no summary)"
            payload = build_compaction_sse(summary, usage, response_id)
            sys.stderr.write(f"[compaction-shim] compaction -> {len(summary)} chars summarised\n")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            return

        outbound = expand_compaction_items(body) if is_responses else body
        try:
            self._forward_streamed(outbound)
        except Exception as exc:  # noqa: BLE001 - report upstream failure to the client
            self.send_error(502, f"upstream request failed: {exc}")

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle
    do_PATCH = _handle
    do_OPTIONS = _handle
    do_HEAD = _handle

    def log_message(self, *args: Any) -> None:  # silence per-request access logging
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST)
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    parser.add_argument("--upstream-host", default=DEFAULT_UPSTREAM_HOST,
                        help="Backend the shim forwards to")
    parser.add_argument("--upstream-port", type=int, default=DEFAULT_UPSTREAM_PORT)
    parser.add_argument("--log-file", help="Optional JSONL request log (metadata only by default)")
    parser.add_argument("--log-bodies", action="store_true",
                        help="Also log request bodies; may contain private conversation data")
    parser.add_argument("--allow-prompt-marker", action="store_true",
                        help="Fall back to matching the compaction prompt text when "
                             "structured metadata is absent (can misfire on quoted text)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = type("ConfiguredShimHandler", (CompactionShimHandler,), {})
    handler.upstream_host = args.upstream_host
    handler.upstream_port = args.upstream_port
    handler.log_file = Path(args.log_file).expanduser() if args.log_file else None
    handler.log_bodies = bool(args.log_bodies)
    handler.allow_prompt_marker = bool(args.allow_prompt_marker)
    server = http.server.ThreadingHTTPServer((args.listen_host, args.listen_port), handler)
    print(
        f"[compaction-shim] {args.listen_host}:{args.listen_port} -> "
        f"{args.upstream_host}:{args.upstream_port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
