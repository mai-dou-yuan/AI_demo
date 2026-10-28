# Cortex · AI Second Brain

本地单用户 AI 工作台：连续对话、PDF 知识问答、会议风险与邮件、跨会话记忆、DeepSeek / Tavily 搜索、PowerPoint 生成。按《开发书.md》实现，业务数据持久保存在 `storage/`，页面展示真实接口与执行状态。

## 启动

环境已安装，无需重新初始化前端。项目根目录运行：

```bash
bash scripts/dev.sh

bash scripts/dev.sh lan
```

打开 **http://localhost:3000**，先登录再访问工作空间。首次随机账号密码仅在本机 `storage/initial-login.txt` 中，登录后必须修改密码（至少 12 位）。账号可通过 `.conda/ai-brain/bin/python scripts/account.py` 在本机重置。API 文档已关闭。详见 [登录与安全说明](登录与安全说明.md)。也可在两个终端分别运行 `bash scripts/dev.sh backend` 和 `bash scripts/dev.sh frontend`。Ctrl+C 停止本脚本启动的进程。启动脚本明确使用项目内 conda Python/Node，并优先加载环境中的 C++ 动态库，避免 PDF/ONNX/SQLite 导入顺序导致系统库版本冲突。

前端通过 Next.js `/api` rewrite 访问后端；需要更改后端地址时，在启动前设置 `BACKEND_URL`。服务仅绑定本机回环地址，无登录，适用于本地 Demo。


同一路由器访问：停止旧服务和 cloudflared 后运行 `bash scripts/dev.sh lan`。脚本自动检测私有 IPv4、更新准确的 Host/Origin 白名单并打印 `http://局域网IP:3000`；仅前端监听 0.0.0.0，后端仍为 127.0.0.1，访问仍须登录。检测失败时使用 `CORTEX_LAN_IP=你的局域网IP bash scripts/dev.sh lan`。LAN 模式会清空公网 HTTPS Origin，仅适合可信局域网 HTTP 测试；需要恢复公网访问时重新配置 AUTH_PUBLIC_ORIGIN 并重启。

## 配置

根目录 `.env` 自动由后端读取，不依赖启动时所在目录。实际密钥不放入前端，不使用 `NEXT_PUBLIC_*`。`.env` 被 gitignore 排除，示例文件 `.env.example` 不含实际密钥。

