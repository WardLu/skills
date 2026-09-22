import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repair  # noqa: E402
import repair_session_offline as offline  # noqa: E402

SESSION_ID = "019fb8f5-5fcc-74c0-8341-61f83f2126ce"

FAKE_CODEX = '''#!/usr/bin/env python3
"""Stand-in for the Codex CLI used by the offline-runner tests."""
import json, os, pathlib, sys

record = pathlib.Path(os.environ["FAKE_CODEX_RECORD"])
mode = os.environ.get("FAKE_CODEX_MODE", "ok")
home = pathlib.Path(os.environ["CODEX_HOME"])

payload = {"argv": sys.argv[1:], "codex_home": str(home), "mode": mode}
rollouts = sorted(home.rglob("rollout-*.jsonl"))
if rollouts:
    payload["rollout"] = str(rollouts[0])
record.write_text(json.dumps(payload), encoding="utf-8")

if mode == "writer-conflict":
    print("ERROR: thread-store conflict: thread "
          + sys.argv[sys.argv.index("resume") + 2]
          + " already has an active writer")
    sys.exit(1)

if rollouts:
    with rollouts[0].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": "2026-09-20T01:00:00Z", "type": "compacted",
                                 "payload": {"message": "handoff", "replacement_history": []}},
                                separators=(",", ":")) + "\\n")
        handle.write(json.dumps({"timestamp": "2026-09-20T01:00:01Z", "type": "event_msg",
                                 "payload": {"type": "task_complete", "error": None}},
                                separators=(",", ":")) + "\\n")
print("context compacted")
'''


def event(kind, payload):
    return json.dumps({"timestamp": "2026-09-20T00:00:00Z", "type": kind, "payload": payload},
                      separators=(",", ":")) + "\n"


