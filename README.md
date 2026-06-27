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
