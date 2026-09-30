"""The provider boundary never has operating-system or tool access."""

from abc import ABC, abstractmethod
from typing import Any


class ProviderUnavailable(RuntimeError):
    """A local model cannot complete the request."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        """Return the model's complete JSON text, without interpreting its actions."""

    async def health(self) -> dict[str, Any]:
        return {"name": "custom provider", "available": True, "error": None}

    async def close(self) -> None:
        """Release resources when the application stops."""
