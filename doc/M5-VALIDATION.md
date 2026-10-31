# M5 验证状态

## 当前结论

2026-10-31：M5.1–M5.6 的实现、自动测试及模拟浏览器验证完成。真实供应商结果如下：

| 供应商与模型              | 状态                                                     | 证据                                           |
| ------------------------- | -------------------------------------------------------- | ---------------------------------------------- |
| DeepSeek deepseek-flash   | 本次合成验收通过；常规启动前仍需修正旧凭据覆盖           | [DeepSeek 验收记录](M5-DEEPSEEK-ACCEPTANCE.md) |
| WSL Ollama deepseek-r1:7b | 连通与生成通过，首轮事实判断错误且缺少引用，内容验收阻塞 | [Ollama 验收记录](M5-OLLAMA-ACCEPTANCE.md)     |

2026-10-31 发布决定：用户已授权合并到 idle 并准备 v0.1.0，Ollama 内容问题作为已知质量限制保留。DeepSeek 结果不覆盖该失败，也不保证模型对任意数据的回答正确；本次发布范围见 [v0.1.0](releases/v0.1.0.md)。

## 工程检查

```powershell
$env:SPACEANALYZER_TEST_SYMLINK = Join-Path $PWD '.cache/symlink-fixture/scan/link'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

后端 31 项 pytest、前端 12 项 Vitest、严格 Pyright、ESLint、格式检查、Python 编译与生产构建通过。每阶段独立本地提交，格式修改后重新检查，没有跳过失败 hook。自动测试只使用临时目录、合成数据和模拟供应商，不自动调用付费接口。

覆盖模型注册与能力校验、TOML 与环境变量优先级、配置脱敏、DeepSeek/Ollama 分片协议、只读证据、快照归属、上下文预算、幂等与互斥、取消、引用校验、持久化、中断恢复、事件重放和前端交互。

## 浏览器与真实生成

早期模拟验证使用隔离 FastAPI、构建后的 React、合成快照及无网络模型。覆盖生成、证据导航、刷新、取消、云端确认和响应式布局，截图在 output/playwright/m5/，结构化结果见 benchmarks/m5-browser.json。

随后真实 DeepSeek 测试验证了相同链路中的实际生成，并补充多轮比例计算、云端请求脱敏、部分快照及后端重启恢复。截图在 output/playwright/m5-deepseek/。两次浏览器记录均为 Chrome 控制台 0 errors / 0 warnings。

Ollama 在首轮内容错误时按用户要求停止，其真实多轮、取消与浏览器验收未继续；不能用模拟或 DeepSeek 的通过替代。

## 配置与剩余事项

本地配置为 backend/config/models.toml，模板随仓库提交；API Key 只放后端环境。此次发现进程/用户级 DeepSeek 凭据返回 401，而系统级凭据有效。隔离验收临时使用后者，没有自动修正持久环境；正常后端需要用户处理覆盖并重启。

Ollama 的事实与引用约束修复方向尚待用户决定。工具自主循环、动态第三方 skill、长时间压力测试和其他硬件/模型版本不属于本轮已验证范围。
