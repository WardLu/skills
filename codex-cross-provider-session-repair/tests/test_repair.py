import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repair  # noqa: E402


SESSION_ID = "019fb8f5-5fcc-74c0-8341-61f83f2126ce"
SESSION_ID_MT = "019fc2cb-5370-7d32-899c-89310a4e370a"


def event(kind, payload):
    return json.dumps({"timestamp": "2026-08-01T00:00:00Z", "type": kind, "payload": payload}, separators=(",", ":")) + "\n"


def msg(role, text, turn_id="turn-1"):
    return event("response_item", {
        "type": "message",
        "id": f"msg-{role}-{turn_id}",
        "role": role,
        "content": [{"type": "input_text" if role != "assistant" else "output_text", "text": text}],
        "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
    })


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
        logs.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, level TEXT, feedback_log_body TEXT)")
        logs.execute("INSERT INTO logs(thread_id, level, feedback_log_body) VALUES (?, ?, ?)", (SESSION_ID, "ERROR", "Item with id 'rs_stale_1' not found"))
        logs.execute("INSERT INTO logs(thread_id, level, feedback_log_body) VALUES (?, ?, ?)", (SESSION_ID, "ERROR", "Item with id 'rs_stale_2' not found"))
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
        backup, removed, provider_updates, _ = repair.rewrite_session(report, None, False, "stale")
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
        backup, removed, provider_updates, _ = repair.rewrite_session(report, "custom", True, "none")
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


    def test_reports_remote_compaction_unsupported(self):
        logs = sqlite3.connect(self.home / "logs_2.sqlite")
        logs.execute(
            "INSERT INTO logs(thread_id, level, feedback_log_body) VALUES (?, ?, ?)",
            (SESSION_ID, "ERROR", "Error running remote compact task: Fatal error: remote compaction v2 expected exactly one compaction output item, got 0 from 1 output items"),
        )
        logs.commit()
        logs.close()

        report = repair.inspect_session(self.home, SESSION_ID)
        self.assertTrue(report["remote_compaction"]["logged_error"])
        self.assertTrue(report["remote_compaction"]["unsupported"])

    def test_disable_remote_compaction_adds_feature(self):
        config = self.home / "config.toml"
        config.write_text('model_provider = "custom"\n[features]\n', encoding="utf-8")

        backup = repair.disable_remote_compaction(self.home)

        self.assertTrue(backup is not None and backup.exists())
        text = config.read_text(encoding="utf-8")
        self.assertIn("remote_compaction_v2 = false", text)

    def test_disable_remote_compaction_is_idempotent(self):
        config = self.home / "config.toml"
        config.write_text(
            'model_provider = "custom"\n[features]\nremote_compaction_v2 = false\n',
            encoding="utf-8",
        )

        backup = repair.disable_remote_compaction(self.home)

        self.assertIsNone(backup)
        self.assertIn("remote_compaction_v2 = false", config.read_text(encoding="utf-8"))


