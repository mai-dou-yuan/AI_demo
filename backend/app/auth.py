"""Single-owner authentication. Session cookies contain only random opaque tokens."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

from fastapi import Request
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from .core import AppError

COOKIE = 'cortex_session'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024).hex()
    return 'scrypt$32768$8$3$' + salt + '$' + key


def verify_password(password, stored):
    # Support the initial bootstrap format as well as explicitly versioned parameters.
    if ':' in stored:
        salt, expected = stored.split(':')
        parallelism = 1
    else:
        algorithm, cost, block, parallel, salt, expected = stored.split('$')
        if (algorithm, cost, block, parallel) != ('scrypt', '32768', '8', '3'):
            return False
        parallelism = 3
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=parallelism, maxmem=64 * 1024 * 1024).hex()
    return hmac.compare_digest(actual, expected)


class Auth:
    def __init__(self, settings, root):
        self.s, self.root = settings, root
        self.path = root / 'auth.sqlite3'
        root.chmod(0o700)
        self.public_origin = settings.auth_public_origin.rstrip('/')
        if self.public_origin:
            parsed = urlsplit(self.public_origin)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise RuntimeError('AUTH_PUBLIC_ORIGIN 必须是无路径的 HTTPS 站点地址')
        self.origins = set(settings.cors_origins)
        if self.public_origin:
            self.origins.add(self.public_origin)
        self.hosts = set(settings.auth_allowed_hosts)
        if self.public_origin:
            self.hosts.add(urlsplit(self.public_origin).hostname)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS owner(id INTEGER PRIMARY KEY CHECK(id=1),username TEXT,password_hash TEXT,must_change INTEGER);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,created REAL,expires REAL,last_seen REAL);
                CREATE TABLE IF NOT EXISTS attempts(ip_hash TEXT,created REAL);
                CREATE TABLE IF NOT EXISTS audit(event TEXT,created REAL);
                CREATE INDEX IF NOT EXISTS attempts_created ON attempts(created);
            ''')
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM owner').fetchone():
                password = secrets.token_urlsafe(24)
                db.execute('INSERT INTO owner VALUES(1,?,?,1)', ('admin', password_hash(password)))
                # No network bootstrap route: only someone with local filesystem access can enroll.
                descriptor = os.open(root / 'initial-login.txt', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(descriptor, 'w') as file:
                    os.fchmod(file.fileno(), 0o600)
                    file.write('Cortex 初始登录（首次登录后必须修改密码）\n账号：admin\n密码：' + password + '\n')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def owner(self):
        with self.connect() as db:
            return dict(db.execute('SELECT * FROM owner WHERE id=1').fetchone())

    def session(self, token):
        if not token or len(token) > 128:
            return None
        timestamp = time.time()
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires<=? OR last_seen<=?', (timestamp, timestamp - self.s.auth_idle_minutes * 60))
            row = db.execute('SELECT * FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()
            if row:
                db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?', (timestamp, digest(token)))
        return row

    def issue(self, response, verified_hash):
        token = secrets.token_urlsafe(32)
        timestamp = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT password_hash FROM owner WHERE id=1').fetchone()[0]
            if not hmac.compare_digest(current, verified_hash):
                raise AppError('账号凭据已更新，请重新登录', 401)
            db.execute('DELETE FROM sessions WHERE expires<=?', (timestamp,))
            # Bound the number of outstanding sessions for this single account.
            db.execute('DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM sessions ORDER BY created DESC LIMIT -1 OFFSET 9)')
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), timestamp, timestamp + self.s.auth_session_hours * 3600, timestamp))
        response.set_cookie(COOKIE, token, httponly=True, secure=bool(self.public_origin), samesite='strict', path='/', max_age=self.s.auth_session_hours * 3600)
        return token

    def status(self, token):
        owner = self.owner()
        return {'authenticated': True, 'username': owner['username'], 'must_change_password': bool(owner['must_change']), 'csrf_token': digest('csrf:' + token)}

    def login(self, username, password, ip):
        timestamp = time.time()
        ip_key = digest(ip)
        with self.connect() as db:
            db.execute('DELETE FROM attempts WHERE created<?', (timestamp - 900,))
            count = db.execute('SELECT count(*) FROM attempts WHERE ip_hash=?', (ip_key,)).fetchone()[0]
            total = db.execute('SELECT count(*) FROM attempts').fetchone()[0]
            if count >= 5 or total >= 30:
                raise AppError('登录尝试过多，请 15 分钟后再试', 429)
            db.execute('INSERT INTO attempts VALUES(?,?)', (ip_key, timestamp))
        owner = self.owner()
        valid = verify_password(password, owner['password_hash'])
        if not hmac.compare_digest(username.encode(), owner['username'].encode()) or not valid:
            self.audit('login_failed')
            raise AppError('账号或密码错误', 401)
        with self.connect() as db:
            db.execute('DELETE FROM attempts WHERE ip_hash=?', (ip_key,))
        self.audit('login_success')
        return owner['password_hash']

    def audit(self, event):
        with self.connect() as db:
            db.execute('INSERT INTO audit VALUES(?,?)', (event, time.time()))
            db.execute('DELETE FROM audit WHERE rowid IN (SELECT rowid FROM audit ORDER BY rowid DESC LIMIT -1 OFFSET 1000)')

    def change_password(self, current, new, ip):
        owner = self.owner()
        try:
            self.login(owner['username'], current, ip)
        except AppError as exc:
            if exc.status == 401:
                raise AppError('当前密码错误', 400) from None
            raise
        if hmac.compare_digest(current.encode(), new.encode()):
            raise AppError('新密码不能与当前密码相同')
        return self.reset_password(owner['username'], new)

    def reset_password(self, username, password):
        if len(password) < 12 or len(password) > 256:
            raise AppError('密码长度须为 12–256 个字符')
        encoded = password_hash(password)
        with self.connect() as db:
            db.execute('UPDATE owner SET username=?,password_hash=?,must_change=0 WHERE id=1', (username, encoded))
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM attempts')
        (self.root / 'initial-login.txt').unlink(missing_ok=True)
        self.audit('password_changed')
        return encoded


class SecurityMiddleware:
    """Enforce auth before route/body processing; don't trust forwarded IP headers."""
    def __init__(self, app, auth):
        self.app, self.auth = app, auth

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        path, method = scope['path'], scope['method']

        async def secured_send(message):
            if message['type'] == 'http.response.start':
                headers = dict(message['headers'])
                headers.update({b'cache-control': b'no-store', b'x-content-type-options': b'nosniff', b'x-frame-options': b'DENY', b'referrer-policy': b'no-referrer', b'permissions-policy': b'camera=(), microphone=(), geolocation=()'})
                headers.setdefault(b'content-security-policy', b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
                if self.auth.public_origin:
                    headers[b'strict-transport-security'] = b'max-age=31536000'
                message['headers'] = list(headers.items())
            await send(message)

        async def reject(detail, status):
            await JSONResponse({'detail': detail}, status_code=status)(scope, receive, secured_send)

        if request.url.hostname not in self.auth.hosts:
            return await reject('不允许的访问主机', 400)
        origin = request.headers.get('origin')
        if origin and origin not in self.auth.origins:
            return await reject('不允许的请求来源', 403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return await reject('不允许跨站请求', 403)
        write = method not in ('GET', 'HEAD', 'OPTIONS')
        if write and (not origin or request.headers.get('x-cortex-request') != '1'):
            return await reject('请求来源校验失败', 403)
        token = request.cookies.get(COOKIE, '')
        public_login = path == '/api/auth/login' and method == 'POST'
        if not public_login:
            if not self.auth.session(token):
                return await reject('请先登录', 401)
            if write and not hmac.compare_digest(request.headers.get('x-csrf-token', '').encode(), digest('csrf:' + token).encode()):
                return await reject('会话校验失败，请重新登录', 403)
            if self.auth.owner()['must_change'] and path not in ('/api/auth/session', '/api/auth/password', '/api/auth/logout'):
                return await reject('首次登录请先修改密码', 403)
        limit = (self.auth.s.max_upload_mb + 1) * 1024 * 1024 if path == '/api/files/upload' else 65536
        if path.startswith('/api/auth/'):
            limit = 8192
        try:
            length = int(request.headers.get('content-length', '0'))
            if length < 0 or length > limit:
                return await reject('请求内容过大', 413)
        except ValueError:
            return await reject('无效的请求长度', 400)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > limit:
                raise HTTPException(status_code=413, detail='请求内容过大')
            return message

        await self.app(scope, limited_receive, secured_send)
