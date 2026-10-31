import asyncio
import json
from collections.abc import AsyncIterator

import httpx2 as httpx
import pytest

from spaceanalyzer.analysis.models.contracts import Message, ModelError, ModelRequest
from spaceanalyzer.analysis.models.deepseek import DeepSeekAdapter


class Chunks(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for offset in range(0, len(self.content), 3):
            yield self.content[offset : offset + 3]


def test_deepseek_stream_and_sanitized_failure() -> None:
    captured: list[dict[str, object]] = []

    def reply(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        body = (
            'data: {"choices":[{"delta":{"content":"你好"},"finish_reason":null}]}\n\n'
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        ).encode()
        return httpx.Response(200, stream=Chunks(body))

    async def run() -> None:
        adapter = DeepSeekAdapter(
            "fixture", "secret", transport=httpx.MockTransport(reply)
        )
        events = [
            event
            async for event in adapter.generate(
                ModelRequest(messages=(Message(role="user", content="hi"),))
            )
        ]
        assert [event.text for event in events if event.kind == "text"] == ["你好"]
        assert events[-1].kind == "finished"
        assert captured[0]["thinking"] == {"type": "disabled"}
        denied = DeepSeekAdapter(
            "fixture",
            "secret",
            transport=httpx.MockTransport(lambda _: httpx.Response(401, text="secret")),
        )
        with pytest.raises(ModelError, match="authentication") as error:
            _ = [event async for event in denied.generate(ModelRequest(messages=()))]
        assert "secret" not in str(error.value)
        broken = DeepSeekAdapter(
            "fixture",
            "secret",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, text="data: {}\n\n")
            ),
        )
        with pytest.raises(ModelError, match="ended"):
            _ = [event async for event in broken.generate(ModelRequest(messages=()))]

    asyncio.run(run())


def test_ollama_local_stream_discovery_and_cloud_rejection() -> None:
    from spaceanalyzer.analysis.models.ollama import OllamaAdapter
    from spaceanalyzer.analysis.models.settings import load_registry

    captured: list[dict[str, object]] = []

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            stream=Chunks(
                b'{"message":{"content":"local"},"done":false}\n'
                b'{"done":true,"done_reason":"stop","eval_count":3}\n'
            ),
        )

    async def run() -> None:
        adapter = OllamaAdapter("fixture", transport=httpx.MockTransport(reply))
        events = [event async for event in adapter.generate(ModelRequest(messages=()))]
        assert events[0].text == "local"
        assert captured[0]["options"] == {"num_predict": 2048, "num_ctx": 8192}
        assert events[-1].kind == "finished"
        cloud = OllamaAdapter(
            "fixture",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"remote_model": "remote"})
            ),
        )
        small = OllamaAdapter(
            "fixture",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "capabilities": ["completion"],
                        "model_info": {"fixture.context_length": 2048},
                    },
                )
            ),
        )
        with pytest.raises(ModelError, match="context"):
            _ = [
                event
                async for event in small.generate(
                    ModelRequest(messages=(), context_window=4096)
                )
            ]
        with pytest.raises(ModelError, match="Cloud"):
            await cloud.check_connection()

    asyncio.run(run())
    with pytest.raises(ValueError, match="loopback"):
        OllamaAdapter("fixture", "https://example.com")
    registry = load_registry({"SPACEANALYZER_OLLAMA_MODEL": "fixture"})
    assert registry.list_models()[0].provider == "ollama"
    assert not load_registry({}).list_models()
    invalid = load_registry({"SPACEANALYZER_DEEPSEEK_MODEL": "fixture"})
    assert invalid.diagnostics
    assert not invalid.list_models()
