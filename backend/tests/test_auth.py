"""Security regressions use temporary credentials/storage; no external calls."""
import json
import stat
import time

import httpx
import pytest

from app.auth import COOKIE, digest
from app.core import Settings
from app.main import create_app

PASSWORD = 'private-test-passphrase-2026'


@pytest.fixture
async def auth_client(tmp_path):
    app = create_app(Settings(storage_dir=tmp_path, auth_allowed_hosts=['test'], cors_origins=['http://test'], _env_file=None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                 headers={'Origin': 'http://test', 'X-Cortex-Request': '1'}) as client:
        yield app, client


async def sign_in(app, client):
    app.state.auth.reset_password('owner', PASSWORD)
    response = await client.post('/api/auth/login', json={'username': 'owner', 'password': PASSWORD})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return response


@pytest.mark.asyncio
async def test_all_data_and_download_routes_require_authentication(auth_client):
    app, client = auth_client
    for path in ['/api/health', '/api/conversations', '/api/conversations/x/messages', '/api/files', '/api/files/x/content',
                 '/api/files/x/text?download=true', '/api/files/x/text?paragraph=1', '/api/meetings', '/api/tasks',
                 '/api/memories', '/api/memories/x/source', '/api/jobs', '/api/artifacts', '/api/artifacts/x/download',
                 '/api/settings/smtp', '/docs', '/redoc', '/openapi.json', '/storage/smtp-settings.json']:
        response = await client.get(path)
        assert response.status_code == 401, path
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
    for method, path in [('POST', '/api/chat/stream'), ('POST', '/api/files/upload'), ('PUT', '/api/settings/smtp'),
                         ('DELETE', '/api/files/x'), ('DELETE', '/api/meetings/x'), ('DELETE', '/api/tasks/x'),
                         ('DELETE', '/api/memories/x'), ('DELETE', '/api/artifacts/x')]:
        assert (await client.request(method, path, content=b'{}')).status_code == 401
    assert app.state.db.all('SELECT * FROM conversations') == []


@pytest.mark.asyncio
async def test_random_bootstrap_and_forced_password_change(auth_client):
    app, client = auth_client
    initial = app.state.db.root / 'initial-login.txt'
    temporary_password = initial.read_text().split('密码：')[1].strip()
    assert len(temporary_password) >= 24
    assert stat.S_IMODE(initial.stat().st_mode) == 0o600
    assert stat.S_IMODE(app.state.auth.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(app.state.db.root.stat().st_mode) == 0o700
    login = await client.post('/api/auth/login', json={'username': 'admin', 'password': temporary_password})
    assert login.status_code == 200 and login.json()['must_change_password']
    assert 'httponly' in login.headers['set-cookie'].lower() and 'samesite=strict' in login.headers['set-cookie'].lower()
    assert 'domain=' not in login.headers['set-cookie'].lower()
    client.headers['X-CSRF-Token'] = login.json()['csrf_token']
    old_token = client.cookies.get(COOKIE)
    assert (await client.get('/api/settings/smtp')).status_code == 403
    invalid = await client.post('/api/auth/password', json={'current_password': temporary_password, 'new_password': 'short'})
    assert invalid.status_code == 422 and temporary_password not in invalid.text and 'short' not in invalid.text
    changed = await client.post('/api/auth/password', json={'current_password': temporary_password, 'new_password': PASSWORD})
    assert changed.status_code == 200 and not changed.json()['must_change_password']
    assert not initial.exists()
    assert app.state.auth.session(old_token) is None
    assert PASSWORD not in app.state.auth.path.read_bytes().decode(errors='ignore')
    client.headers['X-CSRF-Token'] = changed.json()['csrf_token']
    assert (await client.get('/api/settings/smtp')).status_code == 200
    assert (await client.get('/docs')).status_code == 404


@pytest.mark.asyncio
async def test_origin_host_and_csrf_enforcement(auth_client):
    app, client = auth_client
    await sign_in(app, client)
    assert (await client.post('/api/conversations', json={})).status_code == 201
    for headers in [{'Origin': 'https://evil.example'}, {'Origin': 'null'}, {'Origin': ''},
                    {'X-CSRF-Token': 'forged'}, {'X-CSRF-Token': ''}, {'X-Cortex-Request': ''}, {'Sec-Fetch-Site': 'cross-site'}]:
        assert (await client.post('/api/conversations', json={}, headers=headers)).status_code == 403
    assert (await client.get('/api/tasks', headers={'Host': 'evil.example'})).status_code == 400
    assert (await client.get('/api/tasks', headers={'Origin': 'https://evil.example'})).status_code == 403
    assert (await client.post('/api/conversations', content=b'x' * 65537)).status_code == 413
    assert (await client.post('/api/auth/login', content=b'x' * 8193)).status_code == 413
    assert (await client.post('/api/auth/login', json={'username': 'owner', 'password': PASSWORD}, headers={'Origin': 'https://evil.example'})).status_code == 403
    assert (await client.get('/api/tasks', headers={'X-Forwarded-Host': 'evil.example'})).status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_is_persistent_and_forwarded_ip_cannot_bypass(auth_client):
    app, client = auth_client
    app.state.auth.reset_password('owner', PASSWORD)
    for index in range(5):
        response = await client.post('/api/auth/login', json={'username': 'unknown-' + str(index), 'password': 'wrong-password'}, headers={'X-Forwarded-For': f'1.2.3.{index}'})
        assert response.status_code == 401 and response.json()['detail'] == '账号或密码错误'
    assert (await client.post('/api/auth/login', json={'username': 'owner', 'password': PASSWORD})).status_code == 429
    from app.auth import Auth
    restarted = Auth(app.state.services.s, app.state.db.root)
    with pytest.raises(Exception) as error:
        restarted.login('owner', PASSWORD, '127.0.0.1')
    assert error.value.status == 429


@pytest.mark.asyncio
async def test_logout_expiry_password_change_and_secret_redaction(auth_client):
    app, client = auth_client
    await sign_in(app, client)
    token = client.cookies.get(COOKIE)
    with app.state.auth.connect() as db:
        stored = db.execute('SELECT token_hash FROM sessions').fetchone()[0]
    assert stored == digest(token) and stored != token
    payload = {'smtp_host': 'smtp.qq.com', 'smtp_port': 465, 'smtp_user': 'owner@example.com', 'smtp_from': 'owner@example.com',
               'smtp_password': 'private-test-smtp-secret', 'smtp_allowed_recipients': ['owner@example.com']}
    assert (await client.put('/api/settings/smtp', json=payload)).status_code == 200
    assert 'private-test-smtp-secret' not in (await client.get('/api/settings/smtp')).text
    malformed = await client.put('/api/settings/smtp', json={**payload, 'smtp_port': -1})
    assert malformed.status_code == 422 and 'private-test-smtp-secret' not in malformed.text
    assert (await client.post('/api/auth/logout')).status_code == 200
    assert app.state.auth.session(token) is None
    assert (await client.get('/api/tasks')).status_code == 401
    login = await sign_in(app, client)
    token = client.cookies.get(COOKIE)
    with app.state.auth.connect() as db:
        db.execute('UPDATE sessions SET last_seen=?', (time.time() - 3600,))
    assert (await client.get('/api/tasks')).status_code == 401
    await sign_in(app, client)
    token = client.cookies.get(COOKIE)
    with app.state.auth.connect() as db:
        db.execute('UPDATE sessions SET expires=?', (time.time() - 1,))
    assert (await client.get('/api/tasks')).status_code == 401
    await sign_in(app, client)
    old = client.cookies.get(COOKIE)
    changed = await client.post('/api/auth/password', json={'current_password': PASSWORD, 'new_password': PASSWORD + '-new'})
    assert changed.status_code == 200 and app.state.auth.session(old) is None
    assert client.cookies.get(COOKIE) != old


@pytest.mark.asyncio
async def test_public_https_configuration_sets_secure_cookie(tmp_path):
    settings = Settings(storage_dir=tmp_path, auth_public_origin='https://brain.example.com', _env_file=None)
    app = create_app(settings)
    app.state.auth.reset_password('owner', PASSWORD)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://brain.example.com',
                                 headers={'Origin': 'https://brain.example.com', 'X-Cortex-Request': '1'}) as client:
        login = await client.post('/api/auth/login', json={'username': 'owner', 'password': PASSWORD})
        assert login.status_code == 200 and 'secure' in login.headers['set-cookie'].lower()
        assert login.headers['strict-transport-security'] == 'max-age=31536000'
        assert (await client.get('/api/auth/session')).status_code == 200
    with pytest.raises(RuntimeError):
        create_app(Settings(storage_dir=tmp_path, auth_public_origin='http://unsafe.example', _env_file=None))


def test_password_hash_salted_unicode_and_bootstrap_compatibility():
    import hashlib
    from app.auth import password_hash, verify_password
    password = '麦兜的独立登录密码-2026'
    first = password_hash(password)
    assert first.startswith('scrypt$32768$8$3$')
    assert first != password_hash(password)
    assert verify_password(password, first)
    assert not verify_password('wrong-password', first)
    salt = '1234567890abcdef1234567890abcdef'
    old_key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024).hex()
    assert verify_password(password, salt + ':' + old_key)


@pytest.mark.asyncio
async def test_chunked_login_body_limit_and_wrong_current_password(auth_client):
    app, client = auth_client
    async def chunks():
        for _ in range(10):
            yield b'x' * 1024
    response = await client.post('/api/auth/login', content=chunks(), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
    await sign_in(app, client)
    invalid = await client.post('/api/auth/password', json={'current_password': 'incorrect-password', 'new_password': PASSWORD + '-new'})
    assert invalid.status_code == 400
    assert app.state.auth.owner()['password_hash']


def test_password_reset_during_login_cannot_issue_a_stale_session(tmp_path):
    from starlette.responses import Response
    from app.auth import Auth
    from app.core import AppError
    auth = Auth(Settings(storage_dir=tmp_path, _env_file=None), tmp_path)
    auth.reset_password('owner', PASSWORD)
    verified = auth.login('owner', PASSWORD, '127.0.0.1')
    auth.reset_password('owner', PASSWORD + '-changed')
    with pytest.raises(AppError) as error:
        auth.issue(Response(), verified)
    assert error.value.status == 401
    with auth.connect() as db:
        assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0
