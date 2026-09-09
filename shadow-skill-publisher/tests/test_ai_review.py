import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.ai_review import AIReviewError, load_ai_review, persist_ai_review
from shadow_skill_publisher.models import AIReview, Finding, GateSeverity
from shadow_skill_publisher.source import load_source


class AIReviewTests(unittest.TestCase):
    def test_load_ai_review_accepts_schema_version_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "ambiguous_capability_claim",
                                "severity": "warn",
                                "message": "Needs stronger evidence.",
                                "path": "SKILL.md",
                                "claim": "automatic publishing",
                                "provenance": "ai_inference",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            review = load_ai_review(review_path, snapshot)

        self.assertEqual(review.schema_version, 1)
        self.assertEqual(review.source_digest, snapshot.source_digest)
        self.assertEqual(review.findings[0].severity, GateSeverity.WARN)

    def test_ai_review_must_match_source_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": "0" * 64,
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "source_digest_mismatch"):
                load_ai_review(review_path, snapshot)

    def test_unknown_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            review_path.write_text(
                json.dumps({"schema_version": 2, "source_digest": snapshot.source_digest, "findings": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "unsupported_schema_version"):
                load_ai_review(review_path, snapshot)

    def test_invalid_severity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "wrong",
                                "severity": "pass",
                                "message": "Nope",
                                "provenance": "deterministic",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "invalid_severity"):
                load_ai_review(review_path, snapshot)

    def test_invalid_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "wrong",
                                "severity": "warn",
                                "message": "Nope",
                                "provenance": "deterministic",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "invalid_provenance"):
                load_ai_review(review_path, snapshot)

    def test_private_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            private_path = "/" + "Users" + "/example-user/private/file.md"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "private-path",
                                "severity": "warn",
                                "message": "Leaked path",
                                "path": private_path,
                                "provenance": "ai_inference",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "private_absolute_path"):
                load_ai_review(review_path, snapshot)

    def test_private_paths_embedded_in_message_and_claim_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            unix_path = "/" + "home" + "/example-user/private.md"
            windows_path = "C:/" + "Users/Example/skill.md"
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "private-message",
                                "severity": "warn",
                                "message": f"See {unix_path} for details.",
                                "claim": f"Generated from {windows_path}",
                                "provenance": "ai_inference",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "private_absolute_path"):
                load_ai_review(review_path, snapshot)

    def test_oversized_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            review_path = Path(temp_dir) / "ai-review.json"
            large_message = "x" * (70 * 1024)
            review_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_digest": snapshot.source_digest,
                        "findings": [
                            {
                                "code": "oversized",
                                "severity": "warn",
                                "message": large_message,
                                "provenance": "ai_inference",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AIReviewError, "review_too_large"):
                load_ai_review(review_path, snapshot)

    def test_persist_ai_review_redacts_sensitive_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            private_path = "/" + "Users" + "/example-user/private.md"
            review = AIReview(
                schema_version=1,
                source_digest="1" * 64,
                findings=(
                    Finding(
                        code="ambiguous",
                        severity=GateSeverity.WARN,
                        message="token=" + "gh" + "p_" + "12345678901234567890",
                        path="SKILL.md",
                        claim=private_path,
                        provenance="ai_inference",
                    ),
                ),
            )

            persisted = persist_ai_review(review, Path(temp_dir) / "runs" / "run-01")
            saved = json.loads(persisted.read_text(encoding="utf-8"))

        self.assertEqual(persisted.name, "ai-review.json")
        self.assertEqual(persisted.parent.name, "reviews")
        self.assertEqual(saved["schema_version"], 1)
        self.assertNotIn("gh" + "p_", json.dumps(saved))
        self.assertNotIn(private_path, json.dumps(saved))


def _make_snapshot(base_dir: Path):
    root = base_dir / "skill"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\n"
        "name: ai-review-skill\n"
        "description: Synthetic fixture.\n"
        "version: 1.0.0\n"
        "---\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("Synthetic license.\n", encoding="utf-8")
    return load_source(root)


if __name__ == "__main__":
    unittest.main()
