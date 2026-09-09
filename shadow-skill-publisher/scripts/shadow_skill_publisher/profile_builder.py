"""Safe, source-derived defaults for profile-free publisher runs."""

from __future__ import annotations

from typing import Mapping, Sequence

from .models import SourceSnapshot


GENERATED_PROFILE_ORIGIN = "generated"
PROVIDED_PROFILE_ORIGIN = "provided"
STORED_PROFILE_ORIGIN = "stored"


def build_generated_profile(snapshot: SourceSnapshot) -> dict[str, object]:
    """Build an in-memory profile without inventing identity or channel facts."""

    capabilities: list[dict[str, object]] = []
    if snapshot.kind == "prompt":
        capabilities.append(
            {
                "id": "documented-skill-behavior",
                "core": True,
                "evidence": {
                    "type": "source",
                    "path": "SKILL.md",
                    "source_digest": snapshot.source_digest,
                    "summary": "The frozen SKILL.md is the executable prompt contract for this prompt-only Skill.",
                },
            }
        )

    return {
        "schema_version": 1,
        "capabilities": capabilities,
        "commercial": {"mode": "free", "currency": None, "price": None},
        "accounts": {},
        "description_en": snapshot.description,
    }


def apply_source_defaults(profile: Mapping[str, object], snapshot: SourceSnapshot) -> dict[str, object]:
    """Copy deterministic source facts into missing non-sensitive profile fields."""

    result = dict(profile)
    if not _has_text(result.get("description_en")):
        result["description_en"] = snapshot.description
    if not isinstance(result.get("commercial"), Mapping) and "commercial_mode" not in result:
        result["commercial"] = {"mode": "free", "currency": None, "price": None}

    accounts = result.get("accounts", {})
    if isinstance(accounts, Mapping):
        copied_accounts = dict(accounts)
        result["accounts"] = copied_accounts
        skillpay_alias = copied_accounts.get("skillpay")
        if _has_text(skillpay_alias) and not _has_text(result.get("creator_account_alias")):
            result["creator_account_alias"] = str(skillpay_alias).strip()
    return result


def missing_generated_profile_inputs(
    profile: Mapping[str, object], channels: Sequence[str]
) -> tuple[dict[str, object], ...]:
    """Return every non-secret fact still required before channel preparation."""

    accounts = profile.get("accounts", {})
    account_map = accounts if isinstance(accounts, Mapping) else {}
    missing: list[dict[str, object]] = []
    for channel in channels:
        fields: list[str] = []
        if not _has_text(account_map.get(channel)):
            fields.append(f"accounts.{channel}")

        if channel == "lovstudio" and not _profile_source_url(profile):
            fields.append("source_url")
        elif channel == "workbuddy":
            if not _profile_author(profile):
                fields.append("author")
            if not _has_text(profile.get("description_zh")):
                fields.append("description_zh")
            if not _has_content(profile.get("allowed_tools")) and not _has_content(profile.get("allowed-tools")):
                fields.append("allowed_tools")
        elif channel == "skillpay":
            for key in (
                "creator_identity_verified",
                "required_agreements_verified",
                "price_format_verified",
                "form_contract_verified",
            ):
                if profile.get(key) is not True:
                    fields.append(key)

        if fields:
            missing.append({"channel": channel, "fields": tuple(fields)})
    return tuple(missing)


def _profile_source_url(profile: Mapping[str, object]) -> str:
    direct = _text(profile.get("source_url"))
    if direct:
        return direct
    author = profile.get("author")
    if isinstance(author, Mapping):
        return _text(author.get("source_url"))
    return ""


def _profile_author(profile: Mapping[str, object]) -> str:
    author = profile.get("author")
    if isinstance(author, Mapping):
        return _text(author.get("display_name")) or _text(author.get("name"))
    return _text(author)


def _has_content(value: object) -> bool:
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_text(item) for item in value)
    return _has_text(value)


def _has_text(value: object) -> bool:
    return bool(_text(value))


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


__all__ = [
    "GENERATED_PROFILE_ORIGIN",
    "PROVIDED_PROFILE_ORIGIN",
    "STORED_PROFILE_ORIGIN",
    "apply_source_defaults",
    "build_generated_profile",
    "missing_generated_profile_inputs",
]
