"""DeepSeek Chat Completions SSE adapter; no SDK objects escape this module."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2 as httpx

from spaceanalyzer.analysis.models.contracts import ModelError, ModelEvent, ModelRequest
from spaceanalyzer.analysis.models.http import HTTPAdapter, validate_request


class DeepSeekAdapter(HTTPAdapter):
    def __init__(
        self,
        model_id: str,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            model_id,
            "https://api.deepseek.com",
            {"Authorization": f"Bearer {api_key}"},
            transport,
        )

    async def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        validate_request(request)
        payload: dict[str, object] = {
            "model": self.model_id,
            "stream": True,
            "messages": [message.model_dump() for message in request.messages],
            "max_tokens": request.max_tokens,
            "thinking": {"type": "disabled"},
            "stream_options": {"include_usage": True},
        }
        data: list[str] = []
        reason: str | None = None
        async for line in self.lines("/chat/completions", payload):
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif not line and data:
                raw = "\n".join(data)
                data.clear()
                if raw == "[DONE]":
                    if reason is None:
                        raise ModelError(
                            "protocol", "Provider ended without a finish reason"
                        )
                    yield ModelEvent(kind="finished", reason=reason)
                    return
                try:
                    chunk: dict[str, Any] = json.loads(raw)
                    if "error" in chunk:
                        raise ModelError("provider", "Model stream reported an error")
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta", {})
                        if delta.get("tool_calls"):
                            raise ModelError(
                                "unsupported", "Unexpected tool call in text workflow"
                            )
                        if delta.get("content"):
                            yield ModelEvent(kind="text", text=delta["content"])
                        if choice.get("finish_reason"):
                            reason = str(choice["finish_reason"])
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                        yield ModelEvent(
                            kind="usage",
                            input_tokens=usage.get("prompt_tokens"),
                            output_tokens=usage.get("completion_tokens"),
                        )
                except (ValueError, TypeError, AttributeError):
                    raise ModelError("protocol", "Malformed model stream") from None
        raise ModelError("protocol", "Model stream ended unexpectedly")
