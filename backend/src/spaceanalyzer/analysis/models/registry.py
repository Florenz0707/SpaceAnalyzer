"""Explicit model registration without credentials in the public catalogue."""

from dataclasses import dataclass

from spaceanalyzer.analysis.models.contracts import (
    ModelAdapter,
    ModelCapacity,
    ModelSpec,
)


@dataclass(frozen=True)
class ResolvedModel:
    spec: ModelSpec
    adapter: ModelAdapter


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ResolvedModel] = {}
        self.diagnostics: list[str] = []

    def register(self, spec: ModelSpec, adapter: ModelAdapter) -> None:
        if spec.key in self._models:
            raise ValueError("Model key already registered")
        self._models[spec.key] = ResolvedModel(spec, adapter)

    def list_models(self) -> list[ModelSpec]:
        return [model.spec for model in self._models.values()]

    def resolve(
        self, key: str, requirements: ModelCapacity | None = None
    ) -> ResolvedModel:
        if key not in self._models:
            raise KeyError("Unknown model key")
        model = self._models[key]
        needed = requirements or ModelCapacity()
        capacity = model.spec.capacity
        for field in ("text_generation", "streaming", "tool_calling", "reasoning"):
            if getattr(needed, field) and not getattr(capacity, field):
                raise ValueError(f"Model capability not available: {field}")
        formats = ["none", "json", "schema"]
        if formats.index(needed.structured_output) > formats.index(
            capacity.structured_output
        ):
            raise ValueError("Model capability not available: structured_output")
        return model
