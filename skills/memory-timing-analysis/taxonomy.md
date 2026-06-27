# Memory & Timing Taxonomy

Full checklist for the memory-timing lens. Each entry: **what it is**, **signals (language-agnostic, how to spot)**, **vuln_class slug**. Slugs are stable — use them verbatim in findings.

---

## A. MEMORY — leaks & lifecycle

### A1. Unclosed handles (files / sockets / fds)
- **What:** a file, socket, pipe, or OS handle is opened but never closed, or not closed on every exit path.
- **Signals:** `open`/`socket`/`connect`/`fopen`/`createReadStream`/`os.Open` with no matching `close`/`Close`/`defer close`/`with`/`using`/`try-with-resources`/RAII. Close present on happy path but skipped on early `return`/`throw`/`break`/`continue`. Loop that opens per-iteration without closing.
- **vuln_class:** `handle-leak`

### A2. Unclosed DB connections / transactions / cursors
- **What:** connection borrowed from a pool, transaction begun, or cursor opened and never returned/committed/rolled-back/closed.
- **Signals:** `begin`/`beginTransaction`/`getConnection`/`acquire` without guaranteed `commit`/`rollback`/`release`/`close` on all paths; missing `finally`/`defer`; transaction left open on exception; cursor/result-set not closed. Pool exhaustion symptom.
- **vuln_class:** `connection-leak`

### A3. Accumulating event listeners / subscriptions / callbacks
- **What:** listeners/observers/subscriptions registered repeatedly (e.g. per request/render/loop) but never removed; grows unbounded.
- **Signals:** `addEventListener`/`on(`/`subscribe`/`connect`/`addObserver`/`watch` inside a function that runs many times, with no matching `removeEventListener`/`off`/`unsubscribe`/`disconnect`. Components that subscribe in setup but not teardown.
- **vuln_class:** `listener-leak`

### A4. Timers / intervals not cleared
- **What:** repeating timers, intervals, or scheduled tasks created and never cancelled.
- **Signals:** `setInterval`/`setTimeout`(recursive)/`schedule`/`Timer`/`ticker` without `clearInterval`/`clearTimeout`/`cancel`/`stop`; timer created per request/instance; goroutine/thread spawned in a loop with no exit condition.
- **vuln_class:** `timer-leak`

### A5. Unbounded cache / map / collection growth
- **What:** an in-memory map/dict/list/set that only grows — no eviction, TTL, size cap, or LRU.
- **Signals:** module-level/global/static/singleton collection written via user/loop-driven keys with no `evict`/`delete`/`maxSize`/`ttl`/`LRU`/`capacity`. Memoization keyed on unbounded input. Append-only buffers/logs in memory.
- **vuln_class:** `unbounded-cache`

### A6. Unbounded growth under large/streamed input
- **What:** entire request body, file, query result, or stream read fully into memory regardless of size.
- **Signals:** `read()`/`readAll`/`.text()`/`.json()`/`buffer()`/`ioutil.ReadAll`/`.collect()` on untrusted/streamed source with no size limit or streaming; building a giant string/array from a loop over external input; recursion depth driven by input.
- **vuln_class:** `unbounded-input`

### A7. Use-after-free / dangling pointer (manual/unsafe memory only)
- **What:** memory accessed after being freed; pointer/reference outlives its target.
- **Signals (C/C++/unsafe Rust/FFI):** use of pointer after `free`/`delete`; returning address of local/stack var; storing a borrowed pointer past its scope; `std::move`d-from value reused; iterator invalidation after container mutation.
- **vuln_class:** `use-after-free`

### A8. Double-free / double-close
- **What:** the same resource freed/closed/released twice.
- **Signals:** `free`/`delete`/`close`/`release` reachable twice on overlapping paths; freed in both error handler and normal flow; ownership transferred but original still frees; `defer close` plus explicit close.
- **vuln_class:** `double-free`

### A9. Memory leak (manual alloc without free)
- **What:** heap allocation never freed (manual-memory langs).
- **Signals:** `malloc`/`new`/`calloc`/`alloc` without matching `free`/`delete`; early return between alloc and free; overwriting the only pointer to allocated memory; alloc in loop without free.
- **vuln_class:** `mem-leak`

