import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

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


def test_model_file_loading_environment_override_and_secret_rejection(
    tmp_path: Path,
) -> None:
    from spaceanalyzer.analysis.models.settings import load_registry

    config = tmp_path / "models.toml"
    config.write_text(
        'version = 1\n[ollama]\nenabled = true\nmodel_id = "file-model"\n'
        "context_window = 4096\nmax_output_tokens = 1024\n",
        encoding="utf-8",
    )
    registry = load_registry({}, config_path=config)
    model = registry.resolve("ollama-local").spec
    assert model.model_id == "file-model"
    assert model.capacity.context_window == 4096
    override = load_registry(
        {"SPACEANALYZER_OLLAMA_MODEL": "env-model"}, config_path=config
    )
    assert override.resolve("ollama-local").spec.model_id == "env-model"
    config.write_text(
        '[deepseek_api]\nenabled=true\nmodel_id="fixture"\napi_key="private-value"\n',
        encoding="utf-8",
    )
    rejected = load_registry({}, config_path=config)
    assert not rejected.list_models()
    assert rejected.diagnostics
    assert "private-value" not in str(rejected.diagnostics)
    config.write_text("invalid = [", encoding="utf-8")
    assert load_registry({}, config_path=config).diagnostics
