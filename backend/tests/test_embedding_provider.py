import json

import httpx
import pytest

from app.core import AppError, Settings
from app.providers import Providers


@pytest.mark.asyncio
async def test_chat_and_embedding_have_separate_credentials():
    s = Settings(_env_file=None, chat_base_url='https://api.deepseek.com', chat_api_key='chat-test-key', chat_model='deepseek-flash',
        embedding_base_url='https://test-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1',
        embedding_api_key='embedding-test-key', embedding_model='qwen3.7-text-embedding-flash')
    provider = Providers(s)
    async with provider.client() as chat, provider.client(embedding=True) as embedding:
        assert chat.api_key == 'chat-test-key'
        assert embedding.api_key == 'embedding-test-key'
        assert embedding.base_url.host == 'test-workspace.cn-beijing.maas.aliyuncs.com'


@pytest.mark.asyncio
@pytest.mark.parametrize('index_field', ['index', 'text_index'])
async def test_qwen_embedding_batches_are_at_most_twenty(monkeypatch, index_field):
    batch_sizes = []
    original = httpx.AsyncClient
    def handler(request):
        assert str(request.url) == 'https://cn-beijing.maas.qianwenaiapi.com/api/v1/services/embeddings/text-embedding/text-embedding'
        assert request.headers['Authorization'] == 'Bearer embedding-test-key'
        body = json.loads(request.content)
        assert body['model'] == 'qwen3.7-text-embedding-flash'
        assert body['parameters']['output_type'] == 'dense'
        batch_sizes.append(len(body['input']['texts']))
        return httpx.Response(200, json={'output': {'embeddings': [
            {index_field: i, 'embedding': [float(text), .5]} for i, text in reversed(list(enumerate(body['input']['texts'])))
        ]}, 'usage': {'prompt_tokens': 1, 'total_tokens': 1}})
    class MockClient(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr('app.providers.httpx.AsyncClient', MockClient)
    s = Settings(_env_file=None, embedding_api_format='dashscope', embedding_base_url='https://cn-beijing.maas.qianwenaiapi.com/api/v1',
        embedding_api_key='embedding-test-key', embedding_model='qwen3.7-text-embedding-flash')
    results = await Providers(s).embed([str(i) for i in range(45)])
    assert batch_sizes == [20, 20, 5]
    assert [row[0] for row in results] == list(range(45))


@pytest.mark.asyncio
async def test_missing_qwen_url_does_not_send_key_to_default_provider():
    s = Settings(_env_file=None, embedding_base_url='', embedding_api_key='embedding-test-key', embedding_model='qwen3.7-text-embedding-flash')
    assert s.capabilities()['embedding'] is False
    with pytest.raises(AppError, match='EMBEDDING_BASE_URL'):
        await Providers(s).embed(['测试'])


@pytest.mark.asyncio
async def test_dashscope_rejects_missing_vectors(monkeypatch):
    original = httpx.AsyncClient
    class MockClient(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'output': {'embeddings': []}})))
    monkeypatch.setattr('app.providers.httpx.AsyncClient', MockClient)
    s = Settings(_env_file=None, embedding_api_format='dashscope', embedding_base_url='https://cn-beijing.maas.qianwenaiapi.com/api/v1',
        embedding_api_key='embedding-test-key', embedding_model='qwen3.7-text-embedding-flash')
    with pytest.raises(AppError, match='Embedding 请求失败'):
        await Providers(s).embed(['测试'])
