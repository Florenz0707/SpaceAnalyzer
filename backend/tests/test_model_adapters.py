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
