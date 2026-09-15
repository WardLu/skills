"""Coze Skill Store contract based on the documented import and listing flow."""

from __future__ import annotations

from pathlib import Path

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Dossier, PublishState, SourceSnapshot


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
        case_links = facts.get("coze_case_links", ())
        if isinstance(case_links, (str, bytes)):
            case_links = (str(case_links),)
        if not isinstance(case_links, (list, tuple)):
            raise ChannelContractError("channel_contract_unverified", "coze_case_links must be an array", self.manual_fallback)
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
            "case_links": "\n".join(str(value).strip() for value in case_links if str(value).strip()),
            "cover_asset_role": "cover" if "cover" in facts.get("listing_assets", {}) else "",
        }

    def build_disclosure(self, snapshot, dossier, fields):
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        disclosure["coze_contract_checks"] = {
            "listing_qualification_verified": dossier.facts.get("coze_listing_qualification_verified") is True,
            "payment_account_verified": dossier.facts.get("coze_payment_verified") is True,
            "three_public_cases_ready": len(tuple(value for value in fields["case_links"].splitlines() if value)) == 3,
            "cover_ready": fields["cover_asset_role"] == "cover",
        }
        return disclosure

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
