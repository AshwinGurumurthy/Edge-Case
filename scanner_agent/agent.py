"""The scanner LangGraph node.

It collects a target codebase (static), then asks Claude Sonnet to synthesize a
single structured `ScanContext`. The node writes that context onto graph state so
downstream agents can build on it.
"""

from __future__ import annotations

import os
from functools import lru_cache

import anthropic
from dotenv import load_dotenv

from .collector import DEFAULT_MAX_CHARS, CollectedCode, collect
from .state import GraphState, ScanContext

# Load .env so ANTHROPIC_API_KEY (and optional overrides) are available.
load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
# Adaptive thinking tokens + the structured JSON share this budget.
MAX_TOKENS = int(os.getenv("SCANNER_MAX_TOKENS", "12000"))

SYSTEM_PROMPT = """You are a codebase scanner agent inside a multi-agent system. \
Your single job is to read a snapshot of a software project and produce a precise, \
structured understanding of it that LATER agents will act on. You are not writing \
for a human reader — your output is machine-consumed context, so be accurate and \
specific over polished.

Determine, strictly from the evidence provided:
- purpose: what the code is trying to do (the core problem it solves)
- end_to_end_workflow: the ordered flow from trigger/input through to output
- target_industry: the vertical(s) it appears built for
- target_audience: who uses it and what they care about
- features: concrete capabilities, each tied to file evidence
- tech_stack and entry_points

Rules:
- Ground every claim in the provided files. Cite file paths as evidence for features.
- Industry and audience are often implicit. Infer them from naming, domain language, \
dependencies, and docs — but if the signal is weak, leave the list empty rather than \
guessing, and record the gap under assumptions.
- Put anything you inferred under uncertainty into assumptions.
- Set confidence honestly based on how much signal the snapshot actually contained \
(a truncated or sparse snapshot should lower confidence)."""


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """Lazily construct a single Anthropic client (10-minute default timeout)."""
    return anthropic.Anthropic()


def synthesize(collected: CollectedCode) -> ScanContext:
    """Run the structured synthesis pass over collected code."""
    client = get_client()

    user_blob = collected.render()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Stable across scans -> cache it so repeated runs are cheaper.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze the following codebase snapshot and return the "
                    "structured context.\n\n" + user_blob
                ),
            }
        ],
        output_format=ScanContext,
    )

    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("model refused to analyze the codebase")

    context = response.parsed_output
    if context is None:
        raise RuntimeError("model did not return a parseable ScanContext")
    return context


def scanner_node(state: GraphState) -> GraphState:
    """LangGraph node entry point.

    Reads `target` (local path or git URL) from state, writes `scan_context`
    and `scan_meta` on success, or `scan_error` on failure.
    """
    target = state.get("target")
    if not target:
        return {"scan_error": "no 'target' provided in state"}

    max_chars = state.get("max_chars", DEFAULT_MAX_CHARS)

    try:
        collected = collect(target, max_chars=max_chars)
    except Exception as exc:  # noqa: BLE001 — surface any collection failure to the graph
        return {"scan_error": f"collection failed: {exc}"}

    try:
        context = synthesize(collected)
    except Exception as exc:  # noqa: BLE001 — surface any synthesis failure to the graph
        return {"scan_error": f"synthesis failed: {exc}"}

    meta = {
        "root": collected.root,
        "cloned": collected.cloned,
        "files_scanned": collected.files_scanned,
        "files_total": collected.files_total,
        "truncated": collected.truncated,
    }

    # Optionally emit the context as a .md file for humans / other tools.
    output_md = state.get("output_md")
    if output_md:
        try:
            with open(output_md, "w", encoding="utf-8") as fh:
                fh.write(context.as_prompt_context())
            meta["output_md"] = os.path.abspath(output_md)
        except OSError as exc:
            meta["output_md_error"] = str(exc)

    return {"scan_context": context, "scan_meta": meta}
