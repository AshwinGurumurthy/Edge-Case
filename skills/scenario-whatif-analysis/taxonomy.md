# What-If Failure-Mode Taxonomy (whatif lens)

Language-agnostic catalog. For each category: **what it is**, **signals / how to spot it** (in any language), and the **vuln_class** slug to put in the finding. Evidence must be the exact line where a dependency/assumption is used WITHOUT the corresponding safeguard.

The universal procedure for every category: find where the dependency or assumption lives in code -> confirm the safeguard is absent or misconfigured -> trace where the unhandled fault propagates -> write the finding with `trigger_path: "scenario: <condition>"`.

---

## A. External dependency unavailable / slow

### A1. Dependency down (DB / cache / queue / 3rd-party API / peer service)
- **What:** A required downstream is unreachable, refusing connections, or returning 5xx.
- **Signals:** outbound call (HTTP/gRPC/DB query/cache get/publish) with no error handling, no fallback, no degraded path; a failed call propagates an exception straight to the user request or crashes a worker; readiness depends on the dependency at startup with no retry.
- **vuln_class:** `dependency-unavailable`

### A2. Dependency slow / no timeout
- **What:** Downstream responds but slowly (or hangs); caller waits indefinitely.
- **Signals:** HTTP/gRPC/DB/cache call with no timeout set (default-infinite clients), no per-call deadline, no context/cancellation propagation; thread/coroutine blocks on I/O with unbounded wait. Slow dependency -> thread/pool exhaustion -> whole service stalls.
- **vuln_class:** `missing-timeout`

### A3. Cache dependency assumed always present
- **What:** Code treats cache as the source of truth or cannot serve when cache is cold/down.
- **Signals:** read path hits cache only, no DB fallback; cache miss path is unimplemented or errors; cache outage = full outage (no graceful degrade).
- **vuln_class:** `cache-dependency`

---

## B. Time, clock & scheduling assumptions

### B1. Clock skew / NTP drift / wall-vs-monotonic
- **What:** Logic assumes synchronized or never-backward wall clocks across hosts.
- **Signals:** timeouts/durations/elapsed time computed from wall-clock (`now()` differences) instead of a monotonic source; token/lease/cert expiry compared across machines; ordering by timestamp; "future" timestamp rejected. Skew -> premature/late expiry, negative durations, mis-ordering.
- **vuln_class:** `clock-skew`

### B2. Time-of-check to time-of-use / scheduling races
- **What:** A condition checked at one time is acted on later assuming it still holds.
- **Signals:** check-then-act on shared/remote state; scheduled job assumes prior run finished; overlapping cron invocations with no lock.
- **vuln_class:** `tocttou-timing`

---

## C. Load, scaling & capacity

### C1. 10x–100x load / scaling cliff
- **What:** Works at current volume, collapses at higher volume.
- **Signals:** unbounded in-memory collection/accumulation per request or per event; O(n^2) over external-sized input; loading an entire table/list into memory; fan-out that multiplies downstream calls; per-request allocation that doesn't scale; no pagination on large reads.
- **vuln_class:** `scaling-cliff`

### C2. Missing backpressure
- **What:** Producer outpaces consumer with no flow control; queues/buffers grow unbounded.
- **Signals:** unbounded queue/channel/buffer; consumer with no rate limit while producer is fast; accepting work faster than it can be drained; no bounded worker pool. Leads to OOM or latency blowup.
- **vuln_class:** `missing-backpressure`

### C3. Connection / resource pool exhaustion
- **What:** Finite pool (DB conns, sockets, file handles, threads) drained under load or slow downstream.
- **Signals:** pool size unset/tiny or unbounded; connections/handles not released on error paths; one slow dependency holds all pool slots. Often the amplifier of A2.
- **vuln_class:** `pool-exhaustion`

---

## D. Configuration & secrets

### D1. Malformed / missing / changed configuration
- **What:** Required config absent, wrong type, or silently defaulted.
- **Signals:** env var / config key read with no presence check, no validation, or a silent default that masks misconfiguration; config parsed without schema validation; secret/URL/feature value used directly. Missing config -> wrong behavior or runtime crash deep in a request.
- **vuln_class:** `config-malformed`

### D2. Config change at runtime / hot reload hazards
- **What:** Config reloaded live with partial/inconsistent application.
- **Signals:** watchers that swap config non-atomically; some components read old value, others new; no validation before swap.
- **vuln_class:** `config-reload`

---

## E. Deploy, versioning & schema evolution

### E1. Partial deploy / version skew between services
- **What:** Services or replicas run different versions simultaneously (rolling deploy).
- **Signals:** API/message/schema changed without back/forward compatibility; new field assumed present; enum value added that old code can't parse; RPC contract change without versioning. Old<->new interaction breaks during the rollout window.
- **vuln_class:** `version-skew`

### E2. Data migration half-applied / corruption & recovery
- **What:** A schema/data migration fails midway or runs concurrently with old code.
- **Signals:** migration with no transaction/idempotency; code that assumes migration already ran (reads new column unconditionally); no rollback path; destructive migration without backup; dual-write without reconciliation. Half-applied state corrupts reads.
- **vuln_class:** `migration-corruption`

