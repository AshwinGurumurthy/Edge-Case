"""Base agent: a name + a system prompt + its configured LLM client.

Every node in the graph is built on top of this. The agent name is the key into
``settings.AGENT_MODELS``, so the model split is resolved automatically.
"""
from __future__ import annotations

from src.llm.clients import client_for


class Agent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = client_for(name)

    def think(self, user_prompt: str) -> str:
        return self.client.complete(self.system_prompt, user_prompt)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Agent {self.name} backend={self.client.__class__.__name__}>"
