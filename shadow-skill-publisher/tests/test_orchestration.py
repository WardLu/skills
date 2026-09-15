import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda text: {
    line.partition(":")[0].strip(): line.partition(":")[2].strip()
    for line in text.splitlines() if line.strip() and not line.strip().startswith("#") and ":" in line
}, YAMLError=ValueError))

from test_cli import make_home, make_skill, run_cli, source_profile
from shadow_skill_publisher.adapters import ChannelPolicyError
from shadow_skill_publisher.channels.workbuddy import WorkBuddyAdapter
from shadow_skill_publisher.dossier import build_dossier
from shadow_skill_publisher.models import GateReport
from shadow_skill_publisher.source import load_source
from shadow_skill_publisher.profile_builder import apply_source_defaults


class OrchestrationTests(unittest.TestCase):
    def test_batch_prepares_entries_and_refreshes_human_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = make_skill(root / "skill")
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(source_profile(skill)), encoding="utf-8")
            home = root / "publisher-home"
            manifest = root / "batch.json"
            manifest.write_text(json.dumps({"entries": [{
                "source": str(skill), "channels": ["workbuddy"], "profile": str(profile_path)
            }]}), encoding="utf-8")
            (root / "yaml.py").write_text(
                "class YAMLError(ValueError): pass\n"
                "def safe_load(text):\n"
                " return {line.partition(':')[0].strip(): line.partition(':')[2].strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#') and ':' in line}\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"PYTHONPATH": str(root)}):
                result = run_cli(["batch", str(manifest), "--home", str(home), "--json"])

            self.assertEqual(result.exit_code, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["batch_id"].startswith("batch-"))
            self.assertEqual(len(payload["confirmation_scope"]["attempts"]), 1)
            scope = payload["confirmation_scope"]["attempts"][0]
            ledger_md = home / "state" / "publishing-ledger.md"
            self.assertIn("Skill publishing ledger", ledger_md.read_text(encoding="utf-8"))

            resumed = run_cli(["resume", "--home", str(home), "--source", str(skill), "--json"])
            self.assertEqual(resumed.exit_code, 0, resumed.stderr or resumed.stdout)
            continuation = json.loads(resumed.stdout)["attempts"][0]["continuation"]
            self.assertEqual(continuation["next_action"], "confirm_upload")
            self.assertEqual(continuation["channel"], "workbuddy")

            authorized = run_cli([
                "authorize-batch", payload["batch_id"], "--home", str(home), "--kind", "upload", "--json",
            ])
            self.assertEqual(authorized.exit_code, 0, authorized.stderr or authorized.stdout)
            observations = root / "observations.json"
            observations.write_text(json.dumps([{
                "run_id": scope["run_id"], "channel": "workbuddy",
                "event": "upload_completed", "raw_status": "上传完成",
            }]), encoding="utf-8")
            monitored = run_cli(["monitor", str(observations), "--home", str(home), "--json"])
            self.assertEqual(monitored.exit_code, 0, monitored.stderr or monitored.stdout)
            self.assertTrue(json.loads(monitored.stdout)["notification_required"])
            repeated = run_cli(["monitor", str(observations), "--home", str(home), "--json"])
            self.assertEqual(repeated.exit_code, 0, repeated.stderr or repeated.stdout)
            self.assertFalse(json.loads(repeated.stdout)["notification_required"])

    def test_batch_id_changes_when_confirmation_digest_changes(self):
        from shadow_skill_publisher.cli import _batch_id

        first = _batch_id([{"run_id": "one", "upload_confirmation_digest": "paid"}])
        second = _batch_id([{"run_id": "one", "upload_confirmation_digest": "free"}])
        self.assertNotEqual(first, second)

    def test_business_policy_reuses_confirmed_default_price(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill = make_skill(Path(temp_dir) / "skill")
            snapshot = load_source(skill)
            profile = source_profile(skill)
            profile.pop("commercial")
            profile["business_policy"] = {
                "default_mode": "one_time", "default_price": "0.01", "currency": "CNY", "confirmed": True
            }
            profile = apply_source_defaults(profile, snapshot)
            dossier = build_dossier(snapshot, GateReport(True, ()), profile)
            self.assertEqual(dossier.commercial_mode, "one_time")
            self.assertEqual(dossier.price, "0.01")

    def test_listing_asset_digest_is_verified_before_staging(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = make_skill(root / "skill")
            snapshot = load_source(skill)
            profile = source_profile(skill)
            profile["listing_assets"] = {"avatar": {"path": str(root / "avatar.png"), "sha256": "wrong"}}
            (root / "avatar.png").write_bytes(b"not-empty")
            dossier = build_dossier(snapshot, GateReport(True, ()), profile)
            dossier = __import__("dataclasses").replace(dossier, facts={**dossier.facts, **profile})
            with self.assertRaises(ChannelPolicyError) as caught:
                WorkBuddyAdapter().build_staging(snapshot, dossier)
            self.assertEqual(caught.exception.code, "listing_asset_digest_mismatch")


if __name__ == "__main__":
    unittest.main()
