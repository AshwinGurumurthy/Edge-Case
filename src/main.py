"""CLI entry point.

    python -m src.main                      # run the bundled sample incident
    python -m src.main --incident "..."     # analyze your own incident text
    python -m src.main --incident-file x.txt --repo /path/to/repo
    python -m src.main --graph              # print the graph topology (Mermaid)

Runs the full Big Boss -> subtrees -> Debugger -> Big Boss loop and prints the
final verdict plus the per-node audit trail.
"""
from __future__ import annotations

import argparse
import sys

from config import settings
from src.orchestrator.graph import build_graph

SAMPLE_INCIDENT = (
    "Drill: DB Down. We stopped the Postgres container on the demo checkout app. "
    "Within 0.8s the /checkout endpoint started returning 500s. Success rate dropped "
    "to 41%, p95 latency rose to 4200ms, 137 errors logged. The app container reports "
    "'degraded'. No retries or circuit breaker appear to be in place. What broke, how "
    "bad is it, and what should we fix before real users hit this?"
)


def run(incident: str, repo_path: str) -> dict:
    graph = build_graph()
    init = {"incident": incident, "repo_path": repo_path, "iteration": 0, "log": []}
    # recursion_limit guards the bounded Boss<->Debugger loop.
    return graph.invoke(init, config={"recursion_limit": 50})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="WARROOM multi-agent incident analysis")
    p.add_argument("--incident", help="incident text to analyze")
    p.add_argument("--incident-file", help="path to a file with the incident text")
    p.add_argument("--repo", default=".", help="path to the repo under test (default: .)")
    p.add_argument("--graph", action="store_true", help="print graph topology and exit")
    args = p.parse_args(argv)

    if args.graph:
        print(build_graph().get_graph().draw_mermaid())
        return 0

    if args.incident_file:
        with open(args.incident_file, encoding="utf-8") as fh:
            incident = fh.read()
    else:
        incident = args.incident or SAMPLE_INCIDENT

    print(f"Model split: max_iterations={settings.MAX_ITERATIONS}")
    print("Running war room...\n")
    final = run(incident, args.repo)

    print(final.get("final_response", "(no final response produced)"))
    print("\n--- audit trail ---")
    for line in final.get("log", []):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
