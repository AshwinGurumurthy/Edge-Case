"""Uniform LLM client layer.

Two backends -- local Ollama and Anthropic cloud -- behind one tiny interface:

    client.complete(system: str, user: str) -> str

Design choice: **graceful degradation.** If Ollama is not running or the
Anthropic key is missing, the client does not crash; it returns a clearly
labelled ``[STUB::...]`` string. That keeps the entire orchestration graph
runnable end-to-end for demos and CI even with zero infra configured, while
making it obvious in the output which agent was stubbed.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import settings


class LLMClient:
    """Interface every backend implements."""

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        raise NotImplementedError


def _stub(backend: str, user: str, reason: object) -> str:
    preview = user.strip().replace("\n", " ")[:200]
    return (
        f"[STUB::{backend}] (backend unavailable: {reason}) "
        f"Returning a simulated response so the graph keeps running. "
        f"Prompt preview: {preview}..."
    )


@dataclass
class OllamaClient(LLMClient):
    """Local model via Ollama's REST API (/api/chat)."""

    model: str
    host: str = settings.OLLAMA_HOST
    temperature: float = 0.2
    timeout: int = 180

    def complete(self, system: str, user: str) -> str:
        try:
            import requests

            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except Exception as exc:  # network down, model not pulled, etc.
            return _stub(f"ollama:{self.model}", user, exc)


@dataclass
class AnthropicClient(LLMClient):
    """Anthropic Messages API."""

    model: str
    max_tokens: int = 1500
    temperature: float = 0.2

    def complete(self, system: str, user: str) -> str:
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return _stub(f"anthropic:{self.model}", user, "ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in msg.content if b.type == "text").strip()
        except Exception as exc:
            return _stub(f"anthropic:{self.model}", user, exc)


def make_client(spec: settings.ModelSpec) -> LLMClient:
    if spec.backend == "ollama":
        return OllamaClient(model=spec.model, host=settings.OLLAMA_HOST)
    if spec.backend == "anthropic":
        return AnthropicClient(model=spec.model)
    raise ValueError(f"Unknown backend: {spec.backend!r}")


def client_for(agent_name: str) -> LLMClient:
    """Resolve an agent name to its configured client (see settings.AGENT_MODELS)."""
    return make_client(settings.spec_for(agent_name))
