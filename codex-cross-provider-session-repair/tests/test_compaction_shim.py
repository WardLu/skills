import base64
import http.client
import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compaction_shim as shim  # noqa: E402


def compaction_body(request_kind="compaction", input_items=None):
    return json.dumps({
        "model": "probe-model",
        "input": input_items if input_items is not None else [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}
        ],
        "tools": [],
        "client_metadata": {
            "x-codex-turn-metadata": json.dumps({"request_kind": request_kind}),
        },
    }).encode("utf-8")


class FakeHeaders(dict):
    def get(self, key, default=None):
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


def sse(*events):
    out = b""
    for event in events:
        out += f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode("utf-8")
    return out


class DetectRequestKindTests(unittest.TestCase):
    def test_detects_compaction_from_turn_metadata(self):
        headers = FakeHeaders()
        self.assertEqual(shim.detect_request_kind(headers, compaction_body()), "compaction")

    def test_detects_normal_turn(self):
        headers = FakeHeaders()
        body = compaction_body(request_kind="turn")
        self.assertEqual(shim.detect_request_kind(headers, body), "turn")

    def test_server_wide_beta_header_marks_compaction(self):
        # Some builds advertise the beta on every request, so the header alone
        # is treated as a signal; request_kind remains the authoritative one.
        headers = FakeHeaders({"x-codex-beta-features": "remote_compaction_v2"})
        self.assertEqual(shim.detect_request_kind(headers, compaction_body(request_kind="turn")),
                         "compaction")

    def test_prompt_marker_requires_opt_in(self):
        body = json.dumps({
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "what does CONTEXT CHECKPOINT COMPACTION do?"}]}],
        }).encode("utf-8")
        self.assertEqual(shim.detect_request_kind(FakeHeaders(), body), "turn")
        self.assertEqual(shim.detect_request_kind(FakeHeaders(), body, allow_prompt_marker=True),
                         "compaction")

    def test_malformed_body_is_a_turn(self):
        self.assertEqual(shim.detect_request_kind(FakeHeaders(), b"not json"), "turn")


class PayloadTests(unittest.TestCase):
    def test_summary_round_trip(self):
        text = "交接摘要：完成 A，下一步做 B。"
        self.assertEqual(shim.decode_summary(shim.encode_summary(text)), text)

    def test_decode_rejects_non_base64(self):
        self.assertIsNone(shim.decode_summary("not-valid-base64!!"))
        self.assertIsNone(shim.decode_summary(None))

    def test_expand_replaces_compaction_items(self):
        body = json.dumps({
            "input": [
                {"type": "compaction", "id": "cmp_1",
                 "encrypted_content": shim.encode_summary("SUMMARY TEXT")},
                {"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "next"}]},
            ],
        }).encode("utf-8")
        parsed = json.loads(shim.expand_compaction_items(body))
        self.assertEqual([item["type"] for item in parsed["input"]], ["message", "message"])
        self.assertIn("SUMMARY TEXT", parsed["input"][0]["content"][0]["text"])

    def test_expand_keeps_foreign_items_readable(self):
        body = json.dumps({
            "input": [{"type": "compaction", "encrypted_content": "!!opaque!!"}],
        }).encode("utf-8")
        parsed = json.loads(shim.expand_compaction_items(body))
        self.assertIn("not readable", parsed["input"][0]["content"][0]["text"])

    def test_expand_leaves_other_bodies_untouched(self):
        original = json.dumps({"input": [{"type": "message", "role": "user"}]}).encode("utf-8")
        self.assertEqual(shim.expand_compaction_items(original), original)
        self.assertEqual(shim.expand_compaction_items(b"not json"), b"not json")
        self.assertEqual(shim.expand_compaction_items(b'{"input": "string"}'), b'{"input": "string"}')

    def test_extract_compaction_result_reads_text_and_usage(self):
        raw = sse(
            {"type": "response.created", "response": {"id": "resp_1", "status": "in_progress"}},
            {"type": "response.output_item.done", "output_index": 0,
             "item": {"type": "message", "role": "assistant",
                      "content": [{"type": "output_text", "text": "SUMMARY"}]}},
            {"type": "response.completed", "response": {
                "id": "resp_1", "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}},
        )
        text, usage, response_id = shim.extract_compaction_result(raw)
        self.assertEqual(text, "SUMMARY")
        self.assertEqual(usage["total_tokens"], 12)
        self.assertEqual(response_id, "resp_1")

    def test_extract_reads_streamed_text_deltas(self):
        raw = sse(
            {"type": "response.output_text.delta", "delta": "SUM"},
            {"type": "response.output_text.delta", "delta": "MARY"},
            {"type": "response.completed", "response": {"id": "resp_2", "status": "completed"}},
        )
        text, _, response_id = shim.extract_compaction_result(raw)
        self.assertEqual(text, "SUMMARY")
        self.assertEqual(response_id, "resp_2")

    def test_extract_reads_text_from_final_output_only(self):
        raw = sse({"type": "response.completed", "response": {
            "id": "resp_3", "status": "completed",
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "FINAL ONLY"}]}],
        }})
        text, _, response_id = shim.extract_compaction_result(raw)
        self.assertEqual(text, "FINAL ONLY")
        self.assertEqual(response_id, "resp_3")

    def test_extract_does_not_duplicate_when_both_sources_present(self):
        item = {"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": "ONCE"}]}
        raw = sse(
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": {"id": "resp_4", "status": "completed",
                                                        "output": [item]}},
        )
        text, _, _ = shim.extract_compaction_result(raw)
        self.assertEqual(text, "ONCE")

    def test_build_compaction_sse_has_exactly_one_compaction_item(self):
        raw = shim.build_compaction_sse("HELLO", None, "resp_x")
        events = list(shim._iter_sse_events(raw))
        completed = [event for event in events if event["type"] == "response.completed"][0]
        output = completed["response"]["output"]
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["type"], "compaction")
        self.assertEqual(shim.decode_summary(output[0]["encrypted_content"]), "HELLO")
        self.assertEqual(completed["response"]["usage"]["total_tokens"], 0)


