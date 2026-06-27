"""Run the scanner agent on a target codebase.

Usage:
    python run_scanner.py <local-path-or-git-url> [output.md]

Examples:
    python run_scanner.py .
    python run_scanner.py /path/to/project
    python run_scanner.py https://github.com/owner/repo.git
    python run_scanner.py https://github.com/owner/repo.git context.md

Writes the rendered context to a .md file (default: scan_context.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scanner_agent import build_graph


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 1

    target = sys.argv[1]
    output_md = sys.argv[2] if len(sys.argv) == 3 else "scan_context.md"

    graph = build_graph()
    result = graph.invoke({"target": target, "output_md": output_md})

    if result.get("scan_error"):
        print(f"SCAN FAILED: {result['scan_error']}")
        return 1

    meta = result.get("scan_meta", {})
    print(
        f"[scanned {meta.get('files_scanned')}/{meta.get('files_total')} files "
        f"| cloned={meta.get('cloned')} | truncated={meta.get('truncated')}]"
    )
    if meta.get("output_md"):
        print(f"[wrote {meta['output_md']}]")
    elif meta.get("output_md_error"):
        print(f"[failed to write .md: {meta['output_md_error']}]")
    print()
    # Same rendered block that was written to the .md file.
    print(result["scan_context"].as_prompt_context())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
