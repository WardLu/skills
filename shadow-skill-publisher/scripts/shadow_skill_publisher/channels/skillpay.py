"""SkillPay channel contract and deterministic field rendering."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping

from ..adapters import BaseChannelAdapter, ChannelContractError, ChannelPolicyError
from ..confirmations import upload_digest
from ..models import Artifact, ChannelStaging, Dossier, SourceSnapshot, SubmissionPlan

_MANUAL_STATES = ("parse", "safety_review", "product_review", "live")


class SkillPayAdapter(BaseChannelAdapter):
    key = "skillpay"
    contract_version = "2026-09-03"
    official_source_urls = ("https://skillpay.alipay.com/",)
    required_fields = (
        "title",
        "description",
        "license",
        "permissions",
        "data_handling",
        "risk_summary",
        "commercial_mode",
        "cny_price",
        "creator_account_alias",
    )
    optional_fields = ("package_digest",)
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {}
    public_verification_signals = (
        "the uploaded package is parsed as the intended Skill product",
        "a recorded SkillPay safety review result for the same draft",
        "a recorded SkillPay product review result for the same draft",
        "the live product card shows the same title, mode, and CNY price",
    )
    manual_fallback = (
        "Pause automation and compare the active SkillPay creator flow with the documented contract at https://skillpay.alipay.com/ before any upload.",
        "If creator identity, required agreements, supported CNY price format, or the current form contract cannot be verified, record channel_contract_unverified and keep the attempt blocked before upload.",
    )

    def build_staging(self, snapshot: SourceSnapshot, dossier: Dossier) -> ChannelStaging:
        staging = super().build_staging(snapshot, dossier)
        manual_fallback = (
            "SkillPay staging is prepared, but upload remains blocked until the creator account alias, required agreements, supported CNY price format, and current form contract are re-verified in the live flow.",
            "Do not treat parse, safety review, product review, or live visibility as interchangeable evidence.",
        )
        return replace(staging, manual_fallback=manual_fallback)

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan:
        self._ensure_upload_ready(staging, account_alias)
        plan = super().build_plan(staging, artifact, account_alias)
        fields = dict(plan.fields)
        fields["package_digest"] = artifact.sha256
        fields["creator_account_alias"] = staging.fields["creator_account_alias"]
        manual_fallback = (
            "In SkillPay, verify that creator alias `{0}` is the active publisher identity and compare the live form with https://skillpay.alipay.com/ before uploading `{1}`."
            .format(account_alias, Path(artifact.path).name),
            "After the manual path, record separate evidence for `{0}` on the same title, mode, and CNY price."
            .format(", ".join(_MANUAL_STATES)),
        )
        updated = replace(plan, fields=fields, manual_fallback=manual_fallback, upload_confirmation_digest="")
        return replace(updated, upload_confirmation_digest=upload_digest(updated))

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        facts = dossier.facts
        return {
            "title": self._display_title(snapshot.name),
            "description": snapshot.description,
            "license": self._license_label(snapshot, dossier),
            "permissions": self._render_value(facts.get("permissions", ())),
            "data_handling": self._render_value(facts.get("data_handling", ())),
            "risk_summary": self._render_value(facts.get("risks", ())),
            "commercial_mode": dossier.commercial_mode,
            "cny_price": "" if dossier.commercial_mode == "free" else str(dossier.price),
            "creator_account_alias": self._required_text_fact(dossier, "creator_account_alias"),
        }

    def build_disclosure(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        fields: Mapping[str, str],
    ) -> dict[str, object]:
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        disclosure["skillpay_contract_checks"] = {
            "creator_identity_verified": dossier.facts.get("creator_identity_verified") is True,
            "required_agreements_verified": dossier.facts.get("required_agreements_verified") is True,
            "price_format_verified": dossier.facts.get("price_format_verified") is True,
            "form_contract_verified": dossier.facts.get("form_contract_verified") is True,
        }
        return disclosure

    def _ensure_commercial_mode(self, dossier: Dossier) -> None:
        mode = str(dossier.commercial_mode)
        if mode == "per_run":
            raise ChannelPolicyError("per_run_p1_only", "per_run_p1_only", self.manual_fallback)
        if mode not in self.allowed_commercial_modes:
            raise ChannelPolicyError(
                "channel_policy_unsupported",
                "Commercial mode {0!r} is not supported for channel {1}.".format(dossier.commercial_mode, self.key),
                self.manual_fallback,
            )
        if mode == "one_time":
            confirmed = dossier.facts.get("author_confirmed", dossier.facts.get("commercial_confirmed"))
            if confirmed is not True or not str(dossier.price or "").strip():
                raise ChannelPolicyError("price_required", "price_required", self.manual_fallback)

    def _ensure_upload_ready(self, staging: ChannelStaging, account_alias: str) -> None:
        expected_alias = str(staging.fields.get("creator_account_alias", "")).strip()
        actual_alias = str(account_alias).strip()
        if not expected_alias or actual_alias != expected_alias:
            raise ChannelContractError(
                "channel_contract_unverified",
                "SkillPay creator identity must be re-verified before upload.",
                staging.manual_fallback,
            )
        checks = staging.disclosure.get("skillpay_contract_checks", {})
        if not isinstance(checks, Mapping):
            checks = {}
        for key in (
            "creator_identity_verified",
            "required_agreements_verified",
            "price_format_verified",
            "form_contract_verified",
        ):
            if checks.get(key) is not True:
                raise ChannelContractError(
                    "channel_contract_unverified",
                    "SkillPay upload must stay blocked until {0} is verified.".format(key),
                    staging.manual_fallback,
                )

    def _display_title(self, raw_name: str) -> str:
        slug = str(raw_name).strip().replace("_", "-")
        parts = [part for part in slug.split("-") if part]
        return " ".join(part[:1].upper() + part[1:] for part in parts) or str(raw_name).strip()

    def _license_label(self, snapshot: SourceSnapshot, dossier: Dossier) -> str:
        explicit = self._clean_text(dossier.facts.get("license"))
        if explicit and not self._looks_like_path(explicit, snapshot.license_path):
            return explicit
        for line in Path(snapshot.license_path).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                return text
        return explicit

    def _required_text_fact(self, dossier: Dossier, key: str) -> str:
        value = self._clean_text(dossier.facts.get(key))
        if value:
            return value
        raise ChannelContractError(
            "channel_contract_unverified",
            "SkillPay requires verified `{0}` metadata before deterministic staging can continue.".format(key),
            self.manual_fallback,
        )

    def _clean_text(self, value: object) -> str:
        return "" if value is None else str(value).strip()

    def _looks_like_path(self, value: str, license_path: Path) -> bool:
        path = str(license_path)
        return value == path or value.endswith("/LICENSE") or value == "LICENSE"


__all__ = ["SkillPayAdapter"]
