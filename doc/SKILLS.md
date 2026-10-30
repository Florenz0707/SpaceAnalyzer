# Skills 安装记录与候选调研

## 当前状态

2026-10-30 已按用户确认将以下 9 项安装到项目级 `.agents/skills/`。没有全局安装，也没有安装未获确认的候选。

该目录目前被本地 `.agents/.gitignore` 忽略，不随 Git 提交或新工作树自动复制。创建 agent-worktree 时同步已安装目录及忽略文件，并按照 `skills-lock.json` 核验内容；不修改用户已有忽略设置。

安装使用 `skill-installer` 的 `--dest` 和固定 `--ref`，完整保留各技能目录。所有上游文件与固定版本的下载档案逐字节核验；另为六个 Matt Pocock 技能补充仓库根部的原样 MIT `LICENSE`，没有修改技能正文或脚本。

### 已安装清单

| 技能                                                                          | 来源及固定 commit                                 | 许可证                  |
| ----------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------- |
| [frontend-design](../.agents/skills/frontend-design/SKILL.md)                 | [anthropics/skills，ca45fc4][installed-anthropic] | Apache-2.0              |
| [playwright](../.agents/skills/playwright/SKILL.md)                           | [openai/skills，49f948f][installed-openai]        | Apache-2.0，保留 NOTICE |
| [security-best-practices](../.agents/skills/security-best-practices/SKILL.md) | [openai/skills，49f948f][installed-openai]        | Apache-2.0              |
| [codebase-design](../.agents/skills/codebase-design/SKILL.md)                 | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |
| [tdd](../.agents/skills/tdd/SKILL.md)                                         | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |
| [diagnosing-bugs](../.agents/skills/diagnosing-bugs/SKILL.md)                 | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |
| [domain-modeling](../.agents/skills/domain-modeling/SKILL.md)                 | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |
| [writing-for-agents](../.agents/skills/writing-for-agents/SKILL.md)           | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |
| [prototype](../.agents/skills/prototype/SKILL.md)                             | [mattpocock/skills，a496f55][installed-matt]      | MIT                     |

完整 commit、上游目录、安装目录、许可证和全部 52 个文件的 SHA-256 记录在 [skills-lock.json](skills-lock.json)。技能目录属于保留原样的第三方文件，沿用已有 pre-commit、Prettier 和 markdownlint 排除规则；完整性通过来源与哈希核验，不进行批量格式化。

### 项目适配与验证

- 上游文件保持原样，项目差异通过根目录 `AGENTS.md` 的“项目级 skills”约定处理。后续升级先审阅差异，再更新固定版本与清单。
- 领域术语表按需放在根目录 `GLOSSARY.md`，ADR 放在 `doc/adr/`；不因上游示例创建平行的 `docs/` 目录。
- Playwright 使用项目内技能路径，不使用上游示例中的全局 `$CODEX_HOME/skills`。Windows 原生命令见下方；Bash 包装器保留，但未验证本机 Git Bash/WSL 运行环境。
- 安装只是提供指导文件，不会自动运行 TDD、原型、安全审查、浏览器或并行设计流程。跨技能引用的未安装项不视为可用，也不自动补装。
- 当前没有配置 Matt Pocock 的任务跟踪体系，也未安装 `setup-matt-pocock-skills`、`code-review` 等额外技能。
- 不修改应用依赖清单，不安装全局 CLI，不下载浏览器；Playwright CLI 通过 pnpm 临时缓存验证帮助入口，不等于浏览器端到端测试已通过。
- 新增项目级技能在后续会话中加载，按任务范围使用。

2026-10-30 在仓库根目录执行并通过以下 Windows 帮助命令，CLI 入口固定为 `0.1.22`：

```powershell
pnpm --dir frontend dlx @playwright/cli@0.1.22 --help
```

后续浏览器操作可使用相同命令前缀替换 `--help`，遵循技能要求先获取快照再操作元素；截图与调试产物使用项目忽略目录 `output/playwright/`。pnpm 临时缓存不属于应用运行依赖锁定范围。

[installed-anthropic]: https://github.com/anthropics/skills/tree/ca45fc496a3436251f191354091d557da31c15b5
[installed-openai]: https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431
[installed-matt]: https://github.com/mattpocock/skills/tree/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa

## 来源与用途

