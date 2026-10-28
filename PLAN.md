# Cortex 实施记录

实现基线：[开发书.md](开发书.md)。

- [x] 本地 conda、Next.js、FastAPI、SQLite、三栏工作台、统一错误反馈与代理配置。
- [x] LangGraph SQLite checkpoint、SSE 对话、历史与会话重命名。
- [x] PDF 校验、按页分块、真实 Embedding 适配器、Chroma、本地来源查看。
- [x] TXT 编码、结构化会议与证据校验、风险待办、白名单 SMTP、去重与重试。
- [x] 来源可追溯的结构化长期记忆、语义索引与待索引恢复。
- [x] DeepSeek / Tavily 真实搜索适配器、五版式 16:9 PPTX 渲染及真实文件下载。
- [x] 后端集成测试、样例、运行脚本、配置检查工具、README。
- [x] 已提供的 DeepSeek 密钥写入后端 `.env`，不写入示例/前端。
- [ ] 填写 Embedding、SMTP 参数和收件白名单（尚未提供）；DeepSeek 搜索已复用聊天密钥配置。
- [ ] 本机真实服务六项端到端验收、浏览器响应式检查及 PowerPoint 人工打开验证。

所有真实外部服务调用仍需本机网络验证；自动化测试适配器不作为外部服务成功依据。
