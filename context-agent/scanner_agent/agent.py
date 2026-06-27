"""The scanner LangGraph node.

It collects a target codebase (static), then asks an LLM to synthesize a single
structured `ScanContext`. The node writes that context onto graph state so
downstream agents can build on it.

Backend selection (so the MVP runs with or without a cloud key):
  - If ANTHROPIC_API_KEY is set  -> Claude (best quality, big context).
  - Otherwise, if a local Ollama is reachable -> local model (free, offline).
  - Force one with SCANNER_BACKEND=anthropic|ollama.
"""

from __future__ import annotations

import os
from functools import lru_cache

import requests
from dotenv import load_dotenv

from .collector import DEFAULT_MAX_CHARS, CollectedCode, collect
from .state import GraphState, ScanContext

# Load .env so ANTHROPIC_API_KEY (and optional overrides) are available.
load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
# Adaptive thinking tokens + the structured JSON share this budget.
MAX_TOKENS = int(os.getenv("SCANNER_MAX_TOKENS", "12000"))

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite4:micro")
# Local models have smaller context windows than Claude, so the snapshot sent to
# Ollama is capped well below the collection budget.
OLLAMA_MAX_BLOB_CHARS = int(os.getenv("OLLAMA_MAX_BLOB_CHARS", "45000"))

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

USER_PREFIX = "Analyze the following codebase snapshot and return the structured context.\n\n"


def select_backend() -> str:
    """Decide which backend to use. Explicit override wins; else key presence."""
    forced = os.getenv("SCANNER_BACKEND", "").strip().lower()
    if forced in ("anthropic", "ollama"):
        return forced
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama"


@lru_cache(maxsize=1)
def get_anthropic_client():
    """Lazily construct a single Anthropic client (imported lazily so the
    package works without the SDK installed when running on Ollama)."""
    import anthropic

    return anthropic.Anthropic()


def _synthesize_anthropic(user_blob: str) -> ScanContext:
    client = get_anthropic_client()
    response = client.messages.parse(
        model=ANTHROPIC_MODEL,
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
        messages=[{"role": "user", "content": USER_PREFIX + user_blob}],
        output_format=ScanContext,
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("model refused to analyze the codebase")
    context = response.parsed_output
    if context is None:
        raise RuntimeError("model did not return a parseable ScanContext")
    return context


def _synthesize_ollama(user_blob: str) -> ScanContext:
    # Local context windows are small; trim the snapshot and tell the model.
    if len(user_blob) > OLLAMA_MAX_BLOB_CHARS:
        user_blob = (
            user_blob[:OLLAMA_MAX_BLOB_CHARS]
            + "\n... [snapshot trimmed to fit local model context]"
        )
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PREFIX + user_blob},
        ],
        "format": ScanContext.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=600)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama request to {OLLAMA_HOST} failed ({exc}). Is `ollama serve` "
            f"running and is model '{OLLAMA_MODEL}' pulled?"
        ) from exc
    content = resp.json().get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Ollama returned an empty response")
    return ScanContext.model_validate_json(content)


def synthesize(collected: CollectedCode) -> ScanContext:
    """Run the structured synthesis pass over collected code."""
    user_blob = collected.render()
    backend = select_backend()
    if backend == "anthropic":
        return _synthesize_anthropic(user_blob)
    return _synthesize_ollama(user_blob)


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

    backend = select_backend()
    try:
        context = synthesize(collected)
    except Exception as exc:  # noqa: BLE001 — surface any synthesis failure to the graph
        return {"scan_error": f"synthesis failed ({backend}): {exc}"}

    meta = {
        "root": collected.root,
        "cloned": collected.cloned,
        "files_scanned": collected.files_scanned,
        "files_total": collected.files_total,
        "truncated": collected.truncated,
        "backend": backend,
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
