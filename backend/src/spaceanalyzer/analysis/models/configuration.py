"""Strict local model configuration without inline credential fields."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MODELS_FILE = Path(__file__).resolve().parents[4] / "config/models.toml"


class ProviderFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    model_id: str = Field(default="", max_length=200)
    context_window: int | None = Field(default=None, ge=1024, le=2_000_000)
    max_output_tokens: int = Field(default=2048, ge=1, le=8192)


class OllamaFile(ProviderFile):
    base_url: str = "http://127.0.0.1:11434"
    context_window: int | None = 8192


class ModelsFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    deepseek_api: ProviderFile = ProviderFile()
    ollama: OllamaFile = OllamaFile()


def file_environment(path: Path) -> dict[str, str]:
    with path.open("rb") as file:
        config = ModelsFile.model_validate(tomllib.load(file))
    env: dict[str, str] = {}
    for prefix, provider in (
        ("SPACEANALYZER_DEEPSEEK", config.deepseek_api),
        ("SPACEANALYZER_OLLAMA", config.ollama),
    ):
        if not provider.enabled:
            continue
        if not provider.model_id.strip():
            raise ValueError("Enabled provider requires a model ID")
        env[prefix + "_MODEL"] = provider.model_id.strip()
        env[prefix + "_MAX_OUTPUT_TOKENS"] = str(provider.max_output_tokens)
        if provider.context_window is not None:
            env[prefix + "_CONTEXT_WINDOW"] = str(provider.context_window)
    if config.ollama.enabled:
        env["SPACEANALYZER_OLLAMA_URL"] = config.ollama.base_url
    return env
