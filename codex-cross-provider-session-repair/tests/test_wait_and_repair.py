import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import wait_and_repair  # noqa: E402
import start_repair  # noqa: E402


SESSION_ID = "019fe5cf-9cc1-7cd1-8a04-21dca7b5cf85"


def event(kind, payload):
    return json.dumps(
        {"timestamp": "2026-08-10T00:00:00Z", "type": kind, "payload": payload},
        separators=(",", ":"),
    ) + "\n"


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def write_fake_home(root, reasoning_count=2, model=None):
    home = root / ".codex"
    rollout_dir = home / "sessions" / "2026" / "08" / "10"
    rollout_dir.mkdir(parents=True)
    rollout = rollout_dir / f"rollout-test-{SESSION_ID}.jsonl"
    records = [event("session_meta", {"id": SESSION_ID, "model_provider": "custom"})]
    for index in range(reasoning_count):
        records.append(event("response_item", {"type": "reasoning", "id": f"rs_test_{index}"}))
    records.append(
        event(
            "response_item",
            {"type": "message", "id": "msg-visible", "role": "user", "content": []},
        )
    )
    if model:
        records.append(
            event(
                "event_msg",
                {
                    "type": "thread_settings_applied",
                    "thread_settings": {
                        "model": model,
                        "collaboration_mode": {"settings": {"model": model}},
                    },
                },
            )
        )
        records.append(event("event_msg", {"type": "turn_context", "model": model}))
    rollout.write_text("".join(records), encoding="utf-8")
    return home, rollout


