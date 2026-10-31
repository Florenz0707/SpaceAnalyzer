# 项目协作约定

## 目标与只读边界

- 本项目是 Windows 优先、单机运行、前后端分离的磁盘快照分析工具。
- v0.1.0 基线包含一次快照可视化与固定证据模型对话。后续工作按 `doc/PLAN.md` 推进，当前发布范围与已知限制见 `doc/releases/v0.1.0.md`。
- 对被分析的文件系统仅允许读取元数据，不得删除、移动、重命名、改写文件、修改权限或创建标记文件。
- 应用自身数据库可以写入；开发依赖、构建与测试产物只能写入项目工具目录或测试临时目录。
- 不跟随符号链接、目录联接和其他可能越出扫描范围的重解析目标；不自动提权。
- 测试只使用临时目录与合成数据，不自动扫描用户真实目录、整盘或读取文件正文。
- 不提供任意 Shell 执行工具给 Agent；模型仅能调用明确列出的只读查询工具。

## 工作树与分支

- 开发任务在独立的 agent-worktree 中执行，目录位于项目父目录下，默认使用 `D:/SpaceAnalyzer-agent-worktree`。主工作目录 `D:/SpaceAnalyzer` 用于本地运行开发版本。
- 常驻分支为 `main`、`dev`、`idle`，各自职责固定，不删除或混用。
- `main` 保存由用户手动同步的远端基线，不直接承载本地功能开发。Agent 不执行任何 `git push` 或 `git pull`，远端同步由用户负责；不同步时保留本地状态并说明差异，不强制重置或覆盖远端。
- `dev` 保存本地运行的开发版本，主工作目录通常检出 `dev`。需要更新运行版本时，将已验收的 `idle` 版本合并到 `dev`。
- agent-worktree 空闲时保持 `idle`。开始修改前，从 `idle` 创建并切换到独立功能分支，例如 `feat/snapshot-scanner`、`fix/scan-cancellation` 或 `chore/tooling`；不直接在 `idle` 上开发。
- 完成修改、检查与验收后，将功能分支合并到 `idle`，并让 agent-worktree 切回 `idle`。验收未通过时保留功能分支及现场，不提前合并。
- 工作前检查工作树、当前分支和未提交改动。各工作树分别维护依赖与缓存；本地忽略的 skills 需要按 `doc/SKILLS.md` 的固定来源同步，不依赖它们自动出现在新工作树中。
- 本次仓库初始化按用户要求在主目录完成首次提交后，再建立上述工作树与分支；后续开发执行独立工作树流程。

## 任务完成与提交粒度

- 每完成一个独立开发任务或里程碑（例如 M1、M2、M3），同步更新相应文档，运行完整检查，通过后立即创建本地提交；不等到后续里程碑全部完成才集中提交。
- 一次提交围绕一个可说明、可验证的目标，包含必要源码、对应测试和该阶段文档。较大的里程碑可以拆成多个完整的小任务；独立缺陷修复单独提交。
- 用户已授权的开发任务包含检查通过后的阶段性本地提交，无需为每次本地提交重复请求确认。Agent 仍禁止执行 push 或 pull。
- 工程检查通过后的本地提交与最终产品验收分开：验收问题未解决时保留现场和失败证据，不跳过检查制造提交；合并到 idle/dev 仍遵守既定验收流程。
- 交付时列明本轮提交及验证结果，不将多个已完成里程碑长期累积为一个大提交，不改写已有提交来伪造开发时间线。

## Git 提交格式

提交首行使用 `[xxx] brief message`，其中 `xxx` 为变更类型，如 `feat`、`fix`、`docs`、`chore`、`test`、`refactor` 或 `merge`。需要补充说明时，首行后空一行，以列表分点描述原因、主要变更或验证结果。合并提交也遵守此格式。

```text
[feat] Add disk snapshot scanning

- Collect file metadata without following links
- Persist scan errors and aggregate logical sizes
```

已授权任务按上述粒度进行阶段性本地提交；Agent 不执行任何 push 或 pull 操作。合并前完成规定检查，不跳过提交 hook，不将缓存、真实磁盘数据或凭据加入提交。

## 修改后必须验证

每次代码修改完成后，必须从根目录运行以下命令并修复失败项：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

使用 Bash 时运行 `bash scripts/check.sh`。两套入口共用 `.pre-commit-config.yaml`，检查已跟踪和未跟踪文件，包含后端 pytest、前端 Vitest 及 `pnpm build`。不得仅运行单个格式化器来替代。格式化自动修改文件后必须再次运行至全部通过。单独选择 hook 的用法见 `COMPOSE.md`。

