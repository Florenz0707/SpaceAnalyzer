"""Bounded, cancellable HTTP streams with sanitized provider errors."""

from collections.abc import AsyncIterator

import httpx2 as httpx

from spaceanalyzer.analysis.models.contracts import ModelError, ModelRequest


def validate_request(request: ModelRequest) -> None:
    if request.tools or request.reasoning or request.output_format != "text":
        raise ModelError("unsupported", "This release supports text generation only")


class HTTPAdapter:
    def __init__(
        self,
        model_id: str,
        base_url: str,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._transport = transport

    async def lines(self, path: str, payload: dict[str, object]) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                trust_env=False,
                timeout=httpx.Timeout(60, connect=10),
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    "POST", self._base_url + path, headers=self._headers, json=payload
                ) as response:
                    self.validate_status(response.status_code)
                    total = 0
                    async for line in response.aiter_lines():
                        total += len(line)
                        if len(line) > 262144 or total > 2_000_000:
                            raise ModelError(
                                "protocol", "Provider response exceeded limits"
                            )
                        yield line
        except httpx.TimeoutException:
            raise ModelError("timeout", "Model request timed out") from None
        except httpx.HTTPError:
            raise ModelError("connection", "Model connection failed") from None

    @staticmethod
    def validate_status(status: int) -> None:
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            raise ModelError("authentication", "Model authentication failed")
        if status == 429:
            raise ModelError("rate_limit", "Model rate limit reached")
        if status == 404:
            raise ModelError("not_found", "Model or endpoint not found")
        raise ModelError("provider", f"Model request failed (HTTP {status})")

    async def check_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                trust_env=False,
                timeout=10,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    self._base_url + self.discovery_path, headers=self._headers
                )
                self.validate_status(response.status_code)
                return True
        except httpx.HTTPError:
            raise ModelError("connection", "Model connection failed") from None

    discovery_path = "/models"
