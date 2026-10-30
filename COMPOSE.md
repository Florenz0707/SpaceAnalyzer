# 部署与运行

## 当前交付

M1 完成只读扫描和快照业务核心。当前 FastAPI 仍只暴露健康检查，React 仍为初始化页；HTTP 扫描和可视化在 M2、M3 接入。

## 环境与安装

需要 Windows、Python 3.11+、Node.js 22.16+、pnpm 10、uv、Git、pre-commit。各工作树独立安装依赖，不复制虚拟环境。

```powershell
uv sync --project backend --frozen
pnpm --dir frontend install --frozen-lockfile
pre-commit install
```

## 启动

两个终端分别运行：

```powershell
uv run --project backend --frozen uvicorn spaceanalyzer.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
pnpm --dir frontend dev
```

页面为 <http://127.0.0.1:5173>，健康检查为 <http://127.0.0.1:8000/api/health>。Ctrl+C 停止进程。目前不会通过页面或启动过程自动扫描用户磁盘。

## 核心存储与只读边界

`SnapshotService` 在调用方指定的应用数据库中保存任务与快照。当前 HTTP 入口尚未实例化该服务，因此启动 API 不创建快照数据库。测试仅在临时目录创建数据库和合成文件。

同一数据库只运行一个服务实例。扫描仅读取元数据，不跟随链接，排除自身数据库及辅助文件。重启会将未完成任务标记为中断；统计为逻辑大小，不等于系统已用空间。

## 检查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

Bash 使用 `bash scripts/check.sh`，Windows 使用 Git Bash。两套入口保留中文及空格路径、已有缓存配置和失败退出码。可用 `-Hook backend-tests` 或 Bash 位置参数单独调试，验收仍运行完整检查。

用户已准备合成符号链接时，可显式启用真实 Windows 集成用例：

```powershell
$env:SPACEANALYZER_TEST_SYMLINK = Join-Path $PWD '.cache/symlink-fixture/scan/link'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

未设置该变量时，依赖外部准备的符号链接用例明确 skip，不自动提权创建链接。

## 工作树与技能

开发在父目录下的独立 agent-worktree 与功能分支中进行，主目录 dev 用于运行已验收版本。每个任务完成后及时本地提交，Agent 不执行 push 或 pull。完整规范见 `AGENTS.md`。

项目技能位于本地忽略的 `.agents/skills/`，新工作树单独同步，来源与哈希见 `doc/SKILLS.md` 和 `doc/skills-lock.json`。
