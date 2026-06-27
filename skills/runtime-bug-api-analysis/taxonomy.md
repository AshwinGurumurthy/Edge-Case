# runtime-bug-api-analysis — taxonomy

Full, language-agnostic catalog for the runtime/logic + API-contract lens. For each category: **what it is**, **signals (how to spot it, stack-neutral)**, and the **`vuln_class`** slug to emit. Map signals onto the detected language/framework — do not assume a stack.

---

## A. Null / optional / undefined defects

### A1. Null/undefined/optional dereference
- **What**: accessing a member/index/method on a value that can be null, nil, None, undefined, empty Optional, or a not-yet-resolved value.
- **Signals**: chained access (`a.b.c`, `obj["k"]["k2"]`) after a lookup/find/parse/regex-match that can miss; map/dict `.get`/index returning optional then used unconditionally; `Optional`/`Maybe`/`*ptr` unwrapped without check (`.unwrap()`, `!`, `.get()` on empty, force-unwrap); array `[0]`/`first()` on possibly-empty collection; env var/config read then dotted into.
- **vuln_class**: `null-deref`

### A2. Unchecked nullable return
- **What**: a function/DB query/cache/API that documents or can return null/empty/error is consumed as if always present.
- **Signals**: `findOne`/`findById`/`get`/`lookup`/`query` results used without an existence check; "find first" used where zero results possible; DB driver returning `(value, found)` or `(value, err)` where the second is ignored; deserialization returning optional then read directly.
- **vuln_class**: `unchecked-nullable-return`

---

## B. Type & coercion defects

### B1. Type coercion / implicit conversion bug
- **What**: a value is implicitly coerced (string↔number↔bool), truncated, or compared across types, producing wrong logic.
- **Signals**: loose equality across types (`==` vs `===`); string concatenation where numeric add intended; `parseInt`/`atoi`/`Number()` without radix/error check; query/path params (always strings) used in arithmetic or `===` numeric compare; `0`/`""`/`null`/`NaN` falsy traps in guards (`if (x)` where `0` is valid); JSON numbers losing precision (int64 → float/JS number); boolean parsed from string ("false" truthy).
- **vuln_class**: `type-coercion`

### B2. Serialization / deserialization mismatch
- **What**: data encoded/decoded with mismatched shape, field names, casing, or types between producer and consumer.
- **Signals**: snake_case vs camelCase across boundary; date/time encoded as string but parsed as number (or vice versa); enum serialized as int on one side, string on other; missing/extra fields silently dropped; `null` vs absent field conflated; binary/base64 handling assumptions; custom (de)serializer that doesn't round-trip; timezone/offset dropped on serialize.
- **vuln_class**: `serialization-mismatch`

---

## C. Async / concurrency / error-flow defects

### C1. Unhandled promise rejection / unawaited async
- **What**: an async operation is fired without awaiting/joining, so failures vanish or ordering breaks.
- **Signals**: async call not `await`ed/`.then`ed where its result/side effect is needed next; `await` missing inside a loop then result used after; goroutine/thread launched with no error channel/join; `Promise.all` vs sequential where a rejection is dropped; fire-and-forget I/O in a request handler; floating promise lint pattern; background task not tied to lifecycle.
- **vuln_class**: `unawaited-async`

### C2. Missing error handling around I/O / awaits
- **What**: a fallible call (network, DB, file, parse) has no try/catch/`err != nil`/Result handling, so an exception propagates uncaught or a panic crashes the process/handler.
- **Signals**: `await`/network/DB call with no surrounding error handling and no global handler evidence; ignored error return (`_ = err`, `err` not checked); `JSON.parse`/decode on untrusted input without guard; `.unwrap()`/`expect()` on fallible Result; no error middleware registered for the framework.
- **vuln_class**: `missing-error-handling`

### C3. Error swallowing / empty catch
- **What**: an error is caught and discarded (or logged-and-continued) so the caller sees success or corrupted state.
- **Signals**: empty `catch {}` / `except: pass` / `rescue nil` / `if err != nil { }`; catch that returns a default/`null`/`200` masking failure; broad catch-all swallowing everything; `catch` that logs but continues with partially-built state.
- **vuln_class**: `error-swallowing`

### C4. Race condition / shared-state mutation
- **What**: concurrent access to shared mutable state without synchronization, or check-then-act (TOCTOU) gaps.
- **Signals**: module/global mutable state mutated in request handlers; read-modify-write on shared counter/map without lock; `await` between a check and the dependent action; cache populate without single-flight; non-atomic "create if not exists".
- **vuln_class**: `race-condition`

---

## D. Resource & lifecycle defects

### D1. Resource leak (connections/handles/transactions)
- **What**: a resource is acquired but not reliably released on all paths (esp. error paths).
- **Signals**: open/connect/acquire without `finally`/`defer`/`with`/`using`/dispose; early `return`/throw before close; DB transaction begun with no commit/rollback on every branch; file/socket/stream opened, no close; connection pool checkout without checkin; event listener/subscription added, never removed (leak/grow).
- **vuln_class**: `resource-leak`

### D2. Unbounded resource use / missing limits
- **What**: input or work that can grow without bound (memory, goroutines, recursion, payload size).
- **Signals**: reading entire request body/file into memory without size cap; unbounded loop/recursion driven by input; spawning a task per item with no concurrency limit; no timeout on outbound calls; no max page size.
- **vuln_class**: `unbounded-resource`

