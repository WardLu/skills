# Public Release Gate

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`public-release-gate` 把公开仓库 Release 作为完整交付物进行审核。它会同时检查源码、
最终产物、Release 页面和部署状态，不会把 commit 或 CI 通过当成发布批准。

[English](README.md) · [简体中文](README.zh-CN.md)

## 检查内容

- 版本、Tag、README、变更记录和发布说明的一致性；
- 最终构建产物和压缩包；
- 密钥、个人数据、内部资料和第三方许可证；
- 部署响应头、生产状态和 Release 附件。
- 固定的 `docs/release-checklist.md` 回执，其中每项只能为 `completed`、带原因的
  `N/A`，或带原因和下一步的 `blocked`。

## 使用

将 Skill 安装到受支持的 agent：

```bash
npx skills add WardLu/skills --skill public-release-gate --global --agent <agent-name> --yes
```

然后让 agent 审核指定版本、Tag、产物集合和生产 URL。例如：

```text
请在发布前审核 v1.2.3、最终压缩包和已部署 URL。
```

每个独立可发布项目都在 `docs/release-checklist.md` 维护人类可读回执。项目已有检查、
CI 和 Release Watcher 的结果应从该文件链接，不再复制到新的发布控制器或状态存储中。

## 结果与边界

结果为 `PASS`、`BLOCKED` 或 `FAILED`，并附带证据和跳过项。审核默认只读；通过门禁不等于
授权创建 Tag 或 Release、上传附件、修改生产配置或部署。

commit、push 和 Pull Request 请使用 `public-repo-git-gate`。项目专属命令和发布配置应
保留在项目本身。

<details>
<summary>维护者</summary>

发布前构建并检查准确的最终产物；第三方资源的来源、许可证和校验和应与发布证据一起维护。

</details>

## 许可证

MIT，详见 [LICENSE](../LICENSE)。
