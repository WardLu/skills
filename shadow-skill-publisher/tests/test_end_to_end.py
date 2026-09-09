import io
import hashlib
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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

import shadow_skill_publisher.cli as cli_module
from shadow_skill_publisher.cli import main
from shadow_skill_publisher.channels.workbuddy import WorkBuddyAdapter
from shadow_skill_publisher.ledger import Ledger
from shadow_skill_publisher.models import Finding, GateSeverity, PublishState
from shadow_skill_publisher.paths import source_id
from shadow_skill_publisher.source import load_source


def run_cli(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            exit_code = main(argv)
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
    return SimpleNamespace(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def make_skill(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\n"
        "name: workbuddy-fixture\n"
        "description: End-to-end fixture skill.\n"
        "version: 1.0.0\n"
        "---\n"
        "\n"
        "# Fixture\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "references" / "guide.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    return root


def make_home(root: Path, updates=None) -> Path:
    snapshot = load_source(root / "skill")
    profile = {
        "schema_version": 1,
        "capabilities": [
            {
                "id": "validated-locally",
                "core": True,
                "evidence": {
                    "type": "source",
                    "path": "SKILL.md",
                    "source_digest": snapshot.source_digest,
                    "summary": "The frozen source snapshot documents the local validation flow.",
                },
            }
        ],
        "commercial": {"mode": "free", "currency": None, "price": None},
        "accounts": {"workbuddy": "primary"},
        "description_zh": "简短中文介绍",
        "description_en": "A brief English introduction.",
        "author": "Fixture Publisher",
        "allowed_tools": ["Bash", "Read"],
        "permissions": ["read:workspace"],
        "data_handling": ["No remote writes."],
        "risks": ["Submission requires explicit confirmation."],
        "limitations": ["Local-only test fixture."],
        "support_url": "https://example.test/support",
        "author_confirmed": True,
    }
    if updates:
        profile.update(updates)
    home = root / "publisher-home"
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return home


def load_status(home: Path, run_id: str):
    result = run_cli(["status", run_id, "workbuddy", "--home", str(home), "--json"])
    if result.exit_code != 0:
        raise AssertionError(result.stderr or result.stdout)
    payload = json.loads(result.stdout)
    return SimpleNamespace(**payload)


class LocalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.skill = make_skill(self.base / "skill")
        self.home = make_home(self.base)

    def prepare_attempt(self) -> str:
        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--json",
            ]
        )
        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["attempts"]), 1)
        return payload["attempts"][0]["run_id"]

    def authorize_upload(self, run_id: str) -> None:
        status = load_status(self.home, run_id)
        result = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "upload",
                "--digest",
                status.plan["upload_confirmation_digest"],
                "--json",
            ]
        )
        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)

    def finalize_attempt(self, run_id: str, platform_id: str, final_action: str = "submit_review") -> str:
        self.authorize_upload(run_id)
        status = load_status(self.home, run_id)
        fields_path = self.base / f"{platform_id}-fields.json"
        fields_path.write_text(json.dumps(status.plan["fields"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = run_cli(
            [
                "finalize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--platform-id",
                platform_id,
                "--observed-fields",
                str(fields_path),
                "--final-action",
                final_action,
                "--json",
            ]
        )
        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)["plan"]["submission_confirmation_digest"]

    def record_event(self, run_id: str, event: str, evidence: dict):
        evidence_path = self.base / f"{event}-evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return run_cli(
            [
                "record",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--event",
                event,
                "--evidence",
                str(evidence_path),
                "--json",
            ]
        )

    def test_prepare_stops_at_upload_confirmation(self):
        run_id = self.prepare_attempt()

        status = load_status(self.home, run_id)

        self.assertEqual(status.state, PublishState.AWAITING_UPLOAD_CONFIRMATION.value)
        self.assertFalse(status.remote_write_recorded)

    def test_prepare_reapplies_private_channel_copy_and_reports_fact_drift(self):
        safe_copy = "Human channel description — 保持原样。"
        self.home = make_home(
            self.base,
            {"channel_edits": {"workbuddy": {"description": safe_copy}}},
        )
        first_run = self.prepare_attempt()
        first_status = load_status(self.home, first_run)
        self.assertEqual(first_status.plan["fields"]["description"], safe_copy)
        self.assertEqual(
            json.loads((self.home / "runs" / first_run / "plans" / "submission-plan.json").read_text(encoding="utf-8"))["fields"]["description"],
            safe_copy,
        )
        self.assertEqual(
            json.loads((self.home / "runs" / first_run / "dossiers" / "frozen-fields.json").read_text(encoding="utf-8"))["human_edits"]["description"],
            safe_copy,
        )
        private_dossier = json.loads(
            (self.home / "runs" / first_run / "dossiers" / "dossier.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("channel_edits", private_dossier)

        profile_path = self.home / "config" / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile.pop("channel_edits")
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        skill_md = self.skill / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8").replace("description: End-to-end fixture skill.", "description: Changed generated description."),
            encoding="utf-8",
        )
        profile["capabilities"][0]["evidence"]["source_digest"] = load_source(self.skill).source_digest
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        handoff = self.record_event(first_run, "ownership_handoff", {"note": "new source evidence replaces this local owner"})
        self.assertEqual(handoff.exit_code, 0, handoff.stderr or handoff.stdout)

        second_run = self.prepare_attempt()
        second_status = load_status(self.home, second_run)

        self.assertNotEqual(first_run, second_run)
        self.assertEqual(second_status.plan["fields"]["description"], safe_copy)
        self.assertEqual(second_status.frozen_fields["human_edits"], {"description": safe_copy})
        self.assertIn("source_digest", second_status.frozen_fields["drifted_fields"])
        self.assertNotIn("generated_facts", second_status.plan["fields"])

    def test_prepare_rejects_sensitive_private_channel_copy_without_writing_outputs(self):
        sensitive_copy = "Private draft in /Users/private-author/drafts; token=" + "ghp_" + "12345678901234567890"
        self.home = make_home(
            self.base,
            {
                "channel_edits": {
                    "workbuddy": {"description": "Safe copy that must not be written first."},
                    "lovstudio": {"concise_description": sensitive_copy},
                }
            },
        )

        result = run_cli(
            ["prepare", str(self.skill), "--channels", "workbuddy,lovstudio", "--home", str(self.home), "--json"]
        )

        self.assertEqual(result.exit_code, 2, result.stderr or result.stdout)
        self.assertIn("sensitive", result.stderr + result.stdout)
        self.assertNotIn(sensitive_copy, result.stderr + result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())
        self.assertFalse((self.home / "runs").exists())

    def test_prepare_rejects_private_generated_field_edits(self):
        self.home = make_home(
            self.base,
            {"channel_edits": {"workbuddy": {"version": "not allowed"}}},
        )

        result = run_cli(
            ["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("not editable", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())

    def test_prepare_command_evidence_requires_matching_source_bound_digest(self):
        marker = self.base / "command-ran.txt"
        self.home = make_home(
            self.base,
            {
                "capabilities": [
                    {
                        "id": "trusted-command",
                        "core": True,
                        "evidence": {
                            "type": "command",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path({0!r}).write_text('ran', encoding='utf-8')".format(str(marker)),
                            ],
                        },
                    }
                ]
            },
        )
        preview = run_cli(["check", str(self.skill), "--home", str(self.home), "--json"])
        digest = json.loads(preview.stdout)["execution_plan"]["digest"]

        missing = run_cli(
            ["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"]
        )
        wrong = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--exec-digest",
                "0" * 64,
                "--json",
            ]
        )

        self.assertEqual(missing.exit_code, 1)
        self.assertFalse(marker.exists())
        self.assertEqual(wrong.exit_code, 2)
        self.assertFalse(marker.exists())

        authorized = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--exec-digest",
                digest,
                "--json",
            ]
        )

        self.assertEqual(authorized.exit_code, 0, authorized.stderr or authorized.stdout)
        self.assertEqual(marker.read_text(encoding="utf-8"), "ran")
        self.assertTrue(json.loads(authorized.stdout)["report"]["allowed"])

    def test_prepare_rejects_source_changed_by_authorized_command(self):
        skill_md = self.skill / "SKILL.md"
        self.home = make_home(
            self.base,
            {
                "capabilities": [
                    {
                        "id": "mutating-command",
                        "core": True,
                        "evidence": {
                            "type": "command",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; p=Path({0!r}); p.write_text(p.read_text(encoding='utf-8') + '\\nchanged\\n', encoding='utf-8')".format(str(skill_md)),
                            ],
                        },
                    }
                ]
            },
        )
        preview = run_cli(["check", str(self.skill), "--home", str(self.home), "--json"])
        digest = json.loads(preview.stdout)["execution_plan"]["digest"]

        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--exec-digest",
                digest,
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("source_changed_after_execution", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())
        self.assertEqual(list(self.home.rglob("*.zip")), [])

    def test_prepare_artifact_block_returns_blocked_item_and_leaves_no_zip(self):
        finding = Finding(
            code="possible_secret",
            severity=GateSeverity.BLOCK,
            message="Synthetic artifact block.",
            path="SKILL.md",
        )
        with mock.patch.object(cli_module, "verify_artifact", return_value=(finding,)) as verifier:
            result = run_cli(
                ["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"]
            )

        self.assertEqual(result.exit_code, 1)
        verifier.assert_called_once()
        payload = json.loads(result.stdout)
        self.assertEqual(payload["attempts"][0]["state"], "blocked")
        self.assertEqual(payload["attempts"][0]["error_code"], "possible_secret")
        self.assertTrue(payload["attempts"][0]["manual_fallback"])
        self.assertEqual(list(self.home.rglob("*.zip")), [])
        self.assertEqual(list(self.home.rglob("*.manifest.json")), [])

    def test_prepare_preserves_successful_channel_when_later_channel_is_blocked(self):
        self.home = make_home(
            self.base,
            {"accounts": {"workbuddy": "primary", "zhihu-ai-works": "zhihu-primary"}},
        )

        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy,zhihu-ai-works",
                "--home",
                str(self.home),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 1)
        attempts = json.loads(result.stdout)["attempts"]
        self.assertEqual(attempts[0]["channel"], "workbuddy")
        self.assertEqual(attempts[0]["state"], PublishState.AWAITING_UPLOAD_CONFIRMATION.value)
        self.assertEqual(attempts[1]["channel"], "zhihu-ai-works")
        self.assertEqual(attempts[1]["state"], "blocked")
        self.assertEqual(attempts[1]["error_code"], "channel_contract_unverified")
        self.assertTrue(attempts[1]["manual_fallback"])
        self.assertEqual(len(list((self.home / "runs").rglob("*.zip"))), 1)

    def test_prepare_rejects_local_preview_without_opt_in_contract(self):
        self.home = make_home(
            self.base,
            {
                "local_preview": {
                    "enabled": True,
                    "observed_fields": {"unexpected": "drifted"},
                    "final_action": "submit_review",
                }
            },
        )

        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("no_prior_write_contract", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())

    def test_prepare_rejects_local_preview_with_drifted_fields_even_when_adapter_opts_in(self):
        class OptInWorkBuddyAdapter(WorkBuddyAdapter):
            no_prior_write_contract = True

        self.home = make_home(
            self.base,
            {
                "local_preview": {
                    "enabled": True,
                    "observed_fields": {
                        "name": "workbuddy-fixture",
                        "description": "tampered description",
                        "description_zh": "简短中文介绍",
                        "description_en": "A brief English introduction.",
                        "version": "1.0.0",
                        "author": "Fixture Publisher",
                        "allowed-tools": "Bash, Read",
                        "package_root": "skills/workbuddy-fixture",
                        "skill_path": "skills/workbuddy-fixture/SKILL.md",
                        "resource_directories": "references",
                    },
                    "final_action": "submit_review",
                }
            },
        )

        with mock.patch.object(cli_module, "get_channel_adapter", return_value=OptInWorkBuddyAdapter()):
            result = run_cli(
                [
                    "prepare",
                    str(self.skill),
                    "--channels",
                    "workbuddy",
                    "--home",
                    str(self.home),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("exactly match current plan fields", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())

    def test_prepare_allows_local_preview_only_for_explicit_verified_adapter_contract(self):
        class OptInWorkBuddyAdapter(WorkBuddyAdapter):
            no_prior_write_contract = True

        self.home = make_home(self.base, {"local_preview": {"enabled": True, "final_action": "submit_review"}})

        with mock.patch.object(cli_module, "get_channel_adapter", return_value=OptInWorkBuddyAdapter()):
            result = run_cli(
                [
                    "prepare",
                    str(self.skill),
                    "--channels",
                    "workbuddy",
                    "--home",
                    str(self.home),
                    "--json",
                ]
            )

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        item = json.loads(result.stdout)["attempts"][0]
        self.assertEqual(item["state"], PublishState.AWAITING_SUBMISSION_CONFIRMATION.value)
        self.assertTrue(item["plan"]["platform_id"].startswith("local-preview:workbuddy:"))
        self.assertFalse(item["remote_write_recorded"])

    def test_prepare_invalid_channel_returns_exit_two_without_traceback(self):
        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "not-a-channel",
                "--home",
                str(self.home),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("unknown channel", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())

    def test_prepare_invalid_preview_payload_returns_exit_two(self):
        self.home = make_home(
            self.base,
            {"local_preview": {"enabled": True, "observed_fields": "not-a-mapping"}},
        )

        result = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy",
                "--home",
                str(self.home),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("no_prior_write_contract", result.stdout)
        self.assertFalse((self.home / "state" / "publisher.sqlite3").exists())

    def test_record_submission_unknown_returns_exit_three(self):
        run_id = self.prepare_attempt()
        digest = self.finalize_attempt(run_id, "draft-1")
        authorize = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "submission",
                "--digest",
                digest,
                "--json",
            ]
        )
        self.assertEqual(authorize.exit_code, 0, authorize.stderr or authorize.stdout)
        evidence_path = self.base / "submission-unknown.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "raw_status": "submit uncertain",
                    "product_id": "draft-1",
                    "source_version": "1.0.0",
                    "final_action": "submit_review",
                    "note": "token=" + "gh" + "p_" + "12345678901234567890",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = run_cli(
            [
                "record",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--event",
                "submission_unknown",
                "--evidence",
                str(evidence_path),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 3)
        status = load_status(self.home, run_id)
        self.assertEqual(status.state, PublishState.SUBMISSION_UNKNOWN.value)

    def test_record_rejects_undocumented_submitted_alias(self):
        run_id = self.prepare_attempt()
        evidence_path = self.base / "submitted-alias.json"
        evidence_path.write_text(json.dumps({"raw_status": "submitted"}) + "\n", encoding="utf-8")

        result = run_cli(
            [
                "record",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--event",
                "submitted",
                "--evidence",
                str(evidence_path),
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("documented lifecycle events", result.stdout)
        status = load_status(self.home, run_id)
        self.assertEqual(status.state, PublishState.AWAITING_UPLOAD_CONFIRMATION.value)

    def test_finalize_persists_current_submission_digest(self):
        run_id = self.prepare_attempt()
        self.finalize_attempt(run_id, "draft-1")
        ledger = Ledger.open(self.home / "state" / "publisher.sqlite3")
        self.addCleanup(ledger.close)

        plan = ledger.load_submission_plan(run_id)

        self.assertEqual(plan.platform_id, "draft-1")
        self.assertIsNotNone(plan.submission_confirmation_digest)

    def test_finalize_remote_plan_requires_current_upload_authorization(self):
        run_id = self.prepare_attempt()
        status = load_status(self.home, run_id)
        fields_path = self.base / "unconfirmed-fields.json"
        fields_path.write_text(json.dumps(status.plan["fields"]) + "\n", encoding="utf-8")

        result = run_cli(
            [
                "finalize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--platform-id",
                "draft-unconfirmed",
                "--observed-fields",
                str(fields_path),
                "--final-action",
                "submit_review",
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("upload authorization", result.stdout)
        self.assertEqual(load_status(self.home, run_id).state, PublishState.AWAITING_UPLOAD_CONFIRMATION.value)

    def test_record_rejects_empty_or_version_mismatched_live_evidence(self):
        run_id = self.prepare_attempt()
        digest = self.finalize_attempt(run_id, "draft-live")
        authorization = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "submission",
                "--digest",
                digest,
                "--json",
            ]
        )
        self.assertEqual(authorization.exit_code, 0)
        common = {"product_id": "draft-live", "source_version": "1.0.0"}
        for event, raw_status in (
            ("review_submitted", "submitted"),
            ("under_review", "under review"),
            ("approved", "approved"),
        ):
            result = self.record_event(run_id, event, {**common, "raw_status": raw_status})
            self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)

        empty = self.record_event(run_id, "live", {})
        mismatched = self.record_event(
            run_id,
            "live",
            {
                **common,
                "raw_status": "live",
                "source_version": "9.9.9",
                "public_url": "https://example.test/products/workbuddy-fixture",
            },
        )

        self.assertEqual(empty.exit_code, 2)
        self.assertEqual(mismatched.exit_code, 2)
        self.assertEqual(load_status(self.home, run_id).state, PublishState.APPROVED.value)

        live = self.record_event(
            run_id,
            "live",
            {
                **common,
                "raw_status": "live",
                "public_url": "https://example.test/products/workbuddy-fixture",
            },
        )
        self.assertEqual(live.exit_code, 0, live.stderr or live.stdout)
        self.assertEqual(load_status(self.home, run_id).state, PublishState.LIVE.value)

    def test_record_action_must_match_finalized_plan(self):
        run_id = self.prepare_attempt()
        digest = self.finalize_attempt(run_id, "draft-publish", final_action="publish")
        authorize = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "submission",
                "--digest",
                digest,
                "--json",
            ]
        )
        self.assertEqual(authorize.exit_code, 0)

        result = self.record_event(
            run_id,
            "review_submitted",
            {
                "raw_status": "submitted for review",
                "product_id": "draft-publish",
                "source_version": "1.0.0",
            },
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("final_action", result.stdout)

    def test_submission_authorization_rejects_stale_finalized_digest(self):
        run_id = self.prepare_attempt()
        stale_digest = self.finalize_attempt(run_id, "draft-1")
        self.finalize_attempt(run_id, "draft-2")

        result = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "submission",
                "--digest",
                stale_digest,
                "--json",
            ]
        )

        self.assertEqual(result.exit_code, 2)

    def test_remote_drift_blocks_authorization_until_redacted_resolution(self):
        run_id = self.prepare_attempt()
        status = load_status(self.home, run_id)
        secret = "gh" + "p_" + "12345678901234567890"
        drift = self.record_event(
            run_id,
            "remote_drift",
            {
                "local_fields": {"description": "Local " + secret},
                "remote_fields": {"description": "Remote value"},
                "recovery_commands": [
                    [
                        "python3",
                        "scripts/publisher.py",
                        "record",
                        run_id,
                        "workbuddy",
                        "--event",
                        "remote_drift_resolved",
                        "--evidence",
                        "remote-drift-resolution.json",
                    ],
                ],
            },
        )

        self.assertEqual(drift.exit_code, 0, drift.stderr or drift.stdout)
        payload = json.loads(drift.stdout)
        self.assertEqual(payload["state"], PublishState.AWAITING_UPLOAD_CONFIRMATION.value)
        self.assertEqual(payload["blocking_flags"][0]["flag"], "remote_drift")
        self.assertNotIn(secret, drift.stdout)
        self.assertEqual(payload["blocking_flags"][0]["recovery_commands"][0][0], "python3")

        blocked = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "upload",
                "--digest",
                status.plan["upload_confirmation_digest"],
                "--json",
            ]
        )
        self.assertEqual(blocked.exit_code, 2)
        self.assertIn("remote_drift", blocked.stdout)

        resolved = self.record_event(run_id, "remote_drift_resolved", {"note": "manual fields matched"})
        self.assertEqual(resolved.exit_code, 0, resolved.stderr or resolved.stdout)
        self.assertEqual(load_status(self.home, run_id).blocking_flags, [])

        authorized = run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "upload",
                "--digest",
                status.plan["upload_confirmation_digest"],
                "--json",
            ]
        )
        self.assertEqual(authorized.exit_code, 0, authorized.stderr or authorized.stdout)

    def test_qualification_and_quota_flags_are_independent(self):
        run_id = self.prepare_attempt()
        resolutions = {
            "qualification_required": "qualification_resolved",
            "quota_exhausted": "quota_resolved",
            "channel_contract_unverified": "channel_contract_verified",
        }
        for event, resolution_event in resolutions.items():
            commands = [["python3", "scripts/publisher.py", "record", run_id, "workbuddy", "--event", resolution_event, "--evidence", "resolution.json"]]
            result = self.record_event(run_id, event, {"recovery_commands": commands, "note": event})
            self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)

        self.assertEqual(
            {flag["flag"] for flag in load_status(self.home, run_id).blocking_flags},
            {"qualification_required", "quota_exhausted", "channel_contract_unverified"},
        )
        resolution = self.record_event(run_id, "qualification_resolved", {"note": "qualification verified"})
        self.assertEqual(resolution.exit_code, 0, resolution.stderr or resolution.stdout)
        self.assertEqual(
            [flag["flag"] for flag in load_status(self.home, run_id).blocking_flags],
            ["quota_exhausted", "channel_contract_unverified"],
        )

    def test_third_identical_failure_exhausts_retry_and_readback_resets_it(self):
        run_id = self.prepare_attempt()
        evidence = {
            "failure_signature": "network-unavailable",
            "recovery_commands": [
                [
                    "python3",
                    "scripts/publisher.py",
                    "record",
                    run_id,
                    "workbuddy",
                    "--event",
                    "retry_exhausted_resolved",
                    "--evidence",
                    "retry-resolution.json",
                ]
            ],
        }
        for expected_count in (1, 2, 3):
            result = self.record_event(run_id, "attempt_failed", evidence)
            self.assertEqual(result.exit_code, 0 if expected_count < 3 else 1, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["failure_streak"]["consecutive_count"], expected_count)

        exhausted = load_status(self.home, run_id)
        self.assertEqual(exhausted.failure_streak["consecutive_count"], 3)
        self.assertEqual([flag["flag"] for flag in exhausted.blocking_flags], ["retry_exhausted"])

        fourth = self.record_event(run_id, "attempt_failed", evidence)
        self.assertEqual(fourth.exit_code, 1)
        self.assertEqual(json.loads(fourth.stdout)["failure_streak"]["consecutive_count"], 3)

        different = self.record_event(
            run_id,
            "attempt_failed",
            {
                "failure_signature": "validation-timeout",
                "recovery_commands": [
                    [
                        "python3",
                        "scripts/publisher.py",
                        "record",
                        run_id,
                        "workbuddy",
                        "--event",
                        "retry_exhausted_resolved",
                        "--evidence",
                        "retry-resolution.json",
                    ]
                ],
            },
        )
        self.assertEqual(different.exit_code, 0, different.stderr or different.stdout)
        self.assertEqual(load_status(self.home, run_id).failure_streak["consecutive_count"], 1)
        self.assertEqual(load_status(self.home, run_id).blocking_flags, [])

        readback = self.record_event(run_id, "readback_recovered", {"raw_status": "draft still ready"})
        self.assertEqual(readback.exit_code, 0, readback.stderr or readback.stdout)
        reset = load_status(self.home, run_id)
        self.assertEqual(reset.failure_streak["consecutive_count"], 0)
        self.assertEqual(reset.blocking_flags, [])

    def test_prepare_owner_waits_without_artifact_then_handoff_releases_scope(self):
        first = self.prepare_attempt()
        artifact_count = len(list((self.home / "runs").rglob("*.zip")))
        database_path = self.home / "state" / "publisher.sqlite3"
        ledger_before = database_path.read_bytes()

        waiting = run_cli(
            ["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"]
        )
        self.assertEqual(waiting.exit_code, 1)
        wait_payload = json.loads(waiting.stdout)["attempts"][0]
        self.assertEqual(wait_payload["error_code"], "concurrent_attempt")
        self.assertTrue(wait_payload["wait"])
        self.assertEqual(wait_payload["owner"]["run_id"], first)
        self.assertTrue(wait_payload["recovery_commands"])
        self.assertEqual(len(list((self.home / "runs").rglob("*.zip"))), artifact_count)
        self.assertEqual(database_path.read_bytes(), ledger_before)
        self.assertEqual(load_status(self.home, first).blocking_flags, [])

        handoff = self.record_event(first, "ownership_handoff", {"note": "operator takes over"})
        self.assertEqual(handoff.exit_code, 0, handoff.stderr or handoff.stdout)
        resumed = run_cli(
            ["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"]
        )
        self.assertEqual(resumed.exit_code, 0, resumed.stderr or resumed.stdout)
        self.assertNotIn("concurrent_attempt", resumed.stdout)

    def test_channel_blockers_do_not_gate_another_channel(self):
        self.home = make_home(
            self.base,
            {
                "accounts": {"workbuddy": "primary", "lovstudio": "studio-primary"},
                "source_url": "https://example.test/skills/workbuddy-fixture",
            },
        )
        prepared = run_cli(
            [
                "prepare",
                str(self.skill),
                "--channels",
                "workbuddy,lovstudio",
                "--home",
                str(self.home),
                "--json",
            ]
        )
        self.assertEqual(prepared.exit_code, 0, prepared.stderr or prepared.stdout)
        attempts = {item["channel"]: item for item in json.loads(prepared.stdout)["attempts"]}
        workbuddy_id = attempts["workbuddy"]["run_id"]
        lovstudio_id = attempts["lovstudio"]["run_id"]
        drift = self.record_event(
            workbuddy_id,
            "remote_drift",
            {
                "local_fields": {"description": "local"},
                "remote_fields": {"description": "remote"},
                "recovery_commands": [
                    [
                        "python3",
                        "scripts/publisher.py",
                        "record",
                        workbuddy_id,
                        "workbuddy",
                        "--event",
                        "remote_drift_resolved",
                        "--evidence",
                        "remote-drift-resolution.json",
                    ]
                ],
            },
        )
        self.assertEqual(drift.exit_code, 0, drift.stderr or drift.stdout)

        authorized = run_cli(
            [
                "authorize",
                lovstudio_id,
                "lovstudio",
                "--home",
                str(self.home),
                "--kind",
                "upload",
                "--digest",
                attempts["lovstudio"]["plan"]["upload_confirmation_digest"],
                "--json",
            ]
        )
        self.assertEqual(authorized.exit_code, 0, authorized.stderr or authorized.stdout)

    def test_failed_lifecycle_event_keeps_retry_blocker_and_successful_finalize_resets_streak(self):
        run_id = self.prepare_attempt()
        recovery = [
            "python3",
            "scripts/publisher.py",
            "record",
            run_id,
            "workbuddy",
            "--event",
            "retry_exhausted_resolved",
            "--evidence",
            "retry-resolution.json",
        ]
        for _ in range(3):
            self.record_event(
                run_id,
                "attempt_failed",
                {"failure_signature": "transient", "recovery_commands": [recovery]},
            )
        failed = self.record_event(run_id, "zip_parsed", {})
        self.assertEqual(failed.exit_code, 2)
        self.assertEqual([flag["flag"] for flag in load_status(self.home, run_id).blocking_flags], ["retry_exhausted"])

        recovery_result = self.record_event(run_id, "retry_exhausted_resolved", {"note": "manual retry review"})
        self.assertEqual(recovery_result.exit_code, 0, recovery_result.stderr or recovery_result.stdout)
        for _ in range(2):
            self.record_event(
                run_id,
                "attempt_failed",
                {"failure_signature": "transient", "recovery_commands": [recovery]},
            )
        self.assertEqual(load_status(self.home, run_id).failure_streak["consecutive_count"], 2)
        self.finalize_attempt(run_id, "draft-reset")
        self.assertEqual(load_status(self.home, run_id).failure_streak["consecutive_count"], 0)

    def test_recovery_evidence_and_failure_signature_are_redacted_at_rest_and_output(self):
        run_id = self.prepare_attempt()
        opaque = "opaque-private-value-123"
        recorded = self.record_event(
            run_id,
            "remote_drift",
            {
                "local_fields": {"access_token": opaque},
                "remote_fields": {"access_token": "missing"},
                "recovery_commands": [
                    [
                        "python3",
                        "scripts/publisher.py",
                        "record",
                        run_id,
                        "workbuddy",
                        "--event",
                        "remote_drift_resolved",
                        "--evidence",
                        "resolution.json",
                    ]
                ],
            },
        )
        self.assertEqual(recorded.exit_code, 0, recorded.stderr or recorded.stdout)
        self.assertNotIn(opaque, recorded.stdout)
        self.assertNotIn(opaque, (self.home / "runs" / run_id / "evidence" / "remote_drift.json").read_text(encoding="utf-8"))

        self.record_event(run_id, "remote_drift_resolved", {"note": "reviewed"})
        for _ in range(3):
            self.record_event(
                run_id,
                "attempt_failed",
                {
                    "failure_signature": opaque,
                    "recovery_commands": [
                        [
                            "python3",
                            "scripts/publisher.py",
                            "record",
                            run_id,
                            "workbuddy",
                            "--event",
                            "retry_exhausted_resolved",
                            "--evidence",
                            "retry-resolution.json",
                        ]
                    ],
                },
            )
        self.assertNotIn(opaque, (self.home / "state" / "publisher.sqlite3").read_bytes().decode("latin1"))

    def test_failure_streak_current_signature_is_deterministic_and_recovery_argv_is_complete(self):
        run_id = self.prepare_attempt()
        command = [
            "python3",
            "scripts/publisher.py",
            "record",
            run_id,
            "workbuddy",
            "--event",
            "retry_exhausted_resolved",
            "--evidence",
            "retry-resolution.json",
        ]
        for signature in ("A", "B", "A"):
            result = self.record_event(run_id, "attempt_failed", {"failure_signature": signature, "recovery_commands": [command]})
            self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        streak = load_status(self.home, run_id).failure_streak
        self.assertEqual(streak["failure_signature"], hashlib.sha256(b"A").hexdigest())
        self.assertEqual(streak["consecutive_count"], 1)

        malformed = self.record_event(
            run_id,
            "remote_drift",
            {
                "local_fields": {"description": "local"},
                "remote_fields": {"description": "remote"},
                "recovery_commands": [["python3", "scripts/publisher.py", "record", run_id]],
            },
        )
        self.assertEqual(malformed.exit_code, 2)

        invalid_failure = self.record_event(
            run_id,
            "attempt_failed",
            {
                "failure_signature": "must-not-persist",
                "recovery_commands": [
                    [
                        "python3",
                        "scripts/publisher.py",
                        "record",
                        run_id,
                        "workbuddy",
                        "--event",
                        "remote_drift_resolved",
                        "--evidence",
                        "wrong-resolution.json",
                    ]
                ],
            },
        )
        self.assertEqual(invalid_failure.exit_code, 2)
        self.assertEqual(load_status(self.home, run_id).failure_streak["consecutive_count"], 1)

    def test_changed_content_with_same_version_waits_for_existing_owner(self):
        first = self.prepare_attempt()
        skill_md = self.skill / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8").replace("End-to-end fixture skill.", "Changed without a version bump."),
            encoding="utf-8",
        )
        profile_path = self.home / "config" / "profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["capabilities"][0]["evidence"]["source_digest"] = load_source(self.skill).source_digest
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        waiting = run_cli(["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"])
        self.assertEqual(waiting.exit_code, 1)
        self.assertEqual(json.loads(waiting.stdout)["attempts"][0]["owner"]["run_id"], first)

    def test_orphaned_owner_wait_includes_executable_claim_cancel_command(self):
        snapshot = load_source(self.skill)
        ledger = Ledger.open(self.home / "state" / "publisher.sqlite3")
        self.addCleanup(ledger.close)
        owner, acquired = ledger.claim_ownership(snapshot, "workbuddy")
        self.assertTrue(acquired)
        self.assertIsNone(owner.owner_attempt_id)
        before = (self.home / "state" / "publisher.sqlite3").read_bytes()

        waiting = run_cli(["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"])
        self.assertEqual(waiting.exit_code, 1)
        payload = json.loads(waiting.stdout)["attempts"][0]
        command = payload["recovery_commands"][0]
        self.assertEqual(command[:3], ["python3", "scripts/publisher.py", "record"])
        self.assertEqual(command[3], owner.claim_ref)
        self.assertTrue(owner.claim_ref.startswith("claim-"))
        self.assertEqual(command[5:8], ["--event", "ownership_claim_cancelled", "--evidence"])
        self.assertNotIn("owner_token", waiting.stdout)
        self.assertEqual((self.home / "state" / "publisher.sqlite3").read_bytes(), before)

        evidence_path = self.base / "orphan-cancel.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "note": "owner never bound an attempt",
                    "source_id": owner.source_id,
                    "source_version": owner.source_version,
                    "channel": owner.channel,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        cancelled = run_cli(
            [
                "record",
                owner.claim_ref,
                "workbuddy",
                "--home",
                str(self.home),
                "--event",
                "ownership_claim_cancelled",
                "--evidence",
                str(evidence_path),
                "--json",
            ]
        )
        self.assertEqual(cancelled.exit_code, 0, cancelled.stderr or cancelled.stdout)
        resumed = run_cli(["prepare", str(self.skill), "--channels", "workbuddy", "--home", str(self.home), "--json"])
        self.assertEqual(resumed.exit_code, 0, resumed.stderr or resumed.stdout)

    def test_valid_lifecycle_transition_cannot_bypass_active_retry_exhausted(self):
        run_id = self.prepare_attempt()
        self.authorize_upload(run_id)
        recovery = [
            "python3",
            "scripts/publisher.py",
            "record",
            run_id,
            "workbuddy",
            "--event",
            "retry_exhausted_resolved",
            "--evidence",
            "retry-resolution.json",
        ]
        for _ in range(3):
            self.record_event(run_id, "attempt_failed", {"failure_signature": "upload-retry", "recovery_commands": [recovery]})

        blocked = self.record_event(run_id, "upload_completed", {"raw_status": "uploaded"})
        self.assertEqual(blocked.exit_code, 2)
        self.assertEqual(load_status(self.home, run_id).state, PublishState.AWAITING_UPLOAD_CONFIRMATION.value)
        self.assertEqual([flag["flag"] for flag in load_status(self.home, run_id).blocking_flags], ["retry_exhausted"])

        self.assertEqual(self.record_event(run_id, "retry_exhausted_resolved", {"note": "operator reviewed"}).exit_code, 0)
        completed = self.record_event(run_id, "upload_completed", {"raw_status": "uploaded"})
        self.assertEqual(completed.exit_code, 0, completed.stderr or completed.stdout)

    def test_export_writes_redacted_json_atomically(self):
        run_id = self.prepare_attempt()
        digest = self.finalize_attempt(run_id, "draft-1")
        run_cli(
            [
                "authorize",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--kind",
                "submission",
                "--digest",
                digest,
                "--json",
            ]
        )
        evidence_path = self.base / "submitted.json"
        private_home = "/" + "Users" + "/example-user"
        token = "gh" + "p_" + "12345678901234567890"
        evidence_path.write_text(
            json.dumps(
                {
                    "raw_status": "submitted",
                    "product_id": "draft-1",
                    "source_version": "1.0.0",
                    "public_url": "https://example.test/products/workbuddy-fixture",
                    "evidence_path": private_home + "/private/upload.png",
                    "token": token,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        record = run_cli(
            [
                "record",
                run_id,
                "workbuddy",
                "--home",
                str(self.home),
                "--event",
                "review_submitted",
                "--evidence",
                str(evidence_path),
                "--json",
            ]
        )
        self.assertEqual(record.exit_code, 0, record.stderr or record.stdout)
        export_path = self.base / "status.json"
        result = run_cli(
            [
                "export",
                "--home",
                str(self.home),
                "--format",
                "json",
                "--output",
                str(export_path),
            ]
        )

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        exported = export_path.read_text(encoding="utf-8")
        self.assertIn("submitted", exported)
        self.assertNotIn(private_home, exported)
        self.assertNotIn("gh" + "p_", exported)

    def test_export_source_alias_matches_source_id_without_leaking_source_path(self):
        self.prepare_attempt()
        output_by_path = self.base / "by-path.json"
        output_by_id = self.base / "by-id.json"
        from_path = run_cli(
            [
                "export",
                "--home",
                str(self.home),
                "--source",
                str(self.skill),
                "--format",
                "json",
                "--output",
                str(output_by_path),
            ]
        )
        from_id = run_cli(
            [
                "export",
                "--home",
                str(self.home),
                "--source-id",
                source_id(self.skill),
                "--format",
                "json",
                "--output",
                str(output_by_id),
            ]
        )

        self.assertEqual(from_path.exit_code, 0, from_path.stderr or from_path.stdout)
        self.assertEqual(from_id.exit_code, 0, from_id.stderr or from_id.stdout)
        self.assertEqual(output_by_path.read_text(encoding="utf-8"), output_by_id.read_text(encoding="utf-8"))
        self.assertNotIn(str(self.skill), output_by_path.read_text(encoding="utf-8"))

    def test_status_source_returns_local_redacted_rows_and_missing_inputs_do_not_write(self):
        self.prepare_attempt()
        database_path = self.home / "state" / "publisher.sqlite3"
        database_before = database_path.read_bytes()

        result = run_cli(["status", "--source", str(self.skill), "--home", str(self.home), "--json"])

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["attempts"]), 1)
        self.assertEqual(payload["attempts"][0]["channel"], "workbuddy")
        self.assertNotIn(str(self.skill), result.stdout)
        self.assertEqual(database_path.read_bytes(), database_before)

        missing_home = self.base / "missing-ledger-home"
        missing_ledger = run_cli(["status", "--source", str(self.skill), "--home", str(missing_home), "--json"])
        missing_source = run_cli(
            ["status", "--source", str(self.base / "missing-source"), "--home", str(self.home), "--json"]
        )

        self.assertEqual(missing_ledger.exit_code, 2)
        self.assertEqual(missing_source.exit_code, 2)
        self.assertFalse(missing_home.exists())
        self.assertEqual(database_path.read_bytes(), database_before)

    def test_export_redacts_printed_output_path(self):
        run_id = self.prepare_attempt()
        self.assertTrue(run_id)
        private_home = Path("/") / ("Us" + "ers") / "example-user"
        export_path = private_home / "shadow-skill-publisher-export.json"

        with mock.patch.object(cli_module, "_write_atomic") as writer:
            result = run_cli(
                [
                    "export",
                    "--home",
                    str(self.home),
                    "--format",
                    "json",
                    "--output",
                    str(export_path),
                ]
            )

        self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
        writer.assert_called_once()
        self.assertIn("[REDACTED_HOME]", result.stdout)


if __name__ == "__main__":
    unittest.main()
