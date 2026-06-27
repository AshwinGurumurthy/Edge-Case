"""Minimal LangGraph wiring for the scanner.

This compiles a runnable graph containing ONLY the scanner node, so it can be
exercised on its own. It is also the integration point for the wider architecture:
downstream agents attach by reading `state["scan_context"]` (see the commented
edges below).
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .agent import scanner_node
from .state import GraphState


def build_graph():
    """Build and compile the scanner-only graph."""
    builder = StateGraph(GraphState)
    builder.add_node("scanner", scanner_node)
    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", END)

    # --- Downstream agents plug in here (not part of this deliverable) ---
    # They consume state["scan_context"], e.g.:
    #
    #   builder.add_node("planner", planner_node)
    #   builder.add_node("generator", generator_node)
    #   builder.add_edge("scanner", "planner")
    #   builder.add_edge("planner", "generator")
    #   builder.add_edge("generator", END)
    #
    # Each can inject context into its own prompt via:
    #   state["scan_context"].as_prompt_context()
    # --------------------------------------------------------------------

    return builder.compile()


graph = build_graph()
