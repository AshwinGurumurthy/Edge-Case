"""Static collection of a target codebase.

Accepts either a local directory path or a git repository URL. For a URL it does a
shallow clone into a temp dir. It then walks the tree, builds a directory listing,
and gathers the highest-signal files (manifests, docs, configs) plus a sample of
source files, within a character budget. Nothing here calls an LLM — this just
assembles the evidence the synthesis step reasons over.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

DEFAULT_MAX_CHARS = 200_000
MAX_CHARS_PER_FILE = 20_000
MAX_TREE_ENTRIES = 600

# Directories that are never informative about intent.
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".next",
    "out", "target", "vendor", ".idea", ".vscode", ".gradle", "coverage",
    ".terraform", "bin", "obj", ".cache", ".turbo", "site-packages",
}

# Filenames (lowercased) that strongly signal purpose / stack / audience.
PRIORITY_NAMES = {
    "readme", "readme.md", "readme.rst", "readme.txt",
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "pipfile", "go.mod", "cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "gemfile", "dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "makefile", "openapi.yaml", "openapi.json",
    "swagger.yaml", "swagger.json", "schema.prisma", "schema.graphql",
    "manifest.json", "app.json", "main.py", "main.go", "index.js", "index.ts",
    "cli.py", "__main__.py", "settings.py", "config.py",
}

# Extensions worth sampling for feature/workflow inference.
SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".swift", ".scala", ".sql", ".graphql",
    ".proto", ".sh", ".md", ".toml", ".yaml", ".yml",
}


@dataclass
class CollectedCode:
    root: str
    tree: str
    files: list[tuple[str, str]] = field(default_factory=list)  # (relpath, content)
    files_scanned: int = 0
    files_total: int = 0
    truncated: bool = False
    cloned: bool = False

    def render(self) -> str:
        """Flatten into a single prompt-ready blob."""
        parts = [
            f"PROJECT ROOT: {os.path.basename(self.root.rstrip('/')) or self.root}",
            "",
            "DIRECTORY TREE (truncated to high-signal entries):",
            self.tree,
            "",
            "FILE CONTENTS:",
        ]
        for relpath, content in self.files:
            parts.append(f"\n===== {relpath} =====\n{content}")
        if self.truncated:
            parts.append(
                f"\n[NOTE] Collection budget reached. Included {self.files_scanned} of "
                f"{self.files_total} candidate files; remaining files were not sent."
            )
        return "\n".join(parts)


def _is_url(target: str) -> bool:
    t = target.strip()
    return (
        t.startswith(("http://", "https://", "git@", "ssh://"))
        or t.endswith(".git")
    )


def _looks_binary(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(2048)
        return b"\x00" in chunk
    except OSError:
        return True


def _read_text(path: str, limit: int) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        data = data[:limit] + "\n... [truncated]"
    return data


def _clone(url: str) -> str:
    dest = tempfile.mkdtemp(prefix="scanner_clone_")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, dest],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        detail = getattr(exc, "stderr", "") or str(exc)
        raise RuntimeError(f"git clone failed for {url}: {detail.strip()}") from exc
    return dest


def _build_tree(root: str) -> str:
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * depth
        if rel != ".":
            lines.append(f"{indent}{os.path.basename(dirpath)}/")
        for fn in sorted(filenames):
            lines.append(f"{indent}  {fn}")
        if len(lines) >= MAX_TREE_ENTRIES:
            lines.append("  ... [tree truncated]")
            break
    return "\n".join(lines)


def _gather_files(root: str) -> tuple[list[str], list[str]]:
    """Return (priority_paths, source_paths) as absolute paths."""
    priority: list[str] = []
    source: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            abspath = os.path.join(dirpath, fn)
            lower = fn.lower()
            ext = os.path.splitext(lower)[1]
            if lower in PRIORITY_NAMES or lower.startswith("readme"):
                priority.append(abspath)
            elif ext in SOURCE_EXTS:
                source.append(abspath)
    # Stable ordering: priority files first, then shallowest source files
    # (top-level files usually carry the most intent).
    source.sort(key=lambda p: (p.count(os.sep), p))
    return priority, source


def collect(target: str, max_chars: int = DEFAULT_MAX_CHARS) -> CollectedCode:
    """Collect a target codebase into a `CollectedCode` bundle.

    `target` may be a local directory path or a git URL.
    """
    cloned = False
    if _is_url(target):
        root = _clone(target)
        cloned = True
    else:
        root = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(root):
            raise RuntimeError(f"target is not a directory: {root}")

    try:
        tree = _build_tree(root)
        priority, source = _gather_files(root)
        candidates = priority + source
        files_total = len(candidates)

        selected: list[tuple[str, str]] = []
        budget = max_chars
        truncated = False
        for abspath in candidates:
            if budget <= 0:
                truncated = files_total > len(selected)
                break
            if _looks_binary(abspath):
                continue
            content = _read_text(abspath, min(MAX_CHARS_PER_FILE, budget))
            if content is None:
                continue
            relpath = os.path.relpath(abspath, root)
            selected.append((relpath, content))
            budget -= len(content)

        return CollectedCode(
            root=root,
            tree=tree,
            files=selected,
            files_scanned=len(selected),
            files_total=files_total,
            truncated=truncated,
            cloned=cloned,
        )
    finally:
        # Clean up a cloned repo once its bytes are in memory. We keep local
        # targets untouched.
        if cloned:
            shutil.rmtree(root, ignore_errors=True)
