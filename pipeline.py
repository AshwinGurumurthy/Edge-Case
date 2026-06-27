"""Run the full scanner → scenario pipeline.

Usage:
    python pipeline.py <local-path-or-git-url> [output.md]

Examples:
    python pipeline.py .
    python pipeline.py /path/to/project
    python pipeline.py https://github.com/owner/repo.git
    python pipeline.py https://github.com/owner/repo.git scenarios.md

Scans the target codebase, then generates testing scenarios from the scan.
Writes scenarios to a .md file (default: scenarios.md).
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from langgraph.graph import END, START, StateGraph

from scanner_agent.agent import scanner_node
from scanner_agent.state import GraphState
from scenario_agent.agent import scenario_node


def build_pipeline():
    builder = StateGraph(GraphState)
    builder.add_node("scanner", scanner_node)
    builder.add_node("scenario", scenario_node)
    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", "scenario")
    builder.add_edge("scenario", END)
    return builder.compile()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 1

    target = sys.argv[1]
    output_md = sys.argv[2] if len(sys.argv) == 3 else "scenarios.md"

    pipeline = build_pipeline()

    print(f"[pipeline] Scanning: {target}", file=sys.stderr)
    result = pipeline.invoke({"target": target})

    if result.get("scan_error"):
        print(f"[pipeline] SCAN FAILED: {result['scan_error']}")
        return 1

    meta = result.get("scan_meta", {})
    print(
        f"[pipeline] Scanned {meta.get('files_scanned')}/{meta.get('files_total')} files",
        file=sys.stderr,
    )

    scenarios = result.get("scenario_output", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"# Testing Scenarios\n\n> Generated: {timestamp}\n> Target: `{target}`\n\n---\n\n{scenarios}\n"

    Path(output_md).write_text(content, encoding="utf-8")
    print(f"[pipeline] Scenarios written to: {output_md}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
