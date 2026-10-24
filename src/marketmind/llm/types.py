"""Provider-neutral request/response types shared by every LLM adapter."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class LLMToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class LLMMessage(BaseModel):
    role: Role
    content: str = ""
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None  # set when role == "tool"
    # The assistant turn exactly as the provider returned it (reasoning / thinking blocks
    # included). Adapters echo it back verbatim, since some providers reject edited history.
    provider_raw: dict[str, Any] | None = None


class LLMToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class LLMUsage(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            usd=self.usd + other.usd,
        )


class LLMRequest(BaseModel):
    node: str  # graph node making the call: router, select_skills, planner, composer
    model: str
    messages: list[LLMMessage]
    tools: list[LLMToolSpec] = Field(default_factory=list)
    # Ask for a JSON object matching this schema (JSON mode or native structured output).
    response_schema: dict[str, Any] | None = None
    temperature: float | None = None  # ignored by providers that removed sampling params
    max_tokens: int = 2048


class LLMResponse(BaseModel):
    text: str
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model: str
    finish_reason: str
    provider_raw: dict[str, Any] | None = None

    def as_message(self) -> LLMMessage:
        """The assistant turn to append to history before the next call."""
        return LLMMessage(
            role="assistant",
            content=self.text,
            tool_calls=self.tool_calls,
            provider_raw=self.provider_raw,
        )


class TextDelta(BaseModel):
    text: str


class StreamDone(BaseModel):
    response: LLMResponse


StreamEvent = TextDelta | StreamDone


class LLMError(Exception):
    """A provider call failed. `retryable` errors (timeouts, 429, 5xx) are eligible for fallback."""

    def __init__(self, message: str, *, retryable: bool, provider: str) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.provider = provider


class LLMOutputError(Exception):
    """Structured output still failed validation after the allowed retries."""

    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts
