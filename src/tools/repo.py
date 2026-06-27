"""Lightweight repo signal extraction for the context_repo agent.

Deliberately dependency-free and cheap: walk the tree (skipping noise dirs),
detect the stack from manifest files, and surface a short file listing. This is
the cheap local pre-processing that feeds the (expensive) Anthropic agent so it
reasons over facts, not a raw filesystem dump.
"""
from __future__ import annotations

import os

_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", ".vscode"}
_STACK_MARKERS = {
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "package.json": "Node/JavaScript",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "compose.yaml": "Docker Compose",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java/Maven",
}


def summarize_repo(path: str = ".", max_files: int = 60) -> str:
    if not os.path.isdir(path):
        return f"(no repo found at {path!r})"

    stack: set[str] = set()
    files: list[str] = []
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP]
        for fn in filenames:
            if fn in _STACK_MARKERS:
                stack.add(_STACK_MARKERS[fn])
            rel = os.path.relpath(os.path.join(root, fn), path)
            files.append(rel)
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break

    stack_str = ", ".join(sorted(stack)) or "unknown"
    listing = "\n".join(f"  {f}" for f in sorted(files)[:max_files])
    return (
        f"Detected stack: {stack_str}\n"
        f"File count (sampled): {len(files)}\n"
        f"Files:\n{listing}"
    )
