"""LovStudio channel contract and deterministic field rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Dossier, PublishState, SourceSnapshot


class LovStudioAdapter(BaseChannelAdapter):
    key = "lovstudio"
    contract_version = "2026-09-03"
    official_source_urls = (
        "https://lovstudio.ai/skills",
        "https://github.com/lovstudio/cli",
    )
    required_fields = (
        "name",
        "title",
        "concise_description",
        "version",
        "license",
        "source_url",
        "support_url",
        "install_command",
        "permissions",
        "risks",
        "limitations",
    )
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {
        "not published yet": PublishState.DRAFT,
        "published": PublishState.LIVE,
        "ready to install": PublishState.LIVE,
    }
    public_verification_signals = (
        "public skill detail page",
        "current version label",
        "install command for the same skill slug",
        "source link on the detail page",
    )
    manual_fallback = (
        "Open the public LovStudio detail page for the target skill and compare the visible version, install command, and source link.",
        "If any required field is missing or points to a different skill, record channel_contract_unverified and finish the submission manually.",
    )

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        facts = dossier.facts
        source_url = self._source_url(snapshot, dossier)
        support_url = self._clean_text(facts.get("support_url")) or source_url
        semantic = self._semantic_fields(snapshot, dossier)
        semantic.update(
            {
                "name": snapshot.name,
                "title": self._display_title(snapshot.name),
                "concise_description": snapshot.description,
                "version": snapshot.version,
                "license": self._license_label(snapshot, dossier),
                "source_url": source_url,
                "support_url": support_url,
                "install_command": "npx -y lovstudio@latest skills add {0}".format(snapshot.name),
                "permissions": self._render_value(facts.get("permissions", ())),
                "risks": self._render_value(facts.get("risks", ())),
                "limitations": self._render_value(facts.get("limitations", ())),
            }
        )
        return {str(key): semantic[key] for key in self.required_fields}

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

    def _source_url(self, snapshot: SourceSnapshot, dossier: Dossier) -> str:
        direct = self._clean_text(dossier.facts.get("source_url"))
        if direct:
            return direct
        provenance = dossier.facts.get("provenance", ())
        if isinstance(provenance, Mapping):
            provenance = (provenance,)
        if isinstance(provenance, (tuple, list)):
            for record in provenance:
                if not isinstance(record, Mapping):
                    continue
                for key in ("source_url", "url", "repo_url", "repository_url"):
                    candidate = self._clean_text(record.get(key))
                    if candidate:
                        return candidate
        raise ChannelContractError(
            "channel_contract_unverified",
            "LovStudio requires an observed public source URL before deterministic staging can continue.",
            self.manual_fallback,
        )

    def _clean_text(self, value: object) -> str:
        return "" if value is None else str(value).strip()

    def _looks_like_path(self, value: str, license_path: Path) -> bool:
        path = str(license_path)
        return value == path or value.endswith("/LICENSE") or value == "LICENSE"


__all__ = ["LovStudioAdapter"]
