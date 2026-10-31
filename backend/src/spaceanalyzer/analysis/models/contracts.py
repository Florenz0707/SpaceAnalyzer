"""Small model interface; transport details stay inside adapters."""

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelCapacity(Record):
    text_generation: bool = True
    streaming: bool = True
    tool_calling: bool = False
    structured_output: Literal["none", "json", "schema"] = "none"
    reasoning: bool = False
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)


class ModelSpec(Record):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    provider: Literal["deepseek_api", "ollama"]
    model_id: str = Field(min_length=1, max_length=200)
    capacity: ModelCapacity = ModelCapacity()


class Message(Record):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolDefinition(Record):
    name: str
    description: str
    parameters: dict[str, object]


class ModelRequest(Record):
    messages: tuple[Message, ...]
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    tools: tuple[ToolDefinition, ...] = ()
    # Reserved contracts; first release runs fixed queries and never executes calls.
    reasoning: bool = False
    output_format: Literal["text", "json", "schema"] = "text"


class ModelEvent(Record):
    kind: Literal["text", "tool_call", "usage", "finished"]
    text: str = ""
    call_id: str | None = None
    name: str | None = None
    arguments: dict[str, object] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reason: str | None = None


class ModelError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ModelAdapter(Protocol):
    def generate(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...

    async def check_connection(self) -> bool: ...
