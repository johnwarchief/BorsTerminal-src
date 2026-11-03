# Target State Gap Visualizer — Examples

Use this reference when generating current-vs-target architecture comparisons or migration roadmaps.

## Architect use cases

| Question | Prefer this format | Evidence to require |
| --- | --- | --- |
| How large is the gap between current and target state? | Side-by-side comparison (Mermaid or two C4 views) | Current-state map with code evidence + target-state design docs |
| How many migration phases are needed, and what happens in each phase? | Migration roadmap (Mermaid gantt or Markdown table) | Business constraints, team capacity, and technical dependencies |
| Which component is hardest to migrate, and why? | Blocker map (Graphviz) | Dependency map and data-coupling analysis |
| What are the acceptance criteria for each phase? | Phase checkpoint table (Markdown) | Business metrics, technical metrics, and release gates |

## Current vs target comparison (Mermaid)

```mermaid
graph LR
  subgraph current ["Current State (Monolith)"]
    mono[Monolith\norders + billing + inventory]
    mono_db[(Shared PostgreSQL)]
    mono --> mono_db
  end

  subgraph target ["Target State (Services)"]
    order_svc[Order Service]
    billing_svc[Billing Service]
    inventory_svc[Inventory Service]
    order_db[(Orders DB)]
    billing_db[(Billing DB)]
    inventory_db[(Inventory DB)]
    order_svc --> order_db
    billing_svc --> billing_db
    inventory_svc --> inventory_db
  end
```

## Gap map example

```markdown
## Gap Map: Monolith → Microservices

| Gap Type | Description | Complexity | Blocker? |
|----------|-------------|------------|----------|
| Structural gap | Billing and order logic are in the same codebase with no clear boundary | High | Yes |
| Data gap | Shared orders table, written by both billing and order logic | High | Yes |
| Platform gap | No service discovery and no API Gateway | Medium | Yes |
| Team gap | No dedicated billing team and no on-call ownership | Low | No |
| Operations gap | No independent deployment pipeline | Medium | No |
```

## Migration roadmap (Mermaid gantt)

```mermaid
gantt
  title Monolith → Microservices Migration
  dateFormat  YYYY-MM
  section Phase 1: Boundaries
    Domain boundary analysis    :done,    2025-01, 2025-02
    Introduce API Gateway       :active,  2025-02, 2025-03
  section Phase 2: Extract Billing
    Billing service scaffold    :         2025-03, 2025-04
    Dual-write migration        :         2025-04, 2025-05
    Cut-over billing            :         2025-05, 2025-06
  section Phase 3: Extract Inventory
    Inventory service scaffold  :         2025-06, 2025-07
    Cut-over inventory          :         2025-07, 2025-08
  section Phase 4: Decommission
    Remove monolith             :         2025-09, 2025-10
```

## Quality rules

- Target-state nodes must be labeled as `state: proposed` or `state: target`; never present them as current facts.
- Every migration phase must have: deliverable, success metric, and rollback condition.
- Dual-write periods need explicit start and end dates — they're the highest-risk window.
- Data migration complexity (schema + volume + consistency) must be estimated separately from code complexity.