| 候选                    | 来源                                                                                                                                    | 适用阶段                                    | 建议                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------- |
| frontend-design         | [anthropics/skills](https://github.com/anthropics/skills/tree/ca45fc496a3436251f191354091d557da31c15b5/skills/frontend-design)          | M3 空间可视化界面、导航、详情与后续对话区域 | 已安装，指导信息层级与界面设计     |
| playwright              | [openai/skills](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/playwright)              | M3–M4 浏览器交互验收、截图与调试            | 已安装，Windows CLI 帮助命令已验证 |
| security-best-practices | [openai/skills](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-best-practices) | 本机 API、路径边界、后续模型工具审查        | 已安装，用户明确要求安全审查时触发 |

### frontend-design

上游提供界面视觉设计与实现指导，适合规划 Treemap 周边的目录导航、筛选、状态和详情。不能替代性能、无障碍和只读约束；本项目是分析工具，设计应优先服务文件层级与空间比较。

已核实：OpenAI curated 中同名路径返回 404，因此候选来源明确采用 Anthropic 官方仓库，不混淆供应方。

### playwright

上游以 `playwright-cli` 为主，适合执行真实浏览器操作、截图和交互调试。文档中的包装器是 Bash 脚本，并假设全局 skills 位置；本项目通过上述项目路径约定与原生 CLI 命令适配。若后续需要自动化 E2E 测试，应明确增加项目测试依赖，不能把此技能等同于已配置 Playwright 测试套件。

### security-best-practices

上游支持 Python 与 JavaScript/TypeScript，适合审查 FastAPI/React 边界及模型工具。其触发条件要求用户明确请求安全建议或审查，不应在普通开发任务中自动生成安全报告。

## mattpocock/skills 补充调研

### 调研依据

2026-10-30 检查了 [mattpocock/skills 仓库](https://github.com/mattpocock/skills)的 README、技能目录、以下候选的完整 `SKILL.md`，并补读 TDD、模块设计和初始化配置的相关参考文件。本节保留调研结论；随后按用户确认安装的六项及实际状态见上方安装记录。

调查与安装版本均固定为 [`a496f5513d4a4cf889bc48e189e579f4b0bdf6aa`](https://github.com/mattpocock/skills/tree/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa)，仓库采用 [MIT 许可证](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/LICENSE)。下方技能链接均固定到此版本，不代表以后分支内容不会变化。

这些技能主要补充需求、设计、测试与排障方法，不能替代 Python 文件系统接口、FastAPI、SQLite、React 或 Canvas 的官方文档，也没有直接提供本项目的磁盘扫描器或 Treemap 实现。

### 已安装的四项工程能力

以下优先级是结合本项目阶段作出的判断。

| 候选                                  | 上游路径                             | 在本项目中的用途                                                                           | 建议                     |
| ------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------ |
| [codebase-design][mp-codebase-design] | `skills/engineering/codebase-design` | 设计扫描、任务管理、快照仓储和布局接口，隐藏平台与存储细节，避免路由和扫描逻辑耦合         | 优先，M1–M3              |
| [tdd][mp-tdd]                         | `skills/engineering/tdd`             | 通过可观察行为验证大小汇总、链接跳过、取消、快照重载及目录导航，每次完成一个可验证的小功能 | 优先，M1 起              |
| [diagnosing-bugs][mp-diagnosing-bugs] | `skills/engineering/diagnosing-bugs` | 为漏扫、重复统计、取消失效、查询变慢和 Canvas 卡顿建立可复现案例与性能基线                 | 优先，出现复杂故障时使用 |
| [domain-modeling][mp-domain-modeling] | `skills/engineering/domain-modeling` | 统一快照、扫描任务、逻辑大小、分配空间、部分完成和清理候选等术语，按需记录重要决策         | 优先，M1 前后逐步使用    |

#### codebase-design 的适配点

上游强调少量公开入口承载完整行为，并通过这些入口测试。适合封装 Windows 文件系统差异、SQLite 读写与 Treemap 布局，避免建立只转发调用的空壳层。

其 `DESIGN-IT-TWICE.md` 是用户要求比较多种接口方案时才使用的分支，会启动多个子代理；安装本体不意味着每次设计都启动并行探索。采用其设计原则时仍遵守现有 `AGENTS.md`，不为术语一致而随意改写已有项目概念。

#### tdd 的适配点

上游明确要求先与用户确认需要测试的公开接口，再编写测试；不应将“安装了 TDD 技能”理解为可以跳过这个步骤。可以在一个功能规格中统一确认扫描器、快照查询与用户交互的测试范围，避免每条测试重复讨论。

参考文件强调行为测试、独立的期望值以及在系统边界进行替换。本项目优先使用临时目录、合成文件和测试 SQLite 数据库，不扫描用户真实磁盘。其示例以 TypeScript 为主，原则可用于后端 pytest 和前端 Vitest，不需要额外引入一套测试框架。

#### diagnosing-bugs 的适配点

上游流程先建立能暴露具体故障的反馈命令，再缩小案例、验证假设、修复并清理临时日志。性能问题先测基线再修改，适合大目录扫描、批量写入和绘制性能分析。

人工参与的兜底流程引用 Bash 模板；Windows 默认优先使用 pytest、Python 脚本、HTTP 请求或浏览器自动化。需要使用该 Bash 分支时再验证 Git Bash 环境，不将其作为普通排障的前置要求。

#### domain-modeling 的适配点

上游按需维护 `GLOSSARY.md` 与 ADR，不要求先创建空文档。本项目可先澄清“文件逻辑大小之和”与“系统已用空间”的区别，以及“扫描完成”和“扫描完整”的区别。

上游默认 ADR 目录为 `docs/adr/`，本项目通过根目录 `AGENTS.md` 明确映射到 `doc/adr/`；没有新增平行文档目录，也不提前创建术语表。

### 补充能力与后续候选

| 候选                                                     | 用途与阶段                                                     | 前提或限制                                                                                       |
| -------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| [writing-for-agents][mp-writing-for-agents]              | 维护 AGENTS、技能说明及供代理读取的文档，控制重复与文档膨胀    | 已安装；遵守本项目已有文档职责                                                                   |
| [prototype][mp-prototype]                                | M3 前验证扫描状态转换、Treemap 下钻或不同界面方案              | 已安装；原型与正式代码分开，不扫描真实磁盘；仍须运行项目现有检查与测试                           |
| [setup-matt-pocock-skills][mp-setup]                     | 配置该技能体系使用的任务跟踪、术语与 ADR 位置                  | 采用完整工程工作流时加入；先展示配置草案并确认，映射到本项目 `doc/` 约定                         |
| [to-spec][mp-to-spec]                                    | 将已确认的会话整理为具体功能规格                               | 需先配置任务跟踪；原文还要求确认测试接口，随后将规格写入所选任务系统                             |
| [to-tickets][mp-to-tickets]                              | 将 `doc/PLAN.md` 中的阶段拆成可独立验收的纵向任务并记录依赖    | 需先配置任务跟踪并确认拆分；不应仅按数据库、后端、前端切成互相孤立的任务                         |
| [code-review][mp-code-review]                            | 从工程规范与需求实现两个角度审查变更                           | 明确使用两个并行子代理；需任务配置、规格来源和有效 Git 比较基准，当前仓库尚无首个提交            |
| [research][mp-research]                                  | M4–M5 调研平台统计口径、性能接口或模型能力并写入有引用的笔记   | 原文要求后台子代理；本轮只研究其内容，没有调用该技能或启动子代理                                 |
| [improve-codebase-architecture][mp-improve-architecture] | 已有实际代码后寻找耦合、重复查询和难测模块，产出可视化改进报告 | 当前骨架阶段收益有限；还会使用 codebase-design、domain-modeling、grilling 等能力，需一并核对引用 |

上游 README 建议先运行 `setup-matt-pocock-skills` 进行统一初始化。但四项基础能力的正文并非都依赖任务系统；`to-spec`、`to-tickets` 和 `code-review` 则明确要求配置。应区分“拷贝技能文件”和“配置并启用整套工作流”。

如果后续选择任务工作流，可优先考虑其本地 Markdown 方案，避免给单机项目增加外部服务；使用 GitHub Issues 或其他服务则按用户选择配置。具体路径仍待确认，不在本次调研中创建任务或发布 issue。

### 暂不建议加入

- [setup-pre-commit][mp-setup-pre-commit]：实际安装 Husky 和 lint-staged，并包含自动提交步骤。与本项目明确选定的 Python pre-commit 框架及现有检查入口不同，不重复引入。
- `git-guardrails-claude-code`：针对 Claude Code hook，不是本项目 Codex 协作或应用自身只读边界的实现。
- `setup-ts-deep-modules`：位于 `in-progress/`，会引入额外的 TypeScript 依赖边界工具，当前工程规模不需要。
- `implement-spec`、`chief-of-staff` 等执行编排技能：当前不需要引入额外的任务执行与子代理编排体系，先使用已有计划和验证入口。
- `wizard`：侧重生成 Bash 人工配置向导，与当前 Windows 本机运行方式匹配度较低。

### 安装时的约束

- 继续使用项目级 `.agents/skills/`，按表中的真实上游路径选择性安装，不能把当前嵌套目录假设为仓库根下的同名技能。
- 采用固定 commit 安装，保留许可证及引用文件；若修改文档路径、平台命令或工作流要求，记录适配差异。
- 不同时安装整套插件和重复的技能文件；本项目优先使用可审查的项目级文件。
- 安装不代表授权自动创建 issue、修改 Git remote、提交、推送或启动整个执行编排；实际操作遵循用户当次授权和项目约定。
- 一次性原型可不新增重复性测试，但项目规定的 pre-commit、现有测试、文档更新与文件清理仍须执行。

[mp-codebase-design]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/codebase-design/SKILL.md
[mp-tdd]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/tdd/SKILL.md
[mp-diagnosing-bugs]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/diagnosing-bugs/SKILL.md
[mp-domain-modeling]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/domain-modeling/SKILL.md
[mp-writing-for-agents]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/productivity/writing-for-agents/SKILL.md
[mp-prototype]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/prototype/SKILL.md
[mp-setup]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/setup-matt-pocock-skills/SKILL.md
[mp-to-spec]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/to-spec/SKILL.md
[mp-to-tickets]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/to-tickets/SKILL.md
[mp-code-review]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/code-review/SKILL.md
[mp-research]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/research/SKILL.md
[mp-improve-architecture]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/improve-codebase-architecture/SKILL.md
[mp-setup-pre-commit]: https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/misc/setup-pre-commit/SKILL.md

## 后续候选

用户确认的 9 项已全部安装。其余初始化、规格、任务拆分、审查和调研工作流技能仍仅为候选，没有安装。

后续需要扩展时再按名称确认，或继续调研其他来源。应用启动、测试和构建不依赖代理技能的运行环境。
