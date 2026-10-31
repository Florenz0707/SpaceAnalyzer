# SpaceAnalyzer

运行在本机的只读磁盘分析 Web 应用。通过类似 SpaceSniffer 的矩形树图查看目录与文件的空间分布，后续结合大模型解释扫描结果并提供人工清理建议。

## 当前状态

当前功能分支已实现本机元数据扫描、SQLite 快照保存、后台单任务、取消与中断恢复、分页 API，以及 Canvas 矩形树图、目录下钻、排序明细、错误提示与历史快照重载。构建后的前端可以由 FastAPI 同源托管。已增加模型适配、固定证据 workflow 和流式对话；DeepSeek 本次合成验收通过，Ollama 内容验收仍有阻塞。

M1–M4 实现与工程验收已完成，包括十万合成文件、128 层目录、真实 Windows 符号链接与取消回归。当前 M5 验收工作位于 `D:/SpaceAnalyzer-agent-worktree` 的 `test/deepseek-acceptance`，已按任务分别本地提交，尚未合并至 idle/dev。已完成证据与范围边界见 [验证记录](doc/M4-VALIDATION.md)，执行顺序见 [执行计划](doc/PLAN.md)。

## 约束

- 只读访问被分析的文件系统，不提供删除、移动、重命名或修改文件的接口。
- 应用可以写入自身数据库；依赖安装、构建、测试产生的文件仅属于开发工具与应用自身工作目录。
- 默认仅扫描元数据，不读取文件正文，不计算内容哈希，不自动调用模型或外发路径信息。
- 首期采用逻辑大小，不声称等于系统显示的磁盘实际占用。
- 不跟随符号链接或 Windows 目录联接；权限不足等情况显式记录。
- 后端访问的是其所在机器的磁盘；默认仅监听回环地址。

## 技术与目录

前端使用 TypeScript、React、Vite 和 pnpm，后端使用 Python、FastAPI 和 uv。SQLite 保存快照和扫描任务。开发时通过 Vite 代理访问 API。

```text
backend/             Python 依赖、API 源码、测试与 uv.lock
frontend/            前端依赖、页面源码、测试与 pnpm-lock.yaml
scripts/             PowerShell 与 Bash 质量检查入口
doc/                 执行计划、验收与性能记录、skills 来源清单
.agents/skills/      已确认安装的项目级技能及上游引用文件
.vscode/             共享编辑器规范、扩展建议与检查任务
AGENTS.md            项目协作与代码修改约定
CHANGE.md            变更日志
COMPOSE.md           本机安装、运行、构建与故障排查
```

## 快速开始

需要 Python 3.11+、Node.js 22.16+、pnpm 10、uv、Git 和 pre-commit。以下命令在项目根目录运行：

```powershell
uv sync --project backend --frozen
pnpm --dir frontend install --frozen-lockfile
pre-commit install
```

在两个终端分别启动：

```powershell
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
pnpm --dir frontend dev
```

访问 <http://127.0.0.1:5173>。界面输入目录后才开始扫描，不自动扫描用户磁盘。也可以先执行 `pnpm --dir frontend build`，再仅启动后端，通过 <http://127.0.0.1:8000> 使用完整界面。详细步骤及数据库配置见 [COMPOSE.md](COMPOSE.md)。

## 质量检查

开发修改使用同级的独立 `SpaceAnalyzer-agent-worktree` 和功能分支，主目录的 `dev` 分支用于本地运行。分支职责、验收合并流程和提交格式见 [AGENTS.md](AGENTS.md)。

每次修改代码后必须运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

使用 Bash 时运行：

```bash
bash scripts/check.sh
```

两套脚本调用同一份 pre-commit 配置，覆盖所有未忽略的已跟踪及未跟踪文件，并执行 Prettier、markdownlint、Ruff 格式化与检查、ESLint、Pyright、Python 编译、前后端测试和 `pnpm build`。格式化修改文件后应重新运行，直到全部通过。脚本本身不使用 Python；后端检查仍使用 uv 管理的 Python 工具。

