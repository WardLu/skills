# Coze Skill Store

Use this contract for importing an existing Agent Skill package into Coze,
deploying the resulting Skill project, and listing it in the public Skill Store.

- Contract version: `2026-09-12`
- Import documentation: `https://docs.coze.cn/guides_vibe_coding_skill`
- Listing documentation: `https://docs.coze.cn/cozespace_create_skill`
- FAQ and prerequisites: `https://docs.coze.cn/guides_skill_faq`
- Store: `https://space.coze.cn/skills`

## Verified flow

1. On the Coze Coding home page, choose the Skill tab and upload the exact
   `.zip` or `.skill` package.
2. Wait for parsing and security checks, then confirm the resulting project
   still represents the intended Skill before deployment.
3. Deploy the Skill project. Deployment is not store publication.
4. Open Skill Store > My Skills > Created by me, use the target Skill's more
   menu, and choose listing management.
5. Read back the name, summary, cover, description, category, three public case
   links with case images, open-source choice, pricing tier, and developer
   agreement before finalizing the plan.
6. Submit only after the finalized submission digest is authorized. Treat
   review, approval, live visibility, and installability as separate evidence.

## Listing constraints

- Name: at most 20 characters.
- Summary: at most 200 characters.
- Cover, description, category, and three public cases are required for store
  submission. Each case needs a public Coze task share link, name, and image.
- The adapter may stage an import package before listing is ready, but it does
  not build an upload plan until `coze_listing_qualification_verified` and
  `coze_case_assets_verified` are true, the cover receipt is valid, and exactly
  three HTTPS case links are present.
- Paid listing requires merchant payment activation and separate listing
  qualification. Merchant activation alone is not listing approval.
- One-time purchase uses platform-provided monthly price tiers. Prefer CNY 0.01
  only if the live form offers it; otherwise read back the lowest available tier
  and request submission confirmation for that exact value.
- Only the Skill owner may list, update, delist, or remove the public listing.
