from typing import Literal
from pydantic import BaseModel, Field, SecretStr, field_validator


class ConversationInput(BaseModel):
    title: str = Field(default='新会话', min_length=1, max_length=80)


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=256)


class PasswordInput(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=12, max_length=256)


class SmtpInput(BaseModel):
    smtp_host: str = Field(min_length=1, max_length=253)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_use_ssl: bool = True
    smtp_starttls: bool = False
    smtp_user: str = Field(min_length=1, max_length=254)
    smtp_password: SecretStr | None = None
    smtp_from: str = Field(min_length=1, max_length=254)
    smtp_allowed_recipients: list[str] = Field(default_factory=list, max_length=50)

    @field_validator('smtp_host', 'smtp_user', 'smtp_from', mode='before')
    @classmethod
    def trim_smtp(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('smtp_user', 'smtp_from')
    @classmethod
    def valid_mailbox(cls, value):
        import re
        if not re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+', value):
            raise ValueError('请输入完整邮箱地址')
        return value

    @field_validator('smtp_allowed_recipients')
    @classmethod
    def valid_recipients(cls, values):
        return list(dict.fromkeys(cls.valid_mailbox(value.strip()) for value in values))

    @field_validator('smtp_host')
    @classmethod
    def valid_host(cls, value):
        import re
        if not re.fullmatch(r'[a-zA-Z0-9.-]+', value):
            raise ValueError('请输入 SMTP 主机名，不含协议或端口')
        return value


class ChatInput(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1, max_length=12000)
    file_ids: list[str] = Field(default_factory=list, max_length=10)
    search: bool = False


class MemoryFact(BaseModel):
    person: str | None = None
    time_text: str | None = None
    location: str | None = None
    topic: str | None = None
    event: str | None = None
    summary: str = Field(min_length=1, max_length=1000)
    evidence: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)


class MemoryExtraction(BaseModel):
    memories: list[MemoryFact] = Field(default_factory=list, max_length=30)


class MemoryInput(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    person: str | None = Field(default=None, max_length=150)
    time_text: str | None = Field(default=None, max_length=150)
    location: str | None = Field(default=None, max_length=150)
    topic: str | None = Field(default=None, max_length=150)
    evidence: str | None = Field(default=None, max_length=2000)

    @field_validator('*', mode='before')
    @classmethod
    def trim_strings(cls, value):
        return value.strip() if isinstance(value, str) else value


class Risk(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    category: Literal['截止时间风险', '责任人缺失', '进度阻塞', '未解决问题']
    level: Literal['high', 'medium', 'low']
    description: str
    evidence: str = Field(min_length=1, max_length=2000)
    owner: str | None = None
    deadline: str | None = None
    suggestion: str


class MeetingAnalysis(BaseModel):
    summary: str
    people: list[str] = []
    time: str | None = None
    location: str | None = None
    topic: str
    decisions: list[str] = []
    action_items: list[str] = []
    risks: list[Risk] = Field(default_factory=list, max_length=30)
    memories: list[MemoryFact] = Field(default_factory=list, max_length=30)


class Slide(BaseModel):
    layout: Literal['cover', 'section', 'columns', 'chart', 'summary']
    title: str = Field(min_length=1, max_length=48)
    subtitle: str = Field(default='', max_length=150)
    left: list[str] = Field(default_factory=list, max_length=5)
    right: list[str] = Field(default_factory=list, max_length=5)
    categories: list[str] = Field(default_factory=list, max_length=6)
    values: list[float] = Field(default_factory=list, max_length=6)
    data_note: str = Field(default='', max_length=150)


class SlideDeck(BaseModel):
    title: str
    slides: list[Slide] = Field(min_length=5, max_length=20)


class SlidesInput(BaseModel):
    topic: str = Field(min_length=1, max_length=2000)
    pages: int = Field(default=6, ge=5, le=20)
    audience: str = Field(default='企业团队', max_length=150)
    style: str = Field(default='专业、克制、清晰', max_length=150)
    use_knowledge: bool = False


class Intent(BaseModel):
    action: Literal['chat', 'search', 'slides'] = 'chat'
    topic: str = ''
    pages: int = Field(default=6, ge=5, le=20)
    use_knowledge: bool = False
    use_memory: bool = False
    memory_write: bool = False