已跟踪文件也可以通过 `pre-commit run --all-files` 检查。单独执行测试：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Hook backend-tests
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Hook frontend-tests
```

## VS Code

从仓库根目录打开 VS Code，安装 `.vscode/extensions.json` 中的推荐扩展，并先安装项目依赖。共享设置使用项目内 Prettier 和 Ruff、前端 ESLint 配置、相同的 Markdown 规则及严格 Python 类型检查；Python 解释器指向 `backend/.venv`，TypeScript 使用项目 SDK。

保存时执行格式化和适用的自动修复。通过“终端 → 运行任务 → 检查：pre-commit 与全部测试”执行完整检查。编辑器诊断用于即时反馈，最终以 pre-commit 中锁定版本的 CLI 结果为准。当前 Ruff 可执行路径优先适配 Windows；其他平台需改为 `backend/.venv/bin/ruff`。

## Skills

已按用户确认将 9 个技能安装到 `.agents/skills/`：`frontend-design`、`playwright`、`security-best-practices`、`codebase-design`、`tdd`、`diagnosing-bugs`、`domain-modeling`、`writing-for-agents`、`prototype`。

使用场景、项目适配及后续候选见 [skills 文档](doc/SKILLS.md)，固定来源与文件哈希见 [skills-lock.json](doc/skills-lock.json)。技能保存在本地工作树，当前被 `.agents/.gitignore` 忽略，新工作树需单独同步，没有全局安装；新增技能在后续会话中加载。本机 Playwright CLI 的 Windows 帮助命令已验证，浏览器运行按需验证。

## Windows 回收站提示

扫描卷根的 `$RECYCLE.BIN` 或其子目录时，保留所有可读内容的逻辑大小，不跟随链接或自动提权。回收站中的链接/重解析点跳过、权限拒绝在扫描结束（含取消）时分别合并为一条提示，并显示各自实际发生次数；其他错误保留逐条记录。

存在遗漏时仍为部分快照，已读大小不代表回收站完整占用，未知占用不按零计算。`error_count` 表示保存的提示记录数，合并组中的条目数见提示正文。此策略仅适用于 Windows 卷根回收站，普通路径中的同名目录不合并。

新建快照采用策略版本 2；旧快照保持原有数据，需要重新创建快照才能应用新策略。复现与验证范围见 [回收站修复记录](doc/RECYCLE-BIN-FIX.md)。

## 快照模型分析（验收状态见记录）

打开快照后选择“分析此快照”，可在右侧面板选择模型、查看近期会话、发送问题、取消生成并展开证据。证据中的节点可定位到矩形树图对应目录。宽度不足时面板移至下方。

后端已实现 DeepSeek API 和本地 Ollama 的统一适配、固定只读证据 workflow、流式对话与历史保存。默认不启用模型，不自动下载模型或调用云端。编辑本地 `backend/config/models.toml`，首次使用可复制 [配置模板](backend/config/models.example.toml)；配置优先级和密钥设置见 COMPOSE.md。云端会话需要明确勾选外发范围，证据中的文件名和路径移除，但用户输入的文字及近期对话仍会发送。

首版只启用内置 disk-overview 分析方法，预留工具与技能契约，尚不开放模型自主工具循环。建议是人工检查候选，不代表可安全删除。模型失败不影响快照查看。已通过模拟协议、合成数据及 Chrome 端到端验证，DeepSeek 已通过本次合成数据真实验收；Ollama 连通与生成已通过，但首轮事实判断错误及缺少引用的阻塞仍保留，M5 整体验收尚未完成。详见 [Ollama 验收记录](doc/M5-OLLAMA-ACCEPTANCE.md)。架构见 [M5-DESIGN.md](doc/M5-DESIGN.md)，验证与待提供配置见 [M5-VALIDATION.md](doc/M5-VALIDATION.md)。

DeepSeek 真实验收与凭据覆盖注意事项见 [M5-DEEPSEEK-ACCEPTANCE.md](doc/M5-DEEPSEEK-ACCEPTANCE.md)。
