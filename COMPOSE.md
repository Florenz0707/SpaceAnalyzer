# 部署与运行

## v0.1.0 交付方式

本版本按源码发行准备。可在 Windows 本机开发时运行前后端两个进程，也可构建前端后由 FastAPI 单进程提供页面与 API。不依赖 Docker Compose，容器磁盘不是用户宿主机磁盘的默认替代。

用户已授权本轮成果合并至 idle。主目录 dev 的更新与远端发布分别处理；开发工作树的本地模型配置和数据库不会自动复制到其他工作树。发布范围及已知限制见 [发布说明](doc/releases/v0.1.0.md)。

## 环境与安装

需要 Python 3.11+、Node.js 22.16+、pnpm 10 和 uv。Git、pre-commit 及项目 skills 用于开发检查，不是运行源码包的前提。以下命令在解压或检出后的项目根目录执行：

```powershell
uv sync --project backend --frozen
pnpm --dir frontend install --frozen-lockfile
```

使用锁文件安装，不混用 pip/npm/yarn。各工作树独立维护虚拟环境、node_modules 和缓存。

## 模型配置

首次使用复制模板；已有本地配置时保留原文件：

```powershell
Copy-Item backend/config/models.example.toml backend/config/models.toml
```

在 models.toml 填写 model_id，并把所需供应商的 enabled 改为 true。默认两家均关闭，不自动调用云端或下载本地模型。DeepSeek API Key 仅通过后端当前进程的 DEEPSEEK_API_KEY 环境变量提供，TOML 不接受内嵌密钥字段。

配置优先级为环境变量 > 本地 TOML > 默认值。环境中的 MODEL 值即使为空也覆盖文件，可用于显式禁用。可用 SPACEANALYZER_MODELS_FILE 指定其他 TOML，默认文件位置依据代码工作树确定，替代文件的相对路径依据启动目录确定。配置修改后重启，不做热加载，也不自动读取 .env。

| 环境变量                                 | 含义与默认值                               |
| ---------------------------------------- | ------------------------------------------ |
| SPACEANALYZER_DEEPSEEK_MODEL             | DeepSeek 模型 ID；默认不启用               |
| DEEPSEEK_API_KEY                         | DeepSeek 凭据，只在后端使用                |
| SPACEANALYZER_DEEPSEEK_CONTEXT_WINDOW    | 可选上下文声明，默认未知                   |
| SPACEANALYZER_DEEPSEEK_MAX_OUTPUT_TOKENS | 输出预算，默认 2048                        |
| SPACEANALYZER_OLLAMA_MODEL               | 已安装本地模型完整名称/标签                |
| SPACEANALYZER_OLLAMA_URL                 | 默认 `http://127.0.0.1:11434`，仅回环 HTTP |
| SPACEANALYZER_OLLAMA_CONTEXT_WINDOW      | 默认请求 8192，本地最高 65536              |
| SPACEANALYZER_OLLAMA_MAX_OUTPUT_TOKENS   | 输出预算，默认 2048                        |

当前 workflow 实际输出上限为 2048，输入上限为 24000 UTF-8 字节并预留输出及协议预算。这是保守启发式，不是精确 tokenizer；上下文不足会明确拒绝。Ollama 显式发送 num_ctx 并检查模型已声明上限，默认 8192 不保证硬件支持，也不保证任意本地模型回答准确。

DeepSeek deepseek-flash 已通过本次真实合成验收；Ollama 的适配与连通通过，但 deepseek-r1:7b 存在已知内容质量问题。模型选择与凭据由用户自行准备，应用不会自动换供应商。

## 构建与单进程运行

```powershell
pnpm --dir frontend build
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000>，健康检查为 <http://127.0.0.1:8000/api/health>，API 契约为 <http://127.0.0.1:8000/docs>。启动只初始化应用数据库，不自动扫描。用户在页面提交路径后才扫描。使用 Ctrl+C 停止。

同一数据库只启动一个后端进程，不使用多 worker。使用其他端口时直接同源访问该后端；Vite 的默认代理仍指向 8000，需要同步调整开发配置。

## 开发与生产构建预览

两个终端分别运行：

```powershell
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
pnpm --dir frontend dev
```

访问 <http://127.0.0.1:5173>。Vite 把 /api 代理到后端。生产构建预览使用 pnpm --dir frontend preview，监听 127.0.0.1:4173，也需要后端运行；开发/预览服务不作为正式单进程运行方式。

## 数据与快照口径

默认数据库是当前代码工作树的 data/snapshots.sqlite3，可通过 SPACEANALYZER_DATABASE 指定应用数据库路径。扫描排除这一数据库及其 WAL/SHM/journal 文件。数据库同时保存扫描、会话、问题、回答、证据和事件，不提交或打包到源码发行包。

快照结构版本为 SQLite user_version=1，对话结构由 chat_meta 版本 1 单独维护。新扫描使用策略版本 2，旧快照不改写。重启把遗留运行标记为中断失败，不自动续跑或付费重试。跨工作树测试使用独立数据库，勿将旧版程序直接指向新版工作数据库；需要回退时使用停止服务后的独立备份。

统计为逻辑大小，硬链接按目录项计数。首版拒绝 UNC 和根路径/祖先中的重解析点，扫描中不跟随链接、目录联接，不自动提权。回收站链接和权限遗漏分别汇总，其他错误逐条保留；不完整结果不能等同全量或零占用。

## 对话与事件

打开已结束的快照后选择分析，云端会话需要明确同意。云端证据移除原始路径和文件名，但主动输入的文字及近期对话会发送。证据卡用于核对事实，模型建议不代表可以安全删除。

全局仅一个活动分析运行，与扫描分别管理。历史显示最近 50 个会话、每会话最近 20 次运行；模型上下文另有预算。SSE GET /api/runs/{id}/events 接受 after 或 Last-Event-ID，重连不再次生成。显式取消使用 POST /api/runs/{id}/cancel，保留部分文本，但不能保证供应商立即停止计算或计费。

## 开发检查与 VS Code

在 Git 工作副本安装 pre-commit 并运行：

```powershell
pre-commit install
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

