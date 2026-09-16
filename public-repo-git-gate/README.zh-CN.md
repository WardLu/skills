# Public Repository Git Gate

[![技能校验](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![版本 0.1.2](https://img.shields.io/badge/version-0.1.2-2563eb.svg)](VERSION) [![MIT 许可证](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

`public-repo-git-gate` 检查公开仓库在 commit、push 和 Pull Request 边界上即将暴露的
内容。它检查 Git 实际范围，而不只看 `.gitignore` 或文件摘要。

[English](README.md) · [简体中文](README.zh-CN.md)

## 检查内容

| 阶段 | 主要问题 |
| --- | --- |
| Commit | 暂存路径、密钥和公开内容是否可以安全提交？ |
| Push | 分支变更是否指向预期的远程仓库和基线？ |
| Pull Request | 最终 head 是否满足仓库的 CI 和评审门禁？ |

## 使用

将 Skill 安装到受支持的 agent：

```bash
npx skills add WardLu/skills --skill public-repo-git-gate
```

例如：

```text
请在我提交这些改动或创建 Pull Request 前检查这个仓库。
```

## 结果与边界

Skill 会报告检查范围、发现、项目所需检查和剩余门禁。默认只读；通过检查不等于授权
commit、push、创建 PR 或更新远程分支。

最终压缩包、许可证、部署和 GitHub Release 附件应使用独立的 Release 门禁。不要把内部
计划、凭据、客户数据或不必要的私有配置写入公开历史。

<details>
<summary>维护者</summary>

运行离线测试：

```bash
python3 -m unittest discover -s tests -v
```

项目专属例外应放在范围收窄的门禁配置中；发布前复核完整的 staged diff。

</details>

## 许可证

MIT，详见 [LICENSE](../LICENSE)。
