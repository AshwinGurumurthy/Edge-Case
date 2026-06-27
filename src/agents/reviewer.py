"""Reviewer subtree (local Ollama).

Three specialist critics fan out in parallel -- General, Bugs, What-If -- then a
Reviewer Lead aggregates them. All run on local models: critique/opinion work is
cheap, private, and benefits from a diverse panel rather than one strong model.
"""
from __future__ import annotations

from src.agents import prompts
from src.agents.base import Agent
from src.orchestrator.state import WarroomState


def _brief(state: WarroomState) -> str:
    return (
        f"INCIDENT:\n{state['incident']}\n\n"
        f"BIG BOSS DIRECTIVE:\n{state.get('boss_directive', '(none)')}"
    )


def reviewer_general_node(state: WarroomState) -> dict:
    out = Agent("reviewer_general", prompts.REVIEWER_GENERAL).think(_brief(state))
    return {"review_general": out, "log": ["[reviewer_general] done"]}


def reviewer_bugs_node(state: WarroomState) -> dict:
    out = Agent("reviewer_bugs", prompts.REVIEWER_BUGS).think(_brief(state))
    return {"review_bugs": out, "log": ["[reviewer_bugs] done"]}


def reviewer_whatif_node(state: WarroomState) -> dict:
    out = Agent("reviewer_whatif", prompts.REVIEWER_WHATIF).think(_brief(state))
    return {"review_whatif": out, "log": ["[reviewer_whatif] done"]}


def reviewer_aggregate_node(state: WarroomState) -> dict:
    user = (
        f"GENERAL REVIEW:\n{state.get('review_general', '')}\n\n"
        f"BUGS REVIEW:\n{state.get('review_bugs', '')}\n\n"
        f"WHAT-IF REVIEW:\n{state.get('review_whatif', '')}"
    )
    summary = Agent("reviewer", prompts.REVIEWER_AGGREGATE).think(user)
    return {"review_summary": summary, "log": ["[reviewer] aggregated subtree"]}
