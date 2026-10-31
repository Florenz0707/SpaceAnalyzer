# SpaceAnalyzer

Windows 优先、单机运行的只读磁盘快照分析 Web 应用。使用类似 SpaceSniffer 的矩形树图定位空间占用，并基于已保存快照与模型对话，获得人工检查建议。

## v0.1.0 发布准备

本版本已按用户授权合并到本地 idle，正在准备 v0.1.0 源码发行材料。发布说明见 [v0.1.0](doc/releases/v0.1.0.md)，功能与后续工作见 [PLAN.md](doc/PLAN.md)。用户上传版本 tag 后由 GitHub Actions 自动打包并创建 Release，见 [自动发布](doc/RELEASE-WORKFLOW.md)。

当前提供元数据扫描、SQLite 快照、后台任务与取消、历史重载、目录分页、Canvas 矩形树图及模型分析对话。构建后的前端可由 FastAPI 同源托管。DeepSeek deepseek-flash 已通过本次合成数据真实验收；本地 Ollama 适配与连通通过，但 deepseek-r1:7b 的事实判断和引用问题作为已知限制保留，不保证任意本地模型的回答质量。

## 能力与边界

- 只读扫描被分析文件的元数据，不删除、移动、重命名、改写文件或修改权限。
- 不读取文件正文、不计算内容哈希、不跟随链接或 Windows 目录联接，不自动提权。
- 默认逻辑大小；硬链接按目录项计数，快照不是文件系统原子快照，也不代表磁盘实际分配空间。
- 遗漏、错误和取消显式标记为部分快照，未知占用不作为零处理。
- 前端按需查询目录，不加载全盘树；小项及未加载项聚合显示，零字节项仍可在列表查看。
- 模型只使用快照证据，建议需要人工核对；首版固定 workflow，未开放自主工具循环或文件操作工具。
- 应用可以写入自身数据库，扫描和模型分析仅由用户主动发起。模型未配置时，扫描与可视化仍可独立使用。

## 技术与目录

前端使用 TypeScript、React、Vite 和 pnpm；后端使用 Python、FastAPI、uv 与 SQLite。

```text
backend/             应用源码、测试、Python 依赖与 uv.lock
backend/config/      模型配置模板；本地 models.toml 不提交
frontend/            React 界面、测试、前端依赖与 pnpm-lock.yaml
scripts/             PowerShell/Bash 质量检查入口
.github/workflows/   版本 tag 自动源码打包与 Release 发布
doc/                 执行计划、架构、验收证据与发布说明
.vscode/             共享编辑器设置与检查任务
AGENTS.md            项目协作约定
CHANGE.md            版本变更日志
COMPOSE.md           安装、配置、运行、构建与部署
```

## 快速开始

需要 Python 3.11+、Node.js 22.16+、pnpm 10 和 uv。在项目根目录运行：

```powershell
uv sync --project backend --frozen
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000>。输入目录后才开始扫描，启动不会自动扫描磁盘。停止服务使用 Ctrl+C。开发模式、端口和数据库配置见 [COMPOSE.md](COMPOSE.md)。

## 模型配置与对话

复制 [模型配置模板](backend/config/models.example.toml) 为 backend/config/models.toml，填写 model_id 并启用对应供应商，然后重启后端。DeepSeek API Key 只从 DEEPSEEK_API_KEY 环境变量读取，不写入 TOML。环境变量优先于本地 TOML，默认不启用任何模型。

打开快照并选择“分析此快照”，可选择模型、查看近期会话、流式提问、取消生成和展开证据；节点证据可定位到对应目录。云端会话需要明确同意，快照证据移除原始文件名与路径，但用户主动输入的文字和近期对话仍会发送。

架构与扩展边界见 [M5-DESIGN.md](doc/M5-DESIGN.md)，验证状态见 [M5-VALIDATION.md](doc/M5-VALIDATION.md)。回答中的证据引用不能证明所有自然语言结论正确，人工检查建议不等于可安全删除。

## Windows 回收站

保留卷根 $RECYCLE.BIN 中可读内容的大小。链接跳过和权限拒绝在扫描结束或取消时分别汇总，正文保留发生次数；其他错误逐条保存。普通目录中的同名文件夹不合并。

error_count 表示保存的记录数，分组中的实际条目数见正文。新快照采用扫描策略版本 2，旧快照不改写；详情见 [回收站处理](doc/RECYCLE-BIN-FIX.md)。

## 开发与检查

开发使用父目录的独立 agent-worktree 和功能分支，空闲时切回 idle。分支职责、阶段提交和只读边界见 [AGENTS.md](AGENTS.md)。在 Git 工作副本中安装 pre-commit 后执行：

```powershell
pre-commit install
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

Bash 使用 bash scripts/check.sh。完整检查覆盖已跟踪及未忽略的新文件，包含格式、lint、严格类型检查、Python 编译、后端 pytest、前端 Vitest 与生产构建。格式自动修改文件后重新运行至全部通过。

VS Code 使用项目解释器及 TypeScript SDK，编辑器设置与 CLI 一致；CLI 为最终依据。已安装的项目开发技能在本地 .agents/skills/，不包含于源码发行包，运行应用无需安装。来源和固定哈希见 [SKILLS.md](doc/SKILLS.md)。

## 已知限制

- Ollama deepseek-r1:7b 在已测样本中出现最大目录判断错误和缺少引用，不能将生成完成状态视为事实校验通过。
- Windows 的用户级环境可能覆盖系统级 DeepSeek 凭据，旧进程也可能保留旧值；启动前需确认当前终端凭据并重启后端，不打印密钥。
- 同一数据库只运行一个后端进程；会话显示最近 50 个、每会话最近 20 次运行，模型历史受预算限制。
- 首版不提供 UNC 扫描、实时监控、快照对比、重复文件内容分析、自动清理或桌面安装器。

性能证据限于已测环境和合成数据，见 [M4-VALIDATION.md](doc/M4-VALIDATION.md)。本地用户配置、数据库、截图、依赖和缓存均不包含于源码发行包。
