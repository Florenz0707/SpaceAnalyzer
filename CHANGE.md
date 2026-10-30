# 变更日志

按日期维护用户可见行为、工程规范及重要架构决策。未发布修改先写入“未发布”，正式发布时再归档版本。仅记录已实现内容，规划放入 `doc/PLAN.md`。

## 未发布

### 2026-10-30

- 约定在项目父目录的独立 agent-worktree 中开发，固定 main/dev/idle 分支职责、功能分支验收合并流程及 `[xxx] brief message` 提交格式。
- 将 `scripts/` 的 Python 编排脚本替换为 PowerShell/Bash 两套检查入口，pre-commit 直接调用项目工具；同步 VS Code 任务、类型检查范围与执行文档。
- 按用户确认安装 9 个项目级 skills，固定上游 commit，保留完整引用文件与许可证，记录文件哈希及 Windows/文档路径适配约定。
- 补充 mattpocock/skills 调研，固定调查版本，记录模块设计、TDD、故障诊断和领域建模等候选及工作流适配限制。
- 初始化 `backend/` 与 `frontend/`，分别使用 uv 和 pnpm 管理依赖并提交锁文件。
- 增加 FastAPI 健康检查、React 初始化页面及对应测试。
- 配置 pre-commit：Prettier、markdownlint、Ruff 格式化与检查、ESLint、Pyright、Python 编译、前后端测试及前端构建。
- 增加无需暂存文件即可覆盖新文件的检查脚本。
- 配置共享 VS Code 格式化、静态检查、Python 测试与检查任务。
- 增加项目说明、本机部署文档、协作约定、阶段计划与待确认 skills 清单。
- 明确被分析文件系统只读、首期使用逻辑大小、模型功能后置的边界。
