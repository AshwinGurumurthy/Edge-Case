# Security Taxonomy — full checklist

Language-agnostic catalog. For each category: **what it is**, **how to spot it (signals)**, and the **`vuln_class`** slug to use in findings. Map every signal to the detected stack's idioms; the concepts are universal even when the syntax differs.

---

## A. Injection (tainted input reaches an interpreter)

### A1. SQL injection — `vuln_class: sql-injection`
- **What**: untrusted data concatenated/interpolated into a SQL query instead of bound as a parameter.
- **Signals**: string concatenation/format/template building a query (`"... WHERE id=" + x`, f-strings, `%`, `+`, `.format`, template literals) feeding `execute`/`query`/`rawQuery`/`Statement`/`createQuery`. ORM "raw"/"literal" escape hatches (`.raw()`, `text()`, `db.Exec(fmt.Sprintf(...))`). Dynamic table/column names from input. Absence of `?`/`$1`/named bind parameters.

### A2. NoSQL injection — `vuln_class: nosql-injection`
- **What**: untrusted data shapes a NoSQL query/operator (Mongo, DynamoDB, etc.).
- **Signals**: request body/JSON passed directly as a query filter (`find(req.body)`), allowing operator injection (`{"$gt":""}`, `$where`, `$regex`). `eval`/`$where` with user data. Unvalidated query objects.

### A3. OS command injection — `vuln_class: command-injection`
- **What**: untrusted data reaches a shell/exec.
- **Signals**: `system`, `exec`, `execSync`, `spawn(..., {shell:true})`, `popen`, `os/exec` with a shell string, `subprocess` with `shell=True`, backticks, `Runtime.exec(String)`. Tainted data in the command string or args without allow-listing.

### A4. LDAP / directory injection — `vuln_class: ldap-injection`
- **What**: untrusted data in an LDAP filter/DN without escaping.
- **Signals**: filter strings built with concatenation (`(uid=` + user + `)`), no LDAP-special-char escaping.

### A5. Template injection (SSTI) — `vuln_class: template-injection`
- **What**: untrusted data rendered as a template, enabling code/expression execution.
- **Signals**: user input passed as the *template* (not the data) to Jinja/Twig/Freemarker/Velocity/ERB/Handlebars/Thymeleaf render functions; `render_template_string(user)`, string-built templates.

### A6. Cross-site scripting (XSS) — `vuln_class: xss`
- **What**: untrusted data reflected/stored into HTML/JS without context-correct encoding.
- **Signals**: `innerHTML`, `dangerouslySetInnerHTML`, `v-html`, `document.write`, `|safe`/`raw`/`{{{ }}}` template filters, `mark_safe`, disabled auto-escaping, building HTML by string concat. Reflected query/path params into a response body.

### A7. Other interpreter injection — `vuln_class: code-injection`
- **What**: untrusted data into `eval`/`Function`/`exec`/`pickle`/`yaml.load`/XPath/header/log/CRLF/regex (ReDoS) contexts not covered above.
- **Signals**: `eval(`, `new Function(`, dynamic `import`/`require` of a tainted name, XPath built from input, user data in response headers (header/CRLF injection), unbounded user-controlled regex (ReDoS).

---

## B. Authentication & session

### B1. Authentication gaps — `vuln_class: auth-bypass`
- **What**: protected functionality reachable without valid authentication.
- **Signals**: routes/handlers that perform sensitive actions with no auth middleware/decorator; auth checks that can be skipped (early `return`, debug bypass, `if (token)` without verifying); comparison of credentials with `==` (timing) or against a constant.

### B2. Weak session / token handling — `vuln_class: weak-session`
- **What**: insecure session or JWT handling.
- **Signals**: JWT verified with `none` alg or without signature verification (`decode` instead of `verify`, `verify=False`); secrets/keys hardcoded; tokens never expiring; session cookies without `HttpOnly`/`Secure`/`SameSite`; predictable session IDs.

### B3. Missing rate limiting / brute-force exposure — `vuln_class: missing-rate-limit`
- **What**: auth/sensitive endpoints with no throttling.
- **Signals**: login/password-reset/OTP/token endpoints lacking rate-limit middleware, lockout, or backoff; expensive endpoints callable unbounded.

---

## C. Authorization

### C1. Broken access control / IDOR — `vuln_class: idor`
- **What**: a user can access/modify another user's resource because the handler trusts an ID from input without an ownership/role check.
- **Signals**: resource fetched by an ID taken directly from request params/body and returned/mutated without comparing to the authenticated principal (`get(id)` then no `if owner == current_user`); admin endpoints lacking role checks.

### C2. Missing function-level authorization — `vuln_class: missing-authz`
- **What**: privileged operation lacks a role/permission check even if authenticated.
- **Signals**: admin/delete/config endpoints with authentication but no authorization gate; client-side-only role enforcement.

### C3. Mass assignment / over-binding — `vuln_class: mass-assignment`
- **What**: request body bound wholesale to a model, letting an attacker set protected fields (`isAdmin`, `role`, `balance`).
- **Signals**: `Model(**req.body)`, `update(req.body)`, `bind`/`ShouldBind` of whole struct, ORM `create(params)` without an allow-list/`select`/`fillable` filter.

---

## D. Secrets & sensitive data

