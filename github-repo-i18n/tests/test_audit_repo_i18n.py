from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_repo_i18n import (  # noqa: E402
    _locale_neutral_path,
    audit_documents,
    audit_metadata,
    parse_document_specs,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class AuditRepoI18nTests(unittest.TestCase):
    def test_parse_accepts_arbitrary_locales(self) -> None:
        repo = FIXTURES / "en-ja"
        documents = parse_document_specs(
            ["en=README.md", "ja=README.ja.md", "zh-CN=README.zh-CN.md"],
            repo,
        )
        self.assertEqual([item.locale for item in documents], ["en", "ja", "zh-CN"])

    def test_parse_rejects_duplicate_locale(self) -> None:
        repo = FIXTURES / "en-ja"
        with self.assertRaises(ValueError):
            parse_document_specs(["en=README.md", "en=README.ja.md"], repo)

    def test_parse_rejects_duplicate_document_path(self) -> None:
        repo = FIXTURES / "en-ja"
        with self.assertRaises(ValueError):
            parse_document_specs(["en=README.md", "ja=README.md"], repo)

    def test_parse_rejects_path_outside_repository(self) -> None:
        repo = FIXTURES / "en-ja"
        with self.assertRaises(ValueError):
            parse_document_specs(["en=../README.md"], repo)

    def test_three_locale_documents_pass_structural_parity(self) -> None:
        repo = FIXTURES / "multi-locale"
        documents = parse_document_specs(
            ["en=README.md", "ja=README.ja.md", "fr=README.fr.md"],
            repo,
        )
        report = audit_documents(repo, documents, "en", True)
        self.assertTrue(report.ok)
        self.assertIn("manual semantic review", " ".join(report.manual_review).lower())

    def test_heading_and_code_fence_drift_is_reported(self) -> None:
        repo = FIXTURES / "structural-drift"
        documents = parse_document_specs(
            ["en=README.md", "ja=README.ja.md"],
            repo,
        )
        report = audit_documents(repo, documents, "en", False)
        codes = {issue.code for issue in report.issues}
        self.assertIn("heading-structure-mismatch", codes)
        self.assertIn("code-fence-mismatch", codes)

    def test_missing_and_mismatched_link_targets_are_reported(self) -> None:
        repo = FIXTURES / "link-drift"
        documents = parse_document_specs(
            ["en=README.md", "ja=README.ja.md"],
            repo,
        )
        report = audit_documents(repo, documents, "en", False)
        codes = {issue.code for issue in report.issues}
        self.assertIn("missing-local-target", codes)
        self.assertIn("content-link-mismatch", codes)

    def test_cross_family_locale_links_are_not_content_drift(self) -> None:
        # README.zh-CN.md -> RELEASE_NOTES.zh-CN.md is the same document family
        # as README.md -> RELEASE_NOTES.md, so it must not be reported.
        repo = FIXTURES / "cross-family-link"
        documents = parse_document_specs(
            ["en=README.md", "zh-CN=README.zh-CN.md"],
            repo,
        )
        report = audit_documents(repo, documents, "en", True)
        self.assertEqual([issue.code for issue in report.issues], [])
        self.assertTrue(report.ok)

    def test_cross_family_locale_link_drift_is_still_reported(self) -> None:
        # Linking a different family per locale must still fail.
        repo = FIXTURES / "cross-family-drift"
        documents = parse_document_specs(
            ["en=README.md", "zh-CN=README.zh-CN.md"],
            repo,
        )
        report = audit_documents(repo, documents, "en", False)
        codes = {issue.code for issue in report.issues}
        self.assertIn("content-link-mismatch", codes)

    def test_locale_neutral_path_requires_an_existing_sibling(self) -> None:
        repo = FIXTURES / "cross-family-link"
        self.assertEqual(
            _locale_neutral_path(repo / "RELEASE_NOTES.zh-CN.md").name,
            "RELEASE_NOTES.md",
        )
        # NOTES.md does not exist, so the locale-looking name is left alone.
        self.assertEqual(_locale_neutral_path(repo / "NOTES.ja.md").name, "NOTES.ja.md")
        # A name without a locale segment is returned unchanged.
        self.assertEqual(_locale_neutral_path(repo / "README.md").name, "README.md")

    def test_metadata_snapshot_passes(self) -> None:
        issues = audit_metadata(FIXTURES / "metadata-valid.json")
        self.assertEqual(issues, ())

    def test_metadata_snapshot_rejects_duplicate_and_invalid_topics(self) -> None:
        issues = audit_metadata(FIXTURES / "metadata-invalid.json")
        codes = {issue.code for issue in issues}
        self.assertIn("metadata-topics-duplicate", codes)
        self.assertIn("metadata-topic-invalid", codes)
        self.assertIn("metadata-description-multiline", codes)

    def test_metadata_fixture_is_valid_json(self) -> None:
        with (FIXTURES / "metadata-valid.json").open(encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["topics"], ["ai", "developer-tools", "documentation"])

    def test_fixture_images_have_png_signatures(self) -> None:
        images = sorted(FIXTURES.glob("*/assets/*.png"))
        self.assertEqual(len(images), 3)
        for image in images:
            self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", image)


if __name__ == "__main__":
    unittest.main()
