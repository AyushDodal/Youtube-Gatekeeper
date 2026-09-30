"""Ollama's local HTTP API with schema-constrained, non-streaming output."""

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.llm.base import LLMProvider, ProviderUnavailable


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must point to a local loopback HTTP server.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OLLAMA_BASE_URL must not contain credentials, a query, or a fragment.")
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(180, connect=3), trust_env=False)
        self._health: dict[str, Any] | None = None
        self._health_at = 0.0

    def _missing_model_message(self) -> str:
        if not self.model:
            return "No local model configured. Set OLLAMA_MODEL in .env to a model installed in Ollama, then restart the backend."
        return f"Ollama model '{self.model}' is not installed. Pull it with Ollama, or set OLLAMA_MODEL to an installed model."

    async def health(self) -> dict[str, Any]:
        if self._health is not None and time.monotonic() - self._health_at < 10:
            return dict(self._health)
        result = {"name": self.model or "Not configured", "available": False, "error": None}
        if not self.model:
            result["error"] = self._missing_model_message()
        else:
            try:
                response = await self._client.get("/api/tags", timeout=2)
                response.raise_for_status()
                payload = response.json()
                names = {item.get("name", item.get("model", "")) for item in payload.get("models", [])}
                normalized = self.model if ":" in self.model else f"{self.model}:latest"
                result["available"] = self.model in names or normalized in names
                if not result["available"]:
                    result["error"] = self._missing_model_message()
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                result["error"] = f"Cannot reach Ollama at {self.base_url}. Start Ollama and check OLLAMA_BASE_URL."
        self._health = result
        self._health_at = time.monotonic()
        return dict(result)

    async def generate(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        if not self.model:
            raise ProviderUnavailable(self._missing_model_message())
        try:
            response = await self._client.post(
                "/api/chat",
                json={"model": self.model, "messages": messages, "format": schema, "stream": False,
                      "options": {"temperature": 0.35, "num_predict": 1200}},
            )
            if response.status_code == 404:
                raise ProviderUnavailable(self._missing_model_message())
            response.raise_for_status()
            payload = response.json()
            content = payload.get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise ProviderUnavailable("Ollama returned an empty response. Check that the configured model supports structured output.")
            return content
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("The local model took too long to respond. Try again, or choose a smaller model. YouTube access was not changed.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(f"Ollama rejected the request (HTTP {exc.response.status_code}). Check the local model and Ollama logs.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Cannot reach Ollama at {self.base_url}. Start Ollama and try again.") from exc
        except (ValueError, TypeError, AttributeError) as exc:
            raise ProviderUnavailable("Ollama returned an invalid API response. YouTube access was not changed.") from exc

    async def close(self) -> None:
        await self._client.aclose()
