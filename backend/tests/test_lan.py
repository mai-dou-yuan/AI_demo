"""LAN setup must preserve secrets and keep authentication enabled."""
import importlib.util
from pathlib import Path
import stat

import httpx
import pytest

from app.core import Settings
from app.main import create_app

spec = importlib.util.spec_from_file_location('configure_lan', Path(__file__).resolve().parents[2] / 'scripts/configure_lan.py')
lan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lan)


def test_lan_detects_default_physical_interface_and_validates_override(monkeypatch):
    monkeypatch.delenv('CORTEX_LAN_IP', raising=False)
    def results(*args):
        if 'addr' in args:
            return [{'ifname': 'docker0', 'addr_info': [{'local': '172.17.0.1'}]},
                    {'ifname': 'tun0', 'addr_info': [{'local': '10.8.0.1'}]},
                    {'ifname': 'wlp0s1', 'addr_info': [{'local': '192.168.20.9'}]}]
        return [{'dev': 'tun0', 'metric': 1}, {'dev': 'wlp0s1', 'metric': 600}]
    monkeypatch.setattr(lan, 'command_json', results)
    assert lan.detect_ip() == '192.168.20.9'
    monkeypatch.setenv('CORTEX_LAN_IP', '10.0.89.156')
    assert lan.detect_ip() == '10.0.89.156'
    for value in ['0.0.0.0', '127.0.0.1', '8.8.8.8', '192.168.1.2\nINJECT=true']:
        monkeypatch.setenv('CORTEX_LAN_IP', value)
        with pytest.raises(ValueError):
            lan.detect_ip()


@pytest.mark.asyncio
async def test_lan_config_preserves_secrets_and_allows_only_authenticated_local_origin(tmp_path):
    env = tmp_path / '.env'
    env.write_text('CHAT_API_KEY=test-private-key\nSMTP_PASSWORD=test-private-code\nAUTH_PUBLIC_ORIGIN=https://old.example\nAUTH_ALLOWED_HOSTS=["localhost"]\nCORS_ORIGINS=[]\n')
    lan.configure(env, '192.168.20.9')
    text = env.read_text()
    assert 'CHAT_API_KEY=test-private-key\n' in text and 'SMTP_PASSWORD=test-private-code\n' in text
    assert text.count('AUTH_PUBLIC_ORIGIN=') == 1 and 'https://old.example' not in text
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    settings = Settings(storage_dir=tmp_path / 'storage', _env_file=env)
    assert settings.auth_public_origin == '' and '192.168.20.9' in settings.auth_allowed_hosts
    app = create_app(settings)
    app.state.auth.reset_password('owner', 'private-lan-test-password')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://192.168.20.9:3000',
                                headers={'Origin': 'http://192.168.20.9:3000', 'X-Cortex-Request': '1'}) as client:
        assert (await client.get('/api/settings/smtp')).status_code == 401
        login = await client.post('/api/auth/login', json={'username': 'owner', 'password': 'private-lan-test-password'})
        assert login.status_code == 200
        assert 'secure' not in login.headers['set-cookie'].lower()
        client.headers['X-CSRF-Token'] = login.json()['csrf_token']
        assert (await client.post('/api/conversations', json={})).status_code == 201
        assert (await client.get('/api/settings/smtp', headers={'Origin': 'https://old.example'})).status_code == 403
        assert (await client.get('/api/settings/smtp', headers={'Host': 'unknown.example'})).status_code == 400
