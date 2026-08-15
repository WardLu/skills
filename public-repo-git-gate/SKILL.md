---
name: public-repo-git-gate
description: 通用公开 Git 仓库 commit、push 和 PR 防线。检查公开范围、staged/untracked 文件、密钥和个人数据、内部资料、分支与远程目标、PR base/head、CI 和合并前条件。用户要求提交、推送、开 PR、审查公开仓库内容或“按全局防线检查”时使用。
---

# Public Repository Git Gate

把 Git 提交、远程推送和 Pull Request 当成连续的公开性闸门。`.gitignore` 不是安全边界；必须检查 Git 实际会提交或已经纳入版本控制的内容。

本 skill 的检查默认是只读的。通过检查不自动授权 commit、push、创建 PR 或修改远程分支；这些动作仍需用户明确要求，并按当前仓库的分支和审批规则执行。

## 使用脚本

从这个 skill 目录运行。三类检查不是三次全量重复：commit 检查暂存区，push 检查相对 base 的变化，PR 由 CI 对最终 head 独立验证。

```bash
python3 scripts/public_repo_check.py --repo /path/to/repository --staged --require-feature-branch
```

推荐在提交前运行 staged 检查，在推送前运行全量检查：

```bash
python3 scripts/public_repo_check.py --repo /path/to/repository --staged --require-feature-branch
python3 scripts/public_repo_check.py --repo /path/to/repository --changed-since origin/main --check-remote
```

首次接入、规则配置变化、发生过误推送或准备 Release 时，再使用 `--all` 做全量基线检查。项目可以通过 `--config path/to/public-repo-gate.json` 增加项目专属禁用路径和规则。默认规则保持保守；确实需要公开的特殊资源应在项目配置中逐项说明，不能直接关闭整套检查。

如果仓库很大，可以把 `origin/main` 换成 PR 的准确 base SHA；不要使用过旧的本地 base。若 ref 不存在，检查应失败并先同步 base，而不是默认为“没有变化”。

## 分层检查策略

| 阶段 | 检查范围 | 运行内容 | 目标耗时 |
| --- | --- | --- | --- |
| commit | staged 文件 | 路径、密钥、diff 格式、特性分支 | 秒级、离线 |
| push | `base...HEAD` 变化 | 增量公开性检查、remote/branch/upstream 核对 | 秒级，不跑完整测试 |
| PR | 最终 head | CI 全量安全检查、lint、test、build；审查 PR diff | 由 CI 承担 |
| Release | 最终产物和线上状态 | 压缩包、许可证、Tag、部署和附件 | 单独执行 |

commit 通过的结果不能替代 push/PR 的远程状态确认；push 的增量检查也不能替代 PR CI。这样每层只重复自己必须承担的部分。

## Commit 闸门

1. 先确认当前仓库可见性。远程仓库、分支、PR、Preview 和历史默认按公开内容处理。
2. 检查 `git status --short --branch`、当前分支和目标 PR base；普通改动不得直接提交 `main`/`master`。
3. 只把必要文件加入暂存区；检查 staged 文件名、状态和完整 diff，不只看摘要。
4. 运行脚本的 `--staged` 检查和 `git diff --cached --check`。这是快速闸门，不要求每次提交都运行完整测试。
5. 代码风险较高时按项目规则补跑针对性测试；完整 lint、test、build、security 和许可证检查由 PR CI 负责。
6. 检查 commit message、版本文件、公开文档、测试和配置是否同步。内部计划、法律意见、商业策略、客户数据和 agent 私有配置不进入公开提交。

## Push 闸门

1. 推送前重新确认 remote URL、仓库可见性、目标分支、upstream 和 PR head；不要凭旧记忆判断远程状态。
2. 运行 `--changed-since origin/main --check-remote`，再检查本分支最近提交是否包含不应公开的内容。脚本不能证明托管平台的仓库一定是私有或公开，平台设置仍需人工确认。
3. 普通工作流只推送特性分支，不直接推送 `main`。不得使用 `--force` 覆盖他人分支；历史清理等例外必须先保留本地备份并明确记录原因。
4. 推送后通过远程平台确认分支实际存在、提交 SHA 一致、PR base/head 正确，且没有意外创建或更新其他 PR。
5. 若发现误推送，立即停止继续推送；保留备份引用，暂停/关闭 PR，轮换暴露的密钥，从干净公开 base 重建分支，再按托管平台流程处理历史对象和缓存。

## PR 闸门

1. PR 必须以 `main` 为 base，head 指向本次特性分支；标题和描述说明范围、风险、验证结果及未完成项。
2. PR 文件列表和完整 diff 再检查一次，特别是新增文件、生成物、隐藏目录、配置文件、许可证和文档。
3. CI 必须通过；其中应包含一次最终 head 的全量公开性扫描以及项目 lint、test、build、安全和许可证检查。涉及数据库、部署、第三方资源或发布物时，补充对应的真实环境证据。CI 通过不等于生产迁移已执行。
4. PR 描述应明确列出增量本地检查、CI 全量检查、项目测试/构建、安全检查和许可证检查结果；失败或跳过必须说明原因。
5. 作者不能把自己的 PR 当作独立 Review；至少需要一次合适的 Review，必要时请求安全或法律审查。
6. 合并前再次确认没有内部资料、个人数据、密钥或不必要的公开内容。合并后删除特性分支，并独立核对 `main` 的最终提交。

## 检查失败时

停止当前 commit/push/merge，不要“先提交再解释”。先判断是误报、项目专属公开资源，还是确实不应公开；对误报增加最小范围的项目配置并保留理由，对真实问题移出暂存区或从提交中删除。发生密钥、个人数据或内部材料暴露时，按安全事件处理，不能只依赖重写分支历史。

## 与 Release 闸门的边界

本 skill 覆盖 commit、push 和 PR。Tag、最终安装包、压缩包、GitHub Release 附件和生产部署验收使用同仓库的 `public-release-gate` skill；两者都通过后才可称为完整发布审核。不要在 commit、push、PR 每层重复运行 Release 产物扫描。