### A10. Retain cycle / reference cycle (refcounted langs)
- **What:** two objects strongly reference each other (or closure captures owner), preventing release.
- **Signals (Swift/ObjC/CPython/etc.):** strong parent<->child refs without `weak`/`unowned`; closure capturing `self` strongly; delegate held strongly; `__del__` participating in a cycle.
- **vuln_class:** `retain-cycle`

### A11. GC retention / large reference held live
- **What:** large object kept reachable longer than needed, inflating heap (GC langs).
- **Signals:** closure/lambda capturing a large object only partly needed; static/global holding request-scoped data; long-lived collection holding references to short-lived objects; caching whole objects instead of needed fields; listener on long-lived object capturing short-lived one.
- **vuln_class:** `gc-retention`

### A12. Allocation in hot loop / hot path
- **What:** repeated allocation inside a tight or high-frequency loop causing churn/GC pressure or perf collapse.
- **Signals:** `new`/`make`/list/dict/buffer/regex-compile/format-string built fresh every iteration when it could be hoisted; quadratic string concatenation in a loop; recompiling patterns per call.
- **vuln_class:** `hot-loop-alloc`

### A13. OOM risk (aggregate)
- **What:** a path that can drive the process out of memory.
- **Signals:** any of A5/A6 reachable from untrusted input; unbounded concurrency spawning unbounded buffers; recursion without depth limit; exponential blowup (zip bomb, deeply nested parse).
- **vuln_class:** `oom-risk`

### A14. Buffer overflow / out-of-bounds (manual/unsafe)
- **What:** read/write past allocated bounds.
- **Signals:** `memcpy`/`strcpy`/`sprintf`/index arithmetic without bounds check; length from untrusted input used as copy size; off-by-one on array index.
- **vuln_class:** `buffer-overflow`

---

## B. TIMING / CONCURRENCY

### B1. Data race on shared mutable state
- **What:** two+ execution contexts access shared state concurrently, at least one writes, with no synchronization.
- **Signals:** global/static/module/instance field read and written from multiple threads/goroutines/tasks without lock/atomic/channel; map/slice/dict mutated from concurrent handlers; shared counter `x++`/`x += 1`.
- **vuln_class:** `data-race`

### B2. Missing synchronization / locking
- **What:** a critical section that should be guarded isn't, or only partially is.
- **Signals:** some accesses to a field locked, others not (inconsistent locking); lock guards write but not read; documented "not thread-safe" structure used concurrently; `volatile`/`atomic` assumed sufficient for compound ops.
- **vuln_class:** `missing-sync`

### B3. Deadlock / lock-ordering violation
- **What:** circular wait — locks acquired in inconsistent order, or lock held during a blocking/await call.
- **Signals:** two locks acquired in order (A,B) in one site and (B,A) in another; nested locking; lock held across `await`/blocking I/O/RPC/`join`; acquiring same non-reentrant lock recursively; channel send/recv with no receiver/sender.
- **vuln_class:** `deadlock`

### B4. Lock not released on all paths
- **What:** lock acquired but a path (error/early-return/exception) skips the unlock, stalling everyone.
- **Signals:** explicit `lock()`/`acquire()` without `finally`/`defer`/RAII guard; `unlock` only on happy path; exception between lock and unlock.
- **vuln_class:** `lock-leak`

### B5. Livelock / busy-wait
- **What:** threads keep acting but make no progress; or spin without yielding.
- **Signals:** retry loops that all back off identically and collide; `while(!flag){}` spin without sleep/yield; cooperative threads repeatedly yielding to each other.
- **vuln_class:** `livelock`

### B6. TOCTOU (time-of-check to time-of-use)
- **What:** a check and the dependent action are separated by a window in which the condition can change.
- **Signals:** `if exists(file): open(file)`; `if not in cache: cache[k]=...`; permission/auth check then use; `stat` then `open`; balance check then debit across a yield/lock-free gap.
- **vuln_class:** `toctou`

