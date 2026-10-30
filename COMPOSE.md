# 部署与运行

## 部署方式

首期采用 Windows 本机双进程：Python API 访问本机文件系统，浏览器通过 Vite 开发服务访问页面。当前无需 Docker Compose；容器只能看到挂载进去的路径，不作为本机磁盘扫描的默认运行方式。

本文件名按项目约定保留为 `COMPOSE.md`，内容描述实际支持的运行方式。后续单进程托管前端静态资源尚未实现。

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

主目录 `D:/SpaceAnalyzer` 使用 `dev` 分支保存本地运行版本；开发修改在同级 `D:/SpaceAnalyzer-agent-worktree` 的功能分支中进行，空闲时该工作树检出 `idle`。`main` 跟踪远端主分支。具体流程见 `AGENTS.md`。

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

当前不提供安装包、开机启动、远程部署或容器镜像。后续交付计划是在不引入外部服务的前提下由 FastAPI 托管构建产物。

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

当前阶段不创建应用数据库。后续数据库默认位于项目自身 `data/` 目录，自动排除自身数据库及辅助文件，不提交数据库、真实磁盘快照或绝对路径日志。

始终以普通用户运行。无法访问的目录由后续扫描器记录为错误，不通过提权或修改 ACL 绕过。对被分析内容不执行写入操作。模型服务与凭据尚未接入。

## 常见问题

- 命令找不到：确认 Python、uv、pnpm、pre-commit 均在 PATH，重新打开终端。
- npm 全局缓存不可写：可在当前终端设置 `$env:npm_config_cache = "$PWD/.cache/npm"`。
- uv 缓存不可写：可设置 `$env:UV_CACHE_DIR = "$PWD/.cache/uv"`；检查脚本默认使用此项目缓存。
- pre-commit 缓存不可写：可设置 `$env:PRE_COMMIT_HOME = "$PWD/.cache/pre-commit"`；统一检查脚本已设置默认值。
- hook 报依赖缺失：先运行依赖安装命令；所有 hook 使用项目依赖，不自动临时下载检查器。
- 格式化反复变动：确认 VS Code 使用项目 Prettier、Ruff 与共享 Markdown 配置，停用工作区中冲突的格式化器。
- 端口占用：停止已有进程，或同步调整启动参数和 `frontend/vite.config.ts` 的代理配置。
