"""WorkBuddy channel contract and deterministic staging for Skill packages."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path, PurePosixPath
from typing import Mapping

from ..adapters import BaseChannelAdapter, ChannelContractError
from ..models import Artifact, ChannelStaging, Dossier, SourceSnapshot, SubmissionPlan

_TOP_LEVEL_RESOURCE_DIRS = ("references", "scripts", "templates")
_MANUAL_STATES = (
    "zip_parsed",
    "review_submitted",
    "approved",
    "marketplace_visible",
    "installed_in_conversation",
)
_FRONTMATTER_FIELDS = (
    "name",
    "display_name",
    "display_name_en",
    "description",
    "description_zh",
    "description_en",
    "version",
    "author",
    "allowed-tools",
    "workbuddy-package-root",
    "workbuddy-skill-path",
    "workbuddy-resource-directories",
)
_MARKET_METADATA_FIELDS = ("examples_zh", "examples_en")
_MARKET_METADATA_NAME = "_skillhub_meta.json"


class WorkBuddyAdapter(BaseChannelAdapter):
    key = "workbuddy"
    contract_version = "2026-09-03"
    official_source_urls = ("https://open.workbuddy.cn/en/docs/skill",)
    required_fields = (
        "name",
        "display_name",
        "display_name_en",
        "description",
        "description_zh",
        "description_en",
        "version",
        "author",
        "allowed-tools",
        "package_root",
        "skill_path",
        "resource_directories",
        "publication_mode",
    )
    optional_fields = _MARKET_METADATA_FIELDS
    allowed_commercial_modes = ("free", "one_time")
    state_mappings = {}
    public_verification_signals = (
        "ZIP parsing succeeds in Add Skill -> Create Skill",
        "review submission acknowledgement for the uploaded draft",
        "approval evidence recorded separately from submission",
        "marketplace card for the same skill and version is visible",
        "installed skill can be invoked in a conversation after using the marketplace plus button",
    )
    manual_fallback = (
        "Pause automation and verify the staged WorkBuddy package against the official Skill documentation.",
        "Record exact parsing, review, approval, marketplace, and installation evidence before treating the submission as complete.",
    )

    def build_staging(self, snapshot: SourceSnapshot, dossier: Dossier) -> ChannelStaging:
        if dossier.facts.get("workbuddy_developer_profile_verified") is not True:
            raise ChannelContractError(
                "channel_contract_unverified",
                "WorkBuddy developer profile must be saved and verified before publication.",
                self.manual_fallback,
            )
        staging = super().build_staging(snapshot, dossier)
        manual_fallback = (
            "WorkBuddy staging is prepared, but manual completion must still preserve separate evidence for parsing, review submission, approval, marketplace visibility, and installation.",
            "Do not treat ZIP upload, review submission, approval, marketplace visibility, or installation as interchangeable states.",
        )
        return replace(staging, manual_fallback=manual_fallback)

    def build_plan(self, staging: ChannelStaging, artifact: Artifact, account_alias: str) -> SubmissionPlan:
        plan = super().build_plan(staging, artifact, account_alias)
        exact_fields = ", ".join(_FRONTMATTER_FIELDS)
        exact_states = ", ".join(_MANUAL_STATES)
        manual_fallback = (
            "In WorkBuddy Open Platform, sign in with account alias `{0}`, choose `Add Skill -> Create Skill`, and upload `{1}`. "
            "If ZIP parsing fails, unzip the artifact and verify `{2}` exists and its frontmatter still contains `{3}`. "
            "When provided, market quick prompts are stored separately in `{4}` as `examples_zh`/`examples_en`; they may not appear in the upload preview."
            .format(account_alias, Path(artifact.path).name, staging.fields["skill_path"], exact_fields, _MARKET_METADATA_NAME),
            "After the manual path, report these exact states for the same artifact as separate evidence: `{0}`."
            .format(exact_states),
        )
        return replace(plan, manual_fallback=manual_fallback)

    def render_files(self, snapshot: SourceSnapshot, dossier: Dossier) -> Mapping[str, bytes]:
        staged_skill_md = self._render_skill_md(snapshot, dossier).encode("utf-8")
        package_root = self._package_root(snapshot)
        files: dict[str, bytes] = {
            "{0}/SKILL.md".format(package_root): staged_skill_md,
            "{0}/{1}".format(package_root, _MARKET_METADATA_NAME): self._render_market_metadata(snapshot, dossier),
        }
        for relative in snapshot.files:
            parts = PurePosixPath(relative).parts
            if len(parts) < 2 or parts[0] not in _TOP_LEVEL_RESOURCE_DIRS:
                continue
            files["{0}/{1}".format(package_root, relative)] = (Path(snapshot.root) / relative).read_bytes()
        return files

    def render_fields(self, snapshot: SourceSnapshot, dossier: Dossier) -> dict[str, str]:
        source_fields, _ = self._split_skill_md(snapshot.skill_md_text)
        resource_directories = ", ".join(self._resource_directories(snapshot))
        return {
            "name": snapshot.name,
            "display_name": self._display_name(snapshot, dossier, source_fields, "display_name"),
            "display_name_en": self._display_name(snapshot, dossier, source_fields, "display_name_en"),
            "description": snapshot.description,
            "description_zh": self._required_text(snapshot, dossier, source_fields, "description_zh"),
            "description_en": self._required_text(snapshot, dossier, source_fields, "description_en"),
            "examples_zh": "\n".join(self._examples(dossier, "examples_zh")),
            "examples_en": "\n".join(self._examples(dossier, "examples_en")),
            "version": snapshot.version,
            "author": self._required_text(snapshot, dossier, source_fields, "author"),
            "allowed-tools": self._allowed_tools(snapshot, dossier, source_fields),
            "package_root": self._package_root(snapshot),
            "skill_path": "{0}/SKILL.md".format(self._package_root(snapshot)),
            "resource_directories": resource_directories,
            "publication_mode": self._publication_mode(dossier),
        }

    def build_disclosure(self, snapshot, dossier, fields):
        disclosure = dict(super().build_disclosure(snapshot, dossier, fields))
        disclosure["workbuddy_publication_checks"] = {
            "developer_profile_verified": dossier.facts.get("workbuddy_developer_profile_verified") is True,
            "publication_mode": fields["publication_mode"],
        }
        return disclosure

    def _publication_mode(self, dossier: Dossier) -> str:
        mode = str(dossier.facts.get("workbuddy_publication_mode", "")).strip()
        if mode not in {"public", "dedicated"}:
            raise ChannelContractError(
                "channel_contract_unverified",
                "WorkBuddy publication mode must be explicitly confirmed as public or dedicated.",
                self.manual_fallback,
            )
        return mode

    def _render_skill_md(self, snapshot: SourceSnapshot, dossier: Dossier) -> str:
        source_fields, body = self._split_skill_md(snapshot.skill_md_text)
        staged_fields = self.render_fields(snapshot, dossier)
        for key, value in (
            ("name", staged_fields["name"]),
            ("display_name", staged_fields["display_name"]),
            ("display_name_en", staged_fields["display_name_en"]),
            ("description", staged_fields["description"]),
            ("description_zh", staged_fields["description_zh"]),
            ("description_en", staged_fields["description_en"]),
            ("version", staged_fields["version"]),
            ("author", staged_fields["author"]),
            ("allowed-tools", staged_fields["allowed-tools"]),
            ("workbuddy-package-root", staged_fields["package_root"]),
            ("workbuddy-skill-path", staged_fields["skill_path"]),
            ("workbuddy-resource-directories", staged_fields["resource_directories"]),
        ):
            source_fields = self._upsert_scalar(source_fields, key, value)
        return "---\n{0}---\n{1}".format("".join(source_fields), body)

    def _render_market_metadata(self, snapshot: SourceSnapshot, dossier: Dossier) -> bytes:
        """Render SkillHub marketplace metadata without local install state."""

        source_fields, _ = self._split_skill_md(snapshot.skill_md_text)
        payload: dict[str, object] = {
            "name": self._display_name(snapshot, dossier, source_fields, "display_name"),
            "skillName": snapshot.name,
            "version": snapshot.version,
            "source": "local",
        }
        for key in _MARKET_METADATA_FIELDS:
            values = self._examples(dossier, key)
            if values:
                payload[key] = list(values)
        return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def _display_name(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        source_fields: list[str],
        key: str,
    ) -> str:
        candidate = self._lookup_scalar(source_fields, key)
        if candidate:
            return candidate
        value = dossier.facts.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
        parts = [part for part in snapshot.name.replace("_", "-").split("-") if part]
        return " ".join(part[:1].upper() + part[1:] for part in parts) or snapshot.name

    def _required_text(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        source_fields: list[str],
        key: str,
    ) -> str:
        candidate = self._lookup_scalar(source_fields, key)
        if candidate:
            return candidate
        fact_key = key.replace("-", "_")
        value = dossier.facts.get(fact_key, dossier.facts.get(key))
        if value is not None and str(value).strip():
            return str(value).strip()
        raise ChannelContractError(
            "channel_contract_unverified",
            "WorkBuddy requires verified `{0}` metadata before deterministic staging can continue.".format(key),
            self.manual_fallback,
        )

    def _allowed_tools(
        self,
        snapshot: SourceSnapshot,
        dossier: Dossier,
        source_fields: list[str],
    ) -> str:
        candidate = self._lookup_scalar(source_fields, "allowed-tools")
        if candidate:
            return candidate
        raw = dossier.facts.get("allowed_tools", dossier.facts.get("allowed-tools"))
        if raw is None:
            raise ChannelContractError(
                "channel_contract_unverified",
                "WorkBuddy requires a verified `allowed-tools` value before deterministic staging can continue.",
                self.manual_fallback,
            )
        if isinstance(raw, (tuple, list, set, frozenset)):
            values = sorted(str(item).strip() for item in raw if str(item).strip())
            if values:
                return ", ".join(values)
        text = str(raw).strip()
        if text:
            return text
        raise ChannelContractError(
            "channel_contract_unverified",
            "WorkBuddy requires a non-empty `allowed-tools` value before deterministic staging can continue.",
            self.manual_fallback,
        )

    def _examples(self, dossier: Dossier, key: str) -> tuple[str, ...]:
        raw = dossier.facts.get(key, ())
        if isinstance(raw, (tuple, list, set, frozenset)):
            return tuple(str(item).strip() for item in raw if str(item).strip())
        text = str(raw).strip() if raw is not None else ""
        return (text,) if text else ()

    def _resource_directories(self, snapshot: SourceSnapshot) -> tuple[str, ...]:
        present = []
        for directory in _TOP_LEVEL_RESOURCE_DIRS:
            prefix = directory + "/"
            if any(relative.startswith(prefix) for relative in snapshot.files):
                present.append(directory)
        return tuple(present)

    def _package_root(self, snapshot: SourceSnapshot) -> str:
        return snapshot.name

    def _split_skill_md(self, text: str) -> tuple[list[str], str]:
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            raise ChannelContractError(
                "channel_contract_unverified",
                "WorkBuddy requires a source SKILL.md with YAML frontmatter.",
                self.manual_fallback,
            )
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return list(lines[1:index]), "".join(lines[index + 1 :])
        raise ChannelContractError(
            "channel_contract_unverified",
            "WorkBuddy requires a source SKILL.md with a closed YAML frontmatter block.",
            self.manual_fallback,
        )

    def _lookup_scalar(self, lines: list[str], key: str) -> str:
        prefix = key + ":"
        for line in lines:
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return ""

    def _upsert_scalar(self, lines: list[str], key: str, value: str) -> list[str]:
        rendered = "{0}: {1}\n".format(key, self._render_scalar(value))
        updated = []
        replaced = False
        prefix = key + ":"
        for line in lines:
            if line.startswith(prefix):
                if not replaced:
                    updated.append(rendered)
                    replaced = True
                continue
            updated.append(line)
        if not replaced:
            updated.append(rendered)
        return updated

    def _render_scalar(self, value: str) -> str:
        text = str(value)
        if not text:
            return '""'
        if any(token in text for token in ("\n", "\r", "#", ": ", "{", "}", "[", "]")) or text[0] in ("-", "!", "@", "&", "*", "?", "|", ">", "%", "`", '"', "'"):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            return '"{0}"'.format(escaped)
        return text


__all__ = ["WorkBuddyAdapter"]
