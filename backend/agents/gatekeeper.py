import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

from backend.llm.base import LLMProvider
from backend.llm.prompts import SYSTEM_PROMPT


class InvalidLLMResponse(ValueError):
    """A model response cannot safely be treated as a tool recommendation."""


class GatekeeperDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    response: str = Field(min_length=1, max_length=3000)
    decision: Literal["continue_questioning", "deny", "grant"]
    requested_duration_minutes: StrictInt | None
    reasoning_summary: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_decision(self):
        if not self.response.strip() or not self.reasoning_summary.strip():
            raise ValueError("Response and reasoning must not be blank.")
        if self.decision == "grant" and self.requested_duration_minutes is None:
            raise ValueError("Every grant requires a duration.")
        # A model may repeat the user's proposed duration while questioning.
        # Only an explicit grant can dispatch a tool; this value has no effect otherwise.
        return self


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def parse_decision(raw: str) -> GatekeeperDecision:
    try:
        if not isinstance(raw, str) or len(raw) > 20000:
            raise ValueError("Response is missing or too large.")
        payload = json.loads(raw, object_pairs_hook=_unique_object)
        return GatekeeperDecision.model_validate(payload, strict=True)
    except (ValueError, TypeError, ValidationError) as exc:
        raise InvalidLLMResponse("The local model returned an invalid decision. No access was granted. Try again or use another local model.") from exc


class GatekeeperAgent:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def decide(self, messages: list[dict], context: dict) -> GatekeeperDecision:
        model_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "Trusted application context: " + json.dumps(context)},
        ]
        model_messages.extend({"role": row["role"], "content": row["content"]}
                              for row in messages if row["role"] in {"user", "assistant"})
        raw = await self.provider.generate(model_messages, GatekeeperDecision.model_json_schema())
        result = parse_decision(raw)
        if context["round"] >= context["limits"]["max_question_rounds"] and result.decision == "continue_questioning":
            return GatekeeperDecision(
                response="We've reached the question limit without a clear case for access. This request is denied. Start a new request when you have a specific purpose and time limit.",
                decision="deny", requested_duration_minutes=None,
                reasoning_summary="Maximum question rounds reached without a final decision.",
            )
        return result