---

## E. API contract defects

### E1. Request validation gap
- **What**: input crosses the trust boundary into logic/sinks without validation of presence, type, range, or format.
- **Signals**: route handler reads `body`/`query`/`params`/`headers` and uses fields directly; declared validation schema (zod/joi/pydantic/class-validator/JSON Schema) exists but handler bypasses it or validates a subset; required field assumed present; numeric/enum/length/format unchecked; mass-assignment of whole body into a model.
- **vuln_class**: `request-validation-gap`

### E2. Wrong / inconsistent HTTP status code
- **What**: the status code doesn't match the outcome, breaking client logic and retries.
- **Signals**: `200` returned on error/empty/not-found; missing-resource returns `200` with null body instead of `404`; validation failure returns `500` instead of `400`; auth/permission failure returns wrong of `401`/`403`; created resource returns `200` not `201`; same error path returns different codes in different branches; redirect/`3xx` misuse.
- **vuln_class**: `wrong-status-code`

### E3. Response shape vs declared schema mismatch
- **What**: the response body deviates from the OpenAPI/SDL/proto/DTO/TypeScript contract.
- **Signals**: handler returns a field absent from the schema or omits a required one; type differs from declared (string vs number, array vs object); GraphQL resolver returns shape diverging from SDL; nullable-in-schema field never set vs non-null field sometimes null; error responses with ad-hoc shape vs documented error envelope.
- **vuln_class**: `response-shape-mismatch`

### E4. Inconsistent error contract
- **What**: errors are reported in different shapes/codes across endpoints, so clients can't handle them uniformly.
- **Signals**: some endpoints return `{error: "..."}`, others `{message}`, others raw string/HTML; mixed status codes for the same logical error; stack traces / internal details leaked in some responses but not others; error envelope documented but not used.
- **vuln_class**: `inconsistent-error-contract`

### E5. Breaking API change vs prior contract
- **What**: a change alters the public surface in a backward-incompatible way (renamed/removed field, changed type, new required param, changed default).
- **Signals** (needs prior contract — git diff, versioned schema, changelog): field removed/renamed in response or request; param made required; type narrowed; enum value removed; default value changed; endpoint path/verb changed; status-code semantics changed. Report as `health`/`info`→ defect depending on impact; cite the diff/old contract as evidence.
- **vuln_class**: `breaking-api-change`

---

## F. Logic / data-handling defects

### F1. Pagination / cursor / limit bug
- **What**: paging logic skips, duplicates, or fails to terminate.
- **Signals**: off-by-one in `offset`/`limit`; `page * size` overflow or `page=0` vs `page=1` confusion; cursor not advanced / re-uses same cursor; missing `hasMore`/total handling causing infinite or truncated loops; default limit absent (returns all); limit not capped allowing huge pulls; sort key not stable so pages overlap.
- **vuln_class**: `pagination-bug`

### F2. Retry without idempotency
- **What**: an operation with side effects is retried (by code, client, or queue) without an idempotency guard, causing duplication.
- **Signals**: retry loop / retry middleware / at-least-once queue consumer wrapping a non-idempotent write (insert, charge, send, increment); no idempotency key / dedup check; `POST` retried; webhook handler not deduping by event id.
- **vuln_class**: `retry-without-idempotency`

### F3. Default-value / optional-argument bug
- **What**: a missing optional input falls back to a wrong/unsafe default, or a shared mutable default is reused.
- **Signals**: default that changes behavior silently (e.g. defaulting a filter to "all"); mutable default argument shared across calls (Python `def f(x=[])`); `||`/`??` default that overrides a legitimate falsy value (`0`, `""`, `false`); config default differing from documented; missing field defaulted to a value that bypasses a check.
- **vuln_class**: `default-value-bug`

### F4. Incorrect conditional / boundary logic
- **What**: comparison, boundary, or boolean logic that is wrong on edges.
- **Signals**: `<` vs `<=` off-by-one; inverted condition; `&&`/`||` precedence/De Morgan mistakes; empty-collection edge handled wrong; integer overflow/underflow on arithmetic; division without zero check; modulo on negative; date/time arithmetic ignoring DST/leap.
- **vuln_class**: `boundary-logic-bug`

### F5. Outbound client-call contract fault
- **What**: a call to a downstream/external API mishandles its contract.
- **Signals**: response status not checked before parsing body; assumes a field present in third-party response; no timeout/retry/backoff on a remote call (or retry without backoff); ignores partial/`207`/error envelopes; assumes ordering; hardcoded shape that drifts from the upstream API.
- **vuln_class**: `outbound-contract-fault`

---

## Severity guidance for this lens
- **critical**: a guaranteed crash/hang on a common request path; data loss/corruption from a leak, swallowed error, or non-idempotent retry on a core write.
- **high**: reliable failure on a realistic input (e.g. missing-field deref reachable from a public route); transaction leak under error.
- **medium**: fault on uncommon-but-reachable input; status/shape mismatch that breaks well-behaved clients.
- **low**: hard-to-reach edge, minor coercion, defense-in-depth.
- **info**: hygiene, inconsistent-but-harmless conventions, breaking-change signals without confirmed downstream impact.

## Confidence guidance
- **high**: the snippet itself shows the fault and a reachable trigger.
- **medium**: fault visible but reachability/runtime depends on unseen config/middleware.
- **low**: plausible from the slice but needs flow/data not visible here.
