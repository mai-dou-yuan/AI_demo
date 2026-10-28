"""Local SMTP overrides. Secrets are never returned to the browser."""
import json
import os
import tempfile

from pydantic import SecretStr
from .core import AppError
from .schemas import SmtpInput


def public_smtp(settings):
    fields = SmtpInput.model_fields
    return {**{key: getattr(settings, key) for key in fields if key != 'smtp_password'},
            'password_set': bool(settings.smtp_password.get_secret_value()),
            'configured': settings.capabilities()['smtp']}


def apply_smtp(settings, values):
    for key, value in values.items():
        setattr(settings, key, SecretStr(value) if key == 'smtp_password' else value)


def smtp_values(data, settings):
    if data.smtp_use_ssl and data.smtp_starttls:
        raise AppError('SSL 与 STARTTLS 不能同时开启')
    values = data.model_dump(exclude={'smtp_password'})
    password = data.smtp_password.get_secret_value() if data.smtp_password is not None else ''
    values['smtp_password'] = password or settings.smtp_password.get_secret_value()
    return values


def load_smtp(settings, root):
    path = root / 'smtp-settings.json'
    if path.exists():
        try:
            data = SmtpInput.model_validate_json(path.read_text(encoding='utf-8'))
            values = smtp_values(data, settings)
        except Exception:
            raise RuntimeError('本地邮件设置文件无效，请检查 storage/smtp-settings.json') from None
        apply_smtp(settings, values)


def save_smtp(settings, root, data):
    values = smtp_values(data, settings)
    descriptor, temporary = tempfile.mkstemp(prefix='.smtp-settings-', dir=root)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            os.fchmod(file.fileno(), 0o600)
            json.dump(values, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, root / 'smtp-settings.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    apply_smtp(settings, values)
    return public_smtp(settings)
