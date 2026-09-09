import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.evidence import (
    EvidenceProfileError,
    ExecutionAuthorizationError,
    build_execution_plan,
    load_evidence,
    run_trusted_commands,
)
from shadow_skill_publisher.models import CommandEvidence, EvidenceBundle, EvidenceItem, Finding, GateSeverity
from shadow_skill_publisher.quality import run_quality
from shadow_skill_publisher.source import load_source


class QualityGateTests(unittest.TestCase):
    def test_load_evidence_reads_core_and_optional_capabilities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            profile = {
                "schema_version": 1,
                "capabilities": [
                    {
                        "id": "scan-staged-content",
                        "core": True,
                        "evidence": {"type": "command", "command": ["python3", "-m", "unittest"]},
                    },
                    {
                        "id": "optional-export",
                        "core": False,
                        "evidence": {
                            "type": "source",
                            "path": "SKILL.md",
                            "source_digest": snapshot.source_digest,
                            "summary": "Capability is documented in the frozen source snapshot.",
                        },
                    },
                ],
            }

            evidence = load_evidence(profile, snapshot)

        self.assertEqual(tuple(item.capability for item in evidence.core), ("scan-staged-content",))
        self.assertFalse(evidence.core[0].passed)
        self.assertEqual(evidence.core[0].provenance, "command")
        self.assertEqual(tuple(item.capability for item in evidence.optional), ("optional-export",))
        self.assertTrue(evidence.optional[0].passed)
        self.assertEqual(
            evidence.commands,
            (
                CommandEvidence(
                    command=("python3", "-m", "unittest"),
                    returncode=-1,
                    stdout="",
                    stderr="",
                ),
            ),
        )

    def test_core_source_evidence_without_proof_stays_not_evidenced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            evidence = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "validated-locally",
                            "core": True,
                            "evidence": {"type": "source"},
                        }
                    ],
                },
                snapshot,
            )

            report = run_quality(snapshot, evidence)

        self.assertFalse(evidence.core[0].passed)
        self.assertFalse(report.allowed)
        self.assertIn("core_not_evidenced", {finding.code for finding in report.findings})

    def test_non_command_evidence_requires_verifiable_proof(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            evidence = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "documented-core",
                            "core": True,
                            "evidence": {
                                "type": "source",
                                "path": "SKILL.md",
                                "source_digest": snapshot.source_digest,
                                "summary": "The workflow is described in SKILL.md.",
                            },
                        },
                        {
                            "id": "human-confirmed",
                            "core": True,
                            "evidence": {
                                "type": "user",
                                "summary": "Publisher observed the prepared draft in a local recording.",
                                "record_id": "note-123",
                            },
                        },
                        {
                            "id": "catalog-listed",
                            "core": False,
                            "evidence": {
                                "type": "official_page",
                                "summary": "Official listing page shows the same title and version.",
                                "source_url": "https://example.test/listing/demo-skill",
                            },
                        },
                    ],
                },
                snapshot,
            )

        self.assertTrue(all(item.passed for item in evidence.core))
        self.assertTrue(evidence.optional[0].passed)

    def test_user_and_official_page_evidence_without_auditable_reference_stays_not_evidenced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            evidence = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "human-confirmed",
                            "core": True,
                            "evidence": {"type": "user", "summary": " "},
                        },
                        {
                            "id": "catalog-listed",
                            "core": True,
                            "evidence": {
                                "type": "official_page",
                                "summary": "Listing exists.",
                            },
                        },
                    ],
                },
                snapshot,
            )

            report = run_quality(snapshot, evidence)

        self.assertFalse(evidence.core[0].passed)
        self.assertFalse(evidence.core[1].passed)
        self.assertFalse(report.allowed)
        self.assertIn("core_not_evidenced", {finding.code for finding in report.findings})

    def test_source_evidence_rejects_unsafe_paths_and_mismatched_snapshot_binding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))

            unsafe_path = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "validated-locally",
                            "core": True,
                            "evidence": {
                                "type": "source",
                                "path": "../secret.txt",
                                "source_digest": snapshot.source_digest,
                                "summary": "Bad path.",
                            },
                        }
                    ],
                },
                snapshot,
            )
            missing_file = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "validated-locally",
                            "core": True,
                            "evidence": {
                                "type": "source",
                                "path": "missing.md",
                                "source_digest": snapshot.source_digest,
                                "summary": "Missing file.",
                            },
                        }
                    ],
                },
                snapshot,
            )
            wrong_digest = load_evidence(
                {
                    "schema_version": 1,
                    "capabilities": [
                        {
                            "id": "validated-locally",
                            "core": True,
                            "evidence": {
                                "type": "source",
                                "path": "SKILL.md",
                                "source_digest": "b" * 64,
                                "summary": "Wrong digest.",
                            },
                        }
                    ],
                },
                snapshot,
            )

        self.assertFalse(unsafe_path.core[0].passed)
        self.assertFalse(missing_file.core[0].passed)
        self.assertFalse(wrong_digest.core[0].passed)

    def test_load_evidence_rejects_missing_or_invalid_command_declarations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))

            with self.assertRaisesRegex(EvidenceProfileError, "evidence.command must be a sequence"):
                load_evidence(
                    {
                        "schema_version": 1,
                        "capabilities": [
                            {
                                "id": "scan-staged-content",
                                "core": True,
                                "evidence": {"type": "command"},
                            }
                        ],
                    },
                    snapshot,
                )

            with self.assertRaisesRegex(EvidenceProfileError, "evidence.command must contain non-empty strings"):
                load_evidence(
                    {
                        "schema_version": 1,
                        "capabilities": [
                            {
                                "id": "scan-staged-content",
                                "core": True,
                                "evidence": {"type": "command", "command": ["python3", ""]},
                            }
                        ],
                    },
                    snapshot,
                )

    def test_missing_core_evidence_blocks_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))

            report = run_quality(snapshot, EvidenceBundle(core=(), optional=()))

        self.assertFalse(report.allowed)
        self.assertIn("core_not_evidenced", {finding.code for finding in report.findings})

    def test_optional_claim_is_removed_before_warning_allows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            evidence = EvidenceBundle(
                core=(
                    EvidenceItem(
                        evidence_id="scan-staged-content:command",
                        capability="scan-staged-content",
                        core=True,
                        passed=True,
                        provenance="command",
                    ),
                ),
                optional=(
                    EvidenceItem(
                        evidence_id="optional-export:source",
                        capability="optional-export",
                        core=False,
                        passed=False,
                        provenance="source",
                    ),
                ),
            )

            report = run_quality(snapshot, evidence, ai_findings=())

        self.assertTrue(report.allowed)
        self.assertEqual(report.removed_claims, ("optional-export",))
        self.assertIn("optional_claim_removed", {finding.code for finding in report.findings})

    def test_execution_digest_changes_with_source_or_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            snapshot = _make_snapshot(base_dir / "one")
            other_snapshot = _make_snapshot(base_dir / "two", skill_name="other-skill")
            commands = (("python3", "-V"),)
            other_commands = (("python3", "-c", "print('hi')"),)
            other_root = snapshot.root.parent
            first = build_execution_plan(snapshot, commands, snapshot.root, 60, ("PATH",))

            self.assertNotEqual(first.digest, build_execution_plan(other_snapshot, commands, snapshot.root, 60, ("PATH",)).digest)
            self.assertNotEqual(first.digest, build_execution_plan(snapshot, other_commands, snapshot.root, 60, ("PATH",)).digest)
            self.assertNotEqual(first.digest, build_execution_plan(snapshot, commands, other_root, 60, ("PATH",)).digest)
            self.assertNotEqual(first.digest, build_execution_plan(snapshot, commands, snapshot.root, 30, ("PATH",)).digest)
            self.assertNotEqual(first.digest, build_execution_plan(snapshot, commands, snapshot.root, 60, ("PATH", "LANG")).digest)

    def test_run_trusted_commands_requires_matching_digest_and_redacts_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            private_path = "/" + "Users" + "/example-user/private.txt"
            plan = build_execution_plan(
                snapshot,
                (
                    (
                        "python3",
                        "-c",
                        "print('token=' + 'gh' + 'p_' + '12345678901234567890'); print({0!r})".format(private_path),
                    ),
                ),
                snapshot.root,
                5,
                (),
            )

            with self.assertRaisesRegex(ExecutionAuthorizationError, "execution_digest_mismatch"):
                run_trusted_commands(plan, "0" * 64)

            evidence = run_trusted_commands(plan, plan.digest)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].returncode, 0)
        self.assertNotIn("gh" + "p_", evidence[0].stdout)
        self.assertNotIn(private_path, evidence[0].stdout)

    def test_run_trusted_commands_recomputes_digest_from_plan_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            plan = build_execution_plan(
                snapshot,
                (("python3", "-c", "print('ok')"),),
                snapshot.root,
                5,
                (),
            )
            tampered = dataclasses.replace(plan, commands=(("python3", "-c", "print('tampered')"),))

            with self.assertRaisesRegex(ExecutionAuthorizationError, "execution_digest_mismatch"):
                run_trusted_commands(tampered, plan.digest)

    def test_run_trusted_commands_captures_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            plan = build_execution_plan(
                snapshot,
                (("python3", "-c", "import time; time.sleep(2)"),),
                snapshot.root,
                1,
                (),
            )

            evidence = run_trusted_commands(plan, plan.digest)

        self.assertEqual(evidence[0].returncode, 124)
        self.assertIn("timed out", evidence[0].stderr)

    def test_quality_blocks_possible_secret_and_personal_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            private_path = "/" + "Users" + "/example-user/private/file.md"
            snapshot = _make_snapshot(
                Path(temp_dir),
                extra_files={
                    "notes.txt": "token=" + "gh" + "p_" + "12345678901234567890" + "\npath=" + private_path + "\n",
                },
            )
            evidence = _passing_core_evidence()

            report = run_quality(snapshot, evidence)

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.allowed)
        self.assertIn("possible_secret", codes)
        self.assertIn("personal_data", codes)

    def test_quality_blocks_private_key_headers_and_credential_urls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(
                Path(temp_dir),
                extra_files={
                    "secrets.txt": (
                        "db=postgres://" + "example-user:example-pass@db.example/app\n"
                        "key=-----BEGIN "
                        "PRIVATE KEY-----\n"
                        "abc\n"
                        "-----END "
                        "PRIVATE KEY-----\n"
                    ),
                },
            )

            report = run_quality(snapshot, _passing_core_evidence())

        self.assertFalse(report.allowed)
        self.assertIn("possible_secret", {finding.code for finding in report.findings})

    def test_quality_blocks_private_workspace_content_and_warns_for_binary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            private_file = snapshot.root / ".shadow-skill-publisher" / "report.bin"
            private_file.parent.mkdir()
            private_file.write_bytes(b"\x00\x01\x02")
            snapshot = dataclasses.replace(
                snapshot,
                files=snapshot.files + (".shadow-skill-publisher/report.bin",),
            )

            report = run_quality(snapshot, _passing_core_evidence())

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.allowed)
        self.assertIn("private_workspace_content", codes)
        self.assertIn("binary_file_present", codes)

    def test_quality_blocks_missing_or_out_of_scope_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            missing_license_report = run_quality(
                dataclasses.replace(snapshot, license_path=snapshot.root / "MISSING"),
                _passing_core_evidence(),
            )
            with tempfile.TemporaryDirectory() as other_dir:
                external_license = Path(other_dir) / "external-license.txt"
                external_license.write_text("external\n", encoding="utf-8")
                scope_report = run_quality(
                    dataclasses.replace(snapshot, license_path=external_license),
                    _passing_core_evidence(),
                )

        self.assertIn("license_missing", {finding.code for finding in missing_license_report.findings})
        self.assertIn("license_scope_unknown", {finding.code for finding in scope_report.findings})

    def test_quality_blocks_resource_outside_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            report = run_quality(
                dataclasses.replace(snapshot, files=snapshot.files + ("../secret.txt",)),
                _passing_core_evidence(),
            )

        self.assertFalse(report.allowed)
        self.assertIn("resource_outside_root", {finding.code for finding in report.findings})

    def test_quality_blocks_suspicious_commands_and_undisclosed_network_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = _make_snapshot(Path(temp_dir))
            evidence = EvidenceBundle(
                core=_passing_core_evidence().core,
                optional=(),
                commands=(
                    CommandEvidence(command=("rm", "-rf", "dist"), returncode=0, stdout="", stderr=""),
                    CommandEvidence(command=("curl", "https://example.test"), returncode=0, stdout="", stderr=""),
                ),
            )

            report = run_quality(snapshot, evidence)

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.allowed)
        self.assertIn("dangerous_write_undisclosed", codes)
        self.assertIn("network_access_undisclosed", codes)

    def test_ai_findings_cannot_override_deterministic_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            private_path = "/" + "Users" + "/example-user/private/file.md"
            snapshot = _make_snapshot(
                Path(temp_dir),
                extra_files={"notes.txt": "path=" + private_path + "\n"},
            )
            report = run_quality(
                snapshot,
                _passing_core_evidence(),
                ai_findings=(
                    Finding(
                        code="ambiguous_capability_claim",
                        severity=GateSeverity.WARN,
                        message="Needs more examples.",
                        path="SKILL.md",
                        provenance="ai_inference",
                    ),
                ),
            )

        self.assertFalse(report.allowed)
        codes = {finding.code for finding in report.findings}
        self.assertIn("personal_data", codes)
        self.assertIn("ambiguous_capability_claim", codes)


def _make_snapshot(base_dir: Path, skill_name: str = "quality-skill", extra_files=None):
    root = base_dir / "skill"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_name}\n"
        "description: Synthetic quality fixture.\n"
        "version: 1.0.0\n"
        "---\n"
        "\n"
        "# Fixture\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("Synthetic license.\n", encoding="utf-8")
    for relative, content in (extra_files or {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return load_source(root)


def _passing_core_evidence():
    return EvidenceBundle(
        core=(
            EvidenceItem(
                evidence_id="scan-staged-content:command",
                capability="scan-staged-content",
                core=True,
                passed=True,
                provenance="command",
            ),
        ),
        optional=(),
    )


if __name__ == "__main__":
    unittest.main()
