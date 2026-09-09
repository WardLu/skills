import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.archive import build_artifact, verify_artifact
from shadow_skill_publisher.models import Artifact, SourceSnapshot


class ArchiveTests(unittest.TestCase):
    def _snapshot(self, root: Path) -> SourceSnapshot:
        root.mkdir(parents=True)
        (root / "SKILL.md").write_bytes(b"---\nname: demo-skill\ndescription: Demo\nversion: 1.2.3\n---\n")
        (root / "LICENSE").write_bytes(b"MIT\n")
        (root / "scripts").mkdir()
        (root / "scripts" / "run.py").write_bytes(b"print('ok')\n")
        return SourceSnapshot(
            root=root, name="demo-skill", description="Demo", version="1.2.3",
            source_digest="a" * 64, files=("LICENSE", "SKILL.md", "scripts/run.py"),
            license_path=root / "LICENSE", kind="scripted", skill_md_text="",
            git_commit=None, git_branch=None, git_dirty=False, untracked_files=(),
        )

    def test_same_input_produces_same_archive_digest_and_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            staging = {"SKILL.md": (snapshot.root / "SKILL.md").read_bytes(), "README.md": b"excluded"}
            first = build_artifact(snapshot, "skillpay", staging, base / "a")
            second = build_artifact(snapshot, "skillpay", staging, base / "b")
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.files, second.files)
            self.assertEqual(first.files, ("LICENSE", "SKILL.md", "scripts/run.py"))
            self.assertEqual(verify_artifact(first, first.files), ())

    def test_generic_runtime_allowlist_applies_exclusions_before_directory_allow(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            extra = {
                "scripts/private/key.txt": b"not runtime\n",
                "scripts/tests/test_tool.py": b"not runtime\n",
                "references/README.zh-CN.md": b"not runtime\n",
                "references/guide.md": b"runtime guide\n",
            }
            for relative, payload in extra.items():
                path = snapshot.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            snapshot = SourceSnapshot(
                **{**snapshot.__dict__, "files": snapshot.files + tuple(sorted(extra))}
            )

            artifact = build_artifact(snapshot, "skillpay", {}, base / "out")

        self.assertIn("references/guide.md", artifact.files)
        self.assertNotIn("scripts/private/key.txt", artifact.files)
        self.assertNotIn("scripts/tests/test_tool.py", artifact.files)
        self.assertNotIn("references/README.zh-CN.md", artifact.files)

    def test_workbuddy_staging_package_path_survives_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            staging = {
                "demo-skill/SKILL.md": b"---\nname: demo-skill\n---\n",
                "demo-skill/references/guide.md": b"Nested guide\n",
            }
            artifact = build_artifact(snapshot, "workbuddy", staging, base / "out")
            with zipfile.ZipFile(artifact.path) as archive:
                names = tuple(archive.namelist())
            self.assertEqual(
                tuple(sorted(names)),
                (
                    "LICENSE",
                    "demo-skill/SKILL.md",
                    "demo-skill/references/guide.md",
                ),
            )
            self.assertIn("demo-skill/SKILL.md", names)
            self.assertIn("demo-skill/references/guide.md", names)
            self.assertEqual(verify_artifact(artifact, artifact.files), ())

    def test_workbuddy_rejects_other_skill_package_name(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            with self.assertRaisesRegex(ValueError, "workbuddy_package_path_invalid"):
                build_artifact(snapshot, "workbuddy", {"skills/other-skill/SKILL.md": b"bad"}, base / "out")

    def test_workbuddy_rejects_nested_non_runtime_members(self):
        rejected = (
            "README.md", "CHANGELOG.md", "RELEASE_NOTES.md", "tests/test.py",
            ".hidden/file.txt", "private/file.txt", "docs/guide.md", "references/.hidden",
            "scripts/private/file.py", "scripts/internal/file.py", "references/tests/test.md",
            "scripts/__pycache__/file.py", "references/README.rst", "assets/CHANGELOG.txt",
            "references/README.zh-CN.md", "references/CHANGELOG.v2.md", "assets/RELEASE_NOTES-2026.md",
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            for relative in rejected:
                with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, "workbuddy_package_path_invalid"):
                    build_artifact(snapshot, "workbuddy", {f"demo-skill/{relative}": b"bad"}, base / "out")

    def test_symlink_and_parent_member_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.txt", b"bad")
                link = zipfile.ZipInfo("linked")
                link.external_attr = (0o120777 << 16)
                archive.writestr(link, b"target")
            artifact = Artifact("workbuddy", path, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, ())
            findings = verify_artifact(artifact, expected_files=())
            codes = {finding.code for finding in findings}
            self.assertIn("archive_path_escape", codes)
            self.assertIn("archive_symlink", codes)

    def test_license_mismatch_and_manifest_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            with self.assertRaisesRegex(ValueError, "license_mismatch"):
                build_artifact(snapshot, "skillpay", {"LICENSE": b"wrong"}, base / "out")
            artifact = build_artifact(snapshot, "skillpay", {}, base / "out")
            artifact.path.with_name(artifact.path.name + ".manifest.json").write_text("{}", encoding="utf-8")
            self.assertIn("artifact_manifest_mismatch", {f.code for f in verify_artifact(artifact, artifact.files)})

    def test_non_utf8_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("SKILL.md", b"\xff\xfe")
            artifact = Artifact("workbuddy", path, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, ("SKILL.md",))
            self.assertIn("archive_invalid_utf8", {f.code for f in verify_artifact(artifact, artifact.files)})

    def test_stored_compression_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stored.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("SKILL.md", b"valid")
            artifact = Artifact("workbuddy", path, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, ("SKILL.md",))
            self.assertIn("archive_compression_unsupported", {f.code for f in verify_artifact(artifact, artifact.files)})

    def test_manifest_size_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            artifact = build_artifact(snapshot, "skillpay", {}, base / "out")
            manifest_path = artifact.path.with_name(artifact.path.name + ".manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["size_bytes"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertIn("artifact_manifest_mismatch", {f.code for f in verify_artifact(artifact, artifact.files)})

    def test_source_symlink_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            target = base / "outside.py"
            target.write_bytes(b"outside")
            linked = snapshot.root / "scripts" / "linked.py"
            linked.symlink_to(target)
            symlink_snapshot = SourceSnapshot(**{**snapshot.__dict__, "files": snapshot.files + ("scripts/linked.py",)})
            with self.assertRaisesRegex(ValueError, "invalid_source_member"):
                build_artifact(symlink_snapshot, "skillpay", {}, base / "out")

    def test_source_intermediate_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = self._snapshot(base / "source")
            outside = base / "outside"
            outside.mkdir()
            (outside / "run.py").write_bytes(b"outside")
            scripts = snapshot.root / "scripts"
            scripts.rename(snapshot.root / "scripts-real")
            scripts.symlink_to(outside, target_is_directory=True)
            symlink_snapshot = SourceSnapshot(**{**snapshot.__dict__, "files": ("LICENSE", "SKILL.md", "scripts/run.py")})
            with self.assertRaisesRegex(ValueError, "invalid_source_member"):
                build_artifact(symlink_snapshot, "skillpay", {}, base / "out")


if __name__ == "__main__":
    unittest.main()
