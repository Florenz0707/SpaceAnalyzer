# 部署与运行

## 部署方式

支持 Windows 本机开发双进程和构建后的单进程运行：开发时通过 Vite 代理访问 API，构建后由 FastAPI 同源托管前端。当前无需 Docker Compose；容器只能看到挂载路径，不作为本机磁盘扫描的默认运行方式。

本文件名按约定保留为 `COMPOSE.md`。本轮功能位于 `D:/SpaceAnalyzer-agent-worktree` 的 `feat/model-workflow`，包含 M1–M4 及 M5 对话实现；M5 真实模型联调待用户配置，已按任务分别本地提交，尚未合并至主目录 dev；体验本轮功能时应先进入该工作树。

## 环境要求

| 工具       | 要求                                                               |
| ---------- | ------------------------------------------------------------------ |
| 系统       | 首期 Windows，普通用户权限                                         |
| Python     | 3.11+，开发默认 3.11                                               |
| Node.js    | 22.16+，建议使用受支持的 LTS 版本                                  |
| pnpm       | 10.x，`packageManager` 固定为 10.26.1                              |
| uv         | 支持 dependency groups 和 `uv.lock`，初始化使用 0.9.18             |
| pre-commit | 4.x，本机已安装                                                    |
| Git        | 用于本地 hooks 与检查文件发现                                      |
| 检查脚本   | Windows PowerShell 5.1+ 或 Bash；Windows 的 Bash 入口使用 Git Bash |

不需要管理员权限或外部数据库。首次安装依赖需要网络。

## 安装

主目录 `D:/SpaceAnalyzer` 使用 `dev` 分支保存本地运行版本；开发修改在同级 `D:/SpaceAnalyzer-agent-worktree` 的功能分支中进行，空闲时该工作树检出 `idle`。`main` 保存用户手动同步的远端主分支基线；Agent 不执行 push 或 pull。具体流程见 `AGENTS.md`。

每个工作树独立安装依赖，不复制其他工作树的 `.venv` 或 `node_modules`。本地忽略的 `.agents/skills/` 不会随 `git worktree add` 自动复制；需要同步既有技能并核验 `doc/skills-lock.json`，或按清单的固定版本安装。

从仓库根目录执行：

```powershell
uv sync --project backend --frozen
pnpm --dir frontend install --frozen-lockfile
pre-commit install
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

`--frozen` 和 `--frozen-lockfile` 保证使用已锁定依赖；只有明确更新依赖时才不使用这些选项。工具缓存和虚拟环境属于可再生文件，不提交到仓库。

## 开发启动

终端一：

```powershell
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000 --reload
```

终端二：

```powershell
pnpm --dir frontend dev
```

- 页面：<http://127.0.0.1:5173>
- 健康检查：<http://127.0.0.1:8000/api/health>
- API 文档：<http://127.0.0.1:8000/docs>

Vite 将 `/api` 请求代理到 `127.0.0.1:8000`，无需放开任意来源的 CORS。开发服务固定 5173，端口占用时直接报错。通过各终端的 Ctrl+C 停止进程。

## 构建与本地预览

```powershell
pnpm --dir frontend build
pnpm --dir frontend preview
```

构建产物位于 `frontend/dist/`，预览固定监听 <http://127.0.0.1:4173>，同样将 `/api` 代理到 `127.0.0.1:8000`，因此需要后端进程保持运行。预览用于检查静态构建，不能将开发或预览服务视为生产部署方案。

当前不提供安装包、开机启动、远程部署或容器镜像。构建产物已可由 FastAPI 托管，无需额外前端进程。

## 单进程本机运行

先在功能工作树根目录安装依赖并构建，然后启动一个后端进程：

```powershell
pnpm --dir frontend build
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000>。输入本机绝对目录路径或盘符根目录，点击“创建快照”；扫描结束后可下钻、返回、查看详情与遗漏记录。刷新或重启后可从快照列表重新打开，旧快照不会隐式重新扫描。

首期拒绝 UNC、扫描根及其祖先中的链接/重解析路径；硬链接按目录项累计逻辑大小。扫描中的文件变化、权限和平台覆盖限制见 `doc/M4-VALIDATION.md`。目录选择目前通过路径输入完成，不提供系统目录浏览器。

同一个数据库只运行一个后端实例，不配置多进程 workers。`queued` 或 `running` 的遗留任务在下次启动时标记为中断失败；正常关闭会请求取消并等待任务释放资源。对失败、取消和有错误的快照显示部分快照提示，不将其视为完整结果。

