# Skills 集合项目约定

## 仓库边界

- 本仓库保存可独立安装、测试和发布的 Agent Skill；每个 Skill 位于根目录下独立的 kebab-case 目录。
- Skill 入口必须命名为大写 `SKILL.md`，以 YAML frontmatter 开头，并包含与目录/用途一致的 `name` 和可触发的 `description`。
- 根 README 只做目录、安装和兼容性导航；完整工作流放对应 `SKILL.md`，大段背景、示例和实现细节按需放 `references/`、README 或脚本。
- 不为同一 Skill 在多个位置维护漂移副本。安装目录是发布结果，不是本仓库事实源。

## Skill 设计与实现

- 规则只保留模型无法可靠推断的流程、安全边界和完成标准；不要堆叠通用礼貌、重复全局约定或用提示词模拟 CI/权限。
- 新增或修改 Skill 时核对触发条件、输入、输出、失败模式、恢复方式和平台兼容性；危险操作必须默认收窄目标并在写入前备份。
- 优先让脚本承担确定性解析、校验和批量处理。脚本应可从 Skill 目录运行，避免硬编码个人路径，并提供 `--help` 或清晰入口。
- 测试保持离线、确定性和无真实副作用；不得包含真实会话、令牌、密钥、备份、用户名数据或完整诊断内容。
- 面向多个系统的 Skill 要明确共用部分和平台差异，不能声称在未测试的 agent、OS 或版本上已验证。

## 版本与发布

- `VERSION` 是规范版本；发布时同步 `SKILL.md` 元数据、README 徽章/目录、`CHANGELOG.md` 和 `vMAJOR.MINOR.PATCH` 标签。
- 用户可见行为、默认写入范围或安全语义变化需要更新文档与测试；破坏性变化按语义化版本处理。
- 公开发布前分别检查源码、安装包/归档、第三方许可证和最终 Release 附件；普通提交检查不能替代 Release 验收。
- 不把本地已安装副本、测试通过或标签存在单独当成发布完成证据。

## 修改与验证

- 先完整读取目标 Skill 的 `SKILL.md` 及其直接引用，再修改；不要只根据目录名推断行为。
- 元数据检查以 `.github/workflows/validate-skills.yml` 为准，至少验证 frontmatter、`name`、`description` 和大写入口名。
- 运行单个 Skill 测试：`python -m unittest discover -s <skill>/tests -v`；涉及公共校验逻辑时运行所有现有 `*/tests`。
- 脚本、备份、跨平台或修复逻辑变化还要运行对应 `--help`、dry-run/预览和失败路径测试；真实写入结果必须单独验证。
- 修改根目录索引或安装说明时同步 `README.md` 与 `README.zh-CN.md`，并检查链接和版本是否指向现存文件。

## 当前入口

- 集合说明：`README.md`、`README.zh-CN.md`
- CI 校验：`.github/workflows/validate-skills.yml`
- 各 Skill 的行为、测试和发布细节：对应目录中的 `SKILL.md` 与 README
