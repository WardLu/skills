import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.adapters import BaseChannelAdapter, ChannelContractError, ChannelPolicyError
from shadow_skill_publisher.archive import build_artifact, verify_artifact
from shadow_skill_publisher.channels import CHANNEL_KEYS, CHANNEL_REGISTRY, get_channel_adapter
from shadow_skill_publisher.channels.coze_skill_store import CozeSkillStoreAdapter
from shadow_skill_publisher.channels.skillpay import SkillPayAdapter
from shadow_skill_publisher.channels.workbuddy import WorkBuddyAdapter
from shadow_skill_publisher.channels.xiaohongshu_red_skill import XiaohongshuRedSkillAdapter
from shadow_skill_publisher.channels.zhihu_ai_works import ZhihuAiWorksAdapter
from shadow_skill_publisher.models import Artifact, ChannelStaging, Dossier, PublishState, SourceSnapshot


def _snapshot(root: Path, name: str = "demo-skill") -> SourceSnapshot:
    root.mkdir(parents=True)
    license_path = root / "LICENSE"
    license_path.write_text("MIT\n", encoding="utf-8")
    skill_md_text = (
        "---\n"
        "name: {0}\n"
        "description: Demo skill.\n"
        "display_name: Demo Skill\n"
        "version: 1.0.0\n"
        "---\n\n"
        "# Demo Skill\n\n"
        "When the user needs a demo, help with the request.\n"
    ).format(name)
    (root / "SKILL.md").write_text(skill_md_text, encoding="utf-8")
    return SourceSnapshot(
        root=root,
        name=name,
        description="Demo skill.",
        version="1.0.0",
        source_digest="a" * 64,
        files=("LICENSE", "SKILL.md"),
        license_path=license_path,
        kind="prompt",
        skill_md_text=skill_md_text,
        git_commit=None,
        git_branch=None,
        git_dirty=False,
        untracked_files=(),
    )


def _dossier(mode: str = "one_time", price: str = "19") -> Dossier:
    return Dossier(
        identity={"name": "demo-skill", "version": "1.0.0", "kind": "prompt"},
        claims=(),
        removed_claims=(),
        commercial_mode=mode,
        price=price,
        facts={
            "applicability": "Help users complete demo tasks with a packaged prompt Skill.",
            "dependencies": ("OpenAI account", "Python 3.11+"),
            "permissions": ("read:workspace",),
            "external_services": ("openai",),
            "third_party_apis_models": ("OpenAI Responses API", "gpt-5"),
            "data_handling": ("No remote writes.",),
            "risks": ("Human confirmation required.",),
            "limitations": ("Placeholder adapter.",),
            "license": "MIT",
            "support_url": "https://example.test/support",
            "description_zh": "简短中文介绍",
            "description_en": "A brief English introduction.",
            "examples_zh": ("请帮我完成一个演示任务。", "检查演示任务结果。", "总结这次演示。"),
            "examples_en": ("Complete a demo task.", "Check the demo result.", "Summarize the demo."),
            "author": "Example Partner",
            "author_confirmed": True,
            "allowed_tools": ("Bash", "Read"),
            "workbuddy_developer_profile_verified": True,
            "workbuddy_publication_mode": "public",
            "creator_account_alias": "skillpay-creator",
            "creator_identity_verified": True,
            "required_agreements_verified": True,
            "price_format_verified": True,
            "form_contract_verified": True,
            "xiaohongshu_red_skill_agreement_id": "ZXXY20260518001",
            "provenance": (
                {
                    "id": "catalog:github",
                    "type": "official_page",
                    "source_url": "https://github.com/example/demo-skill",
                },
            ),
        },
    )


def _dossier_with_fact(dossier: Dossier, **updates: object) -> Dossier:
    facts = dict(dossier.facts)
    facts.update(updates)
    return Dossier(
        identity=dossier.identity,
        claims=dossier.claims,
        removed_claims=dossier.removed_claims,
        commercial_mode=dossier.commercial_mode,
        price=dossier.price,
        facts=facts,
    )


class DemoAdapter(BaseChannelAdapter):
    key = "demo"
    contract_version = "2026-09-03"
    official_source_urls = ("https://example.test/docs",)
    required_fields = ("title", "summary", "commercial_mode")
    optional_fields = ("support_url",)
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {"draft ready": PublishState.DRAFT, "approved": PublishState.APPROVED}
    public_verification_signals = ("detail page", "public version", "install entry")


