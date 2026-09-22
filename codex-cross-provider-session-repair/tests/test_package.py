import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SKILL_ROOT / "scripts" / "package.py"


class PackageTests(unittest.TestCase):
    def _build(self, output: Path) -> Path:
        subprocess.check_call(
            [sys.executable, str(PACKAGE), "--output", str(output)],
            stdout=subprocess.DEVNULL,
        )
        return output / "codex-cross-provider-session-repair.skill"

    def test_archive_includes_scripts_and_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = self._build(Path(temp))
            with zipfile.ZipFile(archive) as handle:
                names = handle.namelist()
        self.assertIn("codex-cross-provider-session-repair/SKILL.md", names)
        self.assertIn("codex-cross-provider-session-repair/scripts/compaction_shim.py", names)
        self.assertIn(
            "codex-cross-provider-session-repair/scripts/repair_session_offline.py", names
        )
        self.assertIn("codex-cross-provider-session-repair/VERSION", names)
        self.assertFalse([name for name in names if name.endswith(".skill")])

    def test_in_tree_output_does_not_nest_the_previous_archive(self):
        output = SKILL_ROOT / "dist"
        try:
            first = self._build(output)
            first_size = first.stat().st_size
            second = self._build(output)
            second_size = second.stat().st_size
            with zipfile.ZipFile(second) as handle:
                names = handle.namelist()
            self.assertFalse([name for name in names if name.endswith(".skill")])
            self.assertFalse([name for name in names if "/dist/" in name])
        finally:
            for leftover in output.glob("*"):
                leftover.unlink()
            if output.exists() and not any(output.iterdir()):
                output.rmdir()
        self.assertLess(abs(second_size - first_size), first_size * 0.25)

    def test_excludes_evals_pycache_and_ds_store(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = self._build(Path(temp))
            with zipfile.ZipFile(archive) as handle:
                names = handle.namelist()
        self.assertFalse([name for name in names if "/evals/" in name])
        self.assertFalse([name for name in names if "__pycache__" in name])
        self.assertFalse([name for name in names if name.endswith(".DS_Store")])


if __name__ == "__main__":
    unittest.main()
