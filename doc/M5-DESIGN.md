# M5 模型分析与对话架构

## 目标与实现范围

基于已保存快照解释空间分布并给出人工检查候选。首版采用固定 workflow，接入 deepseek_api 与本机 ollama，保留工具和技能扩展契约；不提供清理操作、任意 Shell、SQL 或实时磁盘访问。

ModelAdapter 定义生成事件和连接检查两个入口；ModelRegistry 显式注册 ModelSpec，按稳定 key 解析并校验 ModelCapacity。workflow 不处理供应商原始响应，适配器不执行查询工具、不管理会话历史。

## 模型能力与供应商

ModelCapacity 声明文本、流式、工具调用、结构化输出、推理、上下文与输出上限。首版启用文本及流式，其余保守声明为未启用；请求工具、推理或结构化输出会明确拒绝，不偷偷丢弃参数。能力声明不是模型质量保证，也不是自动发现所有能力。

DeepSeekAdapter 使用 Chat Completions SSE，关闭思考模式，处理 finish_reason、用量与 DONE，统一鉴权、限流、超时及协议错误。错误不回传原始供应商正文或凭据。模型 ID 由配置指定，不写死已过时名称。依据：[官方 Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)。

OllamaAdapter 使用原生 NDJSON，先查询模型详情，要求 completion 能力并拒绝已声明云端模型；仅允许回环 HTTP，不跟随重定向、不使用环境代理。显式发送 num_ctx 与 num_predict，校验模型详情已声明的上下文上限。依据：[官方 Chat](https://docs.ollama.com/api/chat)。实际安装版本与模型仍需联调。

所有配置在后端加载：环境变量覆盖 backend/config/models.toml，未设置项使用默认值；提供可提交模板及 Git 忽略的本地文件。API Key 只允许环境变量，不允许写入 TOML。空配置允许扫描继续运行，非法条目给出脱敏诊断。没有自动供应商回退或模型下载。云端密钥只放后端环境，目录接口不返回地址、请求头或密钥。

## 固定分析与证据

运行步骤为校验绑定配置、读取五类证据、构建有限上下文、生成文本、校验证据引用、持久化终态。五类查询是概览、根目录子项、最大文件、扩展名分布及错误分组；节点详情用于证据导航。每次查询最多返回 20 项，不加载全树，不读取文件内容。

所有 SQL 位于 storage/analysis.py，参数校验及白名单位于 analysis/evidence.py。工具参数没有任意路径或 SQL，快照 ID 来自当前会话。错误统计是保存的记录数；回收站分组不等于受影响条目数量。

证据以 E1–E5 标识，保留快照和查询来源。前端展示事实与节点链接，模型引用可跳转到对应证据。无效引用使回答标记失败，缺少引用显示人工核对提示；引用存在不能证明模型解释正确。不能依据文件名判断可安全删除，也不能叠加父子目录大小估计释放空间。

云端证据投影移除路径、名称及原始错误文本；用户问题和近期对话仍会发送，创建云端会话要求明确同意。目录中的指令式文件名属于不可信数据，不能改变工具权限。部分快照继续保留未知占用说明。

输入限制为至多 24000 UTF-8 字节，并预留配置输出及协议预算；这是保守启发式，不冒充 tokenizer 精确计数。历史只保留预算内最近至多三对已完成问答，失败和未完成回答不进入模型历史。超限明确失败，不静默截断证据。

## 工具与技能扩展

ModelRequest 预留 ToolDefinition，ModelEvent 预留完整工具调用及参数记录。首版适配器不发送工具定义，也不执行模型工具调用；未来需要补齐参数分片、关联 ID、多轮回传和调用预算后才能启用 agent loop。

SkillDefinition 声明版本、目标、能力及工具范围。当前唯一内置 skill 为 disk-overview；EvidenceBuilder 的白名单执行其固定查询。未实现动态 SkillRegistry、第三方技能安装或自主技能选择，不加载仓库 .agents/skills，也不从扫描目录读取指令。

## 会话、存储与事件

会话固定绑定快照、模型配置和云端授权。配置中的供应商或模型 ID 改变后要求新建会话。API 为模型目录及连接检查、会话创建/列表、运行历史、运行创建/详情/取消、节点详情、SSE 事件。

SQLite 共用现有应用数据库，对话表使用独立 chat_meta 版本。问题、回答、证据和用量随 analysis_runs 保存，消息历史由运行投影，不建立重复 messages 表。analysis_events 保存单调序号，状态与事件同事务。文本增量分批写入，以限制 SQLite 写放大。

全局仅一个活动分析运行，与扫描任务分别管理。相同会话和 request_key 幂等；重复键对应不同问题会拒绝。重连使用 after 或 Last-Event-ID，不重新生成。列表限制最近 50 个会话、每会话最近 20 次运行；当前 UI 明确限制近期历史，不承诺完整历史分页。

取消保留部分文本并停止本地请求，不能保证上游立即停止计费。进程启动将遗留运行标记失败，不自动续跑；没有自动付费重试。模型错误不删除快照或影响可视化。

## 模块与验证接口

analysis/models/ 是供应商适配层；analysis/workflow.py 管理执行；analysis/evidence.py 管理可信查询和上下文；storage/analysis.py 与 storage/conversations.py 负责 SQL；api/chat.py 提供路由；frontend/features/chat/ 管理对话。仅为实际功能建立文件，未提前创建空的 tools/ 或 skills/ 目录。

测试通过 Registry/Adapter、EvidenceBuilder、AnalysisWorkflow、HTTP 与 React 用户交互验证。供应商协议使用模拟 HTTP 分片；端到端浏览器使用合成快照与无网络模拟模型。真实模型联调另行进行，不把模拟通过视为供应商验收。
