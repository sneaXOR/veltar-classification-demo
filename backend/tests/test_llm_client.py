import asyncio

import httpx
import pytest

from app.core.config import get_settings
from app.services.classification.llm_client import LLMClient, LLMRequestError


def test_llm_client_builds_file_url(monkeypatch, tmp_path):
    image_path = tmp_path / "pages" / "sample.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")

    monkeypatch.setenv("LLM_IMAGE_TRANSPORT", "file_url")
    monkeypatch.setenv("LLM_FILE_URL_ROOT", str(tmp_path))
    get_settings.cache_clear()

    client = LLMClient(profile_id="environment")
    assert client._build_image_url(image_path) == "file://pages/sample.png"

    get_settings.cache_clear()


def test_llm_client_builds_data_url(monkeypatch, tmp_path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"png")

    monkeypatch.setenv("LLM_IMAGE_TRANSPORT", "data_url")
    monkeypatch.delenv("LLM_FILE_URL_ROOT", raising=False)
    get_settings.cache_clear()

    client = LLMClient(profile_id="environment")
    assert client._build_image_url(image_path).startswith("data:image/png;base64,")

    get_settings.cache_clear()


def test_llm_client_omits_authorization_header_when_api_key_is_empty(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://custom-runtime.local/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()

    try:
        client = LLMClient(profile_id="environment")
        assert "Authorization" not in client.headers
    finally:
        get_settings.cache_clear()


def test_llm_client_rejects_unconfigured_openrouter_runtime(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.6-plus")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()

    try:
        client = LLMClient(profile_id="environment")
        with pytest.raises(LLMRequestError, match="Runtime OpenRouter non configure"):
            asyncio.run(client.generate_text("test missing openrouter key"))
    finally:
        get_settings.cache_clear()


def test_llm_client_uses_openrouter_api_key_for_environment_profile(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.6-plus")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    get_settings.cache_clear()

    try:
        client = LLMClient(profile_id="environment")
        assert client.headers["Authorization"] == "Bearer test-openrouter-key"
    finally:
        get_settings.cache_clear()


def test_llm_client_retries_retryable_http_errors(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    responses = [
        httpx.Response(503, request=request, text="temporary overload"),
        httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]}),
    ]
    attempts: list[int] = []
    sleeps: list[float] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            attempts.append(1)
            return responses.pop(0)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = LLMClient()
    result = asyncio.run(client.generate_text("test retry"))

    assert result == "ok"
    assert len(attempts) == 2
    assert sleeps == [3.0]


def test_llm_client_surfaces_provider_error_body(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    response = httpx.Response(
        404,
        request=request,
        text='{"error":{"message":"No endpoints found that support image input","code":404}}',
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LLMClient()
    with pytest.raises(LLMRequestError, match="support image input"):
        asyncio.run(client.generate_text("test provider error"))


def test_llm_client_respects_provider_retry_hint_on_429(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    responses = [
        httpx.Response(
            429,
            request=request,
            text=(
                '{"error":{"message":"Quota exceeded. '
                'Please retry in 12.5s.","status":"RESOURCE_EXHAUSTED"}}'
            ),
        ),
        httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]}),
    ]
    attempts: list[int] = []
    sleeps: list[float] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            attempts.append(1)
            return responses.pop(0)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = LLMClient()
    result = asyncio.run(client.generate_text("test retry hint"))

    assert result == "ok"
    assert len(attempts) == 2
    assert sleeps == [12.5]


def test_llm_client_allows_more_retries_for_rate_limits(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    responses = [
        httpx.Response(429, request=request, text='{"error":{"message":"Please retry in 0.1s."}}'),
        httpx.Response(429, request=request, text='{"error":{"message":"Please retry in 0.1s."}}'),
        httpx.Response(429, request=request, text='{"error":{"message":"Please retry in 0.1s."}}'),
        httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]}),
    ]
    attempts: list[int] = []
    sleeps: list[float] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            attempts.append(1)
            return responses.pop(0)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = LLMClient()
    result = asyncio.run(client.generate_text("test extended 429 retries"))

    assert result == "ok"
    assert len(attempts) == 4
    assert sleeps == [3.0, 6.0, 9.0]


