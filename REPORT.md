# Edge-Case — Hackathon Report

## The problem

Before you can test, secure, or review an unfamiliar codebase, someone has to
*understand* it and decide **what could go wrong**. That work is manual, slow, and
inconsistent — and it's the bottleneck in front of every QA, security, and
onboarding effort. "Here's a repo link, what should we test?" has no fast answer.

## What we built

A two-agent pipeline that turns a **repo link into a structured test plan**, with
no human in the loop:

1. **Scanner agent** — clones the target (or reads a local path), statically
   collects the highest-signal files (manifests, docs, entry points, a source
   sample) within a character budget, and asks an LLM to synthesize a *typed*
   `ScanContext`: purpose, end-to-end workflow, features (each tied to file
   evidence), tech stack, target audience, and a self-reported confidence.
2. **Scenario agent** — consumes that context and (optionally) researches how
   similar applications fail in the wild via web search, then writes a structured
   markdown test plan: functional, edge-case, security, and performance scenarios
   with expected outcomes.

The two are wired as a LangGraph pipeline (`scanner → scenario → END`). The
`ScanContext` is a Pydantic contract, so the scan is reusable by any future agent.

**Key design choice — degrade, don't fail.** Every stage runs on Anthropic
(Claude Sonnet / Haiku, + Tavily web search) when keys are present, and falls back
to a local Ollama model with no web search when they aren't. The whole pipeline
runs offline and free; keys upgrade quality without code changes.

## What actually works (verified)

- ✅ End-to-end on **zeroclaw** via its Git URL: clones, walks **1,406 files**,
  collects 60 high-signal ones, produces a valid structured `ScanContext`, and
  writes a coherent `scenarios.md` — **with zero API keys** (local Ollama).
- ✅ Structured output is schema-validated (Pydantic) on both the Anthropic and
  Ollama paths.
- ✅ Graceful degradation paths exercised: no Anthropic key → Ollama; no Tavily
  key → scenario generation without web search.

## Honest audit — where it's thin (poking holes)

1. **Coverage is shallow.** On zeroclaw we synthesized from **60 of 1,406 files
   (~4%)**. The budget + "manifests and shallow files first" heuristic means deep
   core logic is often never sampled. The model still self-reports
   `confidence: high` — that confidence is **not calibrated to coverage** and is
   misleading. This is the biggest correctness risk.
2. **Local-model quality is a plumbing demo, not a quality demo.** `granite4:micro`
   frequently leaves structured fields empty and fixates on the first vivid file
   (it called zeroclaw "a Dockerfile explanation"). Credible output needs Claude.
3. **Scenarios aren't grounded in code.** They're generated from the *summary*
   plus web research about "similar apps," not from actual file/line evidence — so
   they can be generic or hallucinated, and nothing maps a scenario back to the
   code path it exercises.
4. **Nothing is verified or executed.** The plan claims "other agents will execute
   these tests," but that stage doesn't exist. No finding is adversarially checked.
5. **Secret-leak surface.** The collector reads config files (`settings.py`,
   `config.py`, `.env`-adjacent) and ships them to the LLM; scanning a private repo
   could send secrets to a cloud API. There's no redaction.
6. **Untrusted-clone risk.** Arbitrary URLs are `git clone`d (depth 1). We only
   *read* files (no build/exec), which limits but doesn't eliminate risk.
7. **Unbounded cost/latency on the cloud path.** The Tavily tool loop
   (`recursion_limit=25`) has no token or dollar budget.
8. **"Multi-agent" is currently two nodes.** The broader vision (the five
   language-agnostic analysis skills; a WARROOM-style reviewer/context/debugger
   panel) lives in sibling branches and is **not integrated** into this pipeline yet.

## Next steps

- Feed coverage stats into the prompt and **cap confidence by % of files seen**.
- Ground scenarios in real `file:line` evidence (reuse the repo's existing
  structured-findings schema and `dedup_key`).
- Add a verification/execution stage downstream of the scenario agent.
- Redact obvious secrets before sending snapshots to a cloud model.
- Integrate the five analysis skills as parallel reviewer agents over the same
  `ScanContext`, then dedup and triage — the originally-planned full pipeline.