class DemoFilesAdapter(DemoAdapter):
    def render_files(self, snapshot: SourceSnapshot, dossier: Dossier):
        return {"channel.json": b"{\"channel\":\"demo\"}"}


def extract_body(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise AssertionError("missing frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[index + 1 :])
    raise AssertionError("unterminated frontmatter")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.snapshot = _snapshot(self.base / "source")
        self.dossier = _dossier()
        artifact_path = self.base / "artifact.zip"
        artifact_path.write_text("payload", encoding="utf-8")
        self.artifact = Artifact(
            channel="demo",
            path=artifact_path,
            sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            size_bytes=artifact_path.stat().st_size,
            files=("LICENSE", "SKILL.md"),
        )

    def test_build_plan_returns_unfinalized_submission_plan(self):
        adapter = DemoAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        self.assertIsInstance(staging, ChannelStaging)
        plan = adapter.build_plan(staging, self.artifact, "primary")
        self.assertEqual(plan.channel, "demo")
        self.assertTrue(plan.upload_confirmation_digest)
        self.assertIsNone(plan.platform_id)
        self.assertIsNone(plan.final_action)
        self.assertIsNone(plan.submission_confirmation_digest)

    def test_unsupported_commercial_mode_is_rejected(self):
        with self.assertRaises(ChannelPolicyError):
            DemoAdapter().build_staging(self.snapshot, _dossier(mode="per_run"))

    def test_contract_drift_raises_unverified_error_for_missing_or_unknown_fields(self):
        adapter = DemoAdapter()
        with self.assertRaises(ChannelContractError) as missing:
            adapter.ensure_contract_fields({"title": "Demo skill"})
        self.assertEqual(missing.exception.code, "channel_contract_unverified")
        self.assertTrue(missing.exception.manual_fallback)

        adapter.ensure_contract_fields(
            {
                "title": "Demo skill",
                "summary": "Demo",
                "commercial_mode": "one_time",
                "support_url": "https://example.test/support",
            }
        )

        with self.assertRaises(ChannelContractError) as unexpected:
            adapter.ensure_contract_fields(
                {"title": "Demo skill", "summary": "Demo", "commercial_mode": "one_time", "new_required": "value"}
            )
        self.assertEqual(unexpected.exception.code, "channel_contract_unverified")

    def test_build_staging_uses_render_files_hook(self):
        staging = DemoFilesAdapter().build_staging(self.snapshot, self.dossier)
        self.assertEqual(staging.files, {"channel.json": b"{\"channel\":\"demo\"}"})

    def test_coze_contract_binds_listing_fields_and_lowest_tier_fallback(self):
        dossier = _dossier_with_fact(
            self.dossier,
            coze_category="互联网",
            coze_open_source=True,
            coze_display_name="Codex使用诊断",
            coze_project_name="Ward的AI产品实战｜Codex Doctor Codex体验医生",
            coze_project_description="分析本地 Codex 会话并给出改进建议。",
            coze_summary="分析 Codex 使用效率并给出改进建议。",
            coze_description="读取本地遥测并生成隐私安全的效率报告。",
            coze_payment_verified=True,
            coze_listing_qualification_verified=False,
            coze_cases=(),
            listing_assets={},
        )
        staging = CozeSkillStoreAdapter().build_staging(self.snapshot, dossier)
        self.assertEqual(staging.fields["skill_name"], "Codex使用诊断")
        self.assertEqual(staging.fields["project_name"], "Ward的AI产品实战｜Codex Doctor Codex体验医生")
        self.assertEqual(staging.fields["preferred_cny_price"], "19")
        self.assertEqual(staging.fields["pricing_strategy"], "prefer_exact_then_lowest_available_tier")
        self.assertFalse(staging.disclosure["coze_contract_checks"]["three_public_cases_ready"])
        self.assertFalse(staging.disclosure["coze_contract_checks"]["listing_qualification_verified"])
        coze_artifact = Artifact(
            channel="coze-skill-store",
            path=self.artifact.path,
            sha256=self.artifact.sha256,
            size_bytes=self.artifact.size_bytes,
            files=self.artifact.files,
        )
        with self.assertRaises(ChannelContractError):
            CozeSkillStoreAdapter().build_plan(staging, coze_artifact, "coze-primary")

    def test_coze_plan_binds_three_named_cases_to_verified_image_receipts(self):
        assets = {}
        for role in ("cover", "case-1", "case-2", "case-3"):
            path = self.base / (role + ".png")
            path.write_bytes((role + " image").encode("utf-8"))
            assets[role] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        cases = tuple(
            {"link": "https://space.coze.cn/task/{0}".format(index), "name": "Case {0}".format(index), "image_role": "case-{0}".format(index)}
            for index in (1, 2, 3)
        )
        dossier = _dossier_with_fact(
            self.dossier,
            coze_category="互联网",
            coze_open_source=True,
            coze_listing_qualification_verified=True,
            coze_cases=cases,
            listing_assets=assets,
        )
        staging = CozeSkillStoreAdapter().build_staging(self.snapshot, dossier)
        self.assertTrue(staging.disclosure["coze_contract_checks"]["three_public_cases_ready"])
        self.assertEqual(
            {receipt["role"] for receipt in staging.disclosure["listing_asset_receipts"]},
            {"cover", "case-1", "case-2", "case-3"},
        )
        coze_artifact = Artifact(
            channel="coze-skill-store",
            path=self.artifact.path,
            sha256=self.artifact.sha256,
            size_bytes=self.artifact.size_bytes,
            files=self.artifact.files,
        )
        plan = CozeSkillStoreAdapter().build_plan(staging, coze_artifact, "coze-primary")
        self.assertIn("Case 1", plan.fields["case_names"])
        self.assertIn("case-1", plan.fields["case_image_roles"])

        duplicate_cases = tuple({**case, "image_role": "case-1"} for case in cases)
        duplicate_dossier = _dossier_with_fact(dossier, coze_cases=duplicate_cases)
        duplicate_staging = CozeSkillStoreAdapter().build_staging(self.snapshot, duplicate_dossier)
        self.assertFalse(duplicate_staging.disclosure["coze_contract_checks"]["three_public_cases_ready"])
        with self.assertRaises(ChannelContractError):
            CozeSkillStoreAdapter().build_plan(duplicate_staging, coze_artifact, "coze-primary")

    def test_workbuddy_injects_required_listing_metadata_without_changing_body(self):
        for relative, payload in {
            "references/api-spec.md": "# API\n",
            "scripts/tool.py": "print('demo')\n",
            "templates/report.sh": "echo demo\n",
        }.items():
            path = self.snapshot.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        self.snapshot = SourceSnapshot(
            **{
                **self.snapshot.__dict__,
                "files": ("LICENSE", "SKILL.md", "references/api-spec.md", "scripts/tool.py", "templates/report.sh"),
                "kind": "scripted",
            }
        )

        staging = WorkBuddyAdapter().build_staging(self.snapshot, self.dossier)
        self.assertIn("demo-skill/SKILL.md", staging.files)
        self.assertIn("demo-skill/_skillhub_meta.json", staging.files)
        market_meta = json.loads(staging.files["demo-skill/_skillhub_meta.json"].decode("utf-8"))
        self.assertEqual(market_meta["examples_zh"], ["请帮我完成一个演示任务。", "检查演示任务结果。", "总结这次演示。"])
        self.assertEqual(market_meta["examples_en"], ["Complete a demo task.", "Check the demo result.", "Summarize the demo."])
        staged = staging.files["demo-skill/SKILL.md"].decode("utf-8")
        self.assertIn("description_zh:", staged)
        self.assertIn("description_en:", staged)
        self.assertEqual(extract_body(staged), extract_body(self.snapshot.skill_md_text))
        self.assertIn("name: demo-skill\n", staged)
        self.assertIn("display_name: Demo Skill\n", staged)
        self.assertIn("display_name_en: Demo Skill\n", staged)
        self.assertIn("version: 1.0.0\n", staged)
        self.assertIn("author: Example Partner\n", staged)
        self.assertIn("allowed-tools: Bash, Read\n", staged)
        self.assertIn("description_zh: 简短中文介绍\n", staged)
        self.assertIn("description_en: A brief English introduction.\n", staged)
        self.assertIn("workbuddy-package-root: demo-skill\n", staged)
        self.assertIn("workbuddy-skill-path: demo-skill/SKILL.md\n", staged)
        self.assertIn("workbuddy-resource-directories: references, scripts, templates\n", staged)
        self.assertEqual(staging.fields["resource_directories"], "references, scripts, templates")
        self.assertEqual(staging.fields["publication_mode"], "public")
        self.assertTrue(staging.disclosure["workbuddy_publication_checks"]["developer_profile_verified"])

        artifact = build_artifact(self.snapshot, "workbuddy", staging.files, self.base / "workbuddy-artifact")
        self.assertEqual(
            artifact.files,
            (
                "demo-skill/LICENSE",
                "demo-skill/SKILL.md",
                "demo-skill/_skillhub_meta.json",
                "demo-skill/references/api-spec.md",
                "demo-skill/scripts/tool.py",
                "demo-skill/templates/report.sh",
            ),
        )
        self.assertEqual(verify_artifact(artifact, artifact.files), ())
        with zipfile.ZipFile(artifact.path) as archive:
            self.assertEqual(
                tuple(sorted(archive.namelist())),
                (
                    "demo-skill/LICENSE",
                    "demo-skill/SKILL.md",
                    "demo-skill/_skillhub_meta.json",
                    "demo-skill/references/api-spec.md",
                    "demo-skill/scripts/tool.py",
                    "demo-skill/templates/report.sh",
                ),
            )

    def test_workbuddy_manual_fallback_lists_exact_zip_account_fields_and_states(self):
        adapter = WorkBuddyAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "workbuddy-artifact")
        plan = adapter.build_plan(staging, artifact, "workbuddy-primary")

        self.assertEqual(plan.channel, "workbuddy")
        self.assertIn("demo-skill-1.0.0-workbuddy.zip", plan.manual_fallback[0])
        self.assertIn("workbuddy-primary", plan.manual_fallback[0])
        self.assertIn("demo-skill/SKILL.md", plan.manual_fallback[0])
        self.assertIn("workbuddy-package-root", plan.manual_fallback[0])
        self.assertIn("workbuddy-skill-path", plan.manual_fallback[0])
        self.assertIn("workbuddy-resource-directories", plan.manual_fallback[0])
        self.assertIn("description_zh", plan.manual_fallback[0])
        self.assertIn("description_en", plan.manual_fallback[0])
        self.assertIn("allowed-tools", plan.manual_fallback[0])
        self.assertIn("approved", plan.manual_fallback[1])
        self.assertIn("marketplace_visible", plan.manual_fallback[1])
        self.assertIn("installed_in_conversation", plan.manual_fallback[1])

    def test_skillpay_plan_binds_title_mode_price_digest_and_creator_alias(self):
        adapter = SkillPayAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "skillpay-artifact")
        plan = adapter.build_plan(staging, artifact, "skillpay-creator")

        self.assertEqual(plan.channel, "skillpay")
        self.assertEqual(plan.fields["title"], "Demo Skill")
        self.assertEqual(plan.fields["description"], self.snapshot.description)
        self.assertEqual(plan.fields["package_digest"], artifact.sha256)
        self.assertEqual(plan.fields["license"], "MIT")
        self.assertEqual(plan.fields["permissions"], "read:workspace")
        self.assertEqual(plan.fields["data_handling"], "No remote writes.")
        self.assertEqual(plan.fields["risk_summary"], "Human confirmation required.")
        self.assertEqual(plan.fields["commercial_mode"], "one_time")
        self.assertEqual(plan.fields["cny_price"], "19")
        self.assertEqual(plan.fields["creator_account_alias"], "skillpay-creator")
        self.assertIn("parse", plan.manual_fallback[1])
        self.assertIn("safety_review", plan.manual_fallback[1])
        self.assertIn("product_review", plan.manual_fallback[1])
        self.assertIn("live", plan.manual_fallback[1])

    def test_skillpay_preserves_exact_cny_price_text(self):
        adapter = SkillPayAdapter()
        dossier = Dossier(
            identity=self.dossier.identity,
            claims=self.dossier.claims,
            removed_claims=self.dossier.removed_claims,
            commercial_mode="one_time",
            price=" 19 ",
            facts=dict(self.dossier.facts),
        )
        staging = adapter.build_staging(self.snapshot, dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "skillpay-artifact-spaced")
        plan = adapter.build_plan(staging, artifact, "skillpay-creator")

        self.assertEqual(staging.fields["cny_price"], " 19 ")
        self.assertEqual(plan.fields["cny_price"], " 19 ")

    def test_skillpay_blocks_one_time_without_confirmed_price(self):
        adapter = SkillPayAdapter()
        dossier = Dossier(
            identity=self.dossier.identity,
            claims=self.dossier.claims,
            removed_claims=self.dossier.removed_claims,
            commercial_mode="one_time",
            price=None,
            facts=dict(self.dossier.facts),
        )
        with self.assertRaises(ChannelPolicyError) as error:
            adapter.build_staging(self.snapshot, dossier)
        self.assertEqual(error.exception.code, "price_required")
        self.assertEqual(error.exception.message, "price_required")

    def test_skillpay_blocks_one_time_without_author_confirmation(self):
        adapter = SkillPayAdapter()
        dossier = _dossier_with_fact(self.dossier, author_confirmed=False)
        with self.assertRaises(ChannelPolicyError) as error:
            adapter.build_staging(self.snapshot, dossier)
        self.assertEqual(error.exception.code, "price_required")
        self.assertEqual(error.exception.message, "price_required")

    def test_skillpay_blocks_per_run_in_p0(self):
        adapter = SkillPayAdapter()
        dossier = Dossier(
            identity=self.dossier.identity,
            claims=self.dossier.claims,
            removed_claims=self.dossier.removed_claims,
            commercial_mode="per_run",
            price="19",
            facts=dict(self.dossier.facts),
        )
        with self.assertRaises(ChannelPolicyError) as error:
            adapter.build_staging(self.snapshot, dossier)
        self.assertEqual(error.exception.code, "per_run_p1_only")
        self.assertEqual(error.exception.message, "per_run_p1_only")

    def test_skillpay_rejects_non_canonical_mode_values(self):
        adapter = SkillPayAdapter()
        for mode in ("One_Time", " free "):
            dossier = Dossier(
                identity=self.dossier.identity,
                claims=self.dossier.claims,
                removed_claims=self.dossier.removed_claims,
                commercial_mode=mode,
                price="19",
                facts=dict(self.dossier.facts),
            )
            with self.assertRaises(ChannelPolicyError) as error:
                adapter.build_staging(self.snapshot, dossier)
            self.assertEqual(error.exception.code, "channel_policy_unsupported")
            self.assertIn(repr(mode), error.exception.message)

    def test_skillpay_blocks_upload_when_creator_identity_or_form_contract_is_unverified(self):
        adapter = SkillPayAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "skillpay-artifact")

        with self.assertRaises(ChannelContractError) as identity_error:
            adapter.build_plan(staging, artifact, "other-account")
        self.assertEqual(identity_error.exception.code, "channel_contract_unverified")

        unverified_staging = adapter.build_staging(
            self.snapshot,
            _dossier_with_fact(self.dossier, form_contract_verified=False),
        )
        with self.assertRaises(ChannelContractError) as form_error:
            adapter.build_plan(unverified_staging, artifact, "skillpay-creator")
        self.assertEqual(form_error.exception.code, "channel_contract_unverified")

    def test_zhihu_blocks_when_required_field_contract_is_unverified(self):
        adapter = ZhihuAiWorksAdapter(contract=None)
        with self.assertRaises(ChannelContractError) as error:
            adapter.build_staging(self.snapshot, self.dossier)
        self.assertEqual(error.exception.code, "channel_contract_unverified")
        self.assertIn("project-square", "\n".join(error.exception.manual_fallback))

    def test_red_skill_plan_contains_rights_limits_and_risks(self):
        adapter = XiaohongshuRedSkillAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "red-skill-artifact")
        plan = adapter.build_plan(staging, artifact, "red-skill-primary")

        self.assertEqual(plan.channel, "xiaohongshu-red-skill")
        self.assertEqual(staging.fields["skill_identity"], "demo-skill")
        self.assertEqual(staging.fields["skill_version"], "1.0.0")
        self.assertEqual(staging.fields["agreement_id"], "ZXXY20260518001")
        self.assertIn("rights_declaration", staging.fields)
        self.assertIn("limitations", staging.fields)
        self.assertIn("risk_disclosure", staging.fields)
        self.assertNotIn("note_content", staging.fields)
        self.assertNotIn("note_creation", staging.fields)
        self.assertNotIn("note_publishing", staging.fields)
        self.assertNotIn("note_to_skill_mounting", staging.fields)
        self.assertNotIn("note", staging.fields["workflow_summary"].lower())
        self.assertEqual(staging.disclosure["red_skill_contract"]["agreement_id"], "ZXXY20260518001")
        self.assertIn("upload_completed", plan.manual_fallback[1])
        self.assertIn("registration_acknowledged", plan.manual_fallback[1])
        self.assertIn("review_submitted", plan.manual_fallback[1])
        self.assertIn("approved", plan.manual_fallback[1])
        self.assertIn("install_prompt_resolved_to_target_version", plan.manual_fallback[1])
        self.assertIn("live", plan.manual_fallback[1])
        self.assertIn("Upload completion does not prove registration acknowledgement.", plan.manual_fallback[1])
        self.assertEqual(
            staging.disclosure["red_skill_contract"]["evidence_states"],
            (
                "upload_completed",
                "registration_acknowledged",
                "review_submitted",
                "approved",
                "install_prompt_resolved_to_target_version",
                "live",
            ),
        )
        self.assertEqual(
            staging.disclosure["red_skill_contract"]["excluded_capabilities"],
            (
                "note_content",
                "note_creation",
                "note_publishing",
                "note_to_skill_mounting",
            ),
        )

    def test_red_skill_agreement_change_requires_new_confirmation_digest(self):
        adapter = XiaohongshuRedSkillAdapter()
        staging = adapter.build_staging(self.snapshot, self.dossier)
        artifact = build_artifact(self.snapshot, adapter.key, staging.files, self.base / "red-skill-artifact")
        baseline_plan = adapter.build_plan(staging, artifact, "red-skill-primary")

        changed_dossier = _dossier_with_fact(
            self.dossier,
            xiaohongshu_red_skill_agreement_id="ZXXY20260601002",
        )
        changed_staging = adapter.build_staging(self.snapshot, changed_dossier)
        changed_plan = adapter.build_plan(changed_staging, artifact, "red-skill-primary")

        self.assertEqual(changed_staging.fields["agreement_id"], "ZXXY20260601002")
        self.assertIn("ZXXY20260601002", changed_staging.fields["rights_declaration"])
        self.assertNotEqual(baseline_plan.upload_confirmation_digest, changed_plan.upload_confirmation_digest)

    def test_status_mapping_normalizes_whitespace_and_case(self):
        self.assertEqual(DemoAdapter().map_status("  Draft Ready  "), PublishState.DRAFT)
        self.assertEqual(DemoAdapter().map_status("approved"), PublishState.APPROVED)
        self.assertIsNone(DemoAdapter().map_status("unknown"))

    def test_registry_uses_explicit_cli_keys_and_replaces_verified_channel_placeholders_only(self):
        self.assertEqual(
            CHANNEL_KEYS,
            ("coze-skill-store", "workbuddy", "skillpay", "zhihu-ai-works", "xiaohongshu-red-skill"),
        )
        self.assertEqual(set(CHANNEL_REGISTRY), set(CHANNEL_KEYS))

        workbuddy = get_channel_adapter("workbuddy")
        self.assertIsInstance(workbuddy, WorkBuddyAdapter)
        self.assertEqual(workbuddy.key, "workbuddy")
        workbuddy_staging = workbuddy.build_staging(self.snapshot, self.dossier)
        self.assertIn("demo-skill/SKILL.md", workbuddy_staging.files)

        skillpay = get_channel_adapter("skillpay")
        self.assertIsInstance(skillpay, SkillPayAdapter)
        self.assertEqual(skillpay.key, "skillpay")
        skillpay_staging = skillpay.build_staging(self.snapshot, self.dossier)
        self.assertEqual(skillpay_staging.fields["commercial_mode"], "one_time")

        zhihu = get_channel_adapter("zhihu-ai-works")
        self.assertIsInstance(zhihu, ZhihuAiWorksAdapter)
        self.assertEqual(zhihu.key, "zhihu-ai-works")
        with self.assertRaises(ChannelContractError) as zhihu_error:
            zhihu.build_staging(self.snapshot, self.dossier)
        self.assertEqual(zhihu_error.exception.code, "channel_contract_unverified")

        red_skill = get_channel_adapter("xiaohongshu-red-skill")
        self.assertIsInstance(red_skill, XiaohongshuRedSkillAdapter)
        self.assertEqual(red_skill.key, "xiaohongshu-red-skill")
        red_skill_staging = red_skill.build_staging(self.snapshot, self.dossier)
        self.assertEqual(red_skill_staging.fields["agreement_id"], "ZXXY20260518001")


if __name__ == "__main__":
    unittest.main()
