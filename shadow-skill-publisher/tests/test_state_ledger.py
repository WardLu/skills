import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.ledger import AuthorizationRequired, Ledger, InvalidTransition
from shadow_skill_publisher.models import Artifact, FrozenFields, PublishState, SourceSnapshot, SubmissionPlan
from shadow_skill_publisher.state import can_transition


class StateTransitionTests(unittest.TestCase):
    def test_exact_prd_edges_are_allowed(self):
        allowed = (
            (PublishState.DRAFT, PublishState.CHECKED),
            (PublishState.DRAFT, PublishState.BLOCKED),
            (PublishState.BLOCKED, PublishState.DRAFT),
            (PublishState.CHECKED, PublishState.PREPARED),
            (PublishState.PREPARED, PublishState.AWAITING_UPLOAD_CONFIRMATION),
            (PublishState.PREPARED, PublishState.AWAITING_SUBMISSION_CONFIRMATION),
            (PublishState.AWAITING_UPLOAD_CONFIRMATION, PublishState.PREPARED),
            (PublishState.AWAITING_UPLOAD_CONFIRMATION, PublishState.UPLOADED),
            (PublishState.UPLOADED, PublishState.PARSING),
            (PublishState.UPLOADED, PublishState.AWAITING_SUBMISSION_CONFIRMATION),
            (PublishState.PARSING, PublishState.PREPARED),
            (PublishState.PARSING, PublishState.AWAITING_SUBMISSION_CONFIRMATION),
            (PublishState.AWAITING_SUBMISSION_CONFIRMATION, PublishState.PREPARED),
            (PublishState.AWAITING_SUBMISSION_CONFIRMATION, PublishState.SUBMITTED),
            (PublishState.AWAITING_SUBMISSION_CONFIRMATION, PublishState.SUBMISSION_UNKNOWN),
            (PublishState.SUBMISSION_UNKNOWN, PublishState.SUBMITTED),
            (PublishState.SUBMISSION_UNKNOWN, PublishState.AWAITING_SUBMISSION_CONFIRMATION),
            (PublishState.SUBMITTED, PublishState.UNDER_REVIEW),
            (PublishState.UNDER_REVIEW, PublishState.CHANGES_REQUESTED),
            (PublishState.UNDER_REVIEW, PublishState.REJECTED),
            (PublishState.UNDER_REVIEW, PublishState.APPROVED),
            (PublishState.CHANGES_REQUESTED, PublishState.PREPARED),
            (PublishState.REJECTED, PublishState.PREPARED),
            (PublishState.APPROVED, PublishState.LIVE),
            (PublishState.LIVE, PublishState.SUPERSEDED),
            (PublishState.LIVE, PublishState.DELISTED),
        )
        for current, target in allowed:
            self.assertTrue(can_transition(current, target), f"{current.value} -> {target.value}")

    def test_non_prd_edges_are_rejected(self):
        blocked = (
            (PublishState.DRAFT, PublishState.PREPARED),
            (PublishState.CHECKED, PublishState.UPLOADED),
            (PublishState.PREPARED, PublishState.UPLOADED),
            (PublishState.UPLOADED, PublishState.SUBMITTED),
            (PublishState.SUBMISSION_UNKNOWN, PublishState.PREPARED),
            (PublishState.APPROVED, PublishState.SUPERSEDED),
            (PublishState.DELISTED, PublishState.LIVE),
        )
        for current, target in blocked:
            self.assertFalse(can_transition(current, target), f"{current.value} -> {target.value}")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.db_path = self.base / "publisher.sqlite3"
        self.ledger = Ledger.open(self.db_path)
        self.snapshot = self._snapshot(self.base / "source")
        self.artifact = self._artifact(self.base / "dist" / "demo.zip", "artifact-one")
        self.plan = self._plan(self.artifact, upload_suffix="upload-v1", submission_suffix=None)
        self.finalized_plan = self._plan(
            self.artifact,
            upload_suffix="upload-v1",
            submission_suffix="submit-v1",
            platform_id="draft-123",
            observed_fields={"title": "Observed demo"},
            final_action="submit_review",
        )

    def _snapshot(self, root: Path) -> SourceSnapshot:
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo skill.\nversion: 1.2.3\n---\n",
            encoding="utf-8",
        )
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        return SourceSnapshot(
            root=root,
            name="demo-skill",
            description="Demo skill.",
            version="1.2.3",
            source_digest="a" * 64,
            files=("LICENSE", "SKILL.md"),
            license_path=root / "LICENSE",
            kind="prompt",
            skill_md_text="---\nname: demo-skill\n---\n",
            git_commit=None,
            git_branch=None,
            git_dirty=False,
            untracked_files=(),
        )

    def _artifact(self, path: Path, payload: str) -> Artifact:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        return Artifact(
            channel="workbuddy",
            path=path,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
            files=("LICENSE", "SKILL.md"),
        )

    def _plan(
        self,
        artifact: Artifact,
        upload_suffix: str,
        submission_suffix: str = None,
        platform_id: str = None,
        observed_fields=None,
        final_action=None,
        account_alias: str = "primary",
        title: str = "Demo title",
    ) -> SubmissionPlan:
        return SubmissionPlan(
            channel="workbuddy",
            contract_version="2026-09-03",
            account_alias=account_alias,
            artifact=artifact,
            fields={"title": title, "summary": "A tidy summary"},
            disclosure={"files": list(artifact.files), "scope": "source bundle"},
            upload_confirmation_digest=upload_suffix,
            platform_id=platform_id,
            observed_fields=observed_fields or {},
            final_action=final_action,
            submission_confirmation_digest=submission_suffix,
            manual_fallback=("copy fields manually",),
        )

    def _advance_to_upload_confirmation(self, attempt_id: str) -> None:
        self.ledger.transition(attempt_id, PublishState.CHECKED, "quality_passed", {})
        self.ledger.transition(attempt_id, PublishState.PREPARED, "artifact_prepared", {})
        self.ledger.transition(
            attempt_id,
            PublishState.AWAITING_UPLOAD_CONFIRMATION,
            "upload_confirmation_ready",
            {"next_action": "confirm_upload"},
        )

    def test_upload_requires_matching_authorization(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.plan)
        self._advance_to_upload_confirmation(attempt)

        with self.assertRaises(AuthorizationRequired):
            self.ledger.transition(
                attempt,
                PublishState.UPLOADED,
                "upload_completed",
                {"raw_status": "upload ok", "public_url": "https://example.test/drafts/1"},
            )

    def test_upload_requires_current_plan_digest(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.plan)
        self._advance_to_upload_confirmation(attempt)
        self.ledger.add_authorization(attempt, "upload", self.plan.upload_confirmation_digest, "2026-09-03T00:00:00Z")

        changed_plan = self._plan(self.artifact, upload_suffix="upload-v2", submission_suffix=None, title="Changed title")
        self.ledger.save_submission_plan(attempt, changed_plan)

        with self.assertRaises(AuthorizationRequired):
            self.ledger.transition(attempt, PublishState.UPLOADED, "upload_completed", {"raw_status": "upload ok"})

    def test_unknown_submission_blocks_retry_until_readback(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.plan)
        self._advance_to_upload_confirmation(attempt)
        self.ledger.add_authorization(attempt, "upload", self.plan.upload_confirmation_digest, "2026-09-03T00:00:00Z")
        self.ledger.transition(attempt, PublishState.UPLOADED, "upload_completed", {"raw_status": "uploaded"})
        self.ledger.save_submission_plan(attempt, self.finalized_plan)
        self.ledger.transition(
            attempt,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
            "prefill_verified",
            {"product_id": "draft-123", "raw_status": "draft ready"},
        )
        self.ledger.add_authorization(
            attempt,
            "submission",
            self.finalized_plan.submission_confirmation_digest,
            "2026-09-03T00:01:00Z",
        )
        self.ledger.transition(
            attempt,
            PublishState.SUBMISSION_UNKNOWN,
            "network_lost_after_submit",
            {"raw_status": "submit uncertain", "final_action": "submit_review"},
        )

        with self.assertRaises(InvalidTransition):
            self.ledger.transition(attempt, PublishState.SUBMITTED, "retry_submit", {"raw_status": "retry"})

        self.ledger.transition(
            attempt,
            PublishState.SUBMITTED,
            "readback_submitted",
            {"raw_status": "submitted", "product_id": "draft-123"},
        )

    def test_submission_boundary_requires_current_upload_and_submission_authorizations(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.finalized_plan)
        self.ledger.transition(attempt, PublishState.CHECKED, "quality_passed", {})
        self.ledger.transition(attempt, PublishState.PREPARED, "artifact_prepared", {})
        self.ledger.transition(
            attempt,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
            "local_preview_finalized",
            {"product_id": "draft-123"},
        )
        self.ledger.add_authorization(
            attempt,
            "submission",
            self.finalized_plan.submission_confirmation_digest,
            "2026-09-03T00:01:00Z",
        )

        with self.assertRaisesRegex(AuthorizationRequired, "upload authorization"):
            self.ledger.transition(
                attempt,
                PublishState.SUBMITTED,
                "review_submitted",
                {"raw_status": "submitted", "final_action": "submit_review"},
            )

        self.ledger.add_authorization(
            attempt,
            "upload",
            self.finalized_plan.upload_confirmation_digest,
            "2026-09-03T00:02:00Z",
        )
        self.ledger.transition(
            attempt,
            PublishState.SUBMITTED,
            "review_submitted",
            {"raw_status": "submitted", "final_action": "submit_review"},
        )
        self.assertEqual(self.ledger.get_attempt(attempt).state, PublishState.SUBMITTED)

    def test_submission_boundary_rejects_action_mismatch(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.finalized_plan)
        self.ledger.transition(attempt, PublishState.CHECKED, "quality_passed", {})
        self.ledger.transition(attempt, PublishState.PREPARED, "artifact_prepared", {})
        self.ledger.transition(
            attempt,
            PublishState.AWAITING_SUBMISSION_CONFIRMATION,
            "local_preview_finalized",
            {"product_id": "draft-123"},
        )
        self.ledger.add_authorization(
            attempt,
            "upload",
            self.finalized_plan.upload_confirmation_digest,
            "2026-09-03T00:01:00Z",
        )
        self.ledger.add_authorization(
            attempt,
            "submission",
            self.finalized_plan.submission_confirmation_digest,
            "2026-09-03T00:02:00Z",
        )

        with self.assertRaisesRegex(InvalidTransition, "final_action"):
            self.ledger.transition(
                attempt,
                PublishState.SUBMITTED,
                "publish",
                {"raw_status": "published", "final_action": "publish"},
            )

    def test_attempt_identity_is_bound_to_artifact(self):
        first = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.assertEqual(self.ledger.get_attempt(first).artifact_sha256, self.artifact.sha256)

        second = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.assertEqual(second, first)

        other_artifact = self._artifact(self.base / "dist" / "demo-v2.zip", "artifact-two")
        third = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", other_artifact)
        self.assertNotEqual(third, first)

    def test_finalized_submission_plan_round_trips(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.finalized_plan)
        self.assertEqual(self.ledger.load_submission_plan(attempt), self.finalized_plan)

    def test_frozen_fields_are_bound_to_attempt_and_redacted_at_rest(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        private_home = "/" + "Users" + "/example-user"
        token = "gh" + "p_" + "12345678901234567890"
        frozen = FrozenFields(
            values={"description": "Use " + private_home + "/private; token=" + token},
            drifted_fields=("source_digest",),
            generated_facts={"source_digest": "a" * 64},
        )

        self.ledger.save_frozen_fields(attempt, frozen)

        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT values_json, generated_facts_json FROM frozen_fields WHERE attempt_id = ?",
                (attempt,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertNotIn(private_home, row[0])
        self.assertNotIn("gh" + "p_", row[0])
        self.assertEqual(self.ledger.load_frozen_fields(self.snapshot.root, "workbuddy").drifted_fields, ("source_digest",))
        self.assertIn("[REDACTED_HOME]", self.ledger.load_frozen_fields_for_attempt(attempt).values["description"])

    def test_submission_plan_storage_redacts_sensitive_nested_strings(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        private_home = "/" + "Users" + "/example-user"
        token = "gh" + "p_" + "12345678901234567890"
        sensitive_plan = SubmissionPlan(
            channel="workbuddy",
            contract_version="2026-09-03",
            account_alias="primary",
            artifact=Artifact(
                channel="workbuddy",
                path=Path(private_home) / "private" / "demo.zip",
                sha256=self.artifact.sha256,
                size_bytes=self.artifact.size_bytes,
                files=self.artifact.files,
            ),
            fields={
                "title": "Demo title",
                "support_email": "alice@example.com",
                "token": token,
            },
            disclosure={
                "cookie": "sid=secret-value",
                "evidence_path": private_home + "/private/upload.png",
                "qr_payload": "otpauth://totp/private",
            },
            upload_confirmation_digest="upload-v1",
            platform_id="draft-123",
            observed_fields={
                "operator_email": "alice@example.com",
                "private_path": private_home + "/private/source",
            },
            final_action="submit_review",
            submission_confirmation_digest="submit-v1",
            manual_fallback=("open " + private_home + "/private/file", "token=secret"),
        )

        self.ledger.save_submission_plan(attempt, sensitive_plan)

        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT plan_json FROM submission_plans WHERE attempt_id = ? ORDER BY revision DESC LIMIT 1",
                (attempt,),
            ).fetchone()
        self.assertIsNotNone(row)
        stored_json = row[0]
        for raw_value in ("alice@example.com", "gh" + "p_", private_home, "otpauth://", "secret-value"):
            self.assertNotIn(raw_value, stored_json)

        round_tripped = self.ledger.load_submission_plan(attempt)
        self.assertEqual(round_tripped.upload_confirmation_digest, "upload-v1")
        self.assertEqual(round_tripped.submission_confirmation_digest, "submit-v1")
        self.assertEqual(round_tripped.final_action, "submit_review")
        self.assertEqual(round_tripped.platform_id, "draft-123")
        self.assertEqual(round_tripped.artifact.sha256, self.artifact.sha256)
        self.assertIn("[REDACTED_HOME]", str(round_tripped.artifact.path))
        self.assertEqual(round_tripped.fields["support_email"], "[REDACTED_ACCOUNT]")
        self.assertEqual(round_tripped.fields["token"], "[REDACTED_PRIVATE]")

    def test_add_authorization_requires_current_plan_digest(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        self.ledger.save_submission_plan(attempt, self.plan)

        with self.assertRaises(AuthorizationRequired):
            self.ledger.add_authorization(attempt, "upload", "stale-upload", "2026-09-03T00:00:00Z")

        self.ledger.add_authorization(attempt, "upload", self.plan.upload_confirmation_digest, "2026-09-03T00:00:00Z")

        with self.assertRaises(AuthorizationRequired):
            self.ledger.add_authorization(attempt, "submission", "submit-v1", "2026-09-03T00:01:00Z")

        self.ledger.save_submission_plan(attempt, self.finalized_plan)

        with self.assertRaises(AuthorizationRequired):
            self.ledger.add_authorization(attempt, "submission", "submit-stale", "2026-09-03T00:02:00Z")

        self.ledger.add_authorization(
            attempt,
            "submission",
            self.finalized_plan.submission_confirmation_digest,
            "2026-09-03T00:03:00Z",
        )

    def test_save_submission_plan_rejects_artifact_channel_mismatch(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        wrong_artifact = Artifact(
            channel="skillpay",
            path=self.artifact.path,
            sha256=self.artifact.sha256,
            size_bytes=self.artifact.size_bytes,
            files=self.artifact.files,
        )
        wrong_plan = self._plan(wrong_artifact, upload_suffix="upload-v1")

        with self.assertRaisesRegex(ValueError, "artifact channel"):
            self.ledger.save_submission_plan(attempt, wrong_plan)

    def test_export_redacts_private_values_and_includes_required_fields(self):
        attempt = self.ledger.create_attempt(self.snapshot, "workbuddy", "primary", "2026-09-03", self.artifact)
        private_home = "/" + "Users" + "/example-user"
        token = "gh" + "p_" + "12345678901234567890"
        self.ledger.save_submission_plan(attempt, self.plan)
        self._advance_to_upload_confirmation(attempt)
        self.ledger.add_authorization(attempt, "upload", self.plan.upload_confirmation_digest, "2026-09-03T00:00:00Z")
        self.ledger.transition(
            attempt,
            PublishState.UPLOADED,
            "upload_completed",
            {
                "raw_status": "upload ok",
                "product_id": "draft-123",
                "public_url": "https://example.test/products/demo-skill",
                "evidence_path": private_home + "/private/upload.png",
                "account_id": "alice@example.com",
                "token": token,
                "next_action": "wait_for_parsing",
            },
        )

        exported_json = self.ledger.export(None, "json")
        payload = json.loads(exported_json)
        self.assertEqual(len(payload), 1)
        row = payload[0]
        self.assertEqual(row["status"], PublishState.UPLOADED.value)
        self.assertEqual(row["raw_status"], "upload ok")
        self.assertEqual(row["version"], self.snapshot.version)
        self.assertEqual(row["product_id"], "draft-123")
        self.assertEqual(row["public_url"], "https://example.test/products/demo-skill")
        self.assertEqual(row["artifact_sha256"], self.artifact.sha256)
        self.assertEqual(row["next_action"], "wait_for_parsing")
        self.assertEqual(row["account_alias"], "primary")
        self.assertNotIn(private_home, exported_json)
        self.assertNotIn("alice@example.com", exported_json)
        self.assertNotIn("gh" + "p_", exported_json)

        exported_markdown = self.ledger.export(None, "markdown")
        self.assertIn("Created At", exported_markdown)
        self.assertIn("Submitted At", exported_markdown)
        self.assertIn("Approved At", exported_markdown)
        self.assertIn("Published At", exported_markdown)
        self.assertIn("Last Verified At", exported_markdown)
        self.assertIn(row["created_at"], exported_markdown)
        self.assertIn("wait_for_parsing", exported_markdown)
        self.assertIn("[REDACTED_HOME]", exported_markdown)
        self.assertNotIn("alice@example.com", exported_markdown)

        exported_csv = self.ledger.export(None, "csv")
        self.assertIn("status,raw_status,source_id,skill_name,version,channel", exported_csv.splitlines()[0])
        self.assertNotIn(private_home, exported_csv)

    def test_schema_version_table_is_initialized(self):
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute("SELECT version FROM schema_version").fetchone()
        self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
