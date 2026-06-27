# context-agent — point it at a repo, get a test plan

**Give it a Git URL (or local path). It reads the codebase, figures out what the
project *is*, then generates a structured set of testing scenarios for it.**

```bash
python context-agent/pipeline.py https://github.com/zeroclaw-labs/zeroclaw.git scenarios.md
```

That single command runs a two-agent LangGraph pipeline end-to-end and writes
`scenarios.md`. It works with **zero API keys** (local Ollama fallback) and gets
much sharper with a Claude key. (Run commands from the repo root.)

---

## What it does

A repo arrives as a link. Two agents run in sequence:

| Stage | Agent | In → Out | Backend |
|---|---|---|---|
| 1. **Scan** | `scanner_agent` | repo link/path → clone + collect high-signal files → **structured `ScanContext`** (purpose, workflow, features w/ file evidence, tech stack, audience, confidence) | Claude (Sonnet) or local Ollama |
| 2. **Scenarios** | `scenario_agent` | `ScanContext` → (optional web research on how similar apps fail) → **markdown test plan** (functional, edge-case, security, performance scenarios + expected outcomes) | Claude (Haiku) + Tavily, or local Ollama |

```
repo link ──▶ [ scanner ] ──ScanContext──▶ [ scenario ] ──▶ scenarios.md
              clone+collect                 (+web search)
              structured synth
```

The `ScanContext` is a typed Pydantic contract (`scanner_agent/state.py`), so the
scan is machine-consumable by any downstream agent — the scenario agent is just
the first consumer.

## Quickstart

```bash
# from the repo root
python -m venv .venv && source .venv/bin/activate
pip install -r context-agent/requirements.txt

# Zero-key path (uses a local Ollama model — install from https://ollama.com, then):
ollama pull granite4:micro
python context-agent/pipeline.py https://github.com/zeroclaw-labs/zeroclaw.git scenarios.md

# Higher-quality path (recommended for demos):
cp ../.env.example ../.env      # then set ANTHROPIC_API_KEY (and optionally TAVILY_API_KEY)
python context-agent/pipeline.py https://github.com/zeroclaw-labs/zeroclaw.git scenarios.md
```

Scanner only (no scenarios), which also prints the structured context:

```bash
python context-agent/run_scanner.py <repo-link-or-path> scan_context.md
```

## Backends (no-key by default, cloud when available)

Both agents pick a backend automatically:

- **`ANTHROPIC_API_KEY` set** → Claude. Scanner uses `claude-sonnet-4-6`; scenario
  uses `claude-haiku-4-5`. If `TAVILY_API_KEY` is also set, the scenario agent
  researches real-world failure patterns via web search before writing the plan.
- **No key** → local Ollama (`granite4:micro` by default), no web search.

Force a backend with `SCANNER_BACKEND` / `SCENARIO_BACKEND` (`anthropic|ollama`).
See [`../.env.example`](../.env.example) for all knobs.

## Layout

```
context-agent/
  pipeline.py            # scanner → scenario, the MVP entry point
  run_scanner.py         # scanner only
  requirements.txt
  scanner_agent/         # repo link → structured ScanContext
    collector.py         #   static clone + high-signal file collection (no LLM)
    agent.py             #   LLM synthesis (Anthropic or Ollama)
    state.py             #   ScanContext schema + shared GraphState
    graph.py             #   scanner-only graph
  scenario_agent/
    agent.py             # ScanContext → test scenarios (Anthropic+Tavily or Ollama)
```

## Status & limitations

This is a hackathon MVP. It works end-to-end on real repos, but it analyzes a
**budgeted static snapshot**, not the whole tree, and the scenarios are grounded
in that snapshot + web research rather than verified against code. See
[`../REPORT.md`](../REPORT.md) for the honest audit of what it does and does not do.
