"""Local-only account reset. No credentials are accepted on command-line arguments."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.auth import Auth
from app.core import Settings


def main():
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    auth = Auth(settings, settings.storage_dir)
    username = input('登录账号（留空保留现有账号）：').strip() or auth.owner()['username']
    if not username.isascii() or not username.replace('_', '').replace('-', '').isalnum() or len(username) > 64:
        raise SystemExit('账号须为 1–64 位英文字母、数字、下划线或短横线')
    password = getpass.getpass('新密码（至少 12 位，不回显）：')
    if password != getpass.getpass('再次输入新密码：'):
        raise SystemExit('两次密码不一致，未修改')
    auth.reset_password(username, password)
    print('账号已更新，所有旧会话已撤销。登录密码无需与邮箱密码相同。')


if __name__ == '__main__':
    main()
