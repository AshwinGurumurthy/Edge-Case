"""Debugger node.

The convergence point: it receives the Reviewer subtree's critique and the
Context subtree's factual brief, reconciles disagreements, and produces the
technical verdict + action plan. Output feeds back to Big Boss for the final
accept/iterate decision.
"""
from __future__ import annotations

from src.agents import prompts
from src.agents.base import Agent
from src.orchestrator.state import WarroomState


def debugger_node(state: WarroomState) -> dict:
    user = (
        f"INCIDENT:\n{state['incident']}\n\n"
        f"REVIEWER CRITIQUE (risks/bugs):\n{state.get('review_summary', '')}\n\n"
        f"CONTEXT BRIEF (repo + infra facts):\n{state.get('context_summary', '')}\n\n"
        f"PRIOR BOSS FEEDBACK (if any):\n{state.get('boss_directive', '(none)')}"
    )
    verdict = Agent("debugger", prompts.DEBUGGER).think(user)

    severity = "SEV-2"
    upper = verdict.upper()
    for sev in ("SEV-1", "SEV-2", "SEV-3"):
        if sev in upper:
            severity = sev
            break

    return {
        "diagnosis": verdict,
        "action_plan": verdict,  # the action plan is embedded in the verdict
        "severity": severity,
        "log": [f"[debugger] verdict produced ({severity})"],
    }
