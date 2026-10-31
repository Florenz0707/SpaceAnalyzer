"""Optional environment configuration; invalid models never disable scanning."""

import os
from collections.abc import Mapping

from spaceanalyzer.analysis.models.contracts import ModelSpec
from spaceanalyzer.analysis.models.deepseek import DeepSeekAdapter
from spaceanalyzer.analysis.models.ollama import OllamaAdapter
from spaceanalyzer.analysis.models.registry import ModelRegistry


def load_registry(environment: Mapping[str, str] | None = None) -> ModelRegistry:
    env = os.environ if environment is None else environment
    registry = ModelRegistry()
    deepseek = env.get("SPACEANALYZER_DEEPSEEK_MODEL", "").strip()
    if deepseek:
        key = env.get("DEEPSEEK_API_KEY", "").strip()
        if key:
            registry.register(
                ModelSpec(
                    key="deepseek-default", provider="deepseek_api", model_id=deepseek
                ),
                DeepSeekAdapter(deepseek, key),
            )
        else:
            registry.diagnostics.append("DeepSeek configured without DEEPSEEK_API_KEY")
    ollama = env.get("SPACEANALYZER_OLLAMA_MODEL", "").strip()
    if ollama:
        try:
            adapter = OllamaAdapter(
                ollama, env.get("SPACEANALYZER_OLLAMA_URL", "http://127.0.0.1:11434")
            )
            registry.register(
                ModelSpec(key="ollama-local", provider="ollama", model_id=ollama),
                adapter,
            )
        except ValueError:
            registry.diagnostics.append(
                "Ollama configuration is invalid; use a local model and loopback URL"
            )
    return registry
