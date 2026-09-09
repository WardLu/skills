"""Shared channel adapter contracts and deterministic placeholder behavior."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Optional

from .confirmations import upload_digest
from .models import Artifact, ChannelStaging, Dossier, PublishState, SourceSnapshot, SubmissionPlan

_DEFAULT_MANUAL_FALLBACK = (
    "Pause automation and compare the live form with the documented channel contract.",
    "If the form changed, record channel_contract_unverified and finish the submission manually.",
)


class ChannelContractError(ValueError):
    """Raised when a channel contract is missing, drifted, or cannot be trusted."""

    def __init__(self, code: str, message: str, manual_fallback: tuple[str, ...] = ()):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.manual_fallback = tuple(manual_fallback)


class ChannelPolicyError(ValueError):
    """Raised when a user-selected policy is unsupported by the channel."""

    def __init__(self, code: str, message: str, manual_fallback: tuple[str, ...] = ()):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.manual_fallback = tuple(manual_fallback)


class BaseChannelAdapter:
    """Reusable adapter base with deterministic staging and plan helpers."""

    key = ""
    contract_version = ""
    official_source_urls = ()
    required_fields = ()
    optional_fields = ()
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {}
    public_verification_signals = ()
    manual_fallback = _DEFAULT_MANUAL_FALLBACK
    contract_verified = True

    def build_staging(self, snapshot: SourceSnapshot, dossier: Dossier) -> ChannelStaging:
        self._ensure_contract_ready()
        self._ensure_metadata()
        self._ensure_commercial_mode(dossier)
        files = dict(self.render_files(snapshot, dossier))
        fields = self.render_fields(snapshot, dossier)
        self.ensure_contract_fields(fields)
        disclosure = self.build_disclosure(snapshot, dossier, fields)
        return ChannelStaging(
            channel=self.key,
            contract_version=self.contract_version,
            files=files,
            fields=fields,
            disclosure=disclosure,
            manual_fallback=tuple(self.manual_fallback),
        )

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan:
        self._ensure_contract_ready()
        if staging.channel != self.key:
            raise ValueError("staging channel must match adapter key")
        if staging.contract_version != self.contract_version:
            raise ValueError("staging contract_version must match adapter contract_version")
        if artifact.channel != self.key:
            raise ValueError("artifact channel must match adapter key")
        plan = SubmissionPlan(
            channel=self.key,
            contract_version=self.contract_version,
            account_alias=str(account_alias),
            artifact=artifact,
            fields=dict(staging.fields),
            disclosure=dict(staging.disclosure),
            upload_confirmation_digest="",
            platform_id=None,
            observed_fields={},
            final_action=None,
            submission_confirmation_digest=None,
            manual_fallback=tuple(staging.manual_fallback),
        )
        return replace(plan, upload_confirmation_digest=upload_digest(plan))

    def map_status(self, raw_status: str) -> Optional[PublishState]:
        text = self._normalize_status(raw_status)
        if not text:
            return None
        state = self.state_mappings.get(text)
        if isinstance(state, PublishState):
            return state
        return None

    def ensure_contract_fields(self, observed_fields: Mapping[str, str]) -> None:
        if not isinstance(observed_fields, Mapping):
            raise TypeError("observed_fields must be a mapping")
        observed = tuple(sorted(str(key) for key in observed_fields))
        required = tuple(sorted(str(key) for key in self.required_fields))
        optional = tuple(sorted(str(key) for key in self.optional_fields))
        allowed = frozenset(required + optional)
        missing = tuple(key for key in required if key not in observed)
        unexpected = tuple(key for key in observed if key not in allowed)
        if missing or unexpected:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if unexpected:
                details.append("unexpected: " + ", ".join(unexpected))
            raise ChannelContractError(
                "channel_contract_unverified",
                "Observed required channel fields drifted from the verified contract (" + "; ".join(details) + ").",
                self.manual_fallback,
            )

    def local_preview_id(self, artifact: Artifact) -> str:
        return "local-preview:{0}:{1}".format(self.key, artifact.sha256[:16])

    def render_files(self, snapshot: SourceSnapshot, dossier: Dossier) -> Mapping[str, bytes]:
        return {}

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        semantic = self._semantic_fields(snapshot, dossier)
        fields = {}
        for key in self.required_fields:
            if key not in semantic:
                raise ChannelContractError(
                    "channel_contract_unverified",
                    "Adapter contract includes an unknown required semantic field: {0}".format(key),
                    self.manual_fallback,
                )
            fields[str(key)] = semantic[key]
        return fields

    def build_disclosure(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        fields: Mapping[str, str],
    ) -> dict[str, object]:
        return {
            "source_digest": snapshot.source_digest,
            "source_version": snapshot.version,
            "permissions": tuple(self._sequence_value(dossier.facts.get("permissions", ()))),
            "external_services": tuple(self._sequence_value(dossier.facts.get("external_services", ()))),
            "data_handling": tuple(self._sequence_value(dossier.facts.get("data_handling", ()))),
            "risks": tuple(self._sequence_value(dossier.facts.get("risks", ()))),
            "limitations": tuple(self._sequence_value(dossier.facts.get("limitations", ()))),
            "claims": tuple(claim.text for claim in dossier.claims),
            "removed_claims": tuple(dossier.removed_claims),
            "commercial_mode": dossier.commercial_mode,
            "price": dossier.price,
            "official_source_urls": tuple(str(item) for item in self.official_source_urls),
            "public_verification_signals": tuple(str(item) for item in self.public_verification_signals),
            "disclosure_summary": {"field_names": tuple(sorted(fields)), "channel": self.key},
        }

    def _semantic_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        return {
            "name": snapshot.name,
            "version": snapshot.version,
            "title": "{0} {1}".format(snapshot.name, snapshot.version),
            "summary": snapshot.description,
            "description": snapshot.description,
            "commercial_mode": dossier.commercial_mode,
            "price": "" if dossier.price is None else str(dossier.price),
            "permissions": self._render_value(dossier.facts.get("permissions", ())),
            "external_services": self._render_value(dossier.facts.get("external_services", ())),
            "data_handling": self._render_value(dossier.facts.get("data_handling", ())),
            "risks": self._render_value(dossier.facts.get("risks", ())),
            "limitations": self._render_value(dossier.facts.get("limitations", ())),
            "support_url": self._render_value(dossier.facts.get("support_url", "")),
        }

    def _ensure_contract_ready(self) -> None:
        if not self.contract_verified:
            raise ChannelContractError(
                "channel_contract_unverified",
                "The channel contract has not been verified yet for {0}.".format(self.key),
                self.manual_fallback,
            )

    def _ensure_metadata(self) -> None:
        if not str(self.key).strip():
            raise ChannelContractError("channel_contract_unverified", "Adapter key is required.", self.manual_fallback)
        if not str(self.contract_version).strip():
            raise ChannelContractError(
                "channel_contract_unverified",
                "Adapter contract_version is required.",
                self.manual_fallback,
            )

    def _ensure_commercial_mode(self, dossier: Dossier) -> None:
        if dossier.commercial_mode not in tuple(str(item) for item in self.allowed_commercial_modes):
            raise ChannelPolicyError(
                "channel_policy_unsupported",
                "Commercial mode {0!r} is not supported for channel {1}.".format(dossier.commercial_mode, self.key),
                self.manual_fallback,
            )

    def _normalize_status(self, raw_status: str) -> str:
        return " ".join(str(raw_status).strip().lower().split())

    def _render_value(self, value: object) -> str:
        if isinstance(value, (tuple, list, set, frozenset)):
            return "\n".join(self._sorted_strings(value))
        return "" if value is None else str(value)

    def _sequence_value(self, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)):
            return (str(value),)
        if isinstance(value, (tuple, list, set, frozenset)):
            return tuple(self._sorted_strings(value))
        return (str(value),)

    def _sorted_strings(self, values: object) -> list[str]:
        if not isinstance(values, (tuple, list, set, frozenset)):
            return [str(values)]
        return sorted((str(item) for item in values), key=str)


class UnverifiedChannelAdapter(BaseChannelAdapter):
    """Explicit placeholder used until a channel contract is implemented."""

    contract_verified = False
