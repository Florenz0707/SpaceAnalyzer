"""Native Ollama adapter, restricted to locally hosted non-cloud models."""

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import httpx2 as httpx

from spaceanalyzer.analysis.models.contracts import ModelError, ModelEvent, ModelRequest
from spaceanalyzer.analysis.models.http import HTTPAdapter, validate_request


class OllamaAdapter(HTTPAdapter):
    def __init__(
        self,
        model_id: str,
        base_url: str = "http://127.0.0.1:11434",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        url = urlsplit(base_url)
        _ = url.port
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise ValueError("Ollama requires an HTTP loopback endpoint")
        if model_id.lower().endswith((":cloud", "-cloud")):
            raise ValueError("Cloud Ollama models are not local")
        super().__init__(model_id, base_url, transport=transport)
        self._model_context: int | None = None

    async def check_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=10,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self._base_url + "/api/show", json={"model": self.model_id}
                )
                self.validate_status(response.status_code)
                data: dict[str, Any] = response.json()
                if data.get("remote_model") or data.get("remote_host"):
                    raise ModelError("unsupported", "Cloud Ollama models are not local")
                if "completion" not in data.get("capabilities", []):
                    raise ModelError(
                        "unsupported", "Model has no declared completion capability"
                    )
                info: dict[str, Any] = data.get("model_info", {})
                windows = [
                    value
                    for key, value in info.items()
                    if key.endswith(".context_length") and isinstance(value, int)
                ]
                self._model_context = min(windows) if windows else None
                return True
        except httpx.HTTPError:
            raise ModelError("connection", "Ollama connection failed") from None
        except (ValueError, TypeError, AttributeError):
            raise ModelError("protocol", "Malformed Ollama model details") from None

    async def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        validate_request(request)
        await self.check_connection()
        context = request.context_window or 8192
        if context > 65536 or (self._model_context and context > self._model_context):
            raise ModelError(
                "context_limit", "Requested local context exceeds model limits"
            )
        payload: dict[str, object] = {
            "model": self.model_id,
            "messages": [m.model_dump() for m in request.messages],
            "stream": True,
            "think": False,
            "options": {"num_predict": request.max_tokens, "num_ctx": context},
        }
        async for line in self.lines("/api/chat", payload):
            if not line.strip():
                continue
            try:
                chunk: dict[str, Any] = json.loads(line)
                if chunk.get("error"):
                    raise ModelError("provider", "Ollama reported a model error")
                message = chunk.get("message", {})
                if message.get("tool_calls"):
                    raise ModelError(
                        "unsupported", "Unexpected tool call in text workflow"
                    )
                if message.get("content"):
                    yield ModelEvent(kind="text", text=message["content"])
                if chunk.get("done") is True:
                    yield ModelEvent(
                        kind="usage",
                        input_tokens=chunk.get("prompt_eval_count"),
                        output_tokens=chunk.get("eval_count"),
                    )
                    yield ModelEvent(
                        kind="finished", reason=chunk.get("done_reason", "stop")
                    )
                    return
            except (ValueError, TypeError, AttributeError):
                raise ModelError("protocol", "Malformed Ollama stream") from None
        raise ModelError("protocol", "Ollama stream ended unexpectedly")