class WaitForDesktopExitTests(unittest.TestCase):
    def test_process_table_ignores_shell_commands_that_only_mention_codex(self):
        table = "\n".join(
            [
                "42 /Applications/ChatGPT.app/Contents/MacOS/ChatGPT",
                "43 /bin/zsh -c ps -axo pid=,comm= | rg ChatGPT",
                "44 /Applications/ChatGPT.app/Contents/Frameworks/ChatGPT Helper.app/Contents/MacOS/ChatGPT Helper",
                "45 /Applications/ChatGPT.app/Contents/Resources/codex",
                "46 /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Versions/151.0/Helpers/Codex (Service).app/Contents/MacOS/Codex (Service)",
                "47 /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Versions/151.0/Helpers/browser_crashpad_handler --database=/Users/test/Library/Application Support/Codex/Crashpad",
            ]
        )

        processes = wait_and_repair.parse_process_table(table)

        self.assertEqual([process.pid for process in processes], [42, 44, 45, 46])

    def test_requires_stable_absence_before_returning(self):
        clock = FakeClock()
        states = [
            [wait_and_repair.ProcessInfo(42, "ChatGPT")],
            [],
            [],
            [],
        ]

        wait_and_repair.wait_for_desktop_exit(
            lambda: states.pop(0),
            timeout=10,
            stable_seconds=2,
            poll_seconds=1,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

        self.assertEqual(clock.value, 3)

    def test_aborts_if_desktop_reappears_during_stability_window(self):
        clock = FakeClock()
        states = [
            [wait_and_repair.ProcessInfo(42, "ChatGPT")],
            [],
            [wait_and_repair.ProcessInfo(99, "ChatGPT")],
        ]

        with self.assertRaises(wait_and_repair.DesktopRestartedError):
            wait_and_repair.wait_for_desktop_exit(
                lambda: states.pop(0),
                timeout=10,
                stable_seconds=2,
                poll_seconds=1,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
            )

    def test_refuses_to_start_when_desktop_was_never_detected(self):
        clock = FakeClock()

        with self.assertRaises(wait_and_repair.DesktopNotDetectedError):
            wait_and_repair.wait_for_desktop_exit(
                lambda: [],
                timeout=10,
                stable_seconds=2,
                poll_seconds=1,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
            )

    def test_allows_already_stopped_when_repair_job_was_started_after_quit(self):
        clock = FakeClock()
        states = [[], [], []]

        wait_and_repair.wait_for_desktop_exit(
            lambda: states.pop(0),
            timeout=10,
            stable_seconds=2,
            poll_seconds=1,
            allow_already_stopped=True,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

        self.assertEqual(clock.value, 2)

    def test_waiting_announces_time_limit_and_periodic_reminders(self):
        clock = FakeClock()
        notices = []

        with self.assertRaises(wait_and_repair.DesktopWaitTimeoutError):
            wait_and_repair.wait_for_desktop_exit(
                lambda: [wait_and_repair.ProcessInfo(42, "ChatGPT")],
                timeout=5,
                stable_seconds=2,
                poll_seconds=1,
                reminder_seconds=(1, 3),
                sleep=clock.sleep,
                monotonic=clock.monotonic,
                notify=lambda status, message: notices.append((status, message)),
            )

        messages = [message for status, message in notices if status == "waiting"]
        self.assertTrue(any("最长等待 5 秒" in message for message in messages))
        self.assertTrue(any("已等待约 1 秒" in message for message in messages))
        self.assertTrue(any("距离超时约 2 秒" in message for message in messages))



class WaitAndRepairTests(unittest.TestCase):
    def test_model_repair_with_none_preserves_reasoning_and_verifies_both_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            home, rollout = write_fake_home(Path(directory), model="ark-code-latest")
            state = sqlite3.connect(home / "state_5.sqlite")
            state.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, model_provider TEXT, model TEXT, cwd TEXT, archived INTEGER)"
            )
            state.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
                (SESSION_ID, "custom", "ark-code-latest", "/work", 0),
            )
            state.commit()
            state.close()
            status_file = Path(directory) / "repair-status.json"
            clock = FakeClock()
            states = [
                [wait_and_repair.ProcessInfo(42, "ChatGPT")],
                [],
                [],
                [],
                [],
            ]

            result = wait_and_repair.run_wait_and_repair(
                session_id=SESSION_ID,
                codex_home=home,
                remove_reasoning="none",
                model="gpt-5.6-luna",
                fix_model=True,
                process_reader=lambda: states.pop(0),
                status_file=status_file,
                timeout=10,
                stable_seconds=2,
                poll_seconds=1,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
            )

            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["post_report"]["reasoning_item_count"], 2)
            self.assertEqual(result["post_report"]["root_thread"]["model"], "gpt-5.6-luna")
            self.assertEqual(result["post_report"]["structured_model_values"], ["gpt-5.6-luna"] * 3)
            self.assertTrue(list(rollout.parent.glob("*.bak-session-repair-*")))

    def test_success_writes_verified_status_and_removes_reasoning(self):
        with tempfile.TemporaryDirectory() as directory:
            home, rollout = write_fake_home(Path(directory))
            status_file = Path(directory) / "repair-status.json"
            clock = FakeClock()
            states = [
                [wait_and_repair.ProcessInfo(42, "ChatGPT")],
                [],
                [],
                [],
                [],
            ]

            result = wait_and_repair.run_wait_and_repair(
                session_id=SESSION_ID,
                codex_home=home,
                remove_reasoning="all",
                process_reader=lambda: states.pop(0),
                status_file=status_file,
                timeout=10,
                stable_seconds=2,
                poll_seconds=1,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
                stream=(stream := io.StringIO()),
            )

            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["post_report"]["reasoning_item_count"], 0)
            self.assertTrue(status_file.exists())
            self.assertEqual(json.loads(status_file.read_text())["status"], "verified")
            self.assertTrue(list(rollout.parent.glob("*.bak-session-repair-*")))
            self.assertIn("可以重新打开 Codex", stream.getvalue())
            self.assertIn("Verified / 已验证", stream.getvalue())
            status_payload = json.loads(status_file.read_text())
            self.assertEqual(status_payload["status_label"], "Verified / 已验证")
            self.assertTrue(status_payload["can_reopen"])
            self.assertEqual(status_payload["next_action"], "Reopen Codex / 可以重新打开 Codex")

    def test_repairs_when_codex_was_already_closed_before_job_started(self):
        with tempfile.TemporaryDirectory() as directory:
            home, rollout = write_fake_home(Path(directory))
            status_file = Path(directory) / "repair-status.json"
            clock = FakeClock()
            states = [[], [], [], []]

            result = wait_and_repair.run_wait_and_repair(
                session_id=SESSION_ID,
                codex_home=home,
                remove_reasoning="all",
                allow_already_stopped=True,
                process_reader=lambda: states.pop(0),
                status_file=status_file,
                timeout=10,
                stable_seconds=2,
                poll_seconds=1,
                sleep=clock.sleep,
                monotonic=clock.monotonic,
            )

            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["post_report"]["reasoning_item_count"], 0)

    def test_refuses_to_apply_when_rollout_changes_while_waiting(self):
        with tempfile.TemporaryDirectory() as directory:
            home, rollout = write_fake_home(Path(directory))
            status_file = Path(directory) / "repair-status.json"
            clock = FakeClock()
            states = [
                [wait_and_repair.ProcessInfo(42, "ChatGPT")],
                [],
                [],
                [],
                [],
            ]
            changed = False

            def sleep(seconds):
                nonlocal changed
                if not changed:
                    rollout.write_text(
                        rollout.read_text(encoding="utf-8")
                        + event("event_msg", {"type": "task_complete"}),
                        encoding="utf-8",
                    )
                    changed = True
                clock.sleep(seconds)

            with self.assertRaises(wait_and_repair.RolloutChangedError):
                wait_and_repair.run_wait_and_repair(
                    session_id=SESSION_ID,
                    codex_home=home,
                    remove_reasoning="all",
                    process_reader=lambda: states.pop(0),
                    status_file=status_file,
                    timeout=10,
                    stable_seconds=2,
                    poll_seconds=1,
                    sleep=sleep,
                    monotonic=clock.monotonic,
                )

            self.assertEqual(json.loads(status_file.read_text())["status"], "failed")
            self.assertFalse(list(rollout.parent.glob("*.bak-session-repair-*")))

    def test_timeout_status_explains_wait_limit_and_next_step(self):
        with tempfile.TemporaryDirectory() as directory:
            home, rollout = write_fake_home(Path(directory))
            status_file = Path(directory) / "repair-status.json"
            clock = FakeClock()
            stream = io.StringIO()

            with self.assertRaises(wait_and_repair.DesktopWaitTimeoutError):
                wait_and_repair.run_wait_and_repair(
                    session_id=SESSION_ID,
                    codex_home=home,
                    remove_reasoning="stale",
                    process_reader=lambda: [wait_and_repair.ProcessInfo(42, "ChatGPT")],
                    status_file=status_file,
                    timeout=3,
                    stable_seconds=2,
                    poll_seconds=1,
                    sleep=clock.sleep,
                    monotonic=clock.monotonic,
                    stream=stream,
                )

            status_payload = json.loads(status_file.read_text())
            self.assertEqual(status_payload["status"], "failed")
            self.assertTrue(status_payload["wait_timed_out"])
            self.assertEqual(status_payload["wait_timeout_seconds"], 3)
            self.assertIn("等待超时", status_payload["conversation_notice"])
            self.assertIn("最多等待 3 秒", stream.getvalue())
            self.assertIn("保持 Codex 关闭", stream.getvalue())
            self.assertFalse(list(rollout.parent.glob("*.bak-session-repair-*")))


if __name__ == "__main__":
    unittest.main()
