import contextlib
import io
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.public_repo_check import check_remote, check_repo, git_paths, scan_paths


class PublicRepoCheckTests(unittest.TestCase):
    def test_forbidden_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "docs" / "internal").mkdir(parents=True)
            (repo / "docs" / "internal" / "plan.md").write_text("private", encoding="utf-8")
            findings = scan_paths(repo, ["docs/internal/plan.md"], staged=False, config={})
        self.assertEqual(findings, ["docs/internal/plan.md: forbidden public-repository path"])

    def test_secret_in_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "config.js").write_text("const token = '" + "sk-proj-" + "123456789012345';", encoding="utf-8")
            findings = scan_paths(repo, ["config.js"], staged=False, config={})
        self.assertEqual(findings, ["config.js: possible secret or credential"])

    def test_binary_candidate_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "model.bin").write_bytes(b"\x00\x01private-looking-text")
            findings = scan_paths(repo, ["model.bin"], staged=False, config={})
        self.assertEqual(findings, [])

    def test_project_config_adds_forbidden_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "docs" / "plan.md").parent.mkdir(parents=True)
            (repo / "docs" / "plan.md").write_text("internal launch plan", encoding="utf-8")
            (repo / "docs" / "notes.md").write_text("confidential phrase", encoding="utf-8")
            findings = scan_paths(
                repo,
                ["docs/plan.md"],
                staged=False,
                config={
                    "forbidden_paths": [r"(^|/)plan\.md$"],
                },
            )
            term_findings = scan_paths(
                repo,
                ["docs/notes.md"],
                staged=False,
                config={"forbidden_terms": [r"confidential phrase"]},
            )
        self.assertEqual(
            findings,
            ["docs/plan.md: forbidden public-repository path"],
        )
        self.assertEqual(term_findings, ["docs/notes.md: possible secret or credential"])

    def test_changed_since_returns_only_incremental_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-b", "main")
            self._git(repo, "config", "user.email", "test@example.com")
            self._git(repo, "config", "user.name", "Public Repo Gate Test")
            (repo / "base.txt").write_text("base", encoding="utf-8")
            self._git(repo, "add", "base.txt")
            self._git(repo, "commit", "-m", "base")
            (repo / "incremental.txt").write_text("incremental", encoding="utf-8")
            self._git(repo, "add", "incremental.txt")
            self._git(repo, "commit", "-m", "incremental")

            paths = git_paths(repo, staged=False, changed_since="HEAD^")

        self.assertEqual(paths, ["incremental.txt"])

    def test_remote_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-b", "main")
            self._git(repo, "remote", "add", "origin", "https://demo:placeholder@example.com/repo.git")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                findings = check_remote(repo)

        self.assertEqual(
            findings,
            ["remote origin: URL contains embedded credentials"],
        )

    def test_protected_branch_requires_feature_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-b", "main")
            findings = check_repo(
                repo,
                staged=False,
                changed_since=None,
                require_feature_branch=True,
                check_remote_flag=False,
                config={},
            )

        self.assertEqual(findings, ["current branch main is protected; use a feature branch and PR"])

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
