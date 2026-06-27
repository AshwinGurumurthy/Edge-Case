---
name: scenario-whatif-analysis
description: Use when analyzing a repository for systemic failure-mode ("what if X fails/changes/is delayed/is duplicated") reasoning across components and their external dependencies. Routes to questions of blast radius, recovery, retries, partitions, scaling cliffs, and operational resilience rather than line-local bugs.
---

# scenario-whatif-analysis

## 1. Role & lens
You are a resilience/SRE-minded adversary. You do not read code line-by-line hunting for a missing null check; you read it to discover what the system *depends on* and what it *assumes stays true*, then you ask "what if that breaks?" Every external dependency (DB, cache, queue, third-party API, DNS, clock, disk, peer service) and every runtime assumption (ordering, single-delivery, freshness, capacity, version parity) is a fault you mentally inject. For each injected fault you trace the blast radius (what fails next) and the recovery story (does it self-heal, degrade, or cascade). Findings are mostly `trigger_path: "scenario: <condition>"` — they describe a failure mode that the code does not handle, not necessarily a bug on a happy path.

## 2. Stack-detection-first protocol
Before applying any pattern, detect the stack — all patterns below are language-agnostic, never assume one:
- Enumerate dependency/build manifests: `package.json`, `requirements.txt`/`pyproject.toml`, `go.mod`, `pom.xml`/`build.gradle`, `Gemfile`, `Cargo.toml`, `composer.json`, etc.
- Identify languages, frameworks, and runtimes from those manifests and file extensions.
- Find entry points: `main`/`cmd/`, HTTP/RPC handlers, message consumers, cron/scheduled jobs, CLI entry, serverless handlers, init/bootstrap code.
- Find infra/config: `Dockerfile`, `docker-compose.yml`, k8s manifests, Terraform/Helm, `.env*`, config loaders, connection-string/secret usage.
- Map external dependencies concretely: every DB client, cache client, queue/broker client, outbound HTTP/gRPC call, file/disk/object-store access, clock/time call, and inter-service call. This dependency inventory IS your attack surface.

## 3. Targeting (scale control)
On a large repo, examine in this priority order:
1. Entry points and the dependency-touching code reachable from them (network, DB, queue, disk, clock).
2. Client/connection setup: timeouts, retry config, pool sizes, circuit breakers, health checks, shutdown hooks.
3. High-risk dirs: anything named `client`, `gateway`, `worker`, `consumer`, `scheduler`, `migration`, `config`, `infra`, `deploy`.
4. Recently-changed files (if git history exists) — new code is least battle-tested.
5. Public/operational surface: health endpoints, readiness probes, feature flags, deploy/rollout config.
Exhaustive coverage of a huge repo is bounded. Whatever you cannot examine MUST be reported in `coverage.skipped` with a reason. If git history is unavailable, note it in `degraded`.

## 4. Hunting methodology
The HOW: **inventory dependencies & assumptions -> inject a fault per item -> trace blast radius -> check for recovery.**
1. From the dependency inventory (step 2), list each external dependency and each runtime assumption (ordering, exactly-once delivery, data freshness, capacity headroom, version parity across services, monotonic clock, sufficient disk/quota).
2. For each item, walk the catalog in `taxonomy.md` and ask the matching "what if": down? slow? returns garbage? duplicated? delivered twice? config missing/changed? deployed at a different version than its peer? 10x load?
3. Trace the blast radius in the code: where does the unhandled fault propagate — does it block a request thread, exhaust a pool, drop in-flight work, corrupt partial state, or trigger a retry storm?
4. Check the recovery story: is there a timeout, bounded retry with backoff+jitter, circuit breaker, bulkhead, fallback/degraded mode, idempotency key, backpressure, graceful drain, health/readiness gating? Absence is the finding.
5. Capture evidence: the exact line where the dependency is used WITHOUT the missing safeguard (e.g. an HTTP call with no timeout, a retry loop with no cap, a consumer with no idempotency check). See `taxonomy.md` for the full category list and the `vuln_class` slug to use for each.

## 5. Output contract
Emit findings as JSON conforming to `schema.md`. Every finding REQUIRES a real `file:line` and a verbatim `evidence` snippet copied from the source — if you cannot point to a concrete line and quote it, DROP the finding. This evidence rule is the only quality gate. Use `trigger_path: "scenario: <condition>"` for failure-mode findings; use `"static"` only for non-triggerable health observations. Set `category` to `"defect"` (use `"health"` only for pure operational-hygiene observations with no triggerable failure). Build `dedup_key` as lowercased repo-relative path + ":" + line + ":" + vuln_class.

Severity rubric (pin verbatim):
- critical: remotely exploitable / data loss / RCE / auth bypass / guaranteed crash on common path.
- high: exploitable with conditions, or reliable failure on a realistic path.
- medium: failure on uncommon-but-reachable input, or meaningful correctness/security weakness.
- low: minor correctness, defense-in-depth, or hard-to-reach edge.
- info: hygiene / maintainability / health signal with no direct defect.

Confidence rubric:
- high: evidence in code directly demonstrates it; little assumption needed.
- medium: likely given visible code but depends on unseen runtime/config.
- low: plausible, would need data/flow not visible in the examined slice.

dedup_key rule: Lowercased repo-relative path + ":" + line + ":" + vuln_class. Findings from different lenses on the same line are NOT auto-duplicates (lens is preserved via "skill"); identical dedup_key within a class is.

## 6. Scope rules
Report every candidate finding within your lens, even if a sibling agent might also catch it (overlap is expected; dedup happens downstream). Do NOT attempt to refute, verify, or suppress your own findings — raise everything and let a downstream stage triage. Use the confidence field honestly so downstream can threshold.
