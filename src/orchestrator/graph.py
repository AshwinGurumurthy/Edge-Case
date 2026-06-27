"""LangGraph wiring for the multi-agent war room.

Topology (matches the spec):

                          +----------------------------+
                          |          BIG BOSS          |  <-- entry & final judge
                          +--------------+-------------+
              dispatch (fan-out) /        \\
                                /          \\
     +-------- REVIEWER subtree --------+   +-------- CONTEXT subtree --------+
     | general    bugs    what-if       |   | repo      mcp      issues       |
     |   \\         |        /           |   |   \\        |        /          |
     |    +--> reviewer (lead) <--+      |   |    +--> context (lead) <--+     |
     +----------------|-----------------+   +-----------------|---------------+
                      \\                                      /
                       \\                                    /
                        +--------------> DEBUGGER <---------+   (aggregates both)
                                            |
                                            v
                                        BIG BOSS  -- RESOLVED? --> END
                                            |  ^
                                            +--+  ITERATE (loop, bounded)

Parallelism is implicit: a node fires once all its in-edges have completed in
the current super-step. So the 3 reviewers run together, the 3 context agents
run together, each lead waits for its 3, and the Debugger waits for both leads.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.big_boss import big_boss_node
from src.agents.context import (
    context_aggregate_node,
    context_issues_node,
    context_mcp_node,
    context_repo_node,
)
from src.agents.debugger import debugger_node
from src.agents.reviewer import (
    reviewer_aggregate_node,
    reviewer_bugs_node,
    reviewer_general_node,
    reviewer_whatif_node,
)
from src.orchestrator.state import WarroomState

# Worker nodes Big Boss fans out to on every (non-final) pass.
_WORKERS = [
    "reviewer_general",
    "reviewer_bugs",
    "reviewer_whatif",
    "context_repo",
    "context_mcp",
    "context_issues",
]


def route_from_boss(state: WarroomState):
    """Big Boss is satisfied -> finish; otherwise fan out to all workers."""
    if state.get("satisfied"):
        return END
    return list(_WORKERS)


def build_graph():
    g = StateGraph(WarroomState)

    # nodes
    g.add_node("big_boss", big_boss_node)
    g.add_node("reviewer_general", reviewer_general_node)
    g.add_node("reviewer_bugs", reviewer_bugs_node)
    g.add_node("reviewer_whatif", reviewer_whatif_node)
    g.add_node("reviewer", reviewer_aggregate_node)
    g.add_node("context_repo", context_repo_node)
    g.add_node("context_mcp", context_mcp_node)
    g.add_node("context_issues", context_issues_node)
    g.add_node("context", context_aggregate_node)
    g.add_node("debugger", debugger_node)

    # entry
    g.set_entry_point("big_boss")

    # Big Boss -> (fan out to workers) | END
    g.add_conditional_edges("big_boss", route_from_boss, [*_WORKERS, END])

    # Reviewer subtree -> reviewer lead
    g.add_edge("reviewer_general", "reviewer")
    g.add_edge("reviewer_bugs", "reviewer")
    g.add_edge("reviewer_whatif", "reviewer")

    # Context subtree -> context lead
    g.add_edge("context_repo", "context")
    g.add_edge("context_mcp", "context")
    g.add_edge("context_issues", "context")

    # both leads converge on the Debugger
    g.add_edge("reviewer", "debugger")
    g.add_edge("context", "debugger")

    # Debugger loops back to Big Boss for the accept/iterate decision
    g.add_edge("debugger", "big_boss")

    return g.compile()
