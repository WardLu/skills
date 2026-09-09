# SkillPay channel contract

## Official entry point

Use `https://skillpay.alipay.com/` as the first-party reference for Skill
publishing, pricing modes, creator identity, review stages, and payment
positioning.

The public site currently states that:

- Skill creators can upload and sell Skill products through SkillPay.
- SkillPay supports both one-time purchase and recurring or usage-scoped commercial models, but those modes have different delivery semantics.
- Skill listing requires separate security review behavior before a product goes live.
- Required agreements must be signed before a product is listed.

The public landing page does not expose a stable machine-readable creator form
contract. Keep upload blocked whenever the live creator flow cannot be
re-verified in session.

## Required prepared fields

SkillPay staging prepares these deterministic fields before artifact packaging and upload planning:

- `title`
- `description`
- `license`
- `permissions`
- `data_handling`
- `risk_summary`
- `commercial_mode`
- `cny_price`
- `creator_account_alias`

Field rules:

- `title` is a display title derived from the frozen `SourceSnapshot.name`.
- `description` stays bound to the frozen source description.
- `license` prefers an explicit dossier fact and otherwise falls back to the first non-empty license line.
- `permissions`, `data_handling`, and `risk_summary` render directly from dossier facts without inferring or rewriting meaning.
- `commercial_mode` supports only the exact dossier values `free` and
  `one_time`; non-canonical variants such as different casing or added
  whitespace are unsupported.
- `cny_price` must stay empty for `free`.
- `cny_price` must stay non-empty for `one_time`, using only a whitespace-only emptiness check; the adapter must then bind the exact provided text without stripping, conversion, rounding, currency inference, or formatting repair.
- `creator_account_alias` must come from verified dossier facts and later match the exact upload account alias.

`package_digest` is a plan-only field derived from the built artifact SHA-256 and must be bound exactly during upload planning.

## Commercial policy boundary

The current flow supports only these commercial paths:

- `free`
- `one_time`

Blocked path:

- `per_run` must raise `ChannelPolicyError` with code and message `per_run_p1_only`.

The public SkillPay site describes recurring or usage-scoped monetization with
separate delivery and agreement requirements. Do not guess how those flows map
onto the current publisher contract; `per_run` remains a future capability.

For `one_time`, deterministic staging requires both:

1. author confirmation; and
2. a non-empty CNY price string.

If either requirement is missing, staging must stop with `price_required` rather than silently downgrading the listing.

## Upload gate and evidence separation

Before any upload, the live creator flow must re-verify all of the following:

- the active creator identity matches the intended `creator_account_alias`;
- required SkillPay agreements are already signed for that creator;
- the intended CNY price string is accepted without normalization guesswork;
- the current creator form still matches the documented field contract.

If any verification is missing, mismatched, or no longer observable, the attempt stays blocked with `channel_contract_unverified` before upload.

Keep these evidence categories separate:

- `parse`
- `safety_review`
- `product_review`
- `live`

None of the states above may stand in for another one. A successfully parsed package does not prove safety review. Safety review does not prove product review. Product review does not prove the product is live. A live product card must still match the intended title, commercial mode, and CNY price.

## Drift boundary

Do not infer hidden creator identifiers, normalize unsupported price formats, or
guess undisclosed creator-form fields from screenshots, prose, or stale runs.

If a future verified SkillPay contract exposes a stable public creator API or
form schema, the adapter can narrow these manual gates. Until then, upload
remains blocked whenever the live creator contract cannot be freshly
re-verified.
