import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import start_repair  # noqa: E402


class StartRepairTests(unittest.TestCase):
    def test_worker_command_is_safe_after_user_quits_before_start(self):
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "skill"
            home = Path(directory) / ".codex"
            status = Path(directory) / "status.json"

            argv = start_repair.build_worker_argv(
                skill_dir=skill_dir,
                session_id="session-1",
                codex_home=home,
                remove_reasoning="stale",
                status_file=status,
                timeout=120,
                stable_seconds=8,
                poll_seconds=1,
            )

            self.assertIn("--allow-already-stopped", argv)
            self.assertIn("--remove-reasoning", argv)
            self.assertIn("stale", argv)
            self.assertIn("--status-file", argv)
            self.assertIn(str(status), argv)

    def test_terminal_command_explains_final_state_and_stays_open(self):
        command = start_repair.build_terminal_command(
            [
                "python3",
                "wait_and_repair.py",
                "--session-id",
                "session-1",
                "--timeout",
                "300",
            ],
            workdir=Path("/tmp/repair-skill"),
        )

        self.assertIn("Wait limit / 等待上限", command)
        self.assertIn("最多 300 秒", command)
        self.assertIn("verified / 已验证", command)
        self.assertIn("failed / 失败", command)
        self.assertIn("read -r", command)
        self.assertIn('exit "$rc"', command)
        self.assertIn("\\033]0;", command)
        self.assertIn("/usr/bin/osascript", command)

    def test_terminal_command_uses_short_runner_path_when_available(self):
        command = start_repair.build_terminal_command(
            [
                "python3",
                "wait_and_repair.py",
                "--session-id",
                "session-1",
                "--codex-home",
                "/Users/wardlu/.codex",
            ],
            workdir=Path("/tmp/repair-skill"),
            runner_path=Path("/tmp/codex-session-repair-session-1.sh"),
        )

        self.assertIn("/bin/zsh", command)
        self.assertIn("/tmp/codex-session-repair-session-1.sh", command)
        self.assertNotIn("--session-id", command)
        self.assertNotIn("--codex-home", command)
        self.assertTrue(command.endswith('exit "$rc"'))

    def test_terminal_command_closes_the_dedicated_repair_window_after_enter(self):
        command = start_repair.build_terminal_command(
            [
                "python3",
                "wait_and_repair.py",
                "--session-id",
                "session-1",
            ],
            workdir=Path("/tmp/repair-skill"),
            runner_path=Path("/tmp/codex-session-repair-session-1.sh"),
        )

        self.assertIn("/usr/bin/osascript", command)
        self.assertIn("Codex session repair session-1", command)
        self.assertIn("\\033]0;", command)
        self.assertIn('exit "$rc"', command)

    def test_terminal_close_script_closes_the_dedicated_repair_window(self):
        script = start_repair.build_terminal_close_applescript("session-1")

        self.assertIn("name of targetWindow", script)
        self.assertIn("count of tabs of targetWindow", script)
        self.assertIn("close targetWindow", script)
        self.assertNotIn("close targetTab", script)

    def test_runner_script_has_readable_sections_and_final_state(self):
        script = start_repair.build_terminal_runner_script(
            ["python3", "wait_and_repair.py", "--session-id", "session-1"],
            session_id="session-1",
            timeout=300,
        )

        self.assertIn("Codex 会话修复 / Codex session repair", script)
        self.assertIn("会话 / Session: session-1", script)
        self.assertIn("等待上限 / Wait limit: 300 秒 / 300 seconds", script)
        self.assertIn("Command+Q", script)
        self.assertIn("Verified / 已验证", script)
        self.assertIn("Failed / 失败", script)
        self.assertIn("read -r", script)

    def test_terminal_applescript_creates_a_readable_window(self):
        script = start_repair.build_terminal_applescript("echo ready", session_id="session-1")

        self.assertIn("coredosc", script)
        self.assertIn("set custom title", script)
        self.assertIn("title displays custom title", script)
        self.assertIn("Codex session repair session-1", script)
        self.assertIn("tell front window", script)
        self.assertIn("number of columns", script)
        self.assertIn("120", script)
        self.assertIn("number of rows", script)
        self.assertIn("36", script)
        self.assertIn("echo ready", script)

    def test_default_status_path_is_predictable(self):
        expected = Path(tempfile.gettempdir()) / "codex-session-repair-session-1.json"
        self.assertEqual(start_repair.default_status_path("session-1"), expected)

    def test_conversation_notice_includes_wait_limit_and_action(self):
        notice = start_repair.build_conversation_notice(300)

        self.assertIn("最多等待 300 秒", notice)
        self.assertIn("完全退出 Codex", notice)
        self.assertIn("maximum wait is 300s", notice)


if __name__ == "__main__":
    unittest.main()
