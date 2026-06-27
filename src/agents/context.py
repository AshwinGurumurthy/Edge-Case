"""Context subtree (Anthropic).

Three fact-gathering agents fan out in parallel -- Understand Repo, MCP, Common
Issues -- then a Context Lead aggregates them. These run on Anthropic because
grounding in real repo structure, infra telemetry, and known failure patterns
needs strong long-context reasoning.
"""
from __future__ import annotations

from src.agents import prompts
from src.agents.base import Agent
from src.mcp.client import MCPClient
from src.orchestrator.state import WarroomState
from src.tools.repo import summarize_repo


def context_repo_node(state: WarroomState) -> dict:
    repo_facts = summarize_repo(state.get("repo_path", "."))
    user = (
        f"INCIDENT:\n{state['incident']}\n\n"
        f"REPO SIGNALS:\n{repo_facts}"
    )
    out = Agent("context_repo", prompts.CONTEXT_REPO).think(user)
    return {"context_repo": out, "log": ["[context_repo] done"]}


def context_mcp_node(state: WarroomState) -> dict:
    user = (
        f"INCIDENT:\n{state['incident']}\n\n"
        f"{MCPClient().as_context()}"
    )
    out = Agent("context_mcp", prompts.CONTEXT_MCP).think(user)
    return {"context_mcp": out, "log": ["[context_mcp] done"]}


def context_issues_node(state: WarroomState) -> dict:
    out = Agent("context_issues", prompts.CONTEXT_ISSUES).think(
        f"INCIDENT:\n{state['incident']}"
    )
    return {"context_issues": out, "log": ["[context_issues] done"]}


def context_aggregate_node(state: WarroomState) -> dict:
    user = (
        f"REPO UNDERSTANDING:\n{state.get('context_repo', '')}\n\n"
        f"MCP / INFRA:\n{state.get('context_mcp', '')}\n\n"
        f"COMMON ISSUES:\n{state.get('context_issues', '')}"
    )
    summary = Agent("context", prompts.CONTEXT_AGGREGATE).think(user)
    return {"context_summary": summary, "log": ["[context] aggregated subtree"]}
