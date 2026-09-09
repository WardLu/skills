"""Xiaohongshu Red Skill channel contract handling."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Artifact, ChannelStaging, Dossier, SourceSnapshot, SubmissionPlan

_DEFAULT_AGREEMENT_ID = "ZXXY20260518001"
_MANUAL_STATES = (
    "upload_completed",
    "registration_acknowledged",
    "review_submitted",
    "approved",
    "install_prompt_resolved_to_target_version",
    "live",
)
_EXCLUDED_CAPABILITIES = (
    "note_content",
    "note_creation",
    "note_publishing",
    "note_to_skill_mounting",
)


class XiaohongshuRedSkillAdapter(BaseChannelAdapter):
    key = "xiaohongshu-red-skill"
    contract_version = "2026-09-03"
    official_source_urls = (
        "https://creator.xiaohongshu.com/",
        "https://www.xiaohongshu.com/",
    )
    required_fields = (
        "skill_identity",
        "skill_version",
        "functionality",
        "applicability",
        "dependencies",
        "required_permissions",
        "third_party_apis_models",
        "workflow_summary",
        "data_handling",
        "limitations",
        "risk_disclosure",
        "license",
        "agreement_id",
        "rights_declaration",
    )
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {}
    public_verification_signals = (
        "creator-side upload completion for the intended Skill package",
        "creator-side registration acknowledgement for the uploaded Skill package",
        "review submission evidence for the same draft and target version",
        "approval evidence recorded separately from review submission",
        "an install prompt that resolves to the target Skill version",
        "a live Red Skill listing that matches the same identity, version, and rights declaration",
    )
    manual_fallback = (
        "Pause automation and compare the live Xiaohongshu Red Skill creator flow with the recorded Task 13 contract before any upload, review submission, or publish action.",
        "If the visible agreement, required Skill fields, or install prompt behavior drift, record channel_contract_unverified and finish the attempt manually without expanding into note creation, note publishing, or note-to-Skill mounting.",
    )

    def build_staging(self, snapshot: SourceSnapshot, dossier: Dossier) -> ChannelStaging:
        staging = super().build_staging(snapshot, dossier)
        agreement_id = str(staging.fields["agreement_id"])
        manual_fallback = (
            "Red Skill staging is prepared, but the live creator flow must still match agreement `{0}` and keep upload completion, Skill registration acknowledgement, review submission, approval, install-prompt resolution, and live visibility as separate evidence."
            .format(agreement_id),
            "Do not add note content, create or publish notes, or mount note content into a Skill while completing this channel.",
        )
        return replace(staging, manual_fallback=manual_fallback)

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan:
        plan = super().build_plan(staging, artifact, account_alias)
        target_version = staging.fields["skill_version"]
        manual_fallback = (
            "In the Xiaohongshu creator flow, sign in with `{0}` and upload `{1}` as the Red Skill package. Confirm the platform registers `{2}` at version `{3}` under agreement `{4}` before any review submission."
            .format(
                account_alias,
                Path(artifact.path).name,
                staging.fields["skill_identity"],
                target_version,
                staging.fields["agreement_id"],
            ),
            "After the manual path, record separate evidence for `{0}`. Upload completion does not prove registration acknowledgement. An install prompt counts only when it resolves to target version `{1}`; note creation, note publishing, and note-to-Skill mounting stay out of scope."
            .format(", ".join(_MANUAL_STATES), target_version),
        )
        return replace(plan, manual_fallback=manual_fallback)

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        facts = dossier.facts
        agreement_id = self._agreement_id(dossier)
        return {
            "skill_identity": snapshot.name,
            "skill_version": snapshot.version,
            "functionality": snapshot.description,
            "applicability": self._render_value(
                facts.get("applicability", "Use this Skill when the packaged functionality matches the target task.")
            ),
            "dependencies": self._render_value(facts.get("dependencies", facts.get("external_services", ()))),
            "required_permissions": self._render_value(facts.get("permissions", ())),
            "third_party_apis_models": self._render_value(
                facts.get("third_party_apis_models", facts.get("external_services", ()))
            ),
            "workflow_summary": self._workflow_summary(snapshot.version),
            "data_handling": self._render_value(facts.get("data_handling", ())),
            "limitations": self._render_value(facts.get("limitations", ())),
            "risk_disclosure": self._render_value(facts.get("risks", ())),
            "license": self._license_label(snapshot, dossier),
            "agreement_id": agreement_id,
            "rights_declaration": self._rights_declaration(snapshot.name, agreement_id),
        }

    def build_disclosure(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        fields: Mapping[str, str],
    ) -> dict[str, object]:
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        agreement_id = str(fields["agreement_id"])
        disclosure["red_skill_contract"] = {
            "agreement_id": agreement_id,
            "default_agreement_id": _DEFAULT_AGREEMENT_ID,
            "requires_new_confirmation_on_agreement_change": True,
            "install_prompt_requires_target_version": True,
            "evidence_states": _MANUAL_STATES,
            "excluded_capabilities": _EXCLUDED_CAPABILITIES,
        }
        return disclosure

    def _agreement_id(self, dossier: Dossier) -> str:
        raw = dossier.facts.get("xiaohongshu_red_skill_agreement_id", _DEFAULT_AGREEMENT_ID)
        text = "" if raw is None else str(raw).strip()
        if text:
            return text
        raise ChannelContractError(
            "channel_contract_unverified",
            "Xiaohongshu Red Skill requires a verified agreement identifier before deterministic staging can continue.",
            self.manual_fallback,
        )

    def _workflow_summary(self, target_version: str) -> str:
        return (
            "Upload and register the Skill package, submit the same draft for review, wait for approval, "
            "generate an install prompt that resolves to version {0}, and only then verify the live listing."
        ).format(target_version)

    def _rights_declaration(self, skill_identity: str, agreement_id: str) -> str:
        return (
            "Publisher confirms it owns or is authorized to distribute `{0}` and its bundled assets under agreement `{1}`."
        ).format(skill_identity, agreement_id)

    def _license_label(self, snapshot: SourceSnapshot, dossier: Dossier) -> str:
        explicit = self._clean_text(dossier.facts.get("license"))
        if explicit and not self._looks_like_path(explicit, snapshot.license_path):
            return explicit
        for line in Path(snapshot.license_path).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                return text
        return explicit

    def _clean_text(self, value: object) -> str:
        return "" if value is None else str(value).strip()

    def _looks_like_path(self, value: str, license_path: Path) -> bool:
        path = str(license_path)
        return value == path or value.endswith("/LICENSE") or value == "LICENSE"


__all__ = ["XiaohongshuRedSkillAdapter"]
