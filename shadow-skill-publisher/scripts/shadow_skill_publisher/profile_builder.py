"""Safe, source-derived defaults for profile-free publisher runs."""

from __future__ import annotations

from pathlib import Path
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
        "examples": _default_examples(snapshot),
    }


def apply_source_defaults(profile: Mapping[str, object], snapshot: SourceSnapshot) -> dict[str, object]:
    """Copy deterministic source facts into missing non-sensitive profile fields."""

    result = dict(profile)
    if not _has_text(result.get("description_en")):
        result["description_en"] = snapshot.description
    if not _has_content(result.get("examples")):
        result["examples"] = _default_examples(snapshot)
    if (
        not isinstance(result.get("commercial"), Mapping)
        and "commercial_mode" not in result
        and not isinstance(result.get("business_policy"), Mapping)
    ):
        result["commercial"] = {"mode": "free", "currency": None, "price": None}

    accounts = result.get("accounts", {})
    if isinstance(accounts, Mapping):
        copied_accounts = dict(accounts)
        result["accounts"] = copied_accounts
        skillpay_alias = copied_accounts.get("skillpay")
        if _has_text(skillpay_alias) and not _has_text(result.get("creator_account_alias")):
            result["creator_account_alias"] = str(skillpay_alias).strip()
    return result


def missing_profile_inputs(
    profile: Mapping[str, object], channels: Sequence[str]
) -> tuple[dict[str, object], ...]:
    """Return required facts and how the agent should obtain them.

    Browser-observable facts are deliberately separated from final user
    decisions. The agent can open a signed-in creator page, observe those
    values, update the private profile, and rerun preparation without asking
    the user to type platform metadata.
    """

    accounts = profile.get("accounts", {})
    account_map = accounts if isinstance(accounts, Mapping) else {}
    missing: list[dict[str, object]] = []
    for channel in channels:
        fields: list[str] = []
        browser_observable: list[str] = []
        agent_draft: list[str] = []
        user_confirmation: list[str] = []
        if not _has_text(account_map.get(channel)):
            field = f"accounts.{channel}"
            fields.append(field)
            browser_observable.append(field)

        if channel == "workbuddy":
            if not _profile_author(profile):
                fields.append("author")
                user_confirmation.append("author")
            if not _has_text(profile.get("description_zh")):
                fields.append("description_zh")
                agent_draft.append("description_zh")
            if not _has_content(profile.get("allowed_tools")) and not _has_content(profile.get("allowed-tools")):
                fields.append("allowed_tools")
                agent_draft.append("allowed_tools")
            if profile.get("workbuddy_developer_profile_verified") is not True:
                fields.append("workbuddy_developer_profile_verified")
                browser_observable.append("workbuddy_developer_profile_verified")
            if str(profile.get("workbuddy_publication_mode", "")).strip() not in {"public", "dedicated"}:
                fields.append("workbuddy_publication_mode")
                user_confirmation.append("workbuddy_publication_mode")
        elif channel == "skillpay":
            for key in (
                "creator_identity_verified",
                "required_agreements_verified",
                "price_format_verified",
                "form_contract_verified",
            ):
                if profile.get(key) is not True:
                    fields.append(key)
                    browser_observable.append(key)
        elif channel == "coze-skill-store":
            if not _has_text(profile.get("coze_category")):
                fields.append("coze_category")
                browser_observable.append("coze_category")
            if profile.get("coze_open_source") not in (True, False):
                fields.append("coze_open_source")
                user_confirmation.append("coze_open_source")
            if profile.get("coze_payment_verified") is not True:
                fields.append("coze_payment_verified")
                browser_observable.append("coze_payment_verified")

        if fields:
            if browser_observable and (agent_draft or user_confirmation):
                next_action = "observe_browser_then_confirm_draft"
            elif browser_observable:
                next_action = "observe_browser"
            elif agent_draft or user_confirmation:
                next_action = "confirm_draft"
            else:
                next_action = "review"
            missing.append(
                {
                    "channel": channel,
                    "fields": tuple(fields),
                    "browser_observable": tuple(browser_observable),
                    "agent_draft": tuple(agent_draft),
                    "user_confirmation": tuple(user_confirmation),
                    "next_action": next_action,
                }
            )
    return tuple(missing)


def _profile_author(profile: Mapping[str, object]) -> str:
    author = profile.get("author")
    if isinstance(author, Mapping):
        return _text(author.get("display_name")) or _text(author.get("name"))
    return _text(author)


def _default_examples(snapshot: SourceSnapshot) -> tuple[str, ...]:
    metadata_path = Path(snapshot.root) / "agents" / "openai.yaml"
    if metadata_path.is_file():
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("default_prompt:"):
                value = line.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    return (value,)
    return ("Use {0} to {1}".format(snapshot.name, snapshot.description),)


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
    "missing_profile_inputs",
]