### D1. Hardcoded secrets & keys — `vuln_class: hardcoded-secret`
- **What**: credentials, API keys, private keys, tokens embedded in source/config.
- **Signals**: high-entropy strings assigned to `password`/`secret`/`api_key`/`token`/`private_key`; `-----BEGIN ... PRIVATE KEY-----`; cloud keys (`AKIA...`); connection strings with inline passwords; secrets committed in `.env`, config, or Dockerfiles. Capture the literal as evidence (it is in the repo already).

### D2. Sensitive data in logs/errors — `vuln_class: sensitive-data-exposure`
- **What**: secrets/PII/tokens written to logs or returned in error responses/stack traces.
- **Signals**: logging request bodies, passwords, tokens, full objects containing credentials; returning raw exception/stack trace to clients; verbose error modes enabled in production config.

---

## E. Cryptography & randomness

### E1. Weak / misused crypto — `vuln_class: weak-crypto`
- **What**: broken or misapplied cryptographic primitives.
- **Signals**: MD5/SHA1 for passwords/signatures; DES/RC4/ECB mode; static/zero IV; password hashing without a salt or with a fast hash (use bcrypt/scrypt/argon2); custom/home-rolled crypto; hardcoded encryption keys.

### E2. Insecure randomness for security use — `vuln_class: insecure-randomness`
- **What**: non-cryptographic RNG used for tokens/IDs/keys/nonces.
- **Signals**: `Math.random`, `rand()`, `random.random`/`randint`, `mt_rand` used to generate session tokens, password-reset tokens, API keys, IVs, or salts (should use a CSPRNG).

---

## F. Server-side request & file handling

### F1. SSRF — `vuln_class: ssrf`
- **What**: server makes an outbound request to a URL controlled by untrusted input.
- **Signals**: tainted URL/host/port passed to an HTTP client (`requests.get(user_url)`, `fetch`, `http.Get`, `URLConnection`, image/webhook/PDF fetchers); no allow-list; ability to hit internal IPs/metadata endpoints (`169.254.169.254`), `file://`, `gopher://`.

### F2. Path traversal / unsafe file ops — `vuln_class: path-traversal`
- **What**: untrusted input used to build a filesystem path, escaping the intended directory.
- **Signals**: request param/filename concatenated into a path passed to `open`/`read`/`write`/`sendFile`/`os.path.join`/`ServeFile` without canonicalization + base-dir containment check; `..` not stripped; archive extraction without zip-slip protection; unrestricted file upload (no type/size/path validation).

### F3. Unsafe deserialization — `vuln_class: unsafe-deserialization`
- **What**: untrusted bytes deserialized via a mechanism that can instantiate arbitrary objects / execute code.
- **Signals**: `pickle.loads`, `yaml.load` (unsafe loader), Java `ObjectInputStream.readObject`, PHP `unserialize`, .NET `BinaryFormatter`, Ruby `Marshal.load`, `Marshal`/`JSON` with type metadata, on data from network/files/cookies.

---

## G. Transport, CORS & network config

### G1. Disabled TLS / cert verification — `vuln_class: tls-verification-disabled`
- **What**: TLS certificate validation turned off, enabling MITM.
- **Signals**: `verify=False`, `rejectUnauthorized:false`, `InsecureSkipVerify:true`, `TrustAllCerts`, `curl -k`, custom trust-all `HostnameVerifier`/`TrustManager`, allowing plaintext HTTP for sensitive traffic.

### G2. Permissive CORS — `vuln_class: permissive-cors`
- **What**: CORS configured to allow any origin (esp. with credentials).
- **Signals**: `Access-Control-Allow-Origin: *` (or reflecting the request `Origin`) combined with `Allow-Credentials: true`; wildcard methods/headers on authenticated endpoints.

---

## H. Configuration & defaults

### H1. Insecure defaults — `vuln_class: insecure-default`
- **What**: insecure framework/app configuration shipped as default.
- **Signals**: debug/dev mode on in prod, default/empty admin credentials, directory listing enabled, dangerous features on (e.g., XXE — XML parser with external entities/DTD enabled), CSRF protection disabled, overly broad file/object permissions (`0777`, public buckets), management endpoints exposed, secrets in plaintext config.

### H2. XML external entity (XXE) — `vuln_class: xxe`
- **What**: XML parser resolves external entities/DTDs from untrusted XML.
- **Signals**: XML parser without `external-general-entities`/DTD disabled; `libxml` with `noent`; `DocumentBuilderFactory` without secure-processing; parsing untrusted XML/SVG/SOAP.

---

## I. Dependencies

### I1. Vulnerable / outdated dependencies — `vuln_class: dep-vuln`
- **What**: a pinned dependency version is known-vulnerable or unmaintained.
- **Signals**: read dependency manifests (`package.json`/lockfile, `requirements.txt`, `go.mod`, `pom.xml`, `Gemfile.lock`, `Cargo.toml`, etc.). Flag versions you recognize as carrying known CVEs, or clearly outdated majorly-behind versions. **Evidence MUST be the manifest line showing package + version.** Confidence `medium`/`low` unless you are certain of the CVE. Note pinned-to-`*`/unpinned ranges as supply-chain risk.

---

## Taint-tracking reminders
- A source is only dangerous if it reaches a sink **without context-correct neutralization**. Note the sanitizer (or its absence) explicitly.
- Validation that constrains *type* (is-int) can still be wrong for the *sink context* (still allows path traversal, etc.). Don't treat any-validation as clearing taint.
- Indirect sources count: data read back from a DB/file/cache that was originally attacker-controlled is still tainted (second-order injection).
- For static findings (secrets, weak crypto, insecure config, dep-vuln) there is no taint path — set `trigger_path` to `static`.
