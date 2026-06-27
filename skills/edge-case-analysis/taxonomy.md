# edge-case-analysis — taxonomy

Two sections: **DEFECT** (category:"defect") and **HEALTH** (category:"health"). For each entry: *what it is*, *how to spot it (language-agnostic signals)*, and the `vuln_class` slug to emit.

The core defect move is always the same: **map the input's full domain, name the invariant the code assumes, find a path where a domain value reaches a sink before the invariant is enforced.**

---

## DEFECT taxonomy (category:"defect", trigger_path = real trigger)

### 1. Empty / null / missing input
- **What:** value is absent (null/None/nil/undefined), empty string, empty body, missing key/field/arg, missing env var/config.
- **Signals:** field access / method call / index / deref immediately after a lookup, parse, or external fetch with no presence check; optional-typed value used as if present; `.get(k)` result used without nil check; required CLI arg/env read without default or guard; destructuring of possibly-absent object.
- **vuln_class:** `null-deref` (deref/use of absent value); `missing-input` (required input absent, no default/error); `empty-input` (empty string/body treated as valid content).

### 2. Very large / unbounded input
- **What:** input whose size or count is attacker- or caller-controlled and unbounded — huge string, huge collection, deep nesting, large file, large number, large pagination limit.
- **Signals:** read-all into memory (`read()`, `readAll`, slurp), unbounded loop over caller-sized input, recursion driven by input depth (stack overflow), no max-length/max-count/max-size check before allocation or processing, regex on unbounded input (ReDoS).
- **vuln_class:** `unbounded-input` (no size/count cap); `resource-exhaustion` (memory/CPU blowup); `deep-recursion` (input-driven stack depth); `redos` (catastrophic backtracking on caller input).

### 3. Unicode / encoding / normalization
- **What:** assumptions that text is ASCII, single-byte, NFC-normalized, length-in-bytes == length-in-chars, or that case-folding is reversible.
- **Signals:** byte-length used as char count or vice versa; substring/truncation by byte/code-unit index (splits surrogate pairs / multibyte); equality/dedup/auth checks on un-normalized strings (NFC vs NFD); case-insensitive compare without locale-safe folding (Turkish-I); encoding assumed without declaring it on decode/encode; homoglyph/zero-width not stripped before identity checks.
- **vuln_class:** `encoding-assumption` (charset/byte-vs-char); `unicode-normalization` (compare/dedup/auth on un-normalized text); `truncation-split` (cut mid-codepoint/grapheme).

### 4. Negative / zero / boundary numbers
- **What:** numeric input reaching 0, negative, or domain edge where code assumed positive / non-zero / in-range.
- **Signals:** division/modulo where divisor is caller-controlled (div-by-zero); array size, count, index, length, timeout, retry-count, allocation derived from a number with no `>= 0` / `> 0` / range check; negative used as index or loop bound; subtraction that can go negative used as unsigned size.
- **vuln_class:** `div-by-zero`; `negative-value` (negative where non-negative assumed); `boundary-number` (min/max domain edge mishandled).

### 5. Off-by-one
- **What:** loop/index/slice boundary that includes or excludes one element wrongly.
- **Signals:** `<=` vs `<` on length-bound loops; `len`/`size` used as a valid index; slice `[i:j]` or `substring(i, j)` at the last element; first/last element handled outside the loop; `+1`/`-1` adjusting an index or boundary; fencepost in range generation.
- **vuln_class:** `off-by-one`.

### 6. Integer overflow / underflow
- **What:** arithmetic that exceeds the type's range, wraps, or in dynamically-typed languages silently turns to float/loses precision.
- **Signals:** multiply/add of caller-controlled values feeding a size/allocation/index; counters/accumulators on fixed-width ints; `len * elemSize`, `a + b` for buffer sizing; timestamp/epoch math near type limits; bit-shift by large amount; cast to narrower type.
- **vuln_class:** `int-overflow` (incl. underflow/wraparound).

### 7. Float precision & equality
- **What:** floating-point used where exactness matters, or compared with `==`.
- **Signals:** `==`/`!=` between floats; money/currency stored or computed as float; accumulation in a loop expected to hit an exact value; `NaN`/`Infinity` from `0.0/0.0`, `log`, parse-of-bad-number propagating unchecked; float used as map key or for equality-based control flow.
- **vuln_class:** `float-precision` (exactness lost / money-in-float); `float-equality` (`==` on floats); `nan-propagation` (NaN/Inf flows unchecked).

### 8. Locale / timezone / DST
- **What:** date/time/number/string formatting or parsing that depends on ambient locale or timezone.
- **Signals:** parse/format date without explicit tz/locale; naive (tz-less) datetime compared across boundaries; `now()`/local time used for durations across DST; number/decimal parse using locale separators (`,` vs `.`); sort/upper/lower without locale; midnight/end-of-day assumed 24h; epoch/UTC vs local mixed.
- **vuln_class:** `timezone-bug` (tz/DST mishandling); `locale-bug` (locale-dependent parse/format/sort).