class ModelTurnTests(unittest.TestCase):
    """Tests for Gemini model-turn-ending compaction detection and repair."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / ".codex"
        self.rollout = self.home / "sessions" / "2026" / "08" / "02"
        self.rollout.mkdir(parents=True)
        self.session_path = self.rollout / f"rollout-test-{SESSION_ID_MT}.jsonl"
        # Build a session where thread_rolled_back hides the last user turn,
        # leaving an assistant message as the last effective item.
        self.session_path.write_text(
            "".join(
                [
                    event("session_meta", {"id": SESSION_ID_MT, "model_provider": "custom", "cwd": "/work"}),
                    # Turn 1: user -> assistant
                    event("event_msg", {"type": "task_started", "turn_id": "t1"}),
                    msg("user", "Hello", "t1"),
                    msg("assistant", "Hi there", "t1"),
                    event("event_msg", {"type": "task_complete", "turn_id": "t1"}),
                    # Turn 2: user -> assistant (this one will be rolled back)
                    event("event_msg", {"type": "task_started", "turn_id": "t2"}),
                    msg("user", "Continue", "t2"),
                    msg("assistant", "Sure", "t2"),
                    event("event_msg", {"type": "task_complete", "turn_id": "t2"}),
                    # Rollback turn 2 — effective history now ends with assistant
                    event("event_msg", {"type": "thread_rolled_back", "num_turns": 1}),
                    # Turn 3: user (rolled back too)
                    event("event_msg", {"type": "task_started", "turn_id": "t3"}),
                    msg("user", "Try again", "t3"),
                    event("event_msg", {"type": "task_complete", "turn_id": "t3"}),
                    event("event_msg", {"type": "thread_rolled_back", "num_turns": 1}),
                ]
            ),
            encoding="utf-8",
        )
        (self.home / "config.toml").write_text('model_provider = "custom"\n', encoding="utf-8")

        logs = sqlite3.connect(self.home / "logs_2.sqlite")
        logs.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, level TEXT, feedback_log_body TEXT)")
        logs.execute(
            "INSERT INTO logs(thread_id, level, feedback_log_body) VALUES (?, ?, ?)",
            (SESSION_ID_MT, "ERROR", "Requests ending with a model turn are not supported."),
        )
        logs.commit()
        logs.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_detects_model_turn_risk(self):
        report = repair.inspect_session(self.home, SESSION_ID_MT)
        mt = report["model_turn"]
        self.assertTrue(mt["model_turn_risk"])
        self.assertTrue(mt["logged_error"])
        self.assertEqual(mt["last_effective_role"], "assistant")

    def test_fix_model_turn_removes_rollbacks(self):
        report = repair.inspect_session(self.home, SESSION_ID_MT)
        backup, _, _, inserts = repair.rewrite_session(
            report, None, False, "none", fix_model_turn=True
        )
        self.assertTrue(backup and backup.exists())
        # After removing rollbacks, the last effective message should be user
        # (from turn 3 or turn 2), so no dummy user message is needed.
        self.assertEqual(inserts, 0)
        # Verify rollbacks were removed
        text = self.session_path.read_text(encoding="utf-8")
        self.assertNotIn("thread_rolled_back", text)
        # Verify post-repair state
        after = repair.inspect_session(self.home, SESSION_ID_MT)
        mt = after["model_turn"]
        self.assertFalse(mt["model_turn_risk"])
        self.assertEqual(mt["last_effective_role"], "user")

    def test_fix_model_turn_appends_user_when_no_rollback(self):
        """When there are no rollbacks and history ends with assistant,
        a dummy user message must be appended."""
        # Rewrite the session to remove rollbacks first, then add a trailing
        # assistant message without a following user message.
        self.session_path.write_text(
            "".join(
                [
                    event("session_meta", {"id": SESSION_ID_MT, "model_provider": "custom", "cwd": "/work"}),
                    event("event_msg", {"type": "task_started", "turn_id": "t1"}),
                    msg("user", "Hello", "t1"),
                    msg("assistant", "Hi there", "t1"),
                    event("event_msg", {"type": "task_complete", "turn_id": "t1"}),
                ]
            ),
            encoding="utf-8",
        )
        report = repair.inspect_session(self.home, SESSION_ID_MT)
        mt = report["model_turn"]
        self.assertTrue(mt["model_turn_risk"])
        self.assertEqual(mt["last_effective_role"], "assistant")

        backup, _, _, inserts = repair.rewrite_session(
            report, None, False, "none", fix_model_turn=True
        )
        self.assertEqual(inserts, 1)
        after = repair.inspect_session(self.home, SESSION_ID_MT)
        self.assertFalse(after["model_turn"]["model_turn_risk"])
        self.assertEqual(after["model_turn"]["last_effective_role"], "user")

    def test_fix_model_turn_appends_user_when_raw_tail_is_user_but_effective_ends_assistant(self):
        """Regression: raw JSONL tail is a user message from an unfinished or
        rolled-back turn, but the effective history ends with an assistant
        message. The rewrite must still append the dummy user message after the
        effective assistant turn."""
        self.session_path.write_text(
            "".join(
                [
                    event("session_meta", {"id": SESSION_ID_MT, "model_provider": "custom", "cwd": "/work"}),
                    event("event_msg", {"type": "task_started", "turn_id": "t1"}),
                    msg("user", "Hello", "t1"),
                    msg("assistant", "Hi there", "t1"),
                    event("event_msg", {"type": "task_complete", "turn_id": "t1"}),
                    # Unfinished turn: raw tail is a user message, but it does
                    # not belong to the effective (completed) history.
                    event("event_msg", {"type": "task_started", "turn_id": "t2"}),
                    msg("user", "Pending", "t2"),
                ]
            ),
            encoding="utf-8",
        )
        report = repair.inspect_session(self.home, SESSION_ID_MT)
        mt = report["model_turn"]
        self.assertTrue(mt["model_turn_risk"])
        self.assertEqual(mt["last_effective_role"], "assistant")

        backup, _, _, inserts = repair.rewrite_session(
            report, None, False, "none", fix_model_turn=True
        )
        self.assertTrue(backup and backup.exists())
        self.assertEqual(inserts, 1)
        after = repair.inspect_session(self.home, SESSION_ID_MT)
        self.assertFalse(after["model_turn"]["model_turn_risk"])
        self.assertEqual(after["model_turn"]["last_effective_role"], "user")


if __name__ == "__main__":
    unittest.main()
