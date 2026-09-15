import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.confirmations import (
    SubmissionPlanIncomplete,
    can_execute_remote_action,
    finalize_submission_plan,
    submission_digest,
    upload_digest,
)
from shadow_skill_publisher.models import Artifact, Authorization, SubmissionPlan


class ConfirmationDigestTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.artifact = self._artifact("demo.zip", "artifact-one")
        self.other_artifact = self._artifact("demo-v2.zip", "artifact-two")
        self.plan = SubmissionPlan(
            channel="workbuddy",
            contract_version="2026-09-03",
            account_alias="primary",
            artifact=self.artifact,
            fields={"title": "Demo skill", "summary": "Deterministic summary"},
            disclosure={
                "permissions": ("read:workspace",),
                "external_services": ("openai",),
                "claims": ("Deterministic packaging.",),
                "risks": ("No external writes without approval.",),
                "limitations": ("Channel adapters pending.",),
                "commercial_mode": "one_time",
                "price": "19",
            },
            upload_confirmation_digest="",
            platform_id=None,
            observed_fields={},
            final_action=None,
            submission_confirmation_digest=None,
            manual_fallback=("copy the fields manually",),
        )

    def _artifact(self, name: str, payload: str) -> Artifact:
        path = self.base / name
        path.write_text(payload, encoding="utf-8")
        return Artifact(
            channel="workbuddy",
            path=path,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
            files=("LICENSE", "SKILL.md"),
        )

    def test_upload_digest_changes_with_account_or_artifact(self):
        self.assertNotEqual(upload_digest(self.plan), upload_digest(replace(self.plan, account_alias="other")))
        self.assertNotEqual(upload_digest(self.plan), upload_digest(replace(self.plan, artifact=self.other_artifact)))

    def test_upload_digest_binds_artifact_policy_and_listing_assets(self):
        with_policy = replace(
            self.plan,
            disclosure={
                **self.plan.disclosure,
                "artifact_policy": {"excluded_patterns": ["scripts/**"]},
            },
        )
        with_asset = replace(
            self.plan,
            disclosure={
                **self.plan.disclosure,
                "listing_asset_receipts": [
                    {"role": "cover", "sha256": "a" * 64, "size_bytes": 12, "suffix": ".png"}
                ],
            },
        )
        self.assertNotEqual(upload_digest(self.plan), upload_digest(with_policy))
        self.assertNotEqual(upload_digest(self.plan), upload_digest(with_asset))

    def test_submission_digest_changes_with_price_or_action(self):
        first = finalize_submission_plan(self.plan, "draft-1", {**self.plan.fields, "price": "19"}, "submit_review")
        changed_price = finalize_submission_plan(self.plan, "draft-1", {**self.plan.fields, "price": "29"}, "submit_review")
        changed_action = finalize_submission_plan(self.plan, "draft-1", dict(first.observed_fields), "publish")
        self.assertNotEqual(submission_digest(first), submission_digest(changed_price))
        self.assertNotEqual(submission_digest(first), submission_digest(changed_action))

    def test_unfinalized_plan_has_no_submission_authorization_digest(self):
        self.assertIsNone(self.plan.submission_confirmation_digest)
        with self.assertRaises(SubmissionPlanIncomplete):
            submission_digest(self.plan)

    def test_upload_digest_is_canonical_for_reordered_mappings(self):
        reordered = replace(
            self.plan,
            fields={"summary": "Deterministic summary", "title": "Demo skill"},
            disclosure={
                "price": "19",
                "commercial_mode": "one_time",
                "limitations": ("Channel adapters pending.",),
                "risks": ("No external writes without approval.",),
                "claims": ("Deterministic packaging.",),
                "external_services": ("openai",),
                "permissions": ("read:workspace",),
            },
        )
        self.assertEqual(upload_digest(self.plan), upload_digest(reordered))

    def test_upload_digest_is_canonical_for_semantically_identical_sets(self):
        original = replace(
            self.plan,
            disclosure={
                "permissions": {"write:logs", "read:workspace"},
                "external_services": frozenset(("openai", "slack")),
                "claims": {"Deterministic packaging.", "No hidden writes."},
                "risks": {"Manual confirmation required.", "Rate limits may apply."},
                "limitations": {"Channel adapters pending.", "No live submit yet."},
                "commercial_mode": "one_time",
                "price": "19",
            },
        )
        reordered = replace(
            self.plan,
            disclosure={
                "permissions": frozenset(("read:workspace", "write:logs")),
                "external_services": {"slack", "openai"},
                "claims": frozenset(("No hidden writes.", "Deterministic packaging.")),
                "risks": frozenset(("Rate limits may apply.", "Manual confirmation required.")),
                "limitations": frozenset(("No live submit yet.", "Channel adapters pending.")),
                "commercial_mode": "one_time",
                "price": "19",
            },
        )
        self.assertEqual(upload_digest(original), upload_digest(reordered))

    def test_remote_prefill_requires_matching_upload_authorization(self):
        self.assertFalse(can_execute_remote_action(self.plan, "prefill", authorizations=()))
        self.assertFalse(
            can_execute_remote_action(
                self.plan,
                "prefill",
                authorizations=(Authorization(kind="submission", digest="submission-digest"),),
            )
        )
        self.assertTrue(
            can_execute_remote_action(
                self.plan,
                "prefill",
                authorizations=(Authorization(kind="upload", digest=upload_digest(self.plan)),),
            )
        )
        self.assertTrue(
            can_execute_remote_action(
                self.plan,
                "upload",
                authorizations=(Authorization(kind="upload", digest=upload_digest(self.plan)),),
            )
        )
        self.assertTrue(
            can_execute_remote_action(
                self.plan,
                "registration",
                authorizations=(Authorization(kind="upload", digest=upload_digest(self.plan)),),
            )
        )

    def test_upload_authorization_does_not_grant_submission_actions(self):
        upload_only = (Authorization(kind="upload", digest=upload_digest(self.plan)),)
        self.assertFalse(can_execute_remote_action(self.plan, "submit_review", authorizations=upload_only))
        self.assertFalse(can_execute_remote_action(self.plan, "publish", authorizations=upload_only))

    def test_submission_actions_require_finalized_plan_and_second_authorization(self):
        finalized = finalize_submission_plan(
            self.plan,
            "draft-1",
            {**self.plan.fields, "price": "19"},
            "submit_review",
        )
        upload_auth = Authorization(kind="upload", digest=upload_digest(finalized))
        submission_auth = Authorization(kind="submission", digest=submission_digest(finalized))

        self.assertTrue(can_execute_remote_action(finalized, "submit_review", authorizations=(upload_auth, submission_auth)))
        self.assertFalse(can_execute_remote_action(finalized, "publish", authorizations=(upload_auth, submission_auth)))
        self.assertFalse(can_execute_remote_action(self.plan, "submit_review", authorizations=(upload_auth, submission_auth)))
        self.assertFalse(
            can_execute_remote_action(
                finalized,
                "submit_review",
                authorizations=(upload_auth, Authorization(kind="submission", digest="stale-digest")),
            )
        )

    def test_publish_authorization_cannot_be_reused_for_submit_review(self):
        finalized = finalize_submission_plan(
            self.plan,
            "draft-1",
            {**self.plan.fields, "price": "19"},
            "publish",
        )
        upload_auth = Authorization(kind="upload", digest=upload_digest(finalized))
        submission_auth = Authorization(kind="submission", digest=submission_digest(finalized))

        self.assertTrue(can_execute_remote_action(finalized, "publish", authorizations=(upload_auth, submission_auth)))
        self.assertFalse(
            can_execute_remote_action(
                finalized,
                "submit_review",
                authorizations=(upload_auth, submission_auth),
            )
        )

    def test_malformed_plan_fails_closed_for_missing_channel(self):
        malformed = replace(self.plan, channel=None)
        auth = Authorization(kind="upload", digest=upload_digest(self.plan))
        self.assertFalse(can_execute_remote_action(malformed, "prefill", authorizations=(auth,)))

    def test_malformed_plan_fails_closed_for_invalid_artifact_size(self):
        malformed_artifact = replace(self.artifact, size_bytes="not-an-int")
        malformed = replace(self.plan, artifact=malformed_artifact)
        auth = Authorization(kind="upload", digest=upload_digest(self.plan))
        self.assertFalse(can_execute_remote_action(malformed, "upload", authorizations=(auth,)))

    def test_digest_scope_mismatch_is_rejected_for_channel_account_and_artifact(self):
        other_channel = replace(self.plan, channel="skillpay")
        other_account = replace(self.plan, account_alias="secondary")
        other_artifact = replace(self.plan, artifact=self.other_artifact)

        self.assertFalse(
            can_execute_remote_action(
                self.plan,
                "upload",
                authorizations=(Authorization(kind="upload", digest=upload_digest(other_channel)),),
            )
        )
        self.assertFalse(
            can_execute_remote_action(
                self.plan,
                "upload",
                authorizations=(Authorization(kind="upload", digest=upload_digest(other_account)),),
            )
        )
        self.assertFalse(
            can_execute_remote_action(
                self.plan,
                "upload",
                authorizations=(Authorization(kind="upload", digest=upload_digest(other_artifact)),),
            )
        )

    def test_plan_and_artifact_channel_mismatch_fails_closed(self):
        mismatched = replace(self.plan, channel="skillpay")
        authorization = Authorization(kind="upload", digest=upload_digest(mismatched))

        self.assertFalse(can_execute_remote_action(mismatched, "upload", authorizations=(authorization,)))

    def test_unknown_remote_action_is_rejected(self):
        auth = Authorization(kind="upload", digest=upload_digest(self.plan))
        self.assertFalse(can_execute_remote_action(self.plan, "delete_remote_listing", authorizations=(auth,)))

    def test_broken_authorization_object_fails_closed(self):
        class BrokenAuthorization:
            @property
            def kind(self):
                raise RuntimeError("kind unavailable")

            @property
            def digest(self):
                raise ValueError("digest unavailable")

        auth = Authorization(kind="upload", digest=upload_digest(self.plan))
        self.assertFalse(can_execute_remote_action(self.plan, "prefill", authorizations=(BrokenAuthorization(), auth)))

    def test_broken_authorization_iterable_fails_closed(self):
        class BrokenIterable:
            def __iter__(self):
                raise RuntimeError("iterator failed")

        self.assertFalse(can_execute_remote_action(self.plan, "prefill", authorizations=BrokenIterable()))

    def test_keyboard_interrupt_from_authorization_is_not_swallowed(self):
        class InterruptingAuthorization:
            @property
            def kind(self):
                raise KeyboardInterrupt()

            @property
            def digest(self):
                return "ignored"

        with self.assertRaises(KeyboardInterrupt):
            can_execute_remote_action(self.plan, "prefill", authorizations=(InterruptingAuthorization(),))

    def test_system_exit_from_authorization_is_not_swallowed(self):
        class ExitingAuthorization:
            @property
            def kind(self):
                return "upload"

            @property
            def digest(self):
                raise SystemExit()

        with self.assertRaises(SystemExit):
            can_execute_remote_action(self.plan, "prefill", authorizations=(ExitingAuthorization(),))


if __name__ == "__main__":
    unittest.main()