当前已按提供的密钥配置 DeepSeek 对话，接口 `https://api.deepseek.com`，模型 `deepseek-flash`（依据 [DeepSeek 当前官方文档](https://api-docs.deepseek.com/api/responses)）。配置存在不等于真实服务验证成功；当前执行沙箱无法联网，实际调用需要在本机运行检查命令。

当前默认使用 DeepSeek 官方 Search API，复用同一把 DeepSeek 聊天密钥，无需 Tavily key。Embedding 和 SMTP 仍需独立配置：

| 服务 | `.env` 字段 | 用途 |
|---|---|---|
| Chat | `CHAT_BASE_URL`、`CHAT_API_KEY`、`CHAT_MODEL` | 对话、结构化会议分析、记忆提取、PPT 大纲 |
| Embedding | `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` | PDF 和长期记忆的语义索引，按 `EMBEDDING_API_FORMAT` 选择 OpenAI 兼容或 DashScope 原生协议 |
| 联网搜索 | `SEARCH_PROVIDER=auto/deepseek/tavily` | auto 在官方 DeepSeek 地址下复用 `CHAT_API_KEY`，其他地址选择 Tavily；显式选择 Tavily 时需 `TAVILY_API_KEY` |
| SMTP | `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_FROM` | 风险邮件真实发送 |
| 白名单 | `SMTP_ALLOWED_RECIPIENTS=["you@example.com"]` | 只能发送到服务端配置的收件人 |
| 代理 | `API_PROXY=` | 空值直连；需要时填写 `http://127.0.0.1:10808` |

HTTP 请求不继承 shell 的 `ALL_PROXY`，避免 SOCKS 与 HTTP 配置冲突。SMTP 不使用 HTTP 代理。465 通常使用 `SMTP_USE_SSL=true`；587 通常使用 `SMTP_USE_SSL=false`、`SMTP_STARTTLS=true`，以邮箱服务商要求为准。修改 `.env` 后重启后端。邮件也可在「待办事项 → 邮件设置」中保存，立即生效并在重启后保留；本地 `storage/smtp-settings.json` 优先于 `.env` 中的 SMTP 字段，文件权限为 0600，包含凭据，请按密钥保管，已被 Git 忽略。API 不返回密码，编辑时密码留空保留旧值；收件人留空不发送。QQ 邮箱须在网页端开通 SMTP 并生成授权码，参见 [QQ 邮箱官方说明](https://help.mail.qq.com/detail/106/985)。保存不会发信，验证发信可点击待办的「重试邮件」。

当前 Embedding 为 `qwen3.7-text-embedding-flash`，使用独立的 Qwen key，不改变 DeepSeek Chat/Search。按提供的控制台示例配置 `EMBEDDING_API_FORMAT=dashscope`、`EMBEDDING_BASE_URL=https://cn-beijing.maas.qianwenaiapi.com/api/v1`、`EMBEDDING_BATCH_SIZE=20`。应用直接调用原生 `/services/embeddings/text-embedding/text-embedding`，请求 dense 向量并解析 `output.embeddings`，无需安装 DashScope SDK。协议字段见[百炼同步向量接口文档](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)。若以后改用 OpenAI 兼容地址，需同时设置 `EMBEDDING_API_FORMAT=openai`。地址未填时不会向默认提供方发送密钥。

```bash
# 只检查配置是否填写，不展示密钥、不调用外部服务
.conda/ai-brain/bin/python scripts/check_services.py

# 真实请求已配置的模型、Embedding、搜索，检查 SMTP 登录；不会发送邮件
.conda/ai-brain/bin/python scripts/check_services.py --live
```

对话使用兼容的 Chat Completions 接口，Embedding 支持 OpenAI 兼容与 DashScope 原生接口。结构化输出采用 JSON Schema 提示加 Pydantic 校验，无有效结构时明确失败；实际兼容性需以你的服务实测。参考 [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

## 使用

1. 对话：发送问题；新建、切换、重命名会话。SSE 展示真实模型片段和工具状态，刷新后从 SQLite 读取历史。普通聊天不自动查询整库；仅要求记住事实时不附来源；询问个人或项目记忆时检索长期记忆；选择 PDF 或提出文档/知识库问题时才检索 PDF。检索类型由意图识别决定，历史回答保持原样。
2. 知识库：上传有文字层的 PDF（20 MB、500 页以内）。解析后先把带物理页码的 UTF-8 原始文本保存到 `storage/extracted/<文件ID>.txt`，再分块、调用 Embedding 写入本地 Chroma。页面可「查看提取文本」或「下载 TXT」，用于对照原 PDF 检查提取顺序和文字完整性；导出不拼接重叠分块。Embedding 失败不影响已保存的 TXT，旧 PDF 首次访问提取文本接口会自动补生成，且不调用模型。 每份 PDF 均有「重新解析」和「删除」：重新解析保留文件 ID，重建提取文本及分块索引；删除经确认后清理原 PDF、提取 TXT、各历史模型集合中的该文件向量、分块和相关任务记录。解析中禁止这两项操作，聊天历史保留，已删除文件的历史引用链接会失效。最近任务保留重新解析前的失败记录，代表历史执行情况。回答来源同时展示 PDF 物理页码与全文连续编号的 TXT 段落范围；点击来源打开提取文本并高亮对应段落，旁边可查看 PDF。TXT 按 PyMuPDF 文本块划分、超长块拆分，不代表原稿语义段落。旧向量可本地定位补齐段号，无需重做 Embedding；已有聊天消息保留原引用，重新提问后使用新格式。「用于对话」限定文档；失败可重试。无 OCR，不支持扫描件。
3. 会议：支持多份独立会议，按标题、文件名、参会人、日期或摘要搜索，按状态筛选，选择单场或查看全部；相同内容去重。会议和失败文件均可删除，清理原文、分析、风险待办/邮件记录、该会议提取的记忆/向量及作业；分析或邮件发送中禁止删除，已发邮件无法撤回。上传 UTF-8/GB18030 TXT（60000 字以内），异步分析摘要、风险和长期事实。证据必须能在原文中定位，模糊日期保留原文。有效风险创建待办并尝试 SMTP，缺配置显示失败而不是已发送。
4. 待办：标记完成、重新打开、重试失败邮件；会议风险卡片与待办页均可删除待办及其邮件记录，保留会议原文、摘要和记忆，发送中禁止删除。文件哈希与风险键去重；已发送到某收件人的邮件不会因重试再次发送。进程在 SMTP 确认前后中断时可能存在不确定结果，重启后标为「结果待核对」，请核对邮箱后再手动重试；SMTP 不提供跨进程故障下的绝对 exactly-once 保证。
5. 记忆：支持「新建记忆」直接录入内容，人物/时间/地点/主题及原文说明可选；手动记录显示「手动录入」，不调用 LLM。原文说明留空时使用记忆内容。每条记录支持确认后删除，清理数据库记录及各历史模型集合中的该条向量，保留原始聊天/会议。人物/时间/地点/主题筛选，查看原文；新会话联合结构化与语义检索。Embedding 失败时事实仍保留在 SQLite，显示待索引，可重建；不同来源的冲突事实保留历史，不覆盖旧记录。更换 Embedding 模型/地址会使用新集合；已有 PDF 需重新索引，现版本建议先备份数据，再清空 `storage` 重新上传，勿混用向量模型。
6. 搜索：开启联网搜索，或直接询问今天/最新/近期的信息。DeepSeek 通过独立的 `POST https://api.deepseek.com/v1/tools/search` 请求获取真实网页结果，再交给聊天模型组织回答；仅调用聊天接口不会自动执行搜索。今天/今日会替换为北京时间日期，引用保留页面发布时间。错误分别显示密钥、余额、限流或网络问题。也可显式切换到 Tavily。参考 [DeepSeek Search 官方文档](https://api-docs.deepseek.com/guides/search/)。
7. PPT：生成结果可在演示文稿页删除，清理 PPTX、下载记录和对应生成作业；聊天历史保留，其中的下载链接失效。聊天中请求生成，或到「演示文稿」指定主题、5–20 页。校验五种版式、字数和页数，用 `python-pptx` 渲染可下载的 16:9 文件。数据图表要求来源说明，无真实统计则明确标为示意数据。仅明确勾选/要求时使用用户文档。

上传的 PDF、TXT、网页和引用内容均作为不可信数据传入模型；邮件收件人与文件路径完全由后端控制。模型输出不会直接执行系统命令。真实功能完成前不会用静态数据伪装结果。UI「已填写」只反映配置存在。

## 验证与样例

```bash
bash scripts/test.sh
cd frontend
npm run build
```

自动化测试使用独立临时数据库与明确的测试适配器，不调用真实外部服务；覆盖三轮历史与 checkpoint 重启恢复、真实 PDF/Chroma 页码检索、会议证据、风险去重、无风险不发信、跨会话记忆、邮件白名单与幂等、搜索/模型/PPT 失败、真实六页 PPTX 的生成与下载。**这些测试不代表 DeepSeek、Embedding、Tavily 或 SMTP 端到端验收通过。**

样例：`samples/meeting-risk.txt`、`samples/meeting-safe.txt`、`samples/project-facts.pdf`。真实验收时先填写必要配置：连续对话三轮 → 上传 PDF 查询 Aurora 上线日期及页码 → 上传风险会议并核对实际收件箱、重复上传 → 新会话问张三职责 → 搜索当天信息 → 生成六页 AI Agent PPT 并用 PowerPoint 打开。

当前验证限制：执行沙箱不允许网络与端口绑定，未验证真实服务调用，未完成浏览器与 PowerPoint 人工检查；默认 Turbopack 构建的 CSS loader 会因无法绑定内部端口失败。TypeScript 与独立 Tailwind CSS 编译可单独验证，本机仍需执行 `npm run build`。

## 项目结构

`backend/app/core.py` 配置/数据库；`providers.py` 外部 HTTP；`graph.py` LangGraph 意图→检索→工具→流式回答→记忆；`services.py` PDF/会议/记忆/邮件；`slides.py` PPT 渲染；`main.py` API/任务生命周期。checkpoint 基于 LangGraph SQLite saver，通过单用户本地适配器执行短事务；耗时网络节点使用 async。无需 Redis/Celery，进程中断的作业标为失败，可查询及重试。

`frontend/src/components/workspace.tsx` 六个工作区与 SSE；`markdown.tsx` 安全的基础 Markdown 展示（标题、列表、代码、引用、链接，不执行 HTML）；`workspace.css` 桌面三栏和移动端导航。复杂 Markdown 表格/数学公式、OCR、在线 PPT 预览、多用户登录均未实现。

运行数据在 `storage/`，退出前保留该目录可恢复。测试目录与实际运行数据隔离；备份时停止服务，再复制完整 `storage`（包含 SQLite checkpoint 与 Chroma）。
