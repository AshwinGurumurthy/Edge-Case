"""Big Boss node -- incident commander and final decision-maker.

Big Boss is visited twice per loop:

1. **Dispatch** (no diagnosis yet): turn the raw incident into a focused
   directive for the two subtrees, then fan out.
2. **Evaluate** (Debugger has produced a diagnosis): decide RESOLVED vs ITERATE.
   RESOLVED -> write the final response and end. ITERATE -> emit feedback and
   loop the subtrees again, bounded by ``settings.MAX_ITERATIONS``.

The dispatch-vs-evaluate branch is chosen by whether ``diagnosis`` is present,
and routing out of this node is handled by ``route_from_boss`` in graph.py.
"""
from __future__ import annotations

from config import settings
from src.agents import prompts
from src.agents.base import Agent
from src.orchestrator.state import WarroomState


def _final_response(state: WarroomState, boss_summary: str) -> str:
    return (
        "=== WARROOM TECHNICAL VERDICT ===\n"
        f"Severity: {state.get('severity', 'n/a')}\n\n"
        f"{state.get('diagnosis', '')}\n\n"
        "=== BIG BOSS SUMMARY ===\n"
        f"{boss_summary}"
    )


def big_boss_node(state: WarroomState) -> dict:
    boss = Agent("big_boss", prompts.BIG_BOSS_DISPATCH)
    iteration = state.get("iteration", 0)

    # Phase 1: dispatch (first entry, nothing diagnosed yet)
    if not state.get("diagnosis"):
        directive = boss.think(f"INCIDENT:\n{state['incident']}")
        return {
            "boss_directive": directive,
            "iteration": 0,
            "satisfied": False,
            "log": ["[big_boss] dispatched directive to subtrees"],
        }

    # Phase 2: evaluate the Debugger's diagnosis
    evaluator = Agent("big_boss", prompts.BIG_BOSS_EVAL)
    verdict = evaluator.think(
        f"INCIDENT:\n{state['incident']}\n\n"
        f"DEBUGGER DIAGNOSIS + ACTION PLAN:\n{state.get('diagnosis', '')}"
    )
    next_iter = iteration + 1
    resolved = "RESOLVED" in verdict.upper()
    forced_stop = next_iter >= settings.MAX_ITERATIONS

    if resolved or forced_stop:
        note = "" if resolved else "\n\n(Max iterations reached -- shipping best diagnosis.)"
        return {
            "iteration": next_iter,
            "satisfied": True,
            "final_response": _final_response(state, verdict + note),
            "log": [f"[big_boss] RESOLVED (iteration {next_iter})"],
        }

    # Not good enough -- loop the subtrees again with feedback.
    return {
        "iteration": next_iter,
        "satisfied": False,
        "boss_directive": verdict,
        "log": [f"[big_boss] ITERATE (iteration {next_iter})"],
    }
