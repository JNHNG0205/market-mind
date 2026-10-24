"""JSON output validated against a Pydantic model, with one corrective retry (DECISIONS.md D6)."""

import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from string import Template

from pydantic import BaseModel, ValidationError

from marketmind.llm.base import LLMProvider
from marketmind.llm.types import LLMMessage, LLMOutputError, LLMRequest, LLMUsage


@dataclass(frozen=True, slots=True)
class JsonResult[T: BaseModel]:
    value: T
    usage: LLMUsage  # summed over every attempt
    attempts: int


@cache
def _prompt(name: str) -> Template:
    return Template(files("marketmind.llm.prompts").joinpath(f"{name}.md").read_text())


def _with_schema_instruction(request: LLMRequest, schema: dict[str, object]) -> LLMRequest:
    instruction = _prompt("json_output").substitute(schema=json.dumps(schema, indent=2))
    messages = list(request.messages)
    if messages and messages[0].role == "system":
        first = messages[0]
        messages[0] = first.model_copy(update={"content": f"{first.content}\n\n{instruction}"})
    else:
        messages.insert(0, LLMMessage(role="system", content=instruction))
    return request.model_copy(update={"messages": messages, "response_schema": schema})


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.removesuffix("```").strip()
    return text


async def complete_json[T: BaseModel](
    llm: LLMProvider, request: LLMRequest, model: type[T], *, retries: int = 1
) -> JsonResult[T]:
    """Ask for JSON matching `model`. Raises `LLMOutputError` once `retries` are spent."""
    current = _with_schema_instruction(request, model.model_json_schema())
    usage = LLMUsage()
    error = ""
    for attempt in range(1, retries + 2):
        response = await llm.complete(current)
        usage = usage + response.usage
        try:
            value = model.model_validate_json(_strip_fences(response.text))
        except ValidationError as exc:
            error = str(exc)[:1000]
            retry = LLMMessage(role="user", content=_prompt("json_retry").substitute(error=error))
            current = current.model_copy(
                update={"messages": [*current.messages, response.as_message(), retry]}
            )
            continue
        return JsonResult(value=value, usage=usage, attempts=attempt)
    raise LLMOutputError(f"invalid structured output: {error}", attempts=retries + 1)
