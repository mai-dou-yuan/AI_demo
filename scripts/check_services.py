"""Print non-secret configuration; --live performs billable API probes, no email."""
import argparse
import asyncio
import json
import smtplib
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.core import AppError, Settings
from app.providers import Providers
from app.schemas import Intent
from app.mail_settings import load_smtp


async def main(live):
    s = Settings()
    load_smtp(s, s.storage_dir)
    p = Providers(s)
    print(json.dumps({'configured': s.capabilities(), 'chat_model': s.chat_model, 'embedding_model': s.embedding_model, 'search_provider': s.effective_search_provider()}, ensure_ascii=False))
    if not live:
        print('仅检查配置是否填写，未调用外部服务。添加 --live 可测试已配置的服务；不会发送邮件。')
        return
    failures = 0
    for name in ('chat', 'embedding', 'search', 'smtp'):
        if not s.capabilities()[name]:
            print(f'{name}: 未配置，跳过')
            continue
        try:
            if name == 'chat':
                await p.structured(Intent, '这是连接测试，将 action 设为 chat，其他字段使用默认值。', '你好')
            elif name == 'embedding':
                vectors = await p.embed(['Cortex 连接测试'])
                print('Embedding 维度:', len(vectors[0]))
            elif name == 'search':
                await p.search('LangGraph official documentation')
            else:
                transport = smtplib.SMTP_SSL if s.smtp_use_ssl else smtplib.SMTP
                options = {'timeout': 15}
                if s.smtp_use_ssl:
                    options['context'] = ssl.create_default_context()
                with transport(s.smtp_host, s.smtp_port, **options) as client:
                    if s.smtp_starttls and not s.smtp_use_ssl:
                        client.starttls(context=ssl.create_default_context())
                    if s.smtp_user:
                        client.login(s.smtp_user, s.smtp_password.get_secret_value())
                    client.noop()
            print(f'{name}: 连接测试通过' + ('（未发送邮件）' if name == 'smtp' else ''))
        except Exception as exc:
            print(f'{name}: ' + (exc.message if isinstance(exc, AppError) else type(exc).__name__))
            failures += 1
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    asyncio.run(main(parser.parse_args().live))
