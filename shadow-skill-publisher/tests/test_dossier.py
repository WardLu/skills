import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.dossier import (
    DossierError,
    apply_channel_edits,
    build_dossier,
    merge_channel_edits,
    render_dossier_json,
    render_dossier_markdown,
)
from shadow_skill_publisher.models import GateReport, SourceSnapshot


def _snapshot(root: Path, digest: str = "a" * 64) -> SourceSnapshot:
    license_path = root / "LICENSE"
    license_path.write_text("MIT", encoding="utf-8")
    return SourceSnapshot(root, "demo-skill", "A synthetic skill.", "1.0.0", digest, ("SKILL.md", "LICENSE"), license_path, "prompt", "---\nname: demo-skill\n---", None, None, False, ())


class DossierTests(unittest.TestCase):
    def test_every_public_claim_has_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            dossier = build_dossier(_snapshot(Path(directory)), GateReport(True, ()), {"claims": [{"id": "scan", "text": "Scans files", "evidence_ids": ["scan:source"]}], "provenance": [{"id": "scan:source", "type": "source"}]})
        self.assertTrue(all(claim.evidence_ids for claim in dossier.claims))

    def test_profile_claim_without_evidence_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = _snapshot(Path(directory))
            with self.assertRaisesRegex(DossierError, "requires evidence_ids"):
                build_dossier(snapshot, GateReport(True, ()), {"claims": [{"text": "Used by one million users"}]})

    def test_unknown_evidence_id_is_rejected_and_identity_claim_stays_source_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = _snapshot(Path(directory))
            with self.assertRaisesRegex(DossierError, "unknown evidence ID"):
                build_dossier(snapshot, GateReport(True, ()), {"claims": [{"text": "bad", "evidence_ids": ["missing"]}]})
            dossier = build_dossier(snapshot, GateReport(True, ()), {})
        record = dossier.facts["provenance"][0]
        self.assertEqual(record["id"], "source:" + snapshot.source_digest)
        self.assertEqual(dossier.claims[0].claim_id, "identity")
        self.assertEqual(dossier.claims[0].evidence_ids, (record["id"],))
        self.assertIn(record["id"], render_dossier_json(dossier))

    def test_default_license_fact_does_not_expose_absolute_source_path(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = _snapshot(Path(directory))
            dossier = build_dossier(snapshot, GateReport(True, ()), {})
            rendered = json.loads(render_dossier_json(dossier))

        self.assertEqual(rendered["license"], "MIT")
        self.assertNotIn(str(snapshot.license_path), render_dossier_json(dossier))

    def test_human_channel_copy_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            dossier = build_dossier(_snapshot(source), GateReport(True, ()), {})
            frozen = merge_channel_edits(dossier, {"title": "Human title"}, prior=None)
            changed = build_dossier(_snapshot(source, "b" * 64), GateReport(True, ()), {})
            regenerated = merge_channel_edits(changed, {}, prior=frozen)
        self.assertEqual(regenerated.values["title"], "Human title")
        self.assertNotIn("title", regenerated.drifted_fields)
        self.assertIn("source_digest", regenerated.drifted_fields)
        self.assertNotIn("__dossier_facts_digest", regenerated.values)

    def test_channel_edits_reapply_only_safe_copy_and_report_fact_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            dossier = build_dossier(_snapshot(source), GateReport(True, ()), {})
            fields, frozen = apply_channel_edits(
                dossier,
                {"description": "Generated description", "version": "1.0.0"},
                {"description": "Human description"},
            )
            changed = build_dossier(_snapshot(source, "b" * 64), GateReport(True, ()), {})
            regenerated, updated = apply_channel_edits(
                changed,
                {"description": "Changed generated description", "version": "1.0.0"},
                {},
                prior=frozen,
            )

        self.assertEqual(fields["description"], "Human description")
        self.assertEqual(regenerated["description"], "Human description")
        self.assertEqual(updated.values, {"description": "Human description"})
        self.assertIn("source_digest", updated.drifted_fields)
        self.assertNotIn("source_digest", updated.values)

    def test_channel_edit_drift_clears_when_generated_facts_stabilize(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            initial = build_dossier(_snapshot(source), GateReport(True, ()), {})
            _, frozen = apply_channel_edits(
                initial,
                {"description": "Generated description"},
                {"description": "Human description"},
            )
            changed = build_dossier(_snapshot(source, "b" * 64), GateReport(True, ()), {})
            _, drifted = apply_channel_edits(
                changed,
                {"description": "Changed generated description"},
                {},
                prior=frozen,
            )
            _, stabilized = apply_channel_edits(
                changed,
                {"description": "Changed generated description"},
                {},
                prior=drifted,
            )

        self.assertIn("source_digest", drifted.drifted_fields)
        self.assertEqual(stabilized.drifted_fields, ())
        self.assertEqual(stabilized.values, {"description": "Human description"})
        self.assertEqual(stabilized.generated_facts, drifted.generated_facts)

    def test_channel_edits_reject_generated_identity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            dossier = build_dossier(_snapshot(Path(directory)), GateReport(True, ()), {})
            with self.assertRaisesRegex(DossierError, "not editable"):
                apply_channel_edits(
                    dossier,
                    {"description": "Generated description", "version": "1.0.0"},
                    {"version": "not allowed"},
                )

    def test_channel_edits_reject_values_changed_by_deterministic_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            dossier = build_dossier(_snapshot(Path(directory)), GateReport(True, ()), {})
            sensitive_copy = "Support notes: /Users/private-author/drafts; token=" + "ghp_" + "12345678901234567890"
            with self.assertRaisesRegex(DossierError, "sensitive") as error:
                apply_channel_edits(dossier, {"description": "Generated description"}, {"description": sensitive_copy})

        self.assertNotIn(sensitive_copy, str(error.exception))

    def test_per_run_is_rejected_and_one_time_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = _snapshot(Path(directory))
            with self.assertRaisesRegex(DossierError, "per_run"):
                build_dossier(snapshot, GateReport(True, ()), {"commercial_mode": "per_run"})
            with self.assertRaisesRegex(DossierError, "confirmation"):
                build_dossier(snapshot, GateReport(True, ()), {"commercial_mode": "one_time", "price": "$5"})
            dossier = build_dossier(snapshot, GateReport(True, ()), {"commercial_mode": "one_time", "price": "$5", "author_confirmed": True})
        self.assertEqual((dossier.commercial_mode, dossier.price), ("one_time", "$5"))

    def test_renderers_include_removed_optional_claims_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            dossier = build_dossier(_snapshot(Path(directory)), GateReport(True, (), ("optional",)), {"audience": "builders"})
        rendered = json.loads(render_dossier_json(dossier))
        self.assertEqual(rendered["removed_optional_claims"], ["optional"])
        self.assertEqual(rendered["audience"], "builders")
        self.assertIn("## Data Handling", render_dossier_markdown(dossier))

    def test_author_and_source_url_are_first_class_dossier_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            dossier = build_dossier(
                _snapshot(Path(directory)),
                GateReport(True, ()),
                {
                    "author": {
                        "display_name": "Example Author",
                        "source_url": "https://example.test/source",
                    }
                },
            )

        self.assertEqual(dossier.facts["author"], "Example Author")
        self.assertEqual(dossier.facts["source_url"], "https://example.test/source")
        rendered = json.loads(render_dossier_json(dossier))
        self.assertEqual(rendered["author"], "Example Author")
        self.assertEqual(rendered["source_url"], "https://example.test/source")


if __name__ == "__main__":
    unittest.main()