静态文件来自 `frontend/dist/`，未知 API 保持 JSON 404，页面路由可回退到 index，缺失 JS/图片等资源不会回退为 HTML。对外仅使用回环监听，API 校验本机 Host/Origin；不要将其作为远程共享服务部署。

## 检查与编辑器

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

使用 Bash 时运行：

```bash
bash scripts/check.sh
```

Windows 如果 PATH 中的 `bash` 指向 WSL 启动器，可在 PowerShell 中显式使用 Git Bash：

```powershell
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

两套入口都可以从其他工作目录调用，会根据脚本位置定位仓库根目录，保留包含空格或中文的文件名，并传回 pre-commit 的退出码。它们设置项目缓存的默认值，同时保留用户已有缓存环境变量；PowerShell 入口结束时恢复环境变量和当前目录。

完整检查包含两个测试套件和前端构建，不会触发用户磁盘扫描。格式化 hook 修改文件时首次返回失败是正常行为；确认修改后重新运行。pre-commit 直接调用锁定的项目工具，脚本无需 Python 编排层；后端测试和编译仍需要 Python。

单独运行检查时，PowerShell 使用 `-Hook <hook-id>`，Bash 使用位置参数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Hook backend-tests
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Hook frontend-tests
```

```bash
bash scripts/check.sh backend-tests
bash scripts/check.sh frontend-tests
```

其他可选 hook ID 见 `.pre-commit-config.yaml`。单项检查用于调试，代码修改后的验收仍执行完整检查。

VS Code 从根目录打开项目，安装推荐扩展，选择 `backend/.venv` 中的解释器及工作区 TypeScript 版本。检查和测试任务在 Windows 调用 PowerShell，其他平台调用 Bash。保存时格式化不替代上述完整检查。

## 项目级 skills

9 个已确认技能安装在各工作树的 `.agents/skills/`，无需全局安装。该目录当前由本地 `.agents/.gitignore` 忽略，需要在新工作树单独同步。固定来源、许可证、使用限制和 Windows CLI 验证方式见 [doc/SKILLS.md](doc/SKILLS.md)，文件哈希见 [doc/skills-lock.json](doc/skills-lock.json)。新增技能将在后续会话中加载。

Playwright 技能文件安装不等同于浏览器安装；目前仅验证了固定版本 CLI 的帮助入口，实际浏览器运行在需要时另行验证。技能运行环境与应用部署依赖分开维护。

## 数据与权限

数据库默认位于当前代码工作树的 `data/snapshots.sqlite3`，服务启动时创建或迁移，但不自动扫描。可在启动前设置 `SPACEANALYZER_DATABASE` 为自己的应用数据库绝对路径；扫描自动排除这一个数据库及其 WAL/SHM/journal 文件。数据库和快照不提交到 Git。

```powershell
$env:SPACEANALYZER_DATABASE = 'D:\SpaceAnalyzer-agent-worktree\data\snapshots.sqlite3'
```

始终以普通用户运行。无法访问的目录由后续扫描器记录为错误，不通过提权或修改 ACL 绕过。对被分析内容不执行写入操作。模型服务与凭据尚未接入。

## 常见问题

- 命令找不到：确认 Python、uv、pnpm、pre-commit 均在 PATH，重新打开终端。
- npm 全局缓存不可写：可在当前终端设置 `$env:npm_config_cache = "$PWD/.cache/npm"`。
- uv 缓存不可写：可设置 `$env:UV_CACHE_DIR = "$PWD/.cache/uv"`；检查脚本默认使用此项目缓存。
- pre-commit 缓存不可写：可设置 `$env:PRE_COMMIT_HOME = "$PWD/.cache/pre-commit"`；统一检查脚本已设置默认值。
- hook 报依赖缺失：先运行依赖安装命令；所有 hook 使用项目依赖，不自动临时下载检查器。
- 格式化反复变动：确认 VS Code 使用项目 Prettier、Ruff 与共享 Markdown 配置，停用工作区中冲突的格式化器。
- 端口占用：停止已有进程，或同步调整启动参数和 `frontend/vite.config.ts` 的代理配置。

## 回收站错误汇总

重新启动本轮修复后的后端，再创建新快照以使用策略版本 2。无需迁移数据库结构；已保存的策略版本 1 快照不会重写。回收站可读内容继续计入占用，链接与权限遗漏分别在扫描结束或取消时汇总，未知占用保持不完整标记，不修改系统权限。

错误列表展示保存的记录数量：例如 100 次链接跳过与 4 次权限拒绝显示为两条汇总，正文保留 100 和 4。扫描期间汇总尚未写入；其他类型错误仍按原方式展示。普通目录中的同名文件夹不应用该规则。

