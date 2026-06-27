"""Scanner agent — a LangGraph node that reads a target codebase and produces a
structured `ScanContext` that downstream agents in the graph consume.

This package intentionally ships ONLY the scanner node. It is built to plug into a
larger multi-agent LangGraph architecture: it writes its result onto shared graph
state (`scan_context`) so later nodes (planner, generator, reviewer, …) can read it.
"""

from .state import GraphState, ScanContext, Feature, WorkflowStep
from .agent import scanner_node, synthesize
from .collector import collect, CollectedCode
from .graph import build_graph

__all__ = [
    "GraphState",
    "ScanContext",
    "Feature",
    "WorkflowStep",
    "scanner_node",
    "synthesize",
    "collect",
    "CollectedCode",
    "build_graph",
]
