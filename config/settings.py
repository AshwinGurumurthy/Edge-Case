"""Central configuration for the multi-agent system.

The single most important thing here is ``AGENT_MODELS``: it declares which
LLM backend (local Ollama vs Anthropic cloud) and which model backs each agent.
This is *the* model-split table for the whole architecture -- change one line
here to re-point any agent at a different model with no code edits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional, but convenient
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


# --- raw env-backed defaults -------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")          # heavier local
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma4:e2b")  # lighter local
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

MAX_ITERATIONS = int(os.getenv("WARROOM_MAX_ITERATIONS", "2"))


@dataclass(frozen=True)
class ModelSpec:
    """Which backend + model an agent uses."""

    backend: str  # "ollama" | "anthropic"
    model: str


# --- THE MODEL SPLIT ---------------------------------------------------------
# Reviewer subtree  -> local Ollama  (fast, private, free; opinion/critique work)
# Context subtree   -> Anthropic     (needs strong reasoning over repo/docs/MCP)
# Big Boss/Debugger -> local Ollama  (orchestration + synthesis)
AGENT_MODELS: dict[str, ModelSpec] = {
    # orchestration / synthesis
    "big_boss": ModelSpec("ollama", OLLAMA_MODEL),
    "debugger": ModelSpec("ollama", OLLAMA_MODEL),
    # Reviewer subtree (local Ollama)
    "reviewer": ModelSpec("ollama", OLLAMA_MODEL),
    "reviewer_general": ModelSpec("ollama", OLLAMA_FAST_MODEL),
    "reviewer_bugs": ModelSpec("ollama", OLLAMA_FAST_MODEL),
    "reviewer_whatif": ModelSpec("ollama", OLLAMA_MODEL),
    # Context subtree (Anthropic)
    "context": ModelSpec("anthropic", ANTHROPIC_MODEL),
    "context_repo": ModelSpec("anthropic", ANTHROPIC_MODEL),
    "context_mcp": ModelSpec("anthropic", ANTHROPIC_MODEL),
    "context_issues": ModelSpec("anthropic", ANTHROPIC_MODEL),
}


def spec_for(agent_name: str) -> ModelSpec:
    if agent_name not in AGENT_MODELS:
        raise KeyError(f"No model configured for agent '{agent_name}'")
    return AGENT_MODELS[agent_name]