Bash 使用 bash scripts/check.sh，Windows 使用 Git Bash。两入口共用配置，保留已有缓存设置并传递失败退出码。脚本覆盖未忽略的已跟踪和未跟踪文件，包含全部测试与前端构建；格式修改后重新检查。

单项调试可用 PowerShell 的 -Hook backend-tests、-Hook frontend-tests 等参数，或 Bash 的位置参数；交付仍执行完整检查。源码归档不含 .git，运行应用不需要安装 hook；开展开发时在 Git 工作副本使用检查入口。

VS Code 选择 backend/.venv 解释器和工作区 TypeScript SDK，格式化、lint 与类型设置跟随 CLI。保存时检查不替代完整入口。共享 Windows Ruff 路径在其他平台需使用对应 .venv/bin/ruff。

用户已准备合成符号链接时可显式启用集成用例，不自动提权：

```powershell
$env:SPACEANALYZER_TEST_SYMLINK = Join-Path $PWD '.cache/symlink-fixture/scan/link'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

未设置时该外部准备用例明确 skip；本轮发布前检查显式启用了它，后端 31 项及前端 12 项通过。

## 常见问题

- 401/403：确认当前启动终端中的 DeepSeek 凭据。Windows 用户级值可能覆盖系统级值，旧终端/进程还可能保留旧值；修正后重启，不输出密钥。应用不会自动切换密钥作用域。
- Ollama 不可达：WSL 运行时先确认 Windows 端能访问配置的回环地址，模型已存在且声明 completion 能力。应用不接受远端 URL 或声明的云端模型。
- 证据或回答超限：按实际模型预算配置上下文/输出；当前仅提供明确失败，不静默截断证据。
- 缓存不可写：可设置 UV_CACHE_DIR、PRE_COMMIT_HOME、npm_config_cache 到当前工作树 .cache 下的对应目录；检查脚本已有默认值。
- 模型不可用：先查看 /api/models 的脱敏诊断，显式 POST /api/models/{key}/check 检查连接。扫描和可视化仍可使用。

## 本地发布材料

v0.1.0 准备以 git archive 导出源码 ZIP，并提供 SHA256SUMS.txt 和 RELEASE-MANIFEST.json。材料保存在忽略目录 output/releases/v0.1.0/。归档只含受 Git 跟踪的项目文件，不含本地配置、数据库、密钥、依赖、缓存或 skills；需按上述步骤安装依赖并构建，未提供桌面安装器。

实际文件摘要与提交号以归档旁的 manifest 为准。发布说明见 doc/releases/v0.1.0.md，正式标签由用户上传，包含 workflow 的版本 tag 会自动触发源码打包与 GitHub Release。

在已有 Git 工作副本中可用以下命令生成源码候选与校验值，目标目录只用于本次发布生成文件：

```powershell
New-Item -ItemType Directory -Force output/releases/v0.1.0
git archive --format=zip --prefix=SpaceAnalyzer-v0.1.0/ --output=output/releases/v0.1.0/SpaceAnalyzer-v0.1.0-source.zip idle
Get-FileHash output/releases/v0.1.0/SpaceAnalyzer-v0.1.0-source.zip -Algorithm SHA256
```

## GitHub 自动发布

.github/workflows/release.yml 在版本 tag push 时运行，自动创建源码 ZIP、SHA256SUMS.txt、RELEASE-MANIFEST.json 并发布 Release。使用 GITHUB_TOKEN 的 contents: write 权限，无需另配发布密钥。版本必须与 tag 去掉 v 一致，并准备 `doc/releases/<tag>.md` 的公开说明区段。

tag 必须包含 workflow 所在提交，已有同名 Release 不覆盖；普通分支 push 不发布。源码包不包含运行时或前端 dist。详细步骤、预发布及失败恢复边界见 [RELEASE-WORKFLOW.md](doc/RELEASE-WORKFLOW.md)。GitHub 端校验与上传尚待首次真实 tag 运行，本地完整检查仍需执行。
