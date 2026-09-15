"""Coze Skill Store contract based on the documented import and listing flow."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Artifact, ChannelStaging, Dossier, PublishState, SourceSnapshot, SubmissionPlan


class CozeSkillStoreAdapter(BaseChannelAdapter):
    key = "coze-skill-store"
    contract_version = "2026-09-12"
    official_source_urls = (
        "https://docs.coze.cn/guides_vibe_coding_skill",
        "https://docs.coze.cn/cozespace_create_skill",
        "https://docs.coze.cn/guides_skill_faq",
        "https://space.coze.cn/skills",
    )
    required_fields = (
        "project_name",
        "project_description",
        "skill_name",
        "version",
        "summary",
        "description",
        "category",
        "open_source",
        "commercial_mode",
        "pricing_strategy",
        "package_format",
    )
    optional_fields = (
        "preferred_cny_price",
        "case_links",
        "case_names",
        "case_image_roles",
        "cover_asset_role",
    )
    field_limits = {"project_name": 50, "skill_name": 20, "summary": 200}
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {
        "解析中": PublishState.PARSING,
        "部署成功": PublishState.UPLOADED,
        "审核中": PublishState.UNDER_REVIEW,
        "审核通过": PublishState.APPROVED,
        "审核未通过": PublishState.REJECTED,
        "已上架": PublishState.LIVE,
        "已下架": PublishState.DELISTED,
    }
    public_verification_signals = (
        "the imported package resolves to the intended Skill project",
        "the Skill project reports deployment success",
        "the listing review references the same Skill and version",
        "the public Skill Store detail page is installable",
    )
    manual_fallback = (
        "Import the exact .zip or .skill package from the Coze Coding home Skill tab; stop if parsing or security checks rewrite the package unexpectedly.",
        "After deployment, open https://space.coze.cn/skills, choose My Skills > Created by me, and stop before listing submission if the qualification, cover, category, three public cases, pricing tier, or developer agreement cannot be read back.",
    )

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        facts = dossier.facts
        name = str(facts.get("coze_display_name") or snapshot.name).strip()
        summary = str(facts.get("coze_summary") or facts.get("description_zh") or snapshot.description).strip()
        description = str(facts.get("coze_description") or facts.get("description_zh") or snapshot.description).strip()
        project_name = str(facts.get("coze_project_name") or name).strip()
        project_description = str(facts.get("coze_project_description") or description).strip()
        category = self._required_fact(facts, "coze_category")
        open_source = facts.get("coze_open_source")
        if open_source not in (True, False):
            raise ChannelContractError(
                "channel_contract_unverified",
                "Coze listing requires an explicit coze_open_source decision.",
                self.manual_fallback,
            )
        preferred_price = "" if dossier.price is None else str(dossier.price)
        pricing_strategy = "free"
        if dossier.commercial_mode == "one_time":
            pricing_strategy = "prefer_exact_then_lowest_available_tier"
        cases = self._cases(facts)
        return {
            "project_name": project_name,
            "project_description": project_description,
            "skill_name": name,
            "version": snapshot.version,
            "summary": summary,
            "description": description,
            "category": category,
            "open_source": "yes" if open_source else "no",
            "commercial_mode": dossier.commercial_mode,
            "pricing_strategy": pricing_strategy,
            "package_format": Path(snapshot.root).name + ".zip",
            "preferred_cny_price": preferred_price,
            "case_links": "\n".join(case["link"] for case in cases),
            "case_names": "\n".join(case["name"] for case in cases),
            "case_image_roles": "\n".join(case["image_role"] for case in cases),
            "cover_asset_role": "cover" if "cover" in facts.get("listing_assets", {}) else "",
        }

    def build_disclosure(self, snapshot, dossier, fields):
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        assets = dossier.facts.get("listing_assets", {})
        asset_roles = frozenset(str(role) for role in assets) if isinstance(assets, Mapping) else frozenset()
        case_links = tuple(value for value in fields["case_links"].splitlines() if value)
        case_names = tuple(value for value in fields["case_names"].splitlines() if value)
        case_image_roles = tuple(value for value in fields["case_image_roles"].splitlines() if value)
        disclosure["coze_contract_checks"] = {
            "listing_qualification_verified": dossier.facts.get("coze_listing_qualification_verified") is True,
            "payment_account_verified": dossier.facts.get("coze_payment_verified") is True,
            "three_public_cases_ready": (
                len(case_links) == len(case_names) == len(case_image_roles) == 3
                and all(value.startswith("https://") for value in case_links)
                and all(role in asset_roles for role in case_image_roles)
            ),
            "cover_ready": fields["cover_asset_role"] == "cover",
        }
        return disclosure

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan:
        checks = staging.disclosure.get("coze_contract_checks", {})
        required = (
            "listing_qualification_verified",
            "three_public_cases_ready",
            "cover_ready",
        )
        if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required):
            raise ChannelContractError(
                "channel_contract_unverified",
                "Coze listing submission requires verified qualification, a cover, and exactly three public cases with verified names and images.",
                self.manual_fallback,
            )
        links = tuple(value.strip() for value in staging.fields["case_links"].splitlines() if value.strip())
        if len(links) != 3 or any(not value.startswith("https://") for value in links):
            raise ChannelContractError(
                "channel_contract_unverified",
                "Coze public case links must contain exactly three HTTPS URLs.",
                self.manual_fallback,
            )
        return super().build_plan(staging, artifact, account_alias)

    def _cases(self, facts) -> tuple[dict[str, str], ...]:
        raw = facts.get("coze_cases", ())
        if not isinstance(raw, (list, tuple)):
            raise ChannelContractError("channel_contract_unverified", "coze_cases must be an array", self.manual_fallback)
        cases = []
        for index, value in enumerate(raw):
            if not isinstance(value, Mapping):
                raise ChannelContractError("channel_contract_unverified", "each coze_cases entry must be a mapping", self.manual_fallback)
            case = {
                "link": str(value.get("link", "")).strip(),
                "name": str(value.get("name", "")).strip(),
                "image_role": str(value.get("image_role", "")).strip(),
            }
            if any(not item for item in case.values()):
                raise ChannelContractError(
                    "channel_contract_unverified",
                    "coze_cases[{0}] requires link, name, and image_role".format(index),
                    self.manual_fallback,
                )
            cases.append(case)
        return tuple(cases)

    def _required_fact(self, facts, key: str) -> str:
        value = str(facts.get(key, "")).strip()
        if not value:
            raise ChannelContractError(
                "channel_contract_unverified",
                "Coze requires verified `{0}` metadata before deterministic staging can continue.".format(key),
                self.manual_fallback,
            )
        return value


__all__ = ["CozeSkillStoreAdapter"]
