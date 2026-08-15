---
name: public-release-gate
description: 通用公开仓库 Release 审核流程，覆盖版本与 Tag 一致性、最终构建产物、压缩包、密钥和内部资料、第三方许可证、生产响应头及 GitHub Release 附件核对。用户要求发布、打 Tag、创建 Release、上线验收或“按全局防线检查”时使用，并按项目实际配置调整。
---

# Public Release Gate

把 Release 当作独立交付物审核。仓库提交检查不等于 Release 审核；必须同时检查源码、最终产物、发布页面和部署状态。commit、push 和 PR 的公开内容与分支闸门由同仓库的 `public-repo-git-gate` skill 负责，不在每次普通提交时重复执行本 skill 的产物检查。

本 skill 是人工审核流程，不宣称单个脚本或 CI 通过就能证明所有 Release 条件。优先复用项目已有的自动化检查，再补做最终产物、托管平台和生产环境的人工核对；没有实际证据时，不得标记为通过。

审核阶段默认只读。创建 Tag、GitHub Release、上传附件、修改生产配置或部署都需要用户明确授权；通过本 skill 不等于获得这些操作的授权。

## 输入与输出

开始前明确仓库根目录、目标版本和 Tag、最终产物路径、第三方资源清单、生产地址以及项目专属配置。

完成后输出一条结构化记录，至少包含：

```text
Release gate: PASS | BLOCKED | FAILED
Repository:
Version / tag:
Build and artifacts:
Publicity and sensitive-data scan:
Third-party notices:
Deployment and response headers:
Release page and attachments:
Evidence:
Skipped checks / residual risks:
```

`PASS` 只表示所有必需证据已核对；`BLOCKED` 表示缺少外部状态、权限或用户决定；`FAILED` 表示检查发现问题。两种非通过状态都不能创建 Tag、GitHub Release 或继续部署。

## 执行顺序

1. 识别仓库可见性、技术栈、构建命令、产物目录、版本来源、第三方资源和部署入口。
2. 检查 `package.json`/锁文件或项目对应的版本文件、README、CHANGELOG、Release Notes 和 Tag 是否一致。
3. 从干净状态构建最终产物；扫描产物目录和最终压缩包，不要只扫描源码。
4. 检查密钥、个人数据、客户数据、内部商业/法律资料、私有模型或服务配置，以及不必要公开的文件。
5. 对 vendored 代码、模型、WASM、字体和媒体逐项核对来源、版本/提交、许可证、再分发条件和 SHA-256；许可证清单必须匹配最终资源。
6. 在部署完成后检查 HTTPS、HTTP 状态、关键静态入口、CSP、HSTS、X-Frame-Options 等项目要求的响应头。
7. 创建 GitHub Release 前核对 Tag、Release 页面和每个附件；附件必须来自已扫描的最终产物，计算并记录 SHA-256。
8. 涉及数据库迁移、边缘函数或外部配置时，单独确认生产状态。CI 通过不代表生产迁移已经执行。

## 复用方式

优先复用项目已有的 `release:check`。没有时，在项目根目录建立 `release-gate.config.json`，至少声明：

```json
{
  "versionFiles": ["package.json"],
  "artifactPaths": ["dist"],
  "vendoredPaths": [],
  "noticeFiles": ["THIRD_PARTY_NOTICES.md"],
  "requireDeploymentChecklist": true,
  "deploymentChecklist": "docs/release-checklist.md",
  "production": {
    "requiredHeaders": [],
    "forbiddenHeaderValues": [],
    "paths": ["/"]
  }
}
```

以上是跨项目约定样例，不是自动校验的通用 schema；项目应由自己的 `release:check` 负责校验实际字段和路径。

项目专属内容放配置中，例如 Supabase 迁移、Vercel 生产地址、Piper 资源和特定响应头；不要把一个项目的假设复制到其他项目。

推荐提供以下命令或等价入口：

```text
npm run verify          # 源码、测试和构建
npm run release:check   # Release 元数据、产物、许可证和部署检查
```

没有自动化入口时，仍执行同样的检查并在 PR/Release Notes 留下证据。任何检查失败都停止发布，不要先创建 Release 再解释。

## 失败、阻塞与恢复

1. 发现密钥、个人数据、内部资料、许可证缺失或产物不一致时，停止发布并记录精确路径、附件或检查项。
2. 遇到无法访问的生产地址、GitHub Release 权限、部署状态或外部配置时，标记为 `BLOCKED`，不要用本地构建成功替代外部证据。
3. 修复后从失败的检查项重新执行，并重新核对受影响的版本、产物哈希和附件；不要直接沿用旧的 `PASS` 记录。
4. 任何已暴露的密钥或个人数据按安全事件处理，轮换凭据并保留事件记录；仅删除文件或改写历史不足以证明风险已经消失。

## 平台边界

版本、构建、产物和许可证检查适用于不同语言和构建系统，但具体命令必须以项目配置为准。GitHub Release、HTTP 响应头和生产部署检查依赖对应托管平台；不能把未测试的平台 CLI、Preview 环境或本地服务器结果描述为生产验证。

## 触发词

将以下请求视为完整触发：

- “按全局公开仓库防线检查本次 Release”
- “检查这个 Tag 能不能发布”
- “审核最终安装包/压缩包和 GitHub Release”
- “上线后验收这个版本”

普通“检查提交”只覆盖 commit/PR 闸门；用户提到 Release、Tag、安装包、商店包、部署或上线时，必须升级为本技能的完整流程。
