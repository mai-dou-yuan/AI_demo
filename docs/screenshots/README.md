# WebUI 截图

README 当前使用仓库「截图/」目录中用户提供的真实截图：首页大图与六个可点击查看完整截图的功能标题。更新脚本优先使用这些原图，并保留自动采集的登录页作为可选补充。邮件设置截图展示邮箱配置界面，SMTP 授权码未回显。原图不做裁剪或修改。

这里存放 GitHub README 引用的真实截图，不存放效果图。截图使用当前项目实际页面；公开发布前确认没有会话标题、个人文件、邮箱、凭据或其他敏感信息。

## 自动截取登录界面

在自己的电脑上启动项目：

```bash
bash scripts/dev.sh
```

另开终端进入项目根目录，执行：

```bash
bash scripts/capture_readme.sh
```

脚本使用本机已有的 Chrome/Chromium，以独立临时浏览器配置打开 `http://127.0.0.1:3000/`，不会读取你日常浏览器的登录会话，也不需要账号密码。生成 `docs/screenshots/login.png`，验证 PNG 文件头后自动更新 README 的截图区域。不会安装软件、禁用浏览器 sandbox 或启动其他业务服务。

当前开发执行沙箱禁止 Chrome 所需的进程/套接字操作，无法在其中完成截图；需要在正常桌面/服务器环境运行。若机器没有 Chrome/Chromium，可直接手动截图，不必为此修改项目依赖。

## 补充工作空间截图

建议浏览器视口为 1440 × 1000，缩放为 100%。使用不含私密记录的演示账号/独立测试数据，保存：

| 文件 | 画面 |
|---|---|
| `workspace.png` | 对话欢迎页或无敏感内容的问答界面；可展示个人工作空间菜单 |
| `knowledge.png` | 使用公开样例的知识库页面或带段落出处的问答 |
| `login.png` | 未填密码的登录页面 |

可使用系统截图工具，或 Chrome 开发者工具中的 Capture screenshot / Capture full size screenshot。PNG 以实际文件保存，不要仅重命名 JPG 扩展名。图片建议小于 1 MiB，不上传整个浏览器配置或任何 storage 数据。

保存后执行：

```bash
.conda/ai-brain/bin/python scripts/update_readme_screenshots.py
```

脚本只插入已有截图，没有对应图片时不生成无效链接。最后在 GitHub 上传或提交 `README.md`、`docs/banner.svg`、`docs/screenshots/*.png`。不要把登录密码或明文 SMTP 授权码截入图片。
