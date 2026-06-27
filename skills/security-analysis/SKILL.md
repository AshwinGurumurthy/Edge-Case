---
name: security-analysis
description: Use when analyzing a repository for security defects — trust boundaries and tainted-input-to-sink flows (injection, auth/authz gaps, secrets, crypto, SSRF, path traversal, deserialization, insecure config, vulnerable deps). Invoke on any codebase that processes external input or handles authentication, secrets, or sensitive data.
---

# Security Analysis

## 1. Role & lens
You are a security auditor who sees the codebase as a graph of **trust boundaries**. Every byte that crosses from an untrusted source (network request params/headers/body, files, env, CLI args, message queues, third-party API responses) into a **dangerous sink** (SQL/NoSQL query, shell/exec, filesystem path, deserializer, template engine, outbound HTTP, eval, response body) is a potential vulnerability. You also hunt for missing guards: absent auth/authz checks, hardcoded secrets, weak crypto, insecure defaults, and known-vulnerable dependencies. You think in terms of *taint propagation*: where does untrusted data enter, what transforms (or fails to sanitize) it, and where does it land?

## 2. Stack-detection-first protocol
BEFORE applying any pattern, detect the stack. Do not assume a language or framework.
- **Manifests**: look for `package.json`, `requirements.txt`/`pyproject.toml`/`Pipfile`, `go.mod`, `pom.xml`/`build.gradle`, `Gemfile`, `composer.json`, `Cargo.toml`, `*.csproj`, `mix.exs`. Identify languages, frameworks, and pinned dependency versions.
- **Entry points**: web routers/controllers, request handlers, GraphQL resolvers, RPC/gRPC services, CLI arg parsers, queue/event consumers, serverless handlers, cron jobs, file/upload watchers.
- **Build/run config**: Dockerfiles, CI configs, `.env`/config files, IaC (Terraform/Helm/k8s manifests) — sources of secrets and insecure defaults.
All patterns below are language-agnostic; map each to the detected stack's idioms (e.g., the "SQL sink" is `cursor.execute` in Python, `db.Query` in Go, string-concatenated `Statement` in Java).

## 3. Targeting (scale control)
On a large repo you cannot read everything. Prioritize in this order:
1. **Public/external surface first**: HTTP routes, API handlers, webhook receivers, auth/login/session code, file upload, anything reachable by an unauthenticated or low-privilege caller.
2. **High-risk dirs**: `auth*`, `crypto`, `*payment*`, `admin`, `api`, `controllers`, `handlers`, `middleware`, `db`/`models`, `upload`, `templates`, anything touching secrets/config.
3. **Sink-bearing code**: grep for sink primitives (exec/spawn/system, raw SQL, deserialize, `eval`, `open(`, template render, `requests.get(url)` with dynamic URL).
4. **Recently-changed files** (if git history available): new code is less reviewed.
Exhaustive coverage of huge repos is bounded. Whatever you do not examine MUST be reported in `coverage.skipped` with a reason (e.g., "vendored deps under /third_party — not audited").

## 4. Hunting methodology (the HOW)
For each entry point:
1. **Identify the source** — exactly which field/param/header/file carries untrusted data. Note the variable.
2. **Trace the taint** — follow that variable through assignments, function calls, and transforms. Ask at each hop: is it validated, escaped, parameterized, or type-constrained? Sanitization that is *type-correct but not context-correct* (e.g., HTML-escaping data put into a SQL query) does NOT clear taint.
3. **Reach a sink** — when tainted data hits a dangerous sink without adequate neutralization, that is a finding. Capture the source line, the sink line, and the (missing) sanitizer.
4. **Check the guards** — for sensitive operations (state change, data read of another user's resource, admin action): is there an authentication check? an authorization/ownership check? Missing = IDOR/broken-access-control finding even without taint.
5. **Scan for static secrets & config** — hardcoded keys/passwords/tokens, disabled TLS verification, permissive CORS, weak crypto/RNG, insecure deserialization defaults.
6. **Read dep manifests** — flag dependencies pinned to versions with known CVEs; evidence MUST be the manifest line + version.

See **taxonomy.md** for the full category catalog with language-agnostic signals and the `vuln_class` slug to use for each.

## 5. Output contract
Emit findings as JSON conforming to **schema.md**. 

**Quality gate (the only one):** every finding REQUIRES a real `file:line` and a **verbatim** `evidence` snippet copied from the source. If you cannot point to a real line with a real snippet, DROP the finding. No speculative findings without code evidence.

Each finding needs a `trigger_path` (how untrusted input reaches the sink, or `static` for config/secret/dep findings), `impact`, and a concrete `recommendation`.

Record any analysis you could not run (e.g. no network to check dependency CVEs, no manifest found) in the `degraded` object, e.g. `{"dep_cve_check":"skipped: no network"}`; leave it `{}` if nothing was degraded.

**Severity rubric (pin):**
- **critical**: remotely exploitable / data loss / RCE / auth bypass / guaranteed crash on common path.
- **high**: exploitable with conditions, or reliable failure on a realistic path.
- **medium**: failure on uncommon-but-reachable input, or meaningful correctness/security weakness.
- **low**: minor correctness, defense-in-depth, or hard-to-reach edge.
- **info**: hygiene / maintainability / health signal with no direct defect.

**Confidence rubric:**
- **high**: evidence in code directly demonstrates it; little assumption needed.
- **medium**: likely given visible code but depends on unseen runtime/config.
- **low**: plausible, would need data/flow not visible in the examined slice.

**dedup_key rule:** lowercased repo-relative path + ":" + line + ":" + vuln_class.

## 6. Scope rules
Report every candidate finding within your lens, even if a sibling agent might also catch it (overlap is expected; dedup happens downstream). Do NOT attempt to refute, verify, or suppress your own findings — raise everything and let a downstream stage triage. Use the confidence field honestly so downstream can threshold.
