# Visualization Consistency Validator — Examples

Use this reference when checking diagram accuracy, building traceability indexes, or setting up CI validation.

## Architect use cases

| Question | Approach | Output |
| --- | --- | --- |
| Does this diagram still match the code? | Compare diagram nodes with services/modules that actually exist in code | Consistency report + diff inventory |
| Which file can each diagram node trace back to? | Build a sourceRefs index and generate a traceability matrix | traceability-matrix.md |
| If this file changed, which diagram nodes are affected? | Reverse index from file path to diagram node | reverse-index.json |
| Which diagram nodes have no code evidence? | Scan sourceRefs for all nodes | untraced-items.md |
| How should CI automatically check diagram completeness? | Define failure conditions and integrate them into CI | traceability-check.md |

## Consistency check format

```markdown
## Consistency Report: system-landscape

Generated: 2025-06-05

### ✅ Matched nodes (high confidence, sourceRefs verified)
- `service.order-api` → `services/order/src/routes.ts` (exists, last modified 2025-05-20)
- `database.orders-db` → `infra/postgres.tf` (exists, confirmed)

### ⚠ Low-confidence nodes (needs verification)
- `service.payment-worker` → `services/payment/worker.ts` (sourceRef exists but file not found in current branch)

### ❌ Untraced nodes (no sourceRefs, current-state)
- `external.legacy-tax-api` — no sourceRefs, no code evidence found

### ❌ Stale nodes (sourceRef file deleted)
- `service.notification-v1` → `services/notification-v1/` (directory removed in PR #318)

### ❌ Missing nodes (found in code, not in model)
- `services/fulfillment/` — deployment YAML exists but no model node
```

## Traceability matrix format

```markdown
## Traceability Matrix: order-service

| Node ID | Label | Type | Primary Source | Test Ref | Doc Ref | Confidence |
|---------|-------|------|----------------|----------|---------|------------|
| service.order-api | Order API | service | services/order/routes.ts | tests/order.test.ts | docs/order-api.md | high |
| database.orders-db | Orders DB | database | infra/postgres.tf | tests/db.test.ts | — | high |
| external.payment-gw | Payment Gateway | external-system | services/order/paymentClient.ts | — | docs/payments.md | medium |
| queue.order-events | Order Events (Kafka) | queue | services/order/events.ts | — | — | low |
```

## Reverse index (JSON snippet)

```json
{
  "services/order/routes.ts": ["service.order-api"],
  "services/order/paymentClient.ts": ["service.order-api", "edge.order-to-payment"],
  "infra/postgres.tf": ["database.orders-db"],
  "services/order/events.ts": ["queue.order-events", "edge.order-publishes-events"]
}
```

## CI check rules

```markdown
## Traceability Check: Fail Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Current-state node has no sourceRefs | ⚠ Warn | Add sourceRefs or mark as `state: unknown` |
| sourceRefs file not found in repo | ❌ Fail | Update or remove node |
| Node confidence is `unknown` in current-state diagram | ⚠ Warn | Verify or reclassify |
| Edge references a deleted node | ❌ Fail | Update model to remove stale edge |
| New service in k8s YAML with no model node | ⚠ Warn | Add node or mark as out-of-scope |
```

## Quality rules

- Consistency check must distinguish current-state, target-state, and proposed nodes.
- A missing sourceRef for a target-state node is acceptable; for a current-state node it is a finding.
- Reverse index should be rebuilt on every model update, not maintained by hand.
- "File exists" is necessary but not sufficient — verify the file still exports the expected symbol or resource.