### E3. Feature-flag / kill-switch gaps
- **What:** No way to disable a risky path without a redeploy; or flag default is unsafe.
- **Signals:** new risky integration with no flag/kill-switch; flag evaluated once at startup (can't toggle live); default-on for unproven path; flag check missing on a fallback branch.
- **vuln_class:** `feature-flag-gap`

---

## F. Distributed-system correctness

### F1. Network partition / split brain
- **What:** Nodes can't communicate but both keep operating, diverging.
- **Signals:** leader election/locking without fencing tokens; multiple writers with no quorum; assuming a peer is dead because it's unreachable; no reconciliation after rejoin.
- **vuln_class:** `split-brain`

### F2. Idempotency under retry / redelivery
- **What:** An operation re-executed (client retry, at-least-once queue redelivery) causes duplicate effects.
- **Signals:** message consumer or POST/charge/email/write handler with no idempotency key, dedup table, or conditional write; "process then ack" without dedup; side effects before commit. At-least-once delivery is the default for most brokers — duplicates WILL happen.
- **vuln_class:** `idempotency-gap`

### F3. Cascading failure / retry storm
- **What:** A localized failure amplifies system-wide via aggressive retries or shared resource contention.
- **Signals:** retry loop with no max attempts, no exponential backoff, no jitter; synchronized retries; retries layered at multiple tiers (client + gateway + service) multiplying load; thundering herd on cache expiry. One slow node -> retry amplification -> total collapse.
- **vuln_class:** `retry-storm`

### F4. Missing circuit breaker / bulkhead
- **What:** No isolation between a failing dependency and the rest of the system.
- **Signals:** every call to a flaky dependency goes through unconditionally (no breaker to fail-fast); one downstream's calls share the same thread pool as everything else (no bulkhead partitioning).
- **vuln_class:** `missing-circuit-breaker`

---

## G. Availability & operational resilience

### G1. Single point of failure
- **What:** One non-redundant component whose loss takes the system down.
- **Signals:** single instance of a stateful service; hardcoded single host/leader; no replica/failover; in-memory-only state lost on restart; one shared lock/coordinator.
- **vuln_class:** `single-point-of-failure`

### G2. Graceful shutdown / in-flight request loss
- **What:** Process exits without draining in-flight work.
- **Signals:** no SIGTERM/shutdown handler; no connection drain; consumer that doesn't finish/ack current message before exit; no readiness flip before shutdown; abrupt `exit`. Deploys/scale-downs then drop or duplicate work.
- **vuln_class:** `ungraceful-shutdown`

### G3. Cold start / warmup
- **What:** First requests after start/scale-up fail or are very slow.
- **Signals:** lazy init of heavy resources on first request; serving traffic before caches/connections warm; readiness probe passes before dependencies ready; JIT/connection-pool warmup ignored.
- **vuln_class:** `cold-start`

---

## H. Storage & quota

### H1. Disk / quota / memory exhaustion
- **What:** A finite local resource fills up.
- **Signals:** unbounded logging/temp-file/upload writes; no rotation/cleanup; no disk-space check before write; unbounded in-memory cache with no eviction; writing user-controlled-size payloads to disk. Full disk -> writes fail, often crashing the process.
- **vuln_class:** `resource-exhaustion`

### H2. Data corruption on partial write / no atomicity
- **What:** A write interrupted midway leaves inconsistent state.
- **Signals:** multi-step write/update with no transaction; file written in place (no write-temp-then-rename); dual-store writes without compensation; non-atomic counter/balance updates. Crash mid-write -> corruption with no recovery.
- **vuln_class:** `partial-write-corruption`

---

## I. Input-shape assumptions from dependencies

### I1. Dependency returns changed / malformed / garbage data
- **What:** A downstream returns data in an unexpected shape (schema drift, partial, error body parsed as success).
- **Signals:** parsing a dependency response without validating shape/status; assuming a field is non-null/present; trusting third-party data ranges; no handling for empty/truncated result. Distinct from down/slow — here it "succeeds" with bad data.
- **vuln_class:** `unvalidated-dependency-data`

---

## How to choose severity (whatif lens)
- critical: the scenario is common/inevitable (e.g. at-least-once redelivery, rolling deploy, any dependency occasionally slow) AND causes data loss, duplicate financial/side effects, or full guaranteed outage.
- high: realistic operational scenario (dependency outage, load spike) causes reliable failure or cascading degradation with no recovery path.
- medium: reachable but less frequent scenario causes a recoverable-but-real failure, or a safeguard is present but weak.
- low: hard-to-reach scenario or defense-in-depth gap with limited blast radius.
- info: operational-hygiene observation (e.g. no health endpoint) with no triggerable failure -> use category "health".

## How to choose confidence
- high: the missing safeguard is visible directly at the cited line (e.g. you can see the call and the absence of a timeout/retry-cap/idempotency check in the same scope).
- medium: the gap is likely but depends on config/runtime not in view (e.g. timeout might be set globally on the client elsewhere).
- low: the failure mode is plausible but you cannot see the dependency wiring or the safeguard's presence/absence from the examined slice.
