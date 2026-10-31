# Tag 自动发布 workflow

## 触发与输出

.github/workflows/release.yml 监听版本 tag 的 push，分支提交不触发，删除 tag 不发布。用户上传包含本 workflow 的提交对应 tag 后，GitHub Actions 自动打包并创建 GitHub Release；本地开发操作不主动推送或发布。

支持 vMAJOR.MINOR.PATCH，以及 vMAJOR.MINOR.PATCH-rc.1 等 SemVer 预发布格式，不接受前导零或构建元数据。预发布 tag 自动使用 prerelease 标记。

发布附件为：

- `SpaceAnalyzer-<tag>-source.zip`：git archive 导出的跟踪源码，带版本目录前缀。
- SHA256SUMS.txt：源码 ZIP 和发布清单的 SHA-256。
- RELEASE-MANIFEST.json：tag、版本、实际提交、归档摘要、打包校验和 workflow 运行链接。

这是源码发行包，不包含 Python/Node 运行时、安装好的依赖或前端构建产物，使用者仍按 COMPOSE.md 安装和构建。不调用模型、不扫描磁盘、不携带本地数据库或凭据。

## 发布前准备

1. 在待发布提交中更新 frontend/package.json、backend/pyproject.toml 和 FastAPI 的版本，三者必须等于 tag 去掉 v 的文本；依赖锁文件仍按 AGENTS.md 同步并完整检查。
2. 创建对应 `doc/releases/<tag>.md`，并提供以下公开说明区段：

```markdown
<!-- github-release:start -->

发布功能、安装方式和已知限制。

<!-- github-release:end -->
```

1. 运行 scripts/check.ps1 或 scripts/check.sh，通过全部检查后由用户创建、上传 tag。

workflow 从公开说明区段生成 Release 正文，将相对文档链接转换为对应 tag 的 GitHub 源码链接。区段外保留本地候选状态、操作记录等内容，避免它们出现在已发布正文中。缺少文件、区段或链接目标都会使发布失败。

首次发布 v0.1.0 时，tag 必须指向包含本次 workflow 和公开说明标记的提交；此前本地候选 ZIP 不被 workflow 读取，GitHub 端会从 tag 重新归档。

## 校验与权限

打包前验证 tag 格式、三个版本、发布说明和跟踪文件范围。若本地配置、环境文件、数据库、依赖、构建目录或 skills 被意外强制提交，拒绝打包；归档随后执行 CRC 校验并生成摘要。

发布 job 仅授予 contents: write，使用自动 GITHUB_TOKEN，不需要另配 PAT。checkout 固定为 actions/checkout v6.0.3 的完整 commit SHA，不持久化 Git 凭据。仓库/组织策略需要允许 Actions 和对应权限。

创建 Release 前查询远端 tag 当前提交，与打包提交不一致则停止。gh release create 使用 --verify-tag，避免创建不存在的 tag，并一次提交三个附件和发布说明。GitHub CLI 会先上传附件再发布；见 [官方 create 文档](https://cli.github.com/manual/gh_release_create)。tag push 触发依据见 [GitHub 事件文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)。

同一 tag 的运行串行，后续触发不会取消上传中的运行。已有同名 Release 时保留 CLI 的失败结果，不覆盖或删除发布内容。上传失败可能留下草稿，应先人工核对草稿/附件再处理，不通过重打 tag 或覆盖资产掩盖失败。

workflow 只执行版本、归档和发布校验，不代替开发约定的完整 pre-commit，也不会把本地测试结果伪装为 GitHub 已运行的检查。

## 本地验证与实际运行限制

本次使用 actionlint 1.7.7 校验实际 workflow，并在隔离 Git 合成仓库执行 workflow 内的 Bash/Node 逻辑。13 类检查通过：触发和权限、Bash 语法、正式版归档/校验和、私有文件排除、正文区段/链接、发布参数、远端 tag 移动拒绝、同名 Release 失败、非法 tag、版本错配、缺少说明、预发布标记、误跟踪私有文件拒绝。

本地 gh 使用无网络替身，仅记录发布调用，不访问或发布真实 Release。正式 GitHub runner、仓库权限和真实附件上传仍待用户第一次上传 tag 验证。完整项目检查仍包含后端 31 项、前端 12 项及生产构建。