### B7. Lost update / check-then-act non-atomic
- **What:** read-modify-write where concurrent actors clobber each other's updates.
- **Signals:** `x = get(); x++; set(x)`; `count += 1` on shared state; read-then-conditional-write without CAS/atomic/transaction/`SELECT ... FOR UPDATE`; non-atomic increment/append.
- **vuln_class:** `lost-update`

### B8. Non-atomic compound operation
- **What:** a multi-step operation assumed atomic but interruptible.
- **Signals:** check-and-insert, get-or-create, move/swap across two structures, multi-field invariant updated without a single lock/transaction; "atomic" only per-field not across fields.
- **vuln_class:** `non-atomic`

### B9. Async interleaving bug (state mutated across await)
- **What:** state read before an `await` is stale after it, or invariant broken because another task ran in between.
- **Signals:** local/shared value read, `await`, then used as if unchanged; reentrancy into the same async function; instance field guarding "in progress" set after an await; cache populated across await allowing duplicate work.
- **vuln_class:** `async-interleave`

### B10. await-in-loop unintended serialization
- **What:** independent async operations awaited one-by-one in a loop, serializing what should be concurrent (perf, or timeout cascade).
- **Signals:** `for (...) { await fn(item) }` where items are independent; sequential awaits with no data dependency instead of `Promise.all`/`gather`/`WaitGroup`/`errgroup`.
- **vuln_class:** `await-in-loop`

### B11. Fire-and-forget / missing await
- **What:** an async call's promise/future is not awaited or its error not handled; ordering and errors are lost.
- **Signals:** async function called without `await`/`.then`/`go`-without-sync; unhandled promise rejection; spawned task whose result/error is dropped; floating background work that outlives request scope.
- **vuln_class:** `missing-await`

### B12. Ordering assumption across async/threads
- **What:** code assumes a particular completion/execution order between independent concurrent flows that isn't guaranteed.
- **Signals:** relying on callback A finishing before B without sequencing; assuming initialization completes before use; reading a value another thread "should have" written; assuming FIFO from a concurrent queue/map iteration.
- **vuln_class:** `ordering-assumption`

### B13. Thundering herd / cache stampede / missing backoff
- **What:** many actors hit the same expensive operation simultaneously, or retry in lockstep, overwhelming a resource.
- **Signals:** cache-miss path with no single-flight/lock; retries with no backoff/jitter; all clients reconnecting at once; no rate limit on expensive recompute; synchronized expiry.
- **vuln_class:** `thundering-herd`

### B14. Signal / timer / callback race
- **What:** a signal handler, timer callback, or completion callback races with main flow or with itself.
- **Signals:** signal handler touching non-async-signal-safe state; callback mutating shared state without lock; timer firing after object disposed; callback invoked twice; cancellation racing with completion.
- **vuln_class:** `callback-race`

### B15. Unbounded concurrency / resource exhaustion via spawn
- **What:** spawning threads/goroutines/tasks/connections without a bound, exhausting OS or memory.
- **Signals:** `go`/`Thread`/`spawn`/`new Worker`/unbounded `Promise.all` over user-sized input; no worker pool/semaphore/limit; per-request goroutine with no cap.
- **vuln_class:** `unbounded-concurrency`

### B16. Atomicity gap in initialization (double-checked locking / lazy init)
- **What:** lazy/singleton init done without proper synchronization, allowing duplicate or partial init.
- **Signals:** double-checked locking without memory barrier/volatile; `if instance is None: instance = ...` reachable concurrently; lazy field set non-atomically.
- **vuln_class:** `unsafe-lazy-init`

---

## Cross-cutting hunting reminders
- Long-lived process + per-event resource acquisition = top leak suspects (A1–A5).
- Untrusted size/count input + full materialization = OOM (A6, A13).
- Any shared mutable state + >1 execution context + a write = start a race analysis (B1, B6, B7, B8).
- Any two locks = check ordering (B3); any lock = check all-paths release (B4).
- Any `await`/yield between a read and its use = async interleave check (B9).
- A defect that is real but currently only a future risk (e.g. unbounded cache with low traffic) -> `category: "health"`, `trigger_path: "static"`.
