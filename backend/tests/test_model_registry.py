import asyncio
from collections.abc import AsyncIterator

import pytest

from spaceanalyzer.analysis.models.contracts import (
    ModelCapacity,
    ModelEvent,
    ModelRequest,
    ModelSpec,
)
from spaceanalyzer.analysis.models.registry import ModelRegistry


class UnusedAdapter:
    async def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        yield ModelEvent(kind="finished", reason="stop")

    async def check_connection(self) -> bool:
        return True


def test_registry_validates_capability_and_hides_configuration() -> None:
    registry = ModelRegistry()
    spec = ModelSpec(key="local", provider="ollama", model_id="fixture")
    registry.register(spec, UnusedAdapter())
    assert registry.resolve("local").spec.model_id == "fixture"
    assert asyncio.run(registry.resolve("local").adapter.check_connection())
    with pytest.raises(ValueError, match="capability"):
        registry.resolve("local", ModelCapacity(tool_calling=True))
    with pytest.raises(ValueError, match="already"):
        registry.register(spec, UnusedAdapter())
    with pytest.raises(KeyError):
        registry.resolve("unknown")
    assert registry.list_models()[0].capacity.streaming