涉及关键行为时补充有意义的测试：扫描聚合、权限错误、链接边界、路径校验、快照一致性、查询分页及可视化交互。基础格式化或纯文案修改不要求新增重复性测试，但仍运行现有测试。

交付时说明检查命令、结果及未验证事项。工具不可用时明确报告原因，不虚构通过结果，不通过跳过 hook、降低规则或无依据豁免掩盖失败。

## 模块划分

- `backend/src/spaceanalyzer/main.py`：应用装配，保持精简。
- `api/`：路由与请求响应模型；`scanner/`：文件系统遍历与聚合；`storage/`：SQLite 连接、迁移和仓储；`services/`：扫描任务和快照业务；`analysis/`：模型适配、证据、对话和 workflow。
- 路由不得直接实现递归扫描或 SQL 聚合；扫描器不依赖 FastAPI、前端或模型 SDK。
- 前端按 `features/snapshots/`、`features/treemap/`、`features/chat/` 组织业务，`components/` 仅放真正共享的 UI，`lib/` 放 API 客户端等通用设施。
- 仅在开始实现对应功能时创建模块，不提前建立空文件夹、泛化基类或占位服务。
- 前端不得全量加载整盘文件树；后端提供有界的目录查询，视图按需加载。

## 规范与依赖

- Python 依赖和类型配置在 `backend/pyproject.toml`，使用 uv，更新依赖时同步 `backend/uv.lock`。
- 前端和 JS 工程工具依赖在 `frontend/package.json`，使用 pnpm，更新时同步 `frontend/pnpm-lock.yaml`。
- 不混用 npm/yarn/pip 管理依赖，不提交手动导出的重复依赖清单。
- Prettier 负责前端、JSON、YAML 与 Markdown 格式，markdownlint 负责 Markdown 补充规则及修复；Ruff 负责 Python 格式与 lint。
- ESLint 零警告，Pyright 严格模式；共享 VS Code 配置须与 CLI 规则一致，CLI 结果为最终依据。
- 文件使用 UTF-8、LF、末尾换行；Python 四空格，其他文件两空格。
- API 统一使用 `/api` 前缀。新增或修改接口时同步契约、调用方和测试。

## 文档更新约定

- 项目用途、能力边界、目录或常用命令变化：更新 `README.md`。
- 每批用户可见功能、修复、工程规范或重要架构变化：更新 `CHANGE.md` 的“未发布”，按日期记录已完成事实。
- 安装、运行、构建、配置、数据位置或部署方式变化：更新 `COMPOSE.md`。
- 里程碑完成、执行顺序或验收条件改变：更新 `doc/PLAN.md`，完成状态必须有验证依据。
- 发布准备同步版本、CHANGE、COMPOSE 和 `doc/releases/<version>.md`；记录实际验证与已知限制，历史失败不得写成已修复，材料不包含本地配置或用户数据。
- skills 仅在用户确认后安装到 `.agents/skills/`；记录来源、固定版本、用途和平台要求到 `doc/SKILLS.md`。未经请求不做全局安装。
- 不将计划写成已实现功能，不提交用户真实磁盘路径、快照或密钥。

## 项目级 skills

- 已安装技能位于 `.agents/skills/`。选择和使用前查阅 `doc/SKILLS.md` 的安装状态与适配约定，固定来源和文件哈希见 `doc/skills-lock.json`。
- 按任务需要读取对应 `SKILL.md`，通过其中的相对链接按需读取参考文件，不为安装而执行技能工作流。
- 领域文档采用根目录 `GLOSSARY.md` 和 `doc/adr/`，在实际产生术语或决策时创建。上游示例中的 `docs/adr/` 在本项目映射为 `doc/adr/`。
- Playwright 在 Windows 优先使用 `doc/SKILLS.md` 中已验证的原生 pnpm CLI 命令；需要 Bash 包装器时使用项目内 `.agents/skills/playwright/scripts/playwright_cli.sh`，不使用全局 skills 路径。
- 技能中的原型、审查、文档和测试方法遵守本文的验证、只读与清理约定；安装不自动授权提交、推送、发布 issue 或执行额外编排。
- 保持上游技能文件原样，项目适配统一写入本节和 `doc/SKILLS.md`；升级时更新锁定来源并重新核验。

## 文件清理与变更范围

- 提交前检查 `git status --short`，移除本次工作引入的废弃代码、临时脚本、重复配置和无引用资源。
- 保留锁文件、必要测试及共享 `.vscode` 配置；不提交虚拟环境、node_modules、缓存、数据库、构建产物和测试报告。
- 清理仅限明确属于本次工作的项目生成文件，禁止递归删除未核实路径、用户数据或他人的改动。
- 不创建或提交与当前任务无关的改动，不推送，不安装未经确认的 skills；已授权开发任务按里程碑及时本地提交。
