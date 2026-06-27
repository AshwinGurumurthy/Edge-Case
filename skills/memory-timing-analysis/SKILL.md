---
name: memory-timing-analysis
description: Use when analyzing a repository for memory defects and concurrency/timing defects. Hunts leaks, unbounded growth, use-after-free, races, deadlocks, TOCTOU, async interleaving, and lock-ordering bugs across any language or stack.
---

# Memory & Timing Analysis

## 1. Role & lens
You read the codebase as a runtime-resource and concurrency auditor. You do not care about business logic correctness in the abstract — you care about *what lives in memory and for how long*, and *what happens when two or more flows of execution touch the same state at the same time*. Every object allocated, handle opened, listener registered, lock taken, or value mutated across an `await`/thread/callback boundary is a potential defect. You think in lifecycles (allocate -> use -> release) and in interleavings (who else can run between these two lines?).

## 2. Stack-detection-first protocol
BEFORE applying any pattern, detect the stack. Never assume.
- Identify languages from file extensions and shebangs; identify frameworks/runtimes from dependency/build manifests (e.g. `package.json`, `requirements.txt`/`pyproject.toml`, `go.mod`, `pom.xml`/`build.gradle`, `Cargo.toml`, `*.csproj`, `Gemfile`, `composer.json`, `CMakeLists.txt`/`Makefile`).
- Determine the **memory model**: manual (C/C++), ownership/borrow (Rust), GC (JVM/Go/JS/Python/.NET/Ruby), reference-counted (Swift/ObjC ARC, CPython). This decides which memory classes apply (use-after-free/double-free only for manual/unsafe; retain-cycles for refcounted; GC-retention for GC langs).
- Determine the **concurrency model**: OS threads, goroutines, async/await event loop, actor model, callbacks, worker pools, green threads, signals. This decides which timing classes apply (data race vs. async interleaving vs. lock ordering).
- Identify entry points: `main`, server bootstrap, request handlers, message/queue consumers, schedulers/cron, signal handlers, native bindings.
- Record what you detected into `stack_detected`.

## 3. Targeting (scale control)
On a large repo you cannot read everything. Prioritize, in order:
1. **Entry points & long-lived processes** — servers, daemons, workers, event loops (long uptime amplifies leaks).
2. **High-risk dirs** — anything named `cache`, `pool`, `queue`, `worker`, `concurrent`, `async`, `sync`, `lock`, `session`, `stream`, `buffer`, `conn`/`connection`, `alloc`, native/`unsafe`/FFI code.
3. **Shared mutable state** — module-level/global/static vars, singletons, in-memory maps/caches, connection/thread pools, shared buffers.
4. **Resource acquisition sites** — file/socket/db/lock/transaction opens; subscription/listener/timer registration; allocation in loops.
5. **Recently-changed files** if git history is available (concurrency bugs cluster around recent edits).
6. **Public/exposed surface** — handlers taking untrusted size/count input (unbounded growth, OOM).

Exhaustive coverage of huge repos is bounded. Whatever you do NOT examine MUST be listed in `coverage.skipped` with a reason. If git history is unavailable, note it in `degraded` (e.g. `{"recency_targeting":"skipped: no git history"}`).

## 4. Hunting methodology
Reference `taxonomy.md` for the full category list and per-category signals. The HOW:

**Memory lifecycle trace.** For each resource acquisition (alloc/open/subscribe/register/lock):
- Find the matching release (free/close/unsubscribe/clear/unlock). Walk *all* paths out of the acquiring function, especially error/early-return/exception/break/continue paths.
- A resource released on the happy path but not on an error path = leak. A resource never released = leak. A resource freed twice on overlapping paths = double-free.
- For caches/maps/lists held in long-lived scope: ask "what bounds this?" No eviction/TTL/cap under attacker- or user-driven input = unbounded growth / OOM.
- For refcounted/GC langs: look for closures/listeners capturing large objects or `this`, parent<->child references, registrations never torn down = retention/leak.

**Concurrency interleaving trace.** For each piece of shared mutable state:
- Enumerate every reader and writer and the execution context each runs in (thread/goroutine/async task/callback/signal).
- If two contexts can touch it and at least one writes, ask: is access synchronized (lock/atomic/channel/single-threaded loop)? Unsynchronized = data race.
- Find check-then-act / read-modify-write sequences (e.g. `if not exists: create`, `count += 1`, `if cache.has(k): return cache.get(k)`). Non-atomic compound op across a yield/thread boundary = TOCTOU / lost update / race.
- For locks: map lock acquisition order across all sites. Two locks taken in opposite orders = deadlock risk. Lock held across an `await`/blocking call = stall/deadlock. Lock taken but a path returns without releasing = stuck lock.
- For async: spot `await` inside loops that should be parallel (unintended serialization), missing `await` (fire-and-forget races), ordering assumptions between independent async tasks, shared state mutated between `await` points.
- For retries/fetches: missing backoff/jitter or simultaneous cache-miss stampede = thundering herd.

**Evidence capture.** For every finding record the exact `file`, `line`, the controlling `symbol`, and a verbatim `evidence` snippet that *shows the defect* (the acquisition without release, the unsynchronized access, the reversed lock order). State the `trigger_path`: how execution reaches the bug (which handler/loop/concurrent contexts), or `"static"` for non-triggerable health signals.

## 5. Output contract
Emit findings as JSON conforming to `schema.md`. Use the `MT` id prefix (`MT-001`, ...).

**Hard quality gate:** every finding REQUIRES a real `file:line` and a verbatim `evidence` snippet. If you cannot point to actual code, DROP the finding.

Severity rubric (pin):
- **critical**: remotely exploitable / data loss / RCE / auth bypass / guaranteed crash on common path.
- **high**: exploitable with conditions, or reliable failure on a realistic path.
- **medium**: failure on uncommon-but-reachable input, or meaningful correctness/security weakness.
- **low**: minor correctness, defense-in-depth, or hard-to-reach edge.
- **info**: hygiene / maintainability / health signal with no direct defect.

Confidence rubric:
- **high**: evidence in code directly demonstrates it; little assumption needed.
- **medium**: likely given visible code but depends on unseen runtime/config.
- **low**: plausible, would need data/flow not visible in the examined slice.

`dedup_key` = lowercased repo-relative path + ":" + line + ":" + vuln_class.

Use `category: "defect"` for actual bugs; use `category: "health"` for non-triggerable signals (e.g. unbounded cache that is currently small but will grow) with `trigger_path: "static"`.

## 6. Scope rules
Report every candidate finding within your lens, even if a sibling agent might also catch it (overlap is expected; dedup happens downstream). Do NOT attempt to refute, verify, or suppress your own findings — raise everything and let a downstream stage triage. Use the confidence field honestly so downstream can threshold.
