# Legacy Discovery Recipes

Use this reference when reverse-modeling systems where documentation is sparse, code is old, or knowledge is tribal.

## Architect use cases

| Challenge | Approach | Output |
| --- | --- | --- |
| No documentation, only code | Extract nodes from imports, DB schema, and config files | Low-confidence dependency graph + evidence inventory |
| Documentation exists but is old | Compare docs with code and annotate differences | Docs-vs-reality gap map |
| Only verbal knowledge from domain experts | Record as human-assumption and mark low confidence | Assumption map + validation backlog |
| The system has many unknown call relationships | Extract actual calls from runtime logs/traces | Runtime-only call graph |
| High-risk legacy areas need identification | Combine technical-debt indicators and change frequency | Legacy risk heatmap |

## Low-confidence model example

```json
{
  "name": "Legacy Billing System",
  "nodes": [
    { "id": "billing-core", "type": "service", "label": "Billing Core", "description": "Main billing module, ~15 years old", "confidence": "high", "sourceRefs": ["src/billing/core.vb"] },
    { "id": "tax-engine", "type": "service", "label": "Tax Engine", "description": "Assumed to be called for invoicing; no clear interface found", "state": "unknown", "confidence": "low", "sourceRefs": ["docs/architecture-2009.doc"] },
    { "id": "ledger-db", "type": "database", "label": "Ledger DB (Oracle)", "confidence": "high", "sourceRefs": ["src/billing/dal/OracleAdapter.vb"] },
    { "id": "mainframe-api", "type": "external-system", "label": "Mainframe API", "confidence": "medium", "sourceRefs": ["src/billing/mainframe/connector.vb"] }
  ],
  "edges": [
    { "from": "billing-core", "to": "ledger-db", "type": "writes", "protocol": "SQL/OCI", "confidence": "high", "sourceRefs": ["src/billing/dal/"] },
    { "from": "billing-core", "to": "mainframe-api", "type": "calls", "protocol": "MQ", "confidence": "medium", "sourceRefs": ["src/billing/mainframe/connector.vb"] },
    { "from": "billing-core", "to": "tax-engine", "type": "calls", "description": "Assumed; no code found — see 2009 doc", "confidence": "low", "sourceRefs": ["docs/architecture-2009.doc"] }
  ]
}
```

## Unknown area annotation

```markdown
## Unknown Areas — Billing System

| Node / Edge | Reason unknown | Discovery action |
|-------------|----------------|-----------------|
| Tax Engine interface | No code found; only 2009 doc | Interview billing owner + check network logs |
| Billing ↔ Reporting integration | Integration tests reference "billing_export" | Find billing_export script, check cron jobs |
| Nightly reconciliation job | Cron entry exists, no source found | Check `/etc/cron.d/` on legacy server |
| Database size and query patterns | Unknown — need DBA access | Run `pg_stat_user_tables` or equivalent |
```

## Quality rules for legacy systems

- Never present low-confidence edges as confirmed facts; always carry `confidence: low`.
- "We've always done it this way" counts as `human-assumption`, not evidence.
- Runtime trace data (logs, Datadog APM) is `medium` confidence for current-state calls.
- Treat old documentation as `low` confidence if it hasn't been verified against current code.
- The goal of the first iteration is a complete low-confidence map, not a perfect high-confidence map.
- Flag every `unknown` node as a discovery task, not a gap to silently ignore.