## M5 模型配置（尚待真实联调）

后端默认读取当前代码工作树中的 `backend/config/models.toml`。仓库提供 `backend/config/models.example.toml` 模板，本轮已在 agent-worktree 创建禁用状态的本地配置。其他工作树首次使用时复制模板：

```powershell
Copy-Item backend/config/models.example.toml backend/config/models.toml
```

编辑本地文件中的 `model_id`，将对应 `enabled` 改为 true，再重启后端。Ollama 地址和上下文预算也在同一文件配置。DeepSeek API Key 仍只从后端环境变量 `DEEPSEEK_API_KEY` 读取，配置文件不允许内嵌密钥字段。

优先级为：环境变量 > 本地 TOML > 默认值。已有环境变量可以覆盖文件中的模型选择与预算；将对应 MODEL 环境变量设为空可显式禁用条目。可通过 `SPACEANALYZER_MODELS_FILE` 指定其他 TOML 路径；相对路径相对于启动目录。修改配置需要重启，不做热加载。本地 `models.toml` 被 Git 忽略，模板随仓库提交；不提交用户模型选择或密钥。非法 TOML 给出脱敏诊断，仍允许扫描运行。

也可以继续使用环境变量：后端读取 `SPACEANALYZER_DEEPSEEK_MODEL` 与 `DEEPSEEK_API_KEY`，以及 `SPACEANALYZER_OLLAMA_MODEL`、可选的 `SPACEANALYZER_OLLAMA_URL`（默认 `http://127.0.0.1:11434`）。密钥只保留在后端进程环境，不发给前端或写入数据库。默认不配置任何模型，不自动调用付费接口或下载模型。

Ollama 仅允许回环 HTTP 地址与本地 completion 模型，拒绝已声明的云端模型；实际联网与模型能力仍需集成测试。无效配置只禁用对应条目，不影响扫描。调整环境变量后重启后端。实际配置由用户在真实联调阶段准备，禁止在聊天、文档或 Git 中填写密钥。

模型预算使用 `SPACEANALYZER_OLLAMA_CONTEXT_WINDOW`（默认请求 8192）、`SPACEANALYZER_OLLAMA_MAX_OUTPUT_TOKENS`（默认 2048），DeepSeek 对应变量为 `SPACEANALYZER_DEEPSEEK_CONTEXT_WINDOW`（默认未知）和 `SPACEANALYZER_DEEPSEEK_MAX_OUTPUT_TOKENS`（默认 2048）。本轮 workflow 单次实际输出上限为 2048，并限制输入至 24000 UTF-8 字节预算，预留输出与协议开销；这是保守应用预算，不是精确 tokenizer 计数。小上下文模型可能因证据超预算被明确拒绝，不静默截断。

Ollama 请求显式发送 num_ctx，默认 8192 是应用请求值，不代表已确认模型或硬件支持。根据实际模型和内存调整，本地最大允许 65536；模型详情声明更小上限时拒绝请求。真实联调前需确认模型名称、Ollama 地址和可用上下文窗口。

M5 对话与快照保存在同一应用数据库中，chat_meta 单独维护对话结构版本，不改变快照 schema 版本。对话含问题、回答、证据和使用量，数据库仍作为本地用户数据排除 Git。每个数据库仅运行一个后端实例，重启后的未完成分析标记为中断失败，不自动重试。

在当前终端设置并替换模型名称后启动后端；应用不自动读取 .env 文件：

```powershell
$env:SPACEANALYZER_OLLAMA_MODEL = '<本地已安装的模型名称>'
$env:SPACEANALYZER_OLLAMA_CONTEXT_WINDOW = '8192'
$env:SPACEANALYZER_DEEPSEEK_MODEL = '<DeepSeek API 模型 ID>'
# DEEPSEEK_API_KEY 由用户在本机当前终端设置，勿贴到聊天或提交仓库。
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000
```

可以只配置其中一家供应商；未安装 Ollama 模型时请自行准备，应用不自动拉取。配置错误在 `/api/models` 中返回脱敏诊断。显式 POST `/api/models/{key}/check` 可以检查连接，真正生成仍需合成快照上的联调。

对话事件 GET `/api/runs/{id}/events?after=<序号>` 返回 SSE，也接受 Last-Event-ID。断线重连只重放已保存事件；显式取消调用 POST `/api/runs/{id}/cancel`。上游是否立即停止计算或计费不能由本地取消保证。首版不自动重试生成；失败后用户再次提交使用新的请求键。
