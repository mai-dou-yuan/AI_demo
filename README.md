<h1 align="center">Cortex</h1>
<p align="center"><strong>你的知识、记忆与行动，始终在线。</strong></p>
<p align="center">个人 AI 工作空间 · 知识库问答 · 会议洞察 · 长期记忆 · 办公自动化</p>
<p align="center">
  <a href="#界面与功能">界面与功能</a> &nbsp; / &nbsp;
  <a href="#快速开始">快速开始</a> &nbsp; / &nbsp;
  <a href="#文档">项目文档</a>
</p>

---

Cortex 将对话、资料、记忆与待办连接在一个工作空间中：上传 PDF，带着来源回答问题；导入会议纪要，提炼行动与风险；让重要事实在下一次对话中继续发挥作用。

**Next.js · FastAPI · LangGraph · SQLite · Chroma**

## 界面与功能

<!-- CORTEX_SCREENSHOTS_START -->

![Cortex 工作空间首页](截图/办公智能体首页.png)

<p align="center"><sub>六个工作区，一个入口。对话、资料与上下文在同一屏中连接。</sub></p>

> **📷 点击下方蓝色标题，查看对应的完整界面截图。**

### 🔹 [01 · 对话与联网搜索](截图/对话-联网查询.png)

结合搜索结果回答问题，保留参考来源。　[查看完整截图 ↗](截图/对话-联网查询.png)

### 🔹 [02 · PDF 知识库](截图/pdf解析-RAG知识库.png)

管理文档、查看提取文本，按 PDF 页码与 TXT 段落追溯出处。　[查看完整截图 ↗](截图/pdf解析-RAG知识库.png)

### 🔹 [03 · 会议分析](截图/会议纪要-分析风险.png)

提炼摘要、决定与行动项，识别需要跟进的风险。　[查看完整截图 ↗](截图/会议纪要-分析风险.png)

### 🔹 [04 · 长期记忆](截图/长期记忆.png)

保存明确事实，按人物、时间、地点与主题检索。　[查看完整截图 ↗](截图/长期记忆.png)

### 🔹 [05 · 待办与邮件](截图/代办事项-发送邮件.png)

跟进责任人与期限，配置邮箱并发送风险提醒。　[查看完整截图 ↗](截图/代办事项-发送邮件.png)

### 🔹 [06 · 演示文稿](截图/PPT生成.png)

输入主题，生成并下载真实的 PowerPoint 文件。　[查看完整截图 ↗](截图/PPT生成.png)

<!-- CORTEX_SCREENSHOTS_END -->

## 快速开始

运行环境：**Linux · Python 3.11 · Node.js 24 · Conda**。

> **首次安装？点击下方「首次使用」展开完整步骤。已有环境可直接运行启动命令。**

<details>
<summary><h3>🔹 首次使用：安装依赖并准备配置　<sub>点击展开步骤</sub></h3></summary>

在项目根目录执行，无需重新创建前端项目：

```bash
conda create --prefix ./.conda/ai-brain -c conda-forge python=3.11 nodejs=24 pip -y
conda activate "$PWD/.conda/ai-brain"
python -m pip install -r requirements.lock.txt
cd frontend
npm ci
cd ..
cp -n .env.example .env
chmod 600 .env
```

编辑本地 `.env` 配置聊天模型、Embedding 和搜索服务。聊天与 Embedding 的凭据独立配置，字段说明见 [.env.example](.env.example)。

完整安装步骤与镜像源选择见 [安装书](安装书.md) 和 [服务器迁移说明](服务器迁移安装说明.md)。

</details>

启动工作空间：

```bash
bash scripts/dev.sh
```

打开 **http://localhost:3000**。首次启动后，在另一终端查看随机登录凭据；登录后必须修改密码：

```bash
cat storage/initial-login.txt
```

<details>
<summary><strong>🔹 局域网访问与常用命令 · 点击展开</strong></summary>

```bash
# 同一路由器访问：停止旧服务后执行，使用终端打印的地址
bash scripts/dev.sh lan

# 在服务器终端重置登录账号或密码
.conda/ai-brain/bin/python scripts/account.py

# 检查配置，不调用外部服务
.conda/ai-brain/bin/python scripts/check_services.py

# 业务、安全回归测试与前端类型检查
bash scripts/test.sh
```

LAN 模式使用 HTTP，会清空公网 HTTPS Origin，仅适合可信局域网临时访问。按需对局域网放行 `3000/TCP`，不开放后端 `8000`。

邮件在「待办事项 → 邮件设置」配置；支持填写发件邮箱、SMTP 授权码和收件人。

</details>

## 数据与部署

业务记录与文件保存在本机 `storage/`；启用模型、Embedding、搜索和邮件时，所需内容会发送到对应外部服务，**并非完全离线运行**。

当前采用单账号、单进程部署，业务 API 与下载接口统一鉴权。`.env` 和运行数据不提交 Git；本地密钥文件未做磁盘级加密。公网运行需使用生产构建、HTTPS 和入口访问控制，详见 [登录与安全说明](登录与安全说明.md)。

<details>
<summary>当前使用边界</summary>

- PDF 需要文字层，尚未启用 OCR。
- 聊天采用最近消息窗口与长度截断，尚未实现自动上下文压缩。
- 服务重启后，中断的后台任务需要手动重试。
- 邮件发送给配置的收件人，不自动将责任人名称映射为邮箱。
- 自动化测试不代替外部服务、浏览器与公网部署验收，模型输出和引用内容仍需核对。

</details>

## 文档

[项目架构](项目架构书.md) · [开发设计](开发书.md) · [环境安装](安装书.md) · [服务器迁移](服务器迁移安装说明.md) · [登录与安全](登录与安全说明.md)

<details>
<summary>历史 README</summary>

[最初版本](docs/archive/README.before-github.md) · [截图改版前](docs/archive/README.before-gallery.md) · [本次排版前](docs/archive/README.before-layout.md)

</details>
