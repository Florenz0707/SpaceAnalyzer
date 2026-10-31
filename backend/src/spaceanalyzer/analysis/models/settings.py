"""Optional environment configuration; invalid models never disable scanning."""

import os
from collections.abc import Mapping

from spaceanalyzer.analysis.models.contracts import ModelCapacity, ModelSpec
from spaceanalyzer.analysis.models.deepseek import DeepSeekAdapter
from spaceanalyzer.analysis.models.ollama import OllamaAdapter
from spaceanalyzer.analysis.models.registry import ModelRegistry


def capacity(
    env: Mapping[str, str], prefix: str, default_context: int | None
) -> ModelCapacity:
    raw = env.get(prefix + "_CONTEXT_WINDOW", "")
    context = int(raw) if raw else default_context
    output = int(env.get(prefix + "_MAX_OUTPUT_TOKENS", "2048"))
    if context is not None and not 1024 <= context <= 2_000_000:
        raise ValueError("Invalid context window")
    if not 1 <= output <= 8192:
        raise ValueError("Invalid output budget")
    if context is not None and context <= output + 512:
        raise ValueError("Context window must include input and output budgets")
    return ModelCapacity(context_window=context, max_output_tokens=output)


def load_registry(environment: Mapping[str, str] | None = None) -> ModelRegistry:
    env = os.environ if environment is None else environment
    registry = ModelRegistry()
    deepseek = env.get("SPACEANALYZER_DEEPSEEK_MODEL", "").strip()
    if deepseek:
        try:
            key = env.get("DEEPSEEK_API_KEY", "").strip()
            if not key:
                raise ValueError("Missing key")
            spec = ModelSpec(
                key="deepseek-default",
                provider="deepseek_api",
                model_id=deepseek,
                capacity=capacity(env, "SPACEANALYZER_DEEPSEEK", None),
            )
            registry.register(spec, DeepSeekAdapter(deepseek, key))
        except ValueError:
            registry.diagnostics.append(
                "DeepSeek configuration invalid; check model, key and budgets"
            )
    ollama = env.get("SPACEANALYZER_OLLAMA_MODEL", "").strip()
    if ollama:
        try:
            limits = capacity(env, "SPACEANALYZER_OLLAMA", 8192)
            if (limits.context_window or 0) > 65536:
                raise ValueError("Local context budget exceeds application limit")
            adapter = OllamaAdapter(
                ollama, env.get("SPACEANALYZER_OLLAMA_URL", "http://127.0.0.1:11434")
            )
            registry.register(
                ModelSpec(
                    key="ollama-local",
                    provider="ollama",
                    model_id=ollama,
                    capacity=limits,
                ),
                adapter,
            )
        except ValueError:
            registry.diagnostics.append(
                "Ollama configuration invalid; check local model, URL and budgets"
            )
    return registry
