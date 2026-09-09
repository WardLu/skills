"""Zhihu AI Works channel contract handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Dossier, PublishState, SourceSnapshot

_DEFAULT_SOURCE_URLS = ("https://www.zhihu.com/project-square",)
_DEFAULT_MANUAL_FALLBACK = (
    "Open https://www.zhihu.com/project-square in a signed-in browser and stop at the current AI Works creation surface before any draft creation, upload, prefill, or submission.",
    "Record the exact visible required labels, accepted artifact type, title or description length limits, and separate signals for draft, submission, review, and public page visibility. If any item cannot be observed, keep channel_contract_unverified.",
)


@dataclass(frozen=True)
class ZhihuObservedField:
    """A visible Zhihu field label bound to a semantic dossier value."""

    semantic_key: str
    label: str
    evidence: str


@dataclass(frozen=True)
class ZhihuAiWorksContract:
    """Versioned read-only contract captured from the Zhihu creator flow."""

    version: str
    required_fields: tuple[ZhihuObservedField, ...]
    optional_fields: tuple[ZhihuObservedField, ...] = ()
    official_source_urls: tuple[str, ...] = _DEFAULT_SOURCE_URLS
    allowed_commercial_modes: tuple[str, ...] = ("free", "one_time")
    status_mappings: Mapping[str, PublishState] = field(default_factory=dict)
    public_verification_signals: tuple[str, ...] = ()
    manual_fallback: tuple[str, ...] = _DEFAULT_MANUAL_FALLBACK


class ZhihuAiWorksAdapter(BaseChannelAdapter):
    key = "zhihu-ai-works"

    def __init__(self, contract: Optional[ZhihuAiWorksContract]):
        self.contract = contract
        self.contract_verified = contract is not None
        self.contract_version = "unverified" if contract is None else contract.version
        self.official_source_urls = _DEFAULT_SOURCE_URLS if contract is None else tuple(contract.official_source_urls)
        self.required_fields = () if contract is None else tuple(field.label for field in contract.required_fields)
        self.optional_fields = () if contract is None else tuple(field.label for field in contract.optional_fields)
        self.allowed_commercial_modes = ("free", "one_time") if contract is None else tuple(contract.allowed_commercial_modes)
        self.state_mappings = {} if contract is None else dict(contract.status_mappings)
        self.public_verification_signals = () if contract is None else tuple(contract.public_verification_signals)
        self.manual_fallback = _DEFAULT_MANUAL_FALLBACK if contract is None else tuple(contract.manual_fallback)

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        if self.contract is None:
            raise ChannelContractError(
                "channel_contract_unverified",
                "The Zhihu AI Works required-field contract has not been verified yet.",
                self.manual_fallback,
            )
        semantic = self._semantic_fields(snapshot, dossier)
        rendered: dict[str, str] = {}
        for field_spec in self.contract.required_fields:
            value = semantic.get(field_spec.semantic_key)
            if value is None:
                raise ChannelContractError(
                    "channel_contract_unverified",
                    "Zhihu AI Works contract references an unknown semantic field: {0}".format(field_spec.semantic_key),
                    self.manual_fallback,
                )
            rendered[field_spec.label] = value
        return rendered

    def build_disclosure(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        fields: Mapping[str, str],
    ) -> dict[str, object]:
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        if self.contract is None:
            disclosure["zhihu_contract"] = {
                "verified": False,
                "required_fields": (),
                "optional_fields": (),
            }
            return disclosure
        disclosure["zhihu_contract"] = {
            "verified": True,
            "required_fields": tuple(self._field_metadata(self.contract.required_fields)),
            "optional_fields": tuple(self._field_metadata(self.contract.optional_fields)),
        }
        return disclosure

    def _field_metadata(self, fields: tuple[ZhihuObservedField, ...]) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "semantic_key": field.semantic_key,
                "label": field.label,
                "evidence": field.evidence,
            }
            for field in fields
        )


__all__ = ["ZhihuAiWorksAdapter", "ZhihuAiWorksContract", "ZhihuObservedField"]
