import dataclasses
import importlib
import shutil
import subprocess
import sys
import tempfile
from unittest import mock
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.models import SourceSnapshot
from shadow_skill_publisher.source import SourceContractError, load_source


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "source-contract"


class SourceContractTests(unittest.TestCase):
    def test_snapshot_declares_expected_fields(self):
        names = tuple(field.name for field in dataclasses.fields(SourceSnapshot))
        self.assertEqual(
            names,
            (
                "root",
                "name",
                "description",
                "version",
                "source_digest",
                "files",
                "license_path",
                "kind",
                "skill_md_text",
                "git_commit",
                "git_branch",
                "git_dirty",
                "untracked_files",
            ),
        )

    def test_prompt_only_skill_loads(self):
        snapshot = load_source(FIXTURES / "prompt-valid")
        self.assertEqual(snapshot.root, (FIXTURES / "prompt-valid").resolve())
        self.assertEqual(snapshot.name, "prompt-only-skill")
        self.assertEqual(snapshot.description, "Synthetic prompt-only fixture.")
        self.assertEqual(snapshot.version, "0.4.0")
        self.assertEqual(snapshot.kind, "prompt")
        self.assertEqual(snapshot.files, ("LICENSE", "SKILL.md"))
        self.assertEqual(snapshot.license_path, (FIXTURES / "prompt-valid" / "LICENSE").resolve())
        self.assertIn("name: prompt-only-skill", snapshot.skill_md_text)

    def test_version_file_precedes_matching_frontmatter(self):
        snapshot = load_source(FIXTURES / "scripted-valid")
        self.assertEqual(snapshot.version, "1.2.3")
        self.assertEqual(snapshot.kind, "scripted")

    def test_missing_skill_md_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "missing_skill_md"):
            load_source(FIXTURES / "missing-skill-md")

    def test_invalid_yaml_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "invalid_frontmatter"):
            load_source(FIXTURES / "invalid-yaml")

    def test_invalid_name_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "invalid_name"):
            load_source(FIXTURES / "invalid-name")

    def test_missing_description_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "missing_description"):
            load_source(FIXTURES / "missing-description")

    def test_missing_version_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "missing_version"):
            load_source(FIXTURES / "missing-version")

    def test_conflicting_versions_block(self):
        with self.assertRaisesRegex(SourceContractError, "version_conflict"):
            load_source(FIXTURES / "version-conflict")

    def test_inherited_repository_license_is_accepted(self):
        snapshot = load_source(FIXTURES / "repo-license-parent" / "inherited-license")
        self.assertEqual(snapshot.files, ("SKILL.md",))
        self.assertEqual(snapshot.version, "2.0.0")
        self.assertEqual(
            snapshot.license_path,
            (FIXTURES / "repo-license-parent" / "LICENSE").resolve(),
        )
        self.assertEqual(snapshot.kind, "prompt")

    def test_spdx_license_metadata_resolves_real_root_license_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "spdx-skill"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: spdx-skill\ndescription: SPDX fixture.\nversion: 1.0.0\nlicense: MIT\n---\n",
                encoding="utf-8",
            )
            (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")

            snapshot = load_source(root)

        self.assertEqual(snapshot.license_path, (root / "LICENSE").resolve())

    def test_explicit_license_path_must_be_real_and_in_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "path-skill"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: path-skill\ndescription: License path fixture.\nversion: 1.0.0\nlicense: legal/NOTICE.txt\n---\n",
                encoding="utf-8",
            )
            (root / "legal").mkdir()
            (root / "legal" / "NOTICE.txt").write_text("Synthetic terms.\n", encoding="utf-8")

            snapshot = load_source(root)

        self.assertEqual(snapshot.license_path, (root / "legal" / "NOTICE.txt").resolve())

    def test_missing_license_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "missing_license"):
            load_source(FIXTURES / "missing-license")

    def test_out_of_root_symlink_blocks(self):
        with self.assertRaisesRegex(SourceContractError, "resource_outside_root"):
            load_source(FIXTURES / "external-symlink")

    def test_git_facts_are_frozen_with_the_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "git-source"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\n"
                "name: git-source-skill\n"
                "description: Synthetic git-backed fixture.\n"
                "version: 3.4.5\n"
                "---\n\n"
                "# Git Fixture\n",
                encoding="utf-8",
            )
            (root / "LICENSE").write_text("Synthetic license text.\n", encoding="utf-8")

            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Fixture Bot"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "SKILL.md", "LICENSE"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, capture_output=True, text=True)
            expected_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (root / "notes.txt").write_text("scratch\n", encoding="utf-8")

            snapshot = load_source(root)

        self.assertEqual(snapshot.git_commit, expected_commit)
        self.assertEqual(snapshot.git_branch, "main")
        self.assertTrue(snapshot.git_dirty)
        self.assertEqual(snapshot.untracked_files, ("notes.txt",))

    def test_nested_skill_in_git_repo_scopes_dirty_and_untracked_to_source_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            skill_root = repo_root / "skills" / "nested-skill"
            other_dir = repo_root / "docs"
            skill_root.mkdir(parents=True)
            other_dir.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "---\n"
                "name: nested-skill\n"
                "description: Nested git fixture.\n"
                "version: 5.6.7\n"
                "---\n",
                encoding="utf-8",
            )
            (skill_root / "LICENSE").write_text("Synthetic license text.\n", encoding="utf-8")
            (other_dir / "guide.md").write_text("outside source root\n", encoding="utf-8")

            subprocess.run(["git", "init", "-b", "main"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Fixture Bot"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo_root, check=True, capture_output=True, text=True)
            expected_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            (other_dir / "guide.md").write_text("changed outside source root\n", encoding="utf-8")
            (repo_root / "notes.txt").write_text("repo level scratch\n", encoding="utf-8")
            (skill_root / "draft.md").write_text("skill scoped scratch\n", encoding="utf-8")

            snapshot = load_source(skill_root)

        self.assertEqual(snapshot.git_commit, expected_commit)
        self.assertEqual(snapshot.git_branch, "main")
        self.assertTrue(snapshot.git_dirty)
        self.assertEqual(snapshot.untracked_files, ("draft.md",))

    def test_non_git_source_has_explicit_empty_git_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "prompt-valid"
            shutil.copytree(FIXTURES / "prompt-valid", root)
            snapshot = load_source(root)
        self.assertIsNone(snapshot.git_commit)
        self.assertIsNone(snapshot.git_branch)
        self.assertFalse(snapshot.git_dirty)
        self.assertEqual(snapshot.untracked_files, ())

    def test_missing_pyyaml_returns_structured_error(self):
        module_name = "shadow_skill_publisher.source"
        original_module = sys.modules.pop(module_name, None)
        original_yaml = sys.modules.pop("yaml", None)

        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "yaml":
                raise ModuleNotFoundError("No module named 'yaml'")
            return real_import(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", side_effect=fake_import):
                reloaded = importlib.import_module(module_name)
            with self.assertRaises(reloaded.SourceContractError) as ctx:
                reloaded.load_source(FIXTURES / "prompt-valid")
        finally:
            sys.modules.pop(module_name, None)
            if original_yaml is not None:
                sys.modules["yaml"] = original_yaml
            if original_module is not None:
                sys.modules[module_name] = original_module

        self.assertEqual(ctx.exception.code, "missing_dependency")
        self.assertIn("PyYAML>=6.0,<7", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
