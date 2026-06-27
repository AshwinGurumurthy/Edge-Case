# WARROOM — Multi-Agent Incident Analysis Architecture

> *Break it before your users do.*

A multi-agent orchestration architecture for **chaos-engineering / resilience
analysis**, inspired by [WARROOM](#about-warroom). Given a failure drill
(DB down, latency spike, request flood) plus the live metrics it produced, a
team of specialized AI agents collaborates to answer:

> **What broke, how bad is it, and what should I fix before real users hit this?**

This repository implements the **agent architecture only** — the orchestration
graph, the agents, the model split, and the integration seams (MCP control
plane, repo understanding). The actual failure *injection* (Podman/Toxiproxy)
is represented by a control-plane stub that you can wire to a live MCP server.

---

## Table of contents
- [The big idea](#the-big-idea)
- [Architecture at a glance](#architecture-at-a-glance)
- [Agent roster](#agent-roster)
- [The model split (why each agent runs where it does)](#the-model-split)
- [How the orchestration loop works](#how-the-orchestration-loop-works)
- [Why LangGraph](#why-langgraph)
- [Design choices & trade-offs](#design-choices--trade-offs)
- [Project layout](#project-layout)
- [Setup](#setup)
- [Running it](#running-it)
- [Extending the system](#extending-the-system)
- [About WARROOM](#about-warroom)

---

## The big idea

One generalist LLM asked *"analyze this outage"* gives a plausible, shallow
answer. This architecture instead runs a **war room of narrow specialists** that
deliberately disagree, then reconciles them:

- a **Reviewer** wing that *critiques* (what's risky / buggy / what-if), and
- a **Context** wing that *gathers facts* (the repo, the live infra via MCP,
  known failure patterns),

which **converge in a Debugger** that produces the technical verdict, looped
under a **Big Boss** that decides whether the answer is good enough to ship or
needs another pass.

The quality comes from **structure** (specialization + adversarial review +
fact-grounding + a refinement loop), not from one big model.

---

## Architecture at a glance

```
                              ┌────────────────────────────┐
                       ┌─────▶│          BIG BOSS          │──── RESOLVED ──▶ END
                       │      │  (commander + final judge) │
                       │      └─────────────┬──────────────┘
                       │       dispatch     │  fan-out (parallel)
                       │            ┌───────┴────────┐
              loop ──┐ │            ▼                ▼
            (ITERATE)│ │   ┌──────────────────┐  ┌──────────────────┐
                     │ │   │ REVIEWER subtree  │  │ CONTEXT subtree   │
                     │ │   │  (local Ollama)   │  │   (Anthropic)     │
                     │ │   │ ┌──────┐ ┌──────┐ │  │ ┌──────┐ ┌──────┐ │
                     │ │   │ │Genrl │ │ Bugs │ │  │ │ Repo │ │ MCP  │ │
                     │ │   │ └──┬───┘ └──┬───┘ │  │ └──┬───┘ └──┬───┘ │
                     │ │   │ ┌──┴───┐    │     │  │ ┌──┴───┐    │     │
                     │ │   │ │What-If│   │     │  │ │Issues│    │     │
                     │ │   │ └──┬───┘────┘     │  │ └──┬───┘────┘     │
                     │ │   │    ▼              │  │    ▼              │
                     │ │   │ Reviewer Lead     │  │ Context Lead      │
                     │ │   └────────┬──────────┘  └────────┬─────────┘
                     │ │            └──────────┬───────────┘
                     │ │                       ▼
                     │ │              ┌──────────────────┐
                     │ └──────────────│     DEBUGGER     │  (aggregates both wings)
                     └────────────────│  verdict + plan  │
                                      └──────────────────┘
```

(`python -m src.main --graph` prints the exact compiled topology as Mermaid.)

---

## Agent roster

| Agent | Role | Backend |
|---|---|---|
| **Big Boss** | Incident commander. Turns the raw incident into a focused directive, fans work out, and at the end decides **RESOLVED vs ITERATE**. | Ollama |
| **Reviewer · General** | High-level read: system behavior, blast radius, affected user flows. | Ollama (fast) |
| **Reviewer · Bugs** | Hunts concrete defects: missing timeouts/retries/circuit-breakers, pool exhaustion, unhandled exceptions, cascades. | Ollama (fast) |
| **Reviewer · What-If** | Adversarial stress: what if it lasts longer, compounds, or hits at peak? Second-order effects. | Ollama |
| **Reviewer · Lead** | Merges & ranks the three critiques into one prioritized risk list. | Ollama |
| **Context · Understand Repo** | Reads repo signals (stack, structure, key files) and explains which components are implicated. | Anthropic |
| **Context · MCP** | Talks to the **MCP control plane**: reads the live infra snapshot + available failure levers and interprets what infra is doing *right now*. | Anthropic |
| **Context · Common Issues** | Maps the incident to known failure patterns and typical root causes for the stack. | Anthropic |
| **Context · Lead** | Merges the three into one evidence-first factual brief. | Anthropic |
| **Debugger** | Convergence point. Reconciles critique + facts → **severity, what failed, likely cause, action plan**. | Ollama |

---

## The model split

This is the central architectural decision and lives in **one table**:
[`config/settings.py`](config/settings.py) → `AGENT_MODELS`.

| Wing | Backend | Why |
|---|---|---|
| **Reviewer subtree** | **Local Ollama** (`mistral` / `gemma4`) | Critique and opinion work is high-volume and benefits from a *diverse panel* of cheap models rather than one expensive call. Runs offline, costs nothing, keeps code private. |
| **Big Boss & Debugger** | **Local Ollama** (heavier model) | Orchestration + synthesis. Local keeps the control loop free and fast; swap to a cloud model in one line if you want stronger judgment. |
| **Context subtree** | **Anthropic API** | Grounding in real repo structure, live infra telemetry, and known failure patterns needs strong long-context reasoning and instruction-following. This is where cloud quality pays off. |

**Graceful degradation:** if Ollama isn't running or `ANTHROPIC_API_KEY` is
unset, the affected agents return clearly labelled `[STUB::...]` output instead
of crashing — so the *entire graph runs end-to-end* for demos and CI with zero
infra. You can literally `python -m src.main` on a fresh checkout and watch the
whole topology execute.

> The spec calls for `mistral`. The defaults ship as `gemma4:e4b` / `gemma4:e2b`
> (already pulled on this machine). Run `ollama pull mistral` and set
> `OLLAMA_MODEL=mistral` in `.env` to match the spec exactly — no code change.

---

## How the orchestration loop works

1. **Dispatch** — Big Boss reads the incident and emits a directive, then fans
   out to all six worker agents **in parallel**.
2. **Reviewer wing** — General / Bugs / What-If run concurrently; the Reviewer
   Lead waits for all three and produces a ranked critique.
3. **Context wing** — Understand Repo / MCP / Common Issues run concurrently;
   the Context Lead waits for all three and produces a factual brief.
4. **Debugger** — waits for **both** leads, reconciles disagreement, and emits
   the verdict: severity + what failed + likely cause + action plan.
5. **Loop-back** — control returns to Big Boss, which judges the verdict:
   - **RESOLVED** → writes the final response and the graph ends.
   - **ITERATE** → emits feedback and re-runs the wings, **bounded** by
     `WARROOM_MAX_ITERATIONS` (default 2) so it always terminates.

Parallelism is structural: a node fires only once *all* its inbound edges have
completed in the current super-step. That's why the three reviewers run
together, each lead blocks on its three children, and the Debugger blocks on
both leads.

Every node appends to an **append-only audit trail** (`state.log`) so you can
see exactly what ran in what order — useful for a demo and for debugging.

---

## Why LangGraph

The topology has three properties a linear "chain" can't express well:

1. **Fan-out / fan-in** — Big Boss → 6 parallel workers → 2 aggregators →
   1 debugger. LangGraph models this natively with edges; a node runs when its
   dependencies complete.
2. **A real loop** — Debugger → Big Boss → (maybe) back to the workers.
   LangGraph supports cyclic graphs with a `recursion_limit` backstop; we add
   our own `MAX_ITERATIONS` for semantic bounding.
3. **Shared, reducer-merged state** — concurrent nodes write into one typed
   `WarroomState`; the `log` field uses an `operator.add` reducer so parallel
   appends don't clobber each other.

CrewAI (role/task) or a hand-rolled async orchestrator could work, but LangGraph
gives the cleanest, most inspectable mapping of *exactly this* graph — including
a free Mermaid render of the compiled topology.

---

## Design choices & trade-offs

- **Specialists over a generalist.** More LLM calls, but each prompt is narrow
  and concrete — which small local models follow far better than a broad ask.
- **Two wings, then converge.** Separating *critique* (Reviewer) from *facts*
  (Context) prevents the model from rationalizing; the Debugger has to
  reconcile them, surfacing gaps.
- **Bounded refinement loop.** The Boss can demand another pass, but
  `MAX_ITERATIONS` guarantees termination and predictable cost.
- **Local-first, cloud-where-it-counts.** Most calls are free/local; only the
  fact-grounding wing spends Anthropic tokens.
- **Stub-by-default integrations.** MCP control plane and repo understanding are
  real seams with working stubs, so the architecture is demoable today and
  productionizable later without restructuring.

---

## Project layout

```
Edge-Case/
├── config/
│   └── settings.py          # THE MODEL SPLIT (agent -> backend/model) + knobs
├── src/
│   ├── main.py              # CLI entry point
│   ├── orchestrator/
│   │   ├── state.py         # typed shared state (WarroomState)
│   │   └── graph.py         # LangGraph nodes + edges + loop wiring
│   ├── agents/
│   │   ├── base.py          # Agent = name + system prompt + resolved client
│   │   ├── prompts.py       # all system prompts, in one place
│   │   ├── big_boss.py      # dispatch + final judge
│   │   ├── reviewer.py      # general / bugs / what-if + lead
│   │   ├── context.py       # repo / mcp / issues + lead
│   │   └── debugger.py      # convergence + verdict
│   ├── llm/
│   │   └── clients.py       # Ollama + Anthropic clients, graceful degradation
│   ├── mcp/
│   │   └── client.py        # MCP control-plane client (stub: tools + snapshot)
│   └── tools/
│       └── repo.py          # cheap local repo-signal extraction
├── examples/
│   └── db_down.txt          # sample incident
├── scripts/
│   ├── setup.ps1            # Windows venv + deps + .env + model pull
│   └── setup.sh             # macOS/Linux equivalent
├── requirements.txt
└── .env.example
```

---

## Setup

A virtualenv is recommended (the Context wing needs the `anthropic` SDK).

**Windows (PowerShell):**
```powershell
./scripts/setup.ps1
```

**macOS / Linux:**
```bash
bash scripts/setup.sh
```

**Manual:**
```bash
python -m venv .venv
# Windows:  . .\.venv\Scripts\Activate.ps1
# Unix:     source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add ANTHROPIC_API_KEY
```

**Local models (Reviewer wing):**
```bash
ollama pull mistral         # then set OLLAMA_MODEL=mistral in .env
# (or keep the gemma4 defaults already configured)
```

---

## Running it

```bash
# bundled sample incident (DB Down drill)
python -m src.main

# your own incident
python -m src.main --incident "Latency spike: +800ms on the DB call path, p95 12s, timeouts cascading."

# from a file, against a specific repo
python -m src.main --incident-file examples/db_down.txt --repo /path/to/your/app

# print the compiled graph topology (Mermaid)
python -m src.main --graph
```

Output is the **technical verdict** (severity, what failed, likely cause, action
plan) + the **Big Boss summary** + a **per-node audit trail**.

> No keys/models configured? It still runs — agents emit labelled `[STUB::...]`
> responses so you can watch the full orchestration flow before wiring backends.

---

## Extending the system

- **Re-point any agent** to a different model/backend: edit one line in
  `config/settings.py` → `AGENT_MODELS`.
- **Add a new specialist:** add a system prompt in `agents/prompts.py`, a node
  function, register it in `graph.py`, and add it to a subtree's fan-out.
- **Go live on the MCP control plane:** replace the stub bodies in
  `src/mcp/client.py` (`list_tools` / `snapshot`) with real calls to your MCP
  server (e.g. `http://127.0.0.1:9100`).
- **Richer repo understanding:** extend `src/tools/repo.py` (read key files,
  parse manifests) — it pre-processes cheaply before the Anthropic agent.

---

## About WARROOM

This architecture is modeled on **WARROOM**, a chaos-engineering and resilience
testing tool that lets developers simulate real system failures (DB outage,
latency injection, traffic surge), observe the blast radius in real time, and
get a plain-English verdict + action plan — *before* failures reach production.
WARROOM's stack: FastAPI backend, an MCP control plane (Podman + Toxiproxy), and
a Flask + Postgres demo app.

This repo reproduces the **interpretation + action-planning brain** as a
multi-agent system: the part that turns raw failure signals into
*"what broke, how bad, what to fix."*
# Edge-Case — multi-agent repository analysis skills

A suite of five **self-contained Claude Code skills** for comprehensive, language-agnostic
analysis of any repository. Each skill is a drop-in lens for a sub-agent; run them in
parallel for maximum recall, then dedup/triage downstream.

## The five lenses

| Skill | Lens | Finding prefix |
|---|---|---|
| [`skills/runtime-bug-api-analysis`](skills/runtime-bug-api-analysis) | Logic/runtime defects & API contract issues | `RT` |
| [`skills/security-analysis`](skills/security-analysis) | Trust boundaries, tainted-input → sink | `SEC` |
| [`skills/edge-case-analysis`](skills/edge-case-analysis) | Boundary/degenerate inputs **+** project-health/maintainability | `EC` |
| [`skills/memory-timing-analysis`](skills/memory-timing-analysis) | Memory leaks & concurrency/timing defects | `MT` |
| [`skills/scenario-whatif-analysis`](skills/scenario-whatif-analysis) | Systemic "what if X fails" failure-mode reasoning | `WI` |

Each skill folder is **self-contained** — `SKILL.md` (lean instructions), `taxonomy.md`
(full checklist, loaded on demand), `schema.md` (the shared findings schema). No folder
references anything outside itself, so any folder can be copied into any project and used
standalone.

## Install (skill-install model)

Copy whichever skills you want into a project's skill directory:

```sh
cp -r skills/security-analysis        /path/to/target/.claude/skills/
cp -r skills/runtime-bug-api-analysis /path/to/target/.claude/skills/
# ...or all of them:
cp -r skills/* /path/to/target/.claude/skills/
```

Claude Code discovers them under `.claude/skills/` automatically. A sub-agent then invokes
the relevant skill (e.g. `security-analysis`) for its lens.

## Design contract

These skills **find and raise** — they are tuned for recall, not precision:

- **Language-agnostic.** Every skill detects the stack first, then applies language-agnostic
  patterns; nothing is hardcoded to one framework.
- **Overlap is expected.** Lenses intentionally overlap (a null-deref may surface from
  runtime, edge-case, and memory/timing). Dedup happens **downstream** on the `dedup_key`
  (`lowercased-path:line:vuln_class`), not inside the skills.
- **No self-verification.** Skills raise every candidate finding and report `confidence`
  honestly; a downstream stage thresholds and triages. The one in-skill quality gate is
  evidence: every finding requires a real `file:line` + a verbatim snippet, or it is dropped.
- **Graceful degradation.** Analysis that can't run (e.g. `edge-case` health mining with no
  git history, or dependency-CVE checks with no network) is skipped and recorded in the
  `degraded` field — never fabricated.

## Shared findings schema

All five skills emit the **same** JSON shape (see any `skills/*/schema.md`), differing only in
`skill`, `lens`, and the finding `id` prefix. Key fields: `severity`
(critical/high/medium/low/info), `confidence` (high/medium/low), `category`
(`defect`, plus `health` for edge-case), `dedup_key`, `evidence`, `trigger_path`.

## Suggested downstream orchestration

To run an analysis: give each skill to a sub-agent over the target repo, enforce `schema.md`
via structured output, merge all findings, dedup on `dedup_key`, then threshold on
`confidence`/`severity` for the final report.
