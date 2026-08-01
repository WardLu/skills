import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repair  # noqa: E402


SESSION_ID = "019fb8f5-5fcc-74c0-8341-61f83f2126ce"


def event(kind, payload):
    return json.dumps({"timestamp": "2026-08-01T00:00:00Z", "type": kind, "payload": payload}, separators=(",", ":")) + "\n"


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / ".codex"
        self.rollout = self.home / "sessions" / "2026" / "08" / "01"
        self.rollout.mkdir(parents=True)
        self.session_path = self.rollout / f"rollout-test-{SESSION_ID}.jsonl"
        self.session_path.write_text(
            "".join(
                [
                    event("session_meta", {"id": SESSION_ID, "model_provider": "sub_lxapi", "cwd": "C:/work"}),
                    event("response_item", {"type": "reasoning", "id": "rs_stale_1", "summary": []}),
                    event("response_item", {"type": "reasoning", "id": "rs_stale_2", "summary": []}),
                    event("response_item", {"type": "message", "id": "msg-visible", "content": [{"text": "Keep me"}]}),
                    event("event_msg", {"type": "agent_reasoning", "text": "Keep this event"}),
                ]
            ),
            encoding="utf-8",
        )
        (self.home / "config.toml").write_text('model_provider = "custom"\n', encoding="utf-8")

        state = sqlite3.connect(self.home / "state_5.sqlite")
        state.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model_provider TEXT, model TEXT, cwd TEXT, archived INTEGER)")
        state.execute("INSERT INTO threads VALUES (?, ?, ?, ?, ?)", (SESSION_ID, "sub_lxapi", "gpt-test", "C:/work", 0))
        state.commit()
        state.close()

        logs = sqlite3.connect(self.home / "logs_2.sqlite")
        logs.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, feedback_log_body TEXT)")
        logs.execute("INSERT INTO logs(thread_id, feedback_log_body) VALUES (?, ?)", (SESSION_ID, "Item with id 'rs_stale_1' not found"))
        logs.execute("INSERT INTO logs(thread_id, feedback_log_body) VALUES (?, ?)", (SESSION_ID, "Item with id 'rs_stale_2' not found"))
        logs.commit()
        logs.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_reports_layers_and_stale_ids(self):
        report = repair.inspect_session(self.home, SESSION_ID)
        self.assertEqual(report["json_parse_errors"], [])
        self.assertEqual(report["global_provider"], "custom")
        self.assertEqual(report["root_thread"]["model_provider"], "sub_lxapi")
        self.assertEqual(report["stale_ids_present_as_reasoning"], ["rs_stale_1", "rs_stale_2"])
        self.assertEqual(report["reasoning_item_count"], 2)

    def test_stale_repair_preserves_visible_and_event_items(self):
        report = repair.inspect_session(self.home, SESSION_ID)
        backup, removed, provider_updates = repair.rewrite_session(report, None, False, "stale")
        self.assertTrue(backup and backup.exists())
        self.assertEqual(removed, 2)
        self.assertEqual(provider_updates, 0)
        repaired = repair.inspect_session(self.home, SESSION_ID)
        self.assertEqual(repaired["reasoning_item_count"], 0)
        text = self.session_path.read_text(encoding="utf-8")
        self.assertIn("msg-visible", text)
        self.assertIn("agent_reasoning", text)

    def test_provider_repair_updates_only_target_layers(self):
        report = repair.inspect_session(self.home, SESSION_ID)
        backup, removed, provider_updates = repair.rewrite_session(report, "custom", True, "none")
        self.assertTrue(backup and backup.exists())
        self.assertEqual(removed, 0)
        self.assertEqual(provider_updates, 1)
        db_backup = repair.update_thread_provider(self.home, SESSION_ID, "custom")
        self.assertTrue(db_backup and db_backup.exists())
        after = repair.inspect_session(self.home, SESSION_ID)
        self.assertEqual(after["target_session_meta"][0]["model_provider"], "custom")
        self.assertEqual(after["root_thread"]["model_provider"], "custom")

    def test_malformed_jsonl_is_not_rewritten(self):
        with self.session_path.open("a", encoding="utf-8") as handle:
            handle.write("not-json\n")
        report = repair.inspect_session(self.home, SESSION_ID)
        with self.assertRaises(ValueError):
            repair.rewrite_session(report, None, False, "all")


if __name__ == "__main__":
    unittest.main()