def test_llm_client_surfaces_response_preview_on_parse_failure(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    response = httpx.Response(
        200,
        request=request,
        json={"choices": [{"message": {"content": '{"broken": }'}}]},
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LLMClient()
    with pytest.raises(LLMRequestError, match="Response preview"):
        asyncio.run(client.generate_json("test malformed json"))


def test_llm_client_surfaces_error_when_choices_are_missing(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions")
    response = httpx.Response(
        200,
        request=request,
        json={"id": "resp_123", "error": {"message": "Temporary upstream failure"}},
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LLMClient()
    with pytest.raises(LLMRequestError, match="Temporary upstream failure"):
        asyncio.run(client.generate_text("test missing choices"))


def test_llm_client_uses_longer_timeout_for_local_qwen(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "120")
    get_settings.cache_clear()

    try:
        client = LLMClient(profile_id="local_qwen_8b")
        assert client.timeout_seconds == 600
        assert client.max_tokens == 3200
    finally:
        get_settings.cache_clear()


def test_llm_client_keeps_system_message_for_default_models():
    client = LLMClient()

    messages = client._build_messages(
        system_text="System guidance",
        content=[{"type": "text", "text": "User payload"}],
    )

    assert messages == [
        {"role": "system", "content": "System guidance"},
        {"role": "user", "content": [{"type": "text", "text": "User payload"}]},
    ]


def test_llm_client_inlines_system_message_for_gemma_models():
    client = LLMClient()
    client.model_name = "google/gemma-3-27b-it:free"

    messages = client._build_messages(
        system_text="System guidance",
        content=[{"type": "text", "text": "User payload"}],
    )

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert isinstance(messages[0]["content"], list)
    assert messages[0]["content"][0]["type"] == "text"
    assert "System guidance" in messages[0]["content"][0]["text"]
    assert messages[0]["content"][1:] == [{"type": "text", "text": "User payload"}]


def _install_payload_capture(monkeypatch):
    captured: dict = {}
    request = httpx.Request("POST", "http://capture/v1/chat/completions")
    response = httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]})

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers=None, json=None):
            captured["payload"] = json
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return captured


def test_llm_client_sends_seed_for_determinism(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.6-plus")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_SEED", "1337")
    get_settings.cache_clear()

    try:
        captured = _install_payload_capture(monkeypatch)
        client = LLMClient(profile_id="environment")
        asyncio.run(client.generate_text("seed check"))
        assert captured["payload"]["seed"] == 1337
        assert captured["payload"]["temperature"] == 0.0
    finally:
        get_settings.cache_clear()


def test_llm_client_adds_openrouter_provider_block_by_default(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "mistralai/mistral-large-2512")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_PROVIDER_ORDER", raising=False)
    get_settings.cache_clear()

    try:
        captured = _install_payload_capture(monkeypatch)
        client = LLMClient(profile_id="environment")
        asyncio.run(client.generate_text("mistral provider check"))
        provider = captured["payload"]["provider"]
        assert provider["require_parameters"] is True
        assert provider["allow_fallbacks"] is True
        assert "order" not in provider
    finally:
        get_settings.cache_clear()


def test_llm_client_pins_openrouter_provider_order_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.6-plus")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ORDER", '["deepinfra","together"]')
    get_settings.cache_clear()

    try:
        captured = _install_payload_capture(monkeypatch)
        client = LLMClient(profile_id="environment")
        asyncio.run(client.generate_text("qwen provider order"))
        provider = captured["payload"]["provider"]
        assert provider["order"] == ["deepinfra", "together"]
        assert provider["allow_fallbacks"] is True
    finally:
        get_settings.cache_clear()


def test_llm_client_omits_provider_block_for_non_openrouter_runtime(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://host.docker.internal:8080/v1")
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()

    try:
        captured = _install_payload_capture(monkeypatch)
        client = LLMClient(profile_id="environment")
        asyncio.run(client.generate_text("local runtime check"))
        assert "provider" not in captured["payload"]
        assert captured["payload"]["seed"] == 42
    finally:
        get_settings.cache_clear()