class RoundTripTests(unittest.TestCase):
    """Drive the real handler against a fake upstream that never compacts."""

    def setUp(self):
        self.upstream_seen = []
        test_case = self

        class Upstream(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                test_case.upstream_seen.append(body)
                payload = shim.sse_event({
                    "type": "response.completed",
                    "response": {"id": "resp_up", "status": "completed",
                                 "output": [{"type": "message", "role": "assistant",
                                             "content": [{"type": "output_text",
                                                          "text": "UPSTREAM SUMMARY"}]}],
                                 "usage": {"input_tokens": 5, "output_tokens": 1,
                                           "total_tokens": 6}},
                })
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()

        handler = type("TestHandler", (shim.CompactionShimHandler,), {})
        handler.upstream_host = "127.0.0.1"
        handler.upstream_port = self.upstream.server_address[1]
        self.shim = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.shim.serve_forever, daemon=True).start()
        self.port = self.shim.server_address[1]

    def tearDown(self):
        self.shim.shutdown()
        self.shim.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()

    def _post(self, body):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("POST", "/v1/responses", body=body,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_compaction_request_becomes_a_compaction_item(self):
        status, raw = self._post(compaction_body())
        self.assertEqual(status, 200)
        events = list(shim._iter_sse_events(raw))
        completed = [event for event in events if event["type"] == "response.completed"][0]
        output = completed["response"]["output"]
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["type"], "compaction")
        self.assertEqual(shim.decode_summary(output[0]["encrypted_content"]),
                         "UPSTREAM SUMMARY")

    def test_normal_turn_expands_replayed_compaction_items(self):
        body = compaction_body(request_kind="turn", input_items=[
            {"type": "compaction", "encrypted_content": shim.encode_summary("OLD CONTEXT")},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "go"}]},
        ])
        status, _ = self._post(body)
        self.assertEqual(status, 200)
        forwarded = json.loads(self.upstream_seen[-1])
        types = [item["type"] for item in forwarded["input"]]
        self.assertNotIn("compaction", types)
        self.assertIn("OLD CONTEXT", forwarded["input"][0]["content"][0]["text"])


class FreePortTests(unittest.TestCase):
    def test_default_listen_port_is_documented(self):
        self.assertEqual(shim.DEFAULT_LISTEN_PORT, 5098)


if __name__ == "__main__":
    unittest.main()
