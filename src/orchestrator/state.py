"""Shared state passed between all graph nodes.

LangGraph merges each node's returned dict into this state. ``log`` uses an
``operator.add`` reducer so concurrent nodes can append without clobbering each
other (every other field is last-writer-wins, which is what we want).
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class WarroomState(TypedDict, total=False):
    # --- inputs ---
    incident: str          # the failure/scenario to analyze (plain English + metrics)
    repo_path: str         # path to the codebase under test
    iteration: int         # Boss<->Debugger refinement loop counter

    # --- Big Boss ---
    boss_directive: str    # what the Boss is asking the subtrees to focus on
    satisfied: bool        # Boss verdict: is the diagnosis good enough to ship?
    final_response: str    # the answer returned to the user

    # --- Reviewer subtree (local Ollama) ---
    review_general: str
    review_bugs: str
    review_whatif: str
    review_summary: str    # Reviewer aggregator output

    # --- Context subtree (Anthropic) ---
    context_repo: str
    context_mcp: str
    context_issues: str
    context_summary: str   # Context aggregator output

    # --- Debugger ---
    diagnosis: str         # technical verdict: what failed + likely cause
    severity: str          # e.g. SEV-1 / SEV-2 / SEV-3
    action_plan: str       # fix-now / improve-next / harden steps

    # --- audit trail (append-only across parallel nodes) ---
    log: Annotated[list[str], operator.add]
