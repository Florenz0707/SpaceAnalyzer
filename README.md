# SpaceAnalyzer

运行在本机的只读磁盘分析 Web 应用。通过类似 SpaceSniffer 的矩形树图查看目录与文件的空间分布，后续结合大模型解释扫描结果并提供人工清理建议。

## 当前状态

M3 已接入快照工作区：扫描进度、历史列表、Canvas 矩形树图、目录下钻、分页明细、错误和只读详情。已知取消接口立即返回终态时未刷新部分快照，紧接的独立修复任务处理该问题；M4 规模验收尚待后续提交。

测试使用合成目录。公开接口与验证范围见 [M1-SPEC.md](doc/M1-SPEC.md)，执行顺序见 [PLAN.md](doc/PLAN.md)。

## 约束

- 只读访问被分析的文件系统，不提供删除、移动、重命名或修改文件的接口。
- 应用可以写入自身数据库；依赖安装、构建、测试产生的文件仅属于开发工具与应用自身工作目录。
- 默认仅扫描元数据，不读取文件正文，不计算内容哈希，不自动调用模型或外发路径信息。
- 首期采用逻辑大小，不声称等于系统显示的磁盘实际占用。
- 不跟随符号链接或 Windows 目录联接；权限不足等情况显式记录。
- 后端访问的是其所在机器的磁盘；默认仅监听回环地址。

## 技术与目录

前端使用 TypeScript、React、Vite 和 pnpm，后端使用 Python、FastAPI 和 uv。SQLite 已用于快照核心存储。开发时通过 Vite 代理访问 API。

```text
backend/             Python 依赖、API 源码、测试与 uv.lock
frontend/            前端依赖、页面源码、测试与 pnpm-lock.yaml
scripts/             PowerShell 与 Bash 质量检查入口
doc/                 详细执行计划、skills 安装记录与来源清单
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

访问 <http://127.0.0.1:5173>。详细部署步骤见 [COMPOSE.md](COMPOSE.md)。

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
