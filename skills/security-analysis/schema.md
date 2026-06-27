# Findings output schema

Emit findings as a single JSON object conforming to the schema below. This schema is identical across all skills in the suite except for the `skill`, `lens`, and finding `id` PREFIX values.

```json
{
  "skill": "security-analysis",
  "lens": "security",
  "stack_detected": ["<language/framework>"],
  "coverage": { "files_examined": 0, "skipped": ["<what was not examined and why>"] },
  "degraded": {},                            // e.g. {"health_analysis":"skipped: no git history"} — empty {} if nothing degraded
  "findings": [
    {
      "id": "SEC-001",                       // PREFIX per skill: RT, SEC, EC, MT, WI
      "title": "<short imperative title>",
      "category": "defect",                  // "defect" for all; edge-case also uses "health"
      "vuln_class": "<stable-taxonomy-slug>",// e.g. null-deref, sql-injection, race-condition, mem-leak, dep-down
      "severity": "critical|high|medium|low|info",
      "confidence": "high|medium|low",
      "location": { "file": "<repo-relative path>", "line": 0, "symbol": "<fn/class or null>" },
      "dedup_key": "<normalized_file_path>:<line>:<vuln_class>",
      "evidence": "<verbatim code snippet showing the issue>",
      "trigger_path": "<how the issue is reached/triggered, or 'static' for non-triggerable health findings>",
      "impact": "<what goes wrong>",
      "recommendation": "<concrete fix>"
    }
  ]
}
```
