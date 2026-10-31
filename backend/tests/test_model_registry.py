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


def test_invalid_optional_model_configuration_does_not_disable_scanning() -> None:
    from spaceanalyzer.analysis.models.settings import load_registry

    registry = load_registry(
        {
            "SPACEANALYZER_DEEPSEEK_MODEL": "x" * 201,
            "DEEPSEEK_API_KEY": "synthetic-secret",
        }
    )
    assert not registry.list_models()
    assert registry.diagnostics
    assert "synthetic-secret" not in str(registry.diagnostics)
    local = load_registry(
        {
            "SPACEANALYZER_OLLAMA_MODEL": "fixture",
            "SPACEANALYZER_OLLAMA_CONTEXT_WINDOW": "4096",
        }
    )
    assert local.resolve("ollama-local").spec.capacity.context_window == 4096
