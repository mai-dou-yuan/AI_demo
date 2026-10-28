"""Local configuration and short, transactional SQLite operations."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    storage_dir: Path = ROOT / 'storage'
    chat_base_url: str = 'https://api.openai.com/v1'
    chat_api_key: SecretStr = SecretStr('')
    chat_model: str = ''
    embedding_base_url: str = 'https://api.openai.com/v1'
    embedding_api_key: SecretStr = SecretStr('')
    embedding_model: str = ''
    embedding_api_format: Literal['openai', 'dashscope'] = 'openai'
    embedding_batch_size: int = Field(default=20, ge=1, le=20)
    tavily_api_key: SecretStr = SecretStr('')
    search_provider: Literal['auto', 'deepseek', 'tavily'] = 'auto'
    smtp_host: str = ''
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    smtp_starttls: bool = False
    smtp_user: str = ''
    smtp_password: SecretStr = SecretStr('')
    smtp_from: str = ''
    smtp_allowed_recipients: list[str] = Field(default_factory=list)
    request_timeout: float = 60
    max_upload_mb: int = 20
    api_proxy: str = ''
    cors_origins: list[str] = ['http://localhost:3000', 'http://127.0.0.1:3000']
    auth_public_origin: str = ''
    auth_session_hours: int = Field(default=8, ge=1, le=24)
    auth_idle_minutes: int = Field(default=30, ge=5, le=120)
    auth_allowed_hosts: list[str] = ['localhost', '127.0.0.1', '::1']

    def effective_search_provider(self):
        if self.search_provider != 'auto':
            return self.search_provider
        return 'deepseek' if urlparse(self.chat_base_url).hostname == 'api.deepseek.com' else 'tavily'

    def capabilities(self):
        return {
            'chat': bool(self.chat_api_key.get_secret_value() and self.chat_model),
            'embedding': bool(self.embedding_base_url and self.embedding_api_key.get_secret_value() and self.embedding_model),
            'search': bool(self.chat_api_key.get_secret_value() if self.effective_search_provider() == 'deepseek' else self.tavily_api_key.get_secret_value()),
            'smtp': bool(self.smtp_host and self.smtp_from and self.smtp_allowed_recipients),
        }


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False)


class AppError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status
        super().__init__(message)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),role TEXT,content TEXT,metadata_json TEXT DEFAULT '{}',created_at TEXT);
CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,filename TEXT,type TEXT,sha256 TEXT UNIQUE,path TEXT,status TEXT,error TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,file_id TEXT REFERENCES files(id),page INTEGER,text TEXT);
CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY,file_id TEXT UNIQUE REFERENCES files(id),summary_json TEXT,analyzed_at TEXT);
CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,person TEXT,time_text TEXT,location TEXT,topic TEXT,event TEXT,summary TEXT,source_type TEXT,source_id TEXT,evidence TEXT,confidence REAL,updated_at TEXT,index_status TEXT DEFAULT 'pending',UNIQUE(source_type,source_id,evidence));
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,meeting_id TEXT REFERENCES meetings(id),risk_key TEXT UNIQUE,title TEXT,category TEXT,level TEXT,description TEXT,owner TEXT,deadline TEXT,evidence TEXT,suggestion TEXT,status TEXT DEFAULT 'open',email_status TEXT DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS email_logs(id TEXT PRIMARY KEY,task_id TEXT REFERENCES tasks(id),recipient TEXT,status TEXT,error TEXT,sent_at TEXT,UNIQUE(task_id,recipient));
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,type TEXT,status TEXT,progress INTEGER,result_id TEXT,error TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,job_id TEXT REFERENCES jobs(id),filename TEXT,mime_type TEXT,path TEXT,created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages(conversation_id,created_at);
CREATE INDEX IF NOT EXISTS ix_memories_source ON memories(source_type,source_id);
'''


class Database:
    def __init__(self, root: Path):
        self.root = root.resolve()
        for directory in ('uploads', 'extracted', 'artifacts', 'chroma'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'brain.sqlite3'
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("UPDATE jobs SET status='failed',error='服务重启，任务已中断，可手动重试' WHERE status IN ('queued','running')")
            db.execute("UPDATE files SET status='failed',error='服务重启，解析已中断' WHERE status='processing'")
            # Never automatically re-send an email whose SMTP acknowledgement was interrupted.
            db.execute("UPDATE email_logs SET status='unknown',error='服务中断，发送结果不确定，请核对邮箱后手动重试' WHERE status='sending'")
            db.execute("UPDATE tasks SET email_status='unknown' WHERE email_status='sending'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def all(self, sql, params=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def one(self, sql, params=(), required=False):
        rows = self.all(sql, params)
        if not rows and required:
            raise AppError('记录不存在', 404)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.connect() as db:
            return db.execute(sql, params).rowcount

    def insert(self, table, data):
        # Table and column names are application constants, never client input.
        with self.connect() as db:
            db.execute(f'INSERT INTO {table} ({",".join(data)}) VALUES ({",".join("?" for _ in data)})', tuple(data.values()))

    def job(self, kind, result_id=None):
        key = uid()
        self.insert('jobs', dict(id=key, type=kind, status='queued', progress=0, result_id=result_id, error=None, created_at=now()))
        return key

    def message(self, conversation_id, role, content, metadata=None):
        key = uid()
        self.insert('messages', dict(id=key, conversation_id=conversation_id, role=role, content=content, metadata_json=dump(metadata or {}), created_at=now()))
        self.execute('UPDATE conversations SET updated_at=? WHERE id=?', (now(), conversation_id))
        return key

    def safe_path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise AppError('文件不存在', 404)
        return path
