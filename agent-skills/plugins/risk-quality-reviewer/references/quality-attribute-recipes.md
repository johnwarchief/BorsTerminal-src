# Quality Attribute Visualizer — Examples

Use this reference when generating quality attribute scenarios, radar charts, or Fitness Function specs.

## Architect use cases

| Question | Prefer this format | Evidence to require |
| --- | --- | --- |
| Which quality attributes currently pass, and where are the gaps? | Quality-attribute radar (Mermaid radar or Markdown matrix) | SLO docs, monitoring metrics, and incident reviews |
| What is the performance target, and how is it verified? | Quality scenario card (Markdown) | Load-test reports, SLA contracts, and P99 metrics |
| Are there architecture constraints that can be verified automatically? | Fitness-function checklist | ArchUnit, custom CI scripts, and alerting rules |
| How should performance, cost, and consistency be traded off? | Quality-attribute conflict matrix (Markdown) | Business goals and team constraints |

## Quality scenario card format

```markdown
### QA-001: API Response Time (Performance)

| Field | Value |
|-------|-------|
| Source | External customer |
| Stimulus | 1000 concurrent checkout requests |
| Environment | Production, peak traffic |
| Artifact | Order Service API |
| Response | Returns HTTP 200 with order ID |
| Measure | P99 < 500ms, error rate < 0.1% |
| Current status | P99 = 820ms at peak — ❌ FAILING |
| Evidence | Grafana dashboard 2024-11 load test |
| Action | Add caching layer on inventory check |
```

## Quality radar (Markdown matrix)

| Quality Attribute | Target | Current | Gap | Evidence |
|-------------------|--------|---------|-----|----------|
| Availability | 99.9% | 99.7% | ❌ | Incident log Q4 |
| Response Time P99 | < 500ms | 820ms | ❌ | Load test report |
| Error Rate | < 0.1% | 0.08% | ✅ | APM metrics |
| Deployability | < 10min deploy | 25min | ❌ | CI pipeline logs |
| Test Coverage | > 80% | 63% | ❌ | Coverage report |
| Security (CVEs) | 0 critical | 2 critical | ❌ | npm audit |

## Fitness Function examples

```markdown
## Fitness Functions — Order Service

### FF-001: No direct DB access from UI layer
- Tool: ArchUnit (Java) / eslint-plugin-import (TS)
- Rule: `ui.*` must not import from `infra.*`
- CI: fail build on violation

### FF-002: P99 < 500ms in load test
- Tool: k6 script in CI
- Rule: `p(99) < 500` in k6 threshold
- CI: fail merge if threshold exceeded

### FF-003: No critical CVEs in production dependencies
- Tool: `npm audit --audit-level=critical`
- CI: fail on any critical severity

### FF-004: Service-to-service calls must go through API Gateway
- Tool: network policy + integration test
- Rule: direct pod-to-pod calls outside cluster mesh rejected
- CI: connectivity smoke test
```

## Quality rules

- Replace "high availability", "high performance" with measurable scenarios (stimulus → measure).
- Show quality attribute conflicts explicitly: consistency vs availability, performance vs cost.
- Every Fitness Function must have a tool, a rule, and a CI integration point.
- Current status must come from evidence (monitoring, tests, audits), not estimation.
