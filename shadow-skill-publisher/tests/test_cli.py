import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

# The package intentionally lives beside the executable under ``scripts``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _simple_safe_load(text: str):
    payload = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        if not _:
            raise ValueError("invalid yaml line")
        payload[key.strip()] = value.strip()
    return payload


sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=_simple_safe_load, YAMLError=ValueError))

from shadow_skill_publisher.cli import COMMANDS, VERSION, main
from shadow_skill_publisher.models import FrozenFields
from shadow_skill_publisher.source import load_source


def run_cli(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            exit_code = main(argv)
        except SystemExit as exc:  # argparse exits on invalid usage
            exit_code = exc.code if isinstance(exc.code, int) else 1
    return SimpleNamespace(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def make_skill(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\n"
        "name: cli-fixture\n"
        "description: CLI fixture skill.\n"
        "version: 1.0.0\n"
        "---\n"
        "\n"
        "# CLI Fixture\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    return root


def make_home(root: Path, profile: dict) -> Path:
    home = root / "publisher-home"
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return home


def command_profile() -> dict:
    return {
        "schema_version": 1,
        "author": {"display_name": "CLI Tester", "source_url": "https://example.test/source"},
        "capabilities": [
            {
                "id": "run-checks",
                "core": True,
                "evidence": {
                    "type": "command",
                    "command": ["python3", "-c", "print('command ok')"],
                },
            }
        ],
        "commercial": {"mode": "free", "currency": None, "price": None},
        "accounts": {"workbuddy": "primary"},
        "description_zh": "中文简介",
        "description_en": "English summary",
        "author": "CLI Tester",
        "allowed_tools": ["Bash"],
        "workbuddy_developer_profile_verified": True,
        "workbuddy_publication_mode": "public",
    }


def source_profile(skill: Path) -> dict:
    profile = command_profile()
    profile["capabilities"] = [
        {
            "id": "source-evidence",
            "core": True,
            "evidence": {
                "type": "source",
                "path": "SKILL.md",
                "source_digest": load_source(skill).source_digest,
                "summary": "The fixture source provides local evidence.",
            },
        }
    ]
    return profile


class CliMetadataTests(unittest.TestCase):
    def test_version_and_commands_are_available(self):
        self.assertEqual(VERSION, "0.6.1")
        self.assertEqual(
            COMMANDS,
            ("check", "prepare", "batch", "authorize-batch", "resume", "monitor", "finalize", "authorize", "record", "status", "export"),
        )

    def test_top_level_help_lists_every_command(self):
        entrypoint = Path(__file__).resolve().parents[1] / "scripts" / "publisher.py"
        result = subprocess.run([sys.executable, str(entrypoint), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        for command in COMMANDS:
            self.assertIn(command, result.stdout)

    def test_frozen_fields_separate_generated_facts(self):
        fields = FrozenFields({"title": "Human title"}, ("title",), {"source": "digest"})
        self.assertEqual(fields.values, {"title": "Human title"})
        self.assertEqual(fields.generated_facts, {"source": "digest"})
        self.assertEqual(FrozenFields({"title": "Human title"}).generated_facts, {})

    def test_check_without_exec_digest_prints_plan_and_stays_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            home = make_home(base, command_profile())

            result = run_cli(["check", str(skill), "--home", str(home), "--json"])

        self.assertEqual(result.exit_code, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["report"]["allowed"])
        self.assertEqual(payload["execution_plan"]["commands"], [["python3", "-c", "print('command ok')"]])
        self.assertEqual(payload["execution_plan"]["cwd"], str(skill.resolve()))
        self.assertFalse((home / "state" / "publisher.sqlite3").exists())
        self.assertFalse((home / "runs").exists())

    def test_check_profile_reads_external_profile_without_creating_home_or_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            profile_path = base / "external-profile.json"
            profile_path.write_text(json.dumps(command_profile()), encoding="utf-8")
            home = base / "unused-home"

            result = run_cli(
                [
                    "check",
                    str(skill),
                    "--profile",
                    str(profile_path),
                    "--home",
                    str(home),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 1, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout)["execution_plan"]["commands"], [["python3", "-c", "print('command ok')"]])
        self.assertFalse(home.exists())

    def test_check_without_profile_generates_prompt_profile_and_stays_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            home = base / "unused-home"

            result = run_cli(["check", str(skill), "--home", str(home), "--json"])

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["report"]["allowed"])
        self.assertEqual(payload["profile"], {"origin": "generated", "missing_inputs": []})
        self.assertIsNone(payload["execution_plan"])
        self.assertFalse(home.exists())

    def test_check_without_profile_keeps_scripted_skill_not_evidenced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            scripts = skill / "scripts"
            scripts.mkdir()
            (scripts / "helper.py").write_text("print('ok')\n", encoding="utf-8")
            home = base / "unused-home"

            result = run_cli(["check", str(skill), "--home", str(home), "--json"])

        self.assertEqual(result.exit_code, 1, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["report"]["allowed"])
        self.assertIn("core_not_evidenced", {item["code"] for item in payload["report"]["findings"]})
        self.assertEqual(payload["profile"]["origin"], "generated")
        self.assertFalse(home.exists())

    def test_prepare_without_profile_reports_all_missing_inputs_without_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            home = base / "unused-home"

            result = run_cli(
                [
                    "prepare",
                    str(skill),
                    "--channels",
                    "workbuddy",
                    "skillpay",
                    "xiaohongshu-red-skill",
                    "--home",
                    str(home),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 1, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["report"]["allowed"])
        self.assertEqual(payload["profile"]["origin"], "generated")
        missing = {item["channel"]: set(item["fields"]) for item in payload["profile"]["missing_inputs"]}
        self.assertEqual(
            missing["workbuddy"],
            {
                "accounts.workbuddy",
                "author",
                "description_zh",
                "allowed_tools",
                "workbuddy_developer_profile_verified",
                "workbuddy_publication_mode",
            },
        )
        self.assertEqual(
            missing["skillpay"],
            {
                "accounts.skillpay",
                "creator_identity_verified",
                "required_agreements_verified",
                "price_format_verified",
                "form_contract_verified",
            },
        )
        self.assertEqual(missing["xiaohongshu-red-skill"], {"accounts.xiaohongshu-red-skill"})
        self.assertEqual(len(payload["attempts"]), 3)
        self.assertTrue(all(item["error_code"] == "needs_browser_observation" for item in payload["attempts"]))
        self.assertEqual(
            payload["attempts"][0]["browser_observable"],
            ["accounts.workbuddy", "workbuddy_developer_profile_verified"],
        )
        self.assertEqual(payload["attempts"][0]["user_confirmation"], ["author", "workbuddy_publication_mode"])
        self.assertEqual(payload["attempts"][0]["agent_draft"], ["description_zh", "allowed_tools"])
        self.assertFalse(home.exists())

    def test_explicit_missing_profile_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")

            result = run_cli(
                [
                    "check",
                    str(skill),
                    "--profile",
                    str(base / "missing-profile.json"),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("missing profile", json.loads(result.stdout)["error"])

    def test_prepare_without_profile_lists_missing_inputs_in_text_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")

            result = run_cli(
                [
                    "prepare",
                    str(skill),
                    "--channels",
                    "workbuddy",
                    "--home",
                    str(base / "unused-home"),
                ]
            )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("workbuddy blocked", result.stdout)
        self.assertIn("accounts.workbuddy", result.stdout)
        self.assertIn("workbuddy_developer_profile_verified", result.stdout)
        self.assertIn("workbuddy_publication_mode", result.stdout)

    def test_removed_lovstudio_channel_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            home = base / "publisher-home"
            result = run_cli(
                ["prepare", str(skill), "--channels", "lovstudio", "--home", str(home), "--json"]
            )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("unknown channel: lovstudio", result.stdout)
        self.assertFalse(home.exists())

    def test_stored_profile_missing_account_routes_to_browser_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            profile = source_profile(skill)
            profile["accounts"] = {}
            home = make_home(base, profile)

            result = run_cli(
                ["prepare", str(skill), "--channels", "workbuddy", "--home", str(home), "--json"]
            )

        self.assertEqual(result.exit_code, 1, result.stderr or result.stdout)
        attempt = json.loads(result.stdout)["attempts"][0]
        self.assertEqual(attempt["error_code"], "needs_browser_observation")
        self.assertEqual(attempt["next_action"], "observe_browser")
        self.assertEqual(attempt["browser_observable"], ["accounts.workbuddy"])

    def test_prepare_preserves_ready_channels_when_one_channel_needs_browser_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            profile = source_profile(skill)
            profile.update(
                {
                    "accounts": {
                        "workbuddy": "primary",
                        "skillpay": "pay-primary",
                        "xiaohongshu-red-skill": "red-primary",
                    },
                    "creator_account_alias": "pay-primary",
                    "creator_identity_verified": True,
                    "required_agreements_verified": False,
                    "price_format_verified": True,
                    "form_contract_verified": True,
                }
            )
            profile_path = base / "profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            home = base / "publisher-home"

            result = run_cli(
                [
                    "prepare",
                    str(skill),
                    "--profile",
                    str(profile_path),
                    "--channels",
                    "workbuddy",
                    "skillpay",
                    "xiaohongshu-red-skill",
                    "--home",
                    str(home),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 1, result.stderr or result.stdout)
        attempts = {item["channel"]: item for item in json.loads(result.stdout)["attempts"]}
        self.assertEqual(attempts["skillpay"]["error_code"], "needs_browser_observation")
        self.assertEqual(attempts["skillpay"]["browser_observable"], ["required_agreements_verified"])
        self.assertNotEqual(attempts["workbuddy"]["state"], "blocked")
        self.assertNotEqual(attempts["xiaohongshu-red-skill"]["state"], "blocked")

    def test_prepare_profile_matches_equivalent_home_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            profile = source_profile(skill)
            home_profile = make_home(base / "home-profile", profile)
            external_profile = base / "external-profile.json"
            external_profile.write_text(json.dumps(profile), encoding="utf-8")
            external_home = base / "external-home"

            from_home = run_cli(
                ["prepare", str(skill), "--channels", "workbuddy", "--home", str(home_profile), "--json"]
            )
            from_profile = run_cli(
                [
                    "prepare",
                    str(skill),
                    "--channels",
                    "workbuddy",
                    "--profile",
                    str(external_profile),
                    "--home",
                    str(external_home),
                    "--json",
                ]
            )

        self.assertEqual(from_home.exit_code, 0, from_home.stderr or from_home.stdout)
        self.assertEqual(from_profile.exit_code, 0, from_profile.stderr or from_profile.stdout)
        home_attempt = json.loads(from_home.stdout)["attempts"][0]
        profile_attempt = json.loads(from_profile.stdout)["attempts"][0]
        self.assertEqual(home_attempt["plan"]["fields"], profile_attempt["plan"]["fields"])
        self.assertEqual(home_attempt["plan"]["upload_confirmation_digest"], profile_attempt["plan"]["upload_confirmation_digest"])

    def test_prepare_derives_safe_english_description_from_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            profile = source_profile(skill)
            profile.pop("description_en")
            profile_path = base / "external-profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")

            result = run_cli(
                [
                    "prepare",
                    str(skill),
                    "--channels",
                    "workbuddy",
                    "--profile",
                    str(profile_path),
                    "--home",
                    str(base / "publisher-home"),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        fields = json.loads(result.stdout)["attempts"][0]["plan"]["fields"]
        self.assertEqual(fields["description_en"], "CLI fixture skill.")

    def test_check_executes_only_with_matching_exec_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            skill = make_skill(base / "skill")
            home = make_home(base, command_profile())

            preview = run_cli(["check", str(skill), "--home", str(home), "--json"])
            plan = json.loads(preview.stdout)["execution_plan"]
            authorized = run_cli(
                [
                    "check",
                    str(skill),
                    "--home",
                    str(home),
                    "--json",
                    "--exec-digest",
                    plan["digest"],
                ]
            )

        self.assertEqual(authorized.exit_code, 0)
        payload = json.loads(authorized.stdout)
        self.assertTrue(payload["report"]["allowed"])
        self.assertEqual(payload["command_results"][0]["returncode"], 0)
        self.assertIn("command ok", payload["command_results"][0]["stdout"])
        self.assertFalse((home / "state" / "publisher.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