### 9. Empty collections / single-element
- **What:** code that assumes a collection is non-empty or has >1 element.
- **Signals:** `[0]`/`first`/`head`/`.pop()`/`max`/`min`/`average` on a possibly-empty collection; reduce without initial value; "join with separator" or "all but last" logic that breaks at size 0 or 1; pairwise/sliding-window over fewer than window elements; division by collection size.
- **vuln_class:** `empty-collection` (empty case unhandled); `single-element` (n==1 case unhandled).

### 10. Pagination first/last boundaries
- **What:** paging/cursor/offset logic at page 0/1, last page, page beyond end, page size 0 or huge.
- **Signals:** `offset = (page-1)*size` with page 0 or negative; `limit`/`size` unbounded or zero; last-page partial fill mishandled; cursor at end returns dupes or skips; off-by-one between "page count" and "has next"; total-count divide for page-count without ceil.
- **vuln_class:** `pagination-boundary`.

### 11. Partial / duplicate input
- **What:** truncated/partial reads, repeated/duplicate items, idempotency assumptions.
- **Signals:** stream/socket read assumed complete in one call; partial write not retried; duplicate keys in input silently overwrite or double-count; replayed request/event processed twice (no idempotency key); set operations assuming uniqueness on non-unique input; merge of partial records losing fields.
- **vuln_class:** `partial-input` (incomplete read/write assumed complete); `duplicate-input` (dupes double-counted / non-idempotent).

### 12. Mixed-type / unexpected-type input
- **What:** dynamically-typed or deserialized input whose runtime type differs from assumed.
- **Signals:** JSON/YAML/form value used as a specific type without check (string where number expected, array where scalar expected, object where string expected); `+` doing string-concat vs numeric-add depending on type; type coercion at a boundary (`"0"`, `""`, `"false"` truthiness); polymorphic deserialization without a tag/type guard.
- **vuln_class:** `type-confusion` (runtime type mismatch / unsafe coercion).

### 13. Ordering / sortedness assumptions
- **What:** code assumes input is sorted, ordered, or in insertion order.
- **Signals:** binary search / merge / dedup-adjacent on data not guaranteed sorted; reliance on map/dict iteration order; "latest is last" assumption on unordered source.
- **vuln_class:** `ordering-assumption`.

---

## HEALTH taxonomy (category:"health", severity mostly info/low, trigger_path:"static")

Health findings still need a real `location.file` + line and verbatim evidence (a line from the file, a manifest entry, or a representative line in the hotspot). Where the signal is git-derived, cite the file the signal is about and quote a representative line; put the git metric in `evidence`/`impact`.

### H1. Complexity hotspots — god files/functions, deep nesting, high fan-in/out
- **What:** oversized files/functions, deeply nested control flow, modules everything depends on.
- **Signals:** file >~800 lines or function >~80 lines; nesting depth >~4; one module imported by very many others (fan-in) or importing very many (fan-out); long parameter lists; high cyclomatic branching.
- **vuln_class:** `complexity-hotspot`.

### H2. Code duplication
- **What:** copy-pasted logic across files/functions.
- **Signals:** near-identical blocks, repeated literals/magic numbers, parallel switch/if-chains updated in lockstep.
- **vuln_class:** `code-duplication`.

### H3. Missing tests around risky code
- **What:** parsers, math, auth, money, boundary logic with no nearby tests.
- **Signals:** risky module has no corresponding test file; test dir absent for a high-risk dir; complex function with zero test references.
- **vuln_class:** `missing-tests`.

### H4. TODO / FIXME / HACK density
- **What:** clusters of deferred work / known defects in comments.
- **Signals:** `TODO`/`FIXME`/`HACK`/`XXX`/`BUG` markers, especially concentrated in one file or near risky logic.
- **vuln_class:** `todo-debt`.

### H5. Bus-factor / contributor concentration
- **What:** few people understand large parts of the code.
- **Signals:** `git shortlog -sne` shows one/two authors with the vast majority of commits; a critical module authored ~entirely by one person.
- **vuln_class:** `bus-factor`.

### H6. Single-owner critical modules
- **What:** a high-risk module owned/edited by exactly one person.
- **Signals:** `CODEOWNERS` single owner on a critical path; git authorship of that file is single-author.
- **vuln_class:** `single-owner`.

### H7. Stale / unmaintained dependencies
- **What:** dependencies far behind, unmaintained, or known-vulnerable.
- **Signals:** old pinned versions in manifest/lockfile; deps with no upstream activity; major versions behind; transitive vuln advisories.
- **vuln_class:** `dep-down` (unavailable/abandoned dep) / `stale-dependency` (outdated).

### H8. Last-commit recency / abandonment
- **What:** module or whole repo not touched in a long time despite being active code.
- **Signals:** `git log` shows last change to a file/dir is very old; whole-repo last commit stale.
- **vuln_class:** `abandonment`.

### H9. Documentation rot
- **What:** docs/READMEs/comments contradicting current code.
- **Signals:** README referencing removed commands/files/APIs; comments describing different behavior than the code; setup steps for deleted tooling.
- **vuln_class:** `doc-rot`.
