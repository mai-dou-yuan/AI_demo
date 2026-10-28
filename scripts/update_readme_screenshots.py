"""Build the GitHub gallery from existing real PNG files; never create mock images."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def update(root=ROOT):
    def available(*paths):
        for relative in paths:
            path = root / relative
            if path.is_file():
                with path.open('rb') as file:
                    if file.read(8) != b'\x89PNG\r\n\x1a\n':
                        raise ValueError(f'不是有效 PNG 文件：{path.name}')
                return relative
        return None

    blocks = []
    home = available('截图/办公智能体首页.png', 'docs/screenshots/workspace.png')
    if home:
        blocks.append(f'![Cortex 工作空间首页]({home})\n\n<p align="center"><sub>六个工作区，一个入口。对话、资料与上下文在同一屏中连接。</sub></p>')
    for title, caption, paths in (
        ('01 · 对话与联网搜索', '结合搜索结果回答问题，保留参考来源。', ('截图/对话-联网查询.png',)),
        ('02 · PDF 知识库', '管理文档、查看提取文本，按 PDF 页码与 TXT 段落追溯出处。', ('截图/pdf解析-RAG知识库.png', 'docs/screenshots/knowledge.png')),
        ('03 · 会议分析', '提炼摘要、决定与行动项，识别需要跟进的风险。', ('截图/会议纪要-分析风险.png',)),
        ('04 · 长期记忆', '保存明确事实，按人物、时间、地点与主题检索。', ('截图/长期记忆.png',)),
        ('05 · 待办与邮件', '跟进责任人与期限，配置邮箱并发送风险提醒。', ('截图/代办事项-发送邮件.png',)),
        ('06 · 演示文稿', '输入主题，生成并下载真实的 PowerPoint 文件。', ('截图/PPT生成.png',)),
        ('登录界面', '验证身份后进入工作空间。', ('docs/screenshots/login.png',)),
    ):
        path = available(*paths)
        if path:
            blocks.append(f'<details>\n<summary><strong>{title}</strong></summary>\n\n{caption}\n\n![Cortex {title}]({path})\n\n</details>')
    if not blocks:
        raise SystemExit('尚无真实界面截图，请先添加 PNG 文件。')
    path = root / 'README.md'
    text = path.read_text(encoding='utf-8')
    pattern = r'(?<=<!-- CORTEX_SCREENSHOTS_START -->)[\s\S]*?(?=<!-- CORTEX_SCREENSHOTS_END -->)'
    if len(re.findall(pattern, text)) != 1:
        raise ValueError('README 截图区域标记缺失或不唯一')
    text = re.sub(pattern, lambda _: '\n\n' + '\n\n'.join(blocks) + '\n\n', text)
    path.write_text(text, encoding='utf-8')
    print('README 已更新真实截图画廊。')


if __name__ == '__main__':
    update()
