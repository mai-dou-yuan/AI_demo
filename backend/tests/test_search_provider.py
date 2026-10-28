import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from pydantic import SecretStr

from app.core import AppError, Settings
from app.providers import Providers


def settings(**overrides):
    return Settings(_env_file=None, chat_base_url='https://api.deepseek.com', chat_api_key=SecretStr('test-only-key'), **overrides)


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    def client(**kwargs):
        return original(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr('app.providers.httpx.AsyncClient', client)


def test_search_auto_uses_deepseek_key_without_tavily():
    s = settings()
    assert s.effective_search_provider() == 'deepseek'
    assert s.capabilities()['search'] is True
    other = Settings(_env_file=None, chat_base_url='https://other.example/v1', chat_api_key=SecretStr('other-key'))
    assert other.effective_search_provider() == 'tavily'
    assert other.capabilities()['search'] is False


@pytest.mark.asyncio
async def test_deepseek_search_request_auth_date_and_citations(monkeypatch):
    def handler(request):
        assert str(request.url) == 'https://api.deepseek.com/v1/tools/search'
        assert request.headers['Authorization'] == 'Bearer test-only-key'
        data = json.loads(request.content)
        assert 'api_key' not in data
        assert data['count'] == 5 and data['need_content'] is True
        assert datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日') in data['query']
        assert len(data['query']) <= 128
        return httpx.Response(200, json={'results': [
            {'title': '南京天气', 'url': 'https://example.org/weather', 'summary': '南京天气预报', 'content': '', 'date': '2026-10-28T00:00:00Z'},
            {'title': '无效来源', 'url': 'javascript:alert(1)', 'summary': '不使用'},
        ]})
    mock_http(monkeypatch, handler)
    results = await Providers(settings()).search('今天南京天气如何')
    assert results == [{'title': '南京天气', 'url': 'https://example.org/weather', 'content': '南京天气预报', 'published_date': '2026-10-28T00:00:00Z'}]


@pytest.mark.asyncio
@pytest.mark.parametrize('status,reason', [(401, '密钥无效'), (402, '余额不足'), (429, '频率超过限制')])
async def test_deepseek_failure_does_not_ask_for_tavily(monkeypatch, status, reason):
    mock_http(monkeypatch, lambda request: httpx.Response(status, json={'error': {'message': 'upstream error'}}))
    with pytest.raises(AppError, match=reason) as exc:
        await Providers(settings()).search('南京天气')
    assert 'TAVILY_API_KEY' not in exc.value.message
    assert 'test-only-key' not in exc.value.message


@pytest.mark.asyncio
async def test_tavily_can_still_be_selected_explicitly(monkeypatch):
    def handler(request):
        assert str(request.url) == 'https://api.tavily.com/search'
        assert json.loads(request.content)['api_key'] == 'tavily-test-key'
        assert 'Authorization' not in request.headers
        return httpx.Response(200, json={'results': [{'title': '来源', 'url': 'https://example.org', 'content': '摘要'}]})
    mock_http(monkeypatch, handler)
    result = await Providers(settings(search_provider='tavily', tavily_api_key=SecretStr('tavily-test-key'))).search('新闻')
    assert result[0]['content'] == '摘要'


@pytest.mark.asyncio
async def test_empty_search_has_explicit_failure(monkeypatch):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json={'results': []}))
    with pytest.raises(AppError, match='未返回结果'):
        await Providers(settings()).search('没有结果的查询')
