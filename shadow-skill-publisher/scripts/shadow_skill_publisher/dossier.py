"""Evidence-backed release dossier generation and channel-copy freezing."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Mapping, Optional

from .models import Claim, Dossier, FrozenFields, GateReport, SourceSnapshot
from .redaction import redact_text


class DossierError(ValueError):
    """Raised when a dossier would make an unsupported or untraceable claim."""


_EDITABLE_CHANNEL_FIELDS = frozenset(
    (
        "title",
        "description",
        "description_zh",
        "description_en",
        "concise_description",
        "functionality",
        "applicability",
        "workflow_summary",
        "risk_summary",
        "limitations",
        "risk_disclosure",
    )
)

def build_dossier(
    snapshot: SourceSnapshot,
    report: GateReport,
    profile: Mapping[str, object],
) -> Dossier:
    """Build a deterministic dossier from a frozen source and gate result.

    Profile values are deliberately copied into ``facts`` rather than inferred from
    prose. Public claims must cite explicit dossier provenance; only the built-in
    identity claim remains source-bound to the frozen snapshot.
    """
    commercial = _commercial(profile)
    provenance = _provenance(snapshot, profile)
    claims = _claims(snapshot, profile, frozenset(item["id"] for item in provenance))
    if any(not claim.evidence_ids for claim in claims):  # defensive contract guard
        raise DossierError("every public claim requires provenance")

    removed = tuple(dict.fromkeys(str(value) for value in report.removed_claims))
    author = profile.get("author", {})
    if not isinstance(author, Mapping):
        author = {}
    facts = {
        "author": _value(author, "display_name", _value(author, "name", "")),
        "source_url": _value(profile, "source_url", _value(author, "source_url", "")),
        "audience": _value(profile, "audience", ()),
        "inputs": _value(profile, "inputs", ()),
        "outputs": _value(profile, "outputs", ()),
        "usage": _value(profile, "usage", ()),
        "dependencies": _value(profile, "dependencies", ()),
        "permissions": _value(profile, "permissions", ()),
        "external_services": _value(profile, "external_services", ()),
        "data_handling": _value(profile, "data_handling", ()),
        "risks": _value(profile, "risks", ()),
        "limitations": _value(profile, "limitations", ()),
        # Keep the generated dossier portable. The source snapshot retains
        # the absolute license path for local validation, but that path must
        # never become a public dossier fact when the profile omits a label.
        "license": _value(profile, "license", _portable_license_label(snapshot)),
        "support_url": _value(profile, "support_url", ""),
        "assets": _value(profile, "assets", snapshot.files),
        "provenance": provenance,
        "source_digest": snapshot.source_digest,
        "source_version": snapshot.version,
        "gate_allowed": report.allowed,
        "git_commit": snapshot.git_commit,
        "git_branch": snapshot.git_branch,
        "git_dirty": snapshot.git_dirty,
    }
    return Dossier(
        identity={"name": snapshot.name, "version": snapshot.version, "kind": snapshot.kind},
        claims=tuple(claims),
        removed_claims=removed,
        commercial_mode=commercial[0],
        price=commercial[1],
        facts=facts,
    )


def _provenance(snapshot: SourceSnapshot, profile: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    source_id = f"source:{snapshot.source_digest}"
    records: list[Mapping[str, object]] = [{"id": source_id, "type": "source", "source_digest": snapshot.source_digest, "version": snapshot.version}]
    supplied = profile.get("provenance", ())
    if isinstance(supplied, Mapping):
        supplied = (supplied,)
    if isinstance(supplied, (str, bytes)) or not isinstance(supplied, (list, tuple)):
        raise DossierError("provenance must be a sequence")
    for index, record in enumerate(supplied):
        if not isinstance(record, Mapping) or not str(record.get("id", "")).strip():
            raise DossierError(f"provenance[{index}] must contain an id")
        if str(record["id"]).strip() != source_id:
            records.append(dict(record))
    return tuple(records)


def _claims(snapshot: SourceSnapshot, profile: Mapping[str, object], evidence_ids: frozenset[str]) -> list[Claim]:
    source_id = f"source:{snapshot.source_digest}"
    raw = profile.get("claims", profile.get("core_claims", ()))
    if raw is None:
        raw = ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise DossierError("claims must be a sequence")
    claims = [Claim("identity", f"{snapshot.name} version {snapshot.version}.", (source_id,))]
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            text = str(item.get("text", item.get("claim", ""))).strip()
            claim_id = str(item.get("id", item.get("claim_id", f"claim-{index + 1}"))).strip()
            refs = item.get("evidence_ids", item.get("provenance", ()))
            if isinstance(refs, str):
                refs = (refs,)
            refs = tuple(str(ref).strip() for ref in refs if str(ref).strip()) if isinstance(refs, (list, tuple)) else ()
        else:
            text, claim_id, refs = str(item).strip(), f"claim-{index + 1}", ()
        if not text:
            raise DossierError(f"claims[{index}] must contain text")
        if not refs:
            raise DossierError(f"claims[{index}] requires evidence_ids")
        unknown = tuple(ref for ref in refs if ref not in evidence_ids)
        if unknown:
            raise DossierError(f"claims[{index}] references unknown evidence ID: {unknown[0]}")
        claims.append(Claim(claim_id or f"claim-{index + 1}", text, refs))
    return claims


def _commercial(profile: Mapping[str, object]) -> tuple[str, Optional[str]]:
    pricing = profile.get("commercial", profile.get("pricing", {}))
    if not isinstance(pricing, Mapping):
        pricing = {}
    mode = str(profile.get("commercial_mode", pricing.get("mode", "free"))).strip().lower()
    if mode == "per_run":
        raise DossierError("per_run commercial mode is not allowed in P0")
    if mode not in {"free", "one_time"}:
        raise DossierError("commercial_mode must be free or one_time")
    price = profile.get("price", pricing.get("price"))
    confirmed = profile.get("author_confirmed", pricing.get("author_confirmed", profile.get("commercial_confirmed")))
    if mode == "one_time" and confirmed is not True:
        raise DossierError("one_time pricing requires author confirmation")
    return mode, None if price is None else str(price)


def _value(profile: Mapping[str, object], key: str, default: object) -> object:
    value = profile.get(key, default)
    return value


def _portable_license_label(snapshot: SourceSnapshot) -> str:
    """Return a public license label without exposing the source path."""

    try:
        for line in Path(snapshot.license_path).read_text(encoding="utf-8").splitlines():
            label = line.strip()
            if label:
                return label
    except (OSError, UnicodeDecodeError):
        pass
    return Path(snapshot.license_path).name or "LICENSE"


def render_dossier_json(dossier: Dossier) -> str:
    """Render a stable, machine-readable dossier."""
    payload = {
        "identity": dict(dossier.identity),
        "author": dossier.facts.get("author"),
        "source_url": dossier.facts.get("source_url"),
        "audience": dossier.facts.get("audience"),
        "inputs": dossier.facts.get("inputs"),
        "outputs": dossier.facts.get("outputs"),
        "usage": dossier.facts.get("usage"),
        "claims": [asdict(claim) for claim in dossier.claims],
        "removed_optional_claims": list(dossier.removed_claims),
        "dependencies": dossier.facts.get("dependencies"),
        "permissions": dossier.facts.get("permissions"),
        "external_services": dossier.facts.get("external_services"),
        "data_handling": dossier.facts.get("data_handling"),
        "risks": dossier.facts.get("risks"),
        "limitations": dossier.facts.get("limitations"),
        "license": dossier.facts.get("license"),
        "support_url": dossier.facts.get("support_url"),
        "assets": dossier.facts.get("assets"),
        "commercial_mode": dossier.commercial_mode,
        "price": dossier.price,
        "provenance": dossier.facts.get("provenance"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_dossier_markdown(dossier: Dossier) -> str:
    """Render the public dossier as readable Markdown without hidden freeze metadata."""
    payload = json.loads(render_dossier_json(dossier))
    lines = [f"# Release Dossier: {payload['identity']['name']}", "", f"- Version: `{payload['identity']['version']}`", f"- Kind: `{payload['identity']['kind']}`", f"- Commercial mode: `{payload['commercial_mode']}`" + (f" ({payload['price']})" if payload["price"] else ""), "", "## Claims", ""]
    for claim in payload["claims"]:
        lines.append(f"- **{claim['claim_id']}**: {claim['text']} _(evidence: {', '.join(claim['evidence_ids'])})_")
    lines.extend(["", "## Removed optional claims", ""])
    lines.extend(f"- {value}" for value in payload["removed_optional_claims"] or ["None"])
    for key in ("author", "source_url", "audience", "inputs", "outputs", "usage", "dependencies", "permissions", "external_services", "data_handling", "risks", "limitations", "license", "support_url", "assets", "provenance"):
        lines.extend(["", f"## {key.replace('_', ' ').title()}", "", f"```json\n{json.dumps(payload[key], ensure_ascii=False, sort_keys=True, indent=2)}\n```"])
    return "\n".join(lines) + "\n"


def merge_channel_edits(dossier: Dossier, edits: Mapping[str, str], prior: Optional[FrozenFields] = None) -> FrozenFields:
    """Freeze human channel copy independently, preserving it across regeneration."""
    current = validate_channel_edits(edits)
    prior_values = validate_channel_edits(prior.values) if prior else {}
    current_facts = _generated_facts(dossier)
    frozen = dict(prior_values)
    frozen.update(current)
    drifted: set[str] = set()
    if prior:
        drifted.update(key for key in set(prior.generated_facts) | set(current_facts) if prior.generated_facts.get(key) != current_facts.get(key))
    return FrozenFields(values=frozen, drifted_fields=tuple(sorted(drifted)), generated_facts=current_facts)


def apply_channel_edits(
    dossier: Dossier,
    generated_fields: Mapping[str, str],
    edits: Mapping[str, str],
    prior: Optional[FrozenFields] = None,
) -> tuple[dict[str, str], FrozenFields]:
    """Reapply private human copy without allowing generated identity changes.

    The returned field mapping is suitable for a local submission plan.  The
    accompanying ``FrozenFields`` remains private metadata; generated hashes
    are never inserted into platform-facing fields.
    """

    fields = {str(key): str(value) for key, value in generated_fields.items()}
    current = validate_channel_edits(edits)
    unknown = sorted(set(current) - set(fields))
    if unknown:
        raise DossierError("channel edits reference fields not emitted by this channel: {0}".format(", ".join(unknown)))
    frozen = merge_channel_edits(dossier, current, prior)
    unknown_prior = sorted(set(frozen.values) - set(fields))
    if unknown_prior:
        raise DossierError("frozen channel edits reference fields not emitted by this channel: {0}".format(", ".join(unknown_prior)))
    fields.update(frozen.values)
    return fields, frozen


def validate_channel_edits(edits: Mapping[str, str]) -> dict[str, str]:
    """Reject unsafe private copy instead of persisting a redacted substitute."""
    if not isinstance(edits, Mapping):
        raise DossierError("edits must be a mapping")
    normalized = {str(key).strip(): str(value) for key, value in edits.items()}
    empty = sorted(key for key in normalized if not key)
    if empty:
        raise DossierError("channel edit field names must be non-empty")
    forbidden = sorted(set(normalized) - _EDITABLE_CHANNEL_FIELDS)
    if forbidden:
        raise DossierError("channel edit fields are not editable: {0}".format(", ".join(forbidden)))
    sensitive = sorted(key for key, value in normalized.items() if redact_text(value) != value)
    if sensitive:
        raise DossierError("channel edit values look sensitive: {0}".format(", ".join(sensitive)))
    return normalized


def _generated_facts(dossier: Dossier) -> Mapping[str, str]:
    """Return opaque per-key hashes for drift comparison, never channel copy."""
    values: dict[str, object] = {"identity": dossier.identity, "claims": [asdict(c) for c in dossier.claims], "removed_claims": dossier.removed_claims, "commercial_mode": dossier.commercial_mode, "price": dossier.price}
    values.update(dossier.facts)
    return {key: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest() for key, value in values.items()}