class OfflineRunnerTests(unittest.TestCase):
    def setUp(self):
        os.environ[repair.FEATURE_PROBE_OPT_OUT_ENV] = "1"
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / ".codex"
        self.rollout_dir = self.home / "sessions" / "2026" / "09" / "20"
        self.rollout_dir.mkdir(parents=True)
        self.rollout = self.rollout_dir / f"rollout-test-{SESSION_ID}.jsonl"
        self.rollout.write_text("".join([
            event("session_meta", {"id": SESSION_ID, "model_provider": "custom",
                                   "cwd": str(self.root)}),
            event("event_msg", {"type": "thread_settings_applied",
                                "thread_settings": {"model": "probe-model-a"}}),
            event("event_msg", {"type": "task_complete", "error": {
                "message": "Error running remote compact task: Fatal error: remote "
                           "compaction v2 expected exactly one compaction output item, "
                           "got 0 from 1 output items"}}),
        ]), encoding="utf-8")
        (self.home / "config.toml").write_text(
            'model_provider = "custom"\n\n[model_providers.custom]\n'
            'name = "Probe"\nbase_url = "http://127.0.0.1:5000/v1"\nwire_api = "responses"\n',
            encoding="utf-8",
        )
        state = sqlite3.connect(self.home / "state_5.sqlite")
        state.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model_provider TEXT, "
                      "model TEXT, cwd TEXT, archived INTEGER)")
        state.execute("INSERT INTO threads VALUES (?, ?, ?, ?, 0)",
                      (SESSION_ID, "custom", "probe-model-a", str(self.root)))
        state.commit()
        state.close()

        self.fake_bin = self.root / "codex"
        self.fake_bin.write_text(FAKE_CODEX, encoding="utf-8")
        self.fake_bin.chmod(self.fake_bin.stat().st_mode | stat.S_IEXEC)
        self.record = self.root / "fake-codex-record.json"
        os.environ["FAKE_CODEX_RECORD"] = str(self.record)
        os.environ.pop("FAKE_CODEX_MODE", None)

    def tearDown(self):
        os.environ.pop(repair.FEATURE_PROBE_OPT_OUT_ENV, None)
        os.environ.pop("FAKE_CODEX_RECORD", None)
        os.environ.pop("FAKE_CODEX_MODE", None)
        self.temp.cleanup()

    def _run(self, *extra):
        argv = ["--session-id", SESSION_ID, "--codex-home", str(self.home),
                "--codex-bin", str(self.fake_bin), "--listen-port", "0", *extra]
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = offline.main(argv)
        return code, stdout.getvalue()

    def test_derive_shim_base_url_preserves_path_prefix(self):
        self.assertEqual(
            offline.derive_shim_base_url("http://127.0.0.1:5000/v1", 5098),
            "http://127.0.0.1:5098/v1",
        )
        self.assertEqual(
            offline.derive_shim_base_url("https://api.example.com/responses", 6000),
            "http://127.0.0.1:6000/responses",
        )

    def test_read_provider_base_url_variants(self):
        text = '[model_providers.custom]\nbase_url = "http://127.0.0.1:5000/v1"\n'
        self.assertEqual(offline.read_provider_base_url(text, "custom"),
                         "http://127.0.0.1:5000/v1")
        quoted = '[model_providers."my.provider"]\nbase_url = "http://host:1/v1"\n'
        self.assertEqual(offline.read_provider_base_url(quoted, "my.provider"), "http://host:1/v1")
        self.assertIsNone(offline.read_provider_base_url(text, "missing"))

    def test_upstream_host_port_from_base_url(self):
        self.assertEqual(offline.upstream_host_port("http://127.0.0.1:5000/v1"),
                         ("127.0.0.1", 5000))
        self.assertEqual(offline.upstream_host_port("https://api.example.com/v1"),
                         ("api.example.com", 443))
        self.assertEqual(offline.upstream_host_port("http://api.example.com/v1"),
                         ("api.example.com", 80))

    def test_classify_run_output(self):
        self.assertEqual(offline.classify_run_output("all good"), "ok")
        self.assertEqual(offline.classify_run_output("already has an active writer"),
                         "writer-conflict")
        self.assertEqual(
            offline.classify_run_output(
                "Error running remote compact task: Fatal error: remote compaction v2 "
                "expected exactly one compaction output item, got 0 from 1 output items"),
            "compaction-error",
        )

    def test_helpers_count_compacted_and_read_last_error(self):
        records = [json.loads(line) for line in self.rollout.read_text().splitlines()]
        self.assertEqual(offline.count_compacted_records(records), 0)
        self.assertIsNotNone(offline.last_task_complete_error(records))
        self.assertEqual(offline.session_model(records, {"model": "db-model"}), "db-model")
        self.assertEqual(offline.session_model(records, None), "probe-model-a")

    def test_dry_run_writes_nothing(self):
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn("Dry run only", out)
        self.assertRegex(out, r"http://127\.0\.0\.1:\d+/v1")
        self.assertEqual(list(self.rollout_dir.glob("*.bak-*")), [])
        self.assertFalse(self.record.exists())

    def test_apply_compacts_and_verifies(self):
        code, out = self._run("--apply")
        self.assertEqual(code, 0, out)
        self.assertIn("Verified", out)
        record = json.loads(self.record.read_text())
        self.assertEqual(Path(record["codex_home"]).resolve(), self.home.resolve())
        self.assertIn("exec", record["argv"])
        self.assertIn("resume", record["argv"])
        self.assertIn("model=probe-model-a", record["argv"])
        self.assertIn('model_providers.custom.base_url="http://127.0.0.1:', " ".join(record["argv"]))
        self.assertTrue(list(self.rollout_dir.glob("rollout-*.jsonl.bak-session-repair-*")))
        self.assertTrue(list(self.home.glob("state_5.sqlite.bak-session-repair-*")))
        self.assertIn("compacted", self.rollout.read_text())

    def test_apply_reports_writer_conflict_blocker(self):
        os.environ["FAKE_CODEX_MODE"] = "writer-conflict"
        code, out = self._run("--apply")
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED", out)
        self.assertIn("Fully quit Codex", out)

    def test_refuses_rollout_with_parse_errors(self):
        self.rollout.write_text(self.rollout.read_text() + "{not json}\n", encoding="utf-8")
        code, _ = self._run("--apply")
        self.assertEqual(code, 2)
        self.assertFalse(self.record.exists())

    def test_compact_token_limit_override_is_forwarded(self):
        self._run("--apply", "--compact-token-limit", "800000")
        record = json.loads(self.record.read_text())
        self.assertIn("model_auto_compact_token_limit=800000", record["argv"])


if __name__ == "__main__":
    unittest.main()
