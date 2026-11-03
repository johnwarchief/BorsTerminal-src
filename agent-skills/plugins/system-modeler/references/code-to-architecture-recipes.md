# Code to Architecture Modeler — Examples

Use this reference when reverse-engineering architecture models from code, configuration, or manifests.

## Architect use cases

| Input artifact | What to extract | Output view |
| --- | --- | --- |
| `package.json` / `go.mod` / `pom.xml` | Direct dependencies, versions, and external libraries | Dependency map |
| Kubernetes YAML / Helm charts | Services, ports, environment variables, and ingress | Deployment topology + C4 Container |
| Dockerfile / docker-compose.yml | Service boundaries, networks, and volumes | Deployment topology |
| TypeScript / Java import statements | Module dependencies and hierarchy | Dependency map + C4 Component |
| OpenAPI / AsyncAPI / Protobuf | Interface boundaries and data contracts | C4 Container + interface map |
| Database migrations / ORM mapping | Data model and ownership | Data-flow map |

## Evidence confidence rules

| Evidence source | Confidence |
| --- | --- |
| Import / require statements in code | high |
| k8s Service + Deployment YAML | high |
| OpenAPI spec (deployed) | high |
| docker-compose ports + depends_on | medium |
| Dependency described in README | low |
| Inference from file/directory naming | low |
| No code evidence, interview only | human-assumption |

## Extraction workflow

```markdown
## Reverse Modeling: Order Service

### Step 1: Collect artifacts
- [ ] `services/order/package.json` — dependencies
- [ ] `k8s/order-deployment.yaml` — deployment config
- [ ] `services/order/src/` — import graph
- [ ] `docs/api/order-openapi.yaml` — interfaces

### Step 2: Extract nodes
- service.order-api (type: service, high confidence, k8s + code)
- database.orders-db (type: database, high confidence, k8s PVC + migration)
- external.payment-gateway (type: external-system, medium, env var + client code)

### Step 3: Extract edges
- order-api → orders-db: writes (SQL, high, src/repository.ts)
- order-api → payment-gateway: calls (HTTPS, medium, src/paymentClient.ts)

### Step 4: Flag unknowns
- Does order-api consume events from inventory? (Low confidence, only README mention)
- Who calls order-api? (Unknown — need API gateway logs)
```

## Minimal extracted model.json

```json
{
  "name": "Order Service — Reverse Model",
  "nodes": [
    { "id": "order-api", "type": "service", "label": "Order API", "confidence": "high", "sourceRefs": ["k8s/order-deployment.yaml", "services/order/src/routes.ts"] },
    { "id": "orders-db", "type": "database", "label": "Orders DB", "confidence": "high", "sourceRefs": ["infra/postgres.tf", "services/order/migrations/"] },
    { "id": "payment-gw", "type": "external-system", "label": "Payment Gateway", "confidence": "medium", "sourceRefs": ["services/order/src/paymentClient.ts"] },
    { "id": "inventory-events", "type": "queue", "label": "Inventory Events (assumed)", "state": "unknown", "confidence": "low", "sourceRefs": ["docs/README.md#events"] }
  ],
  "edges": [
    { "from": "order-api", "to": "orders-db", "type": "writes", "protocol": "SQL", "confidence": "high", "sourceRefs": ["services/order/src/repository.ts"] },
    { "from": "order-api", "to": "payment-gw", "type": "calls", "protocol": "HTTPS", "confidence": "medium", "sourceRefs": ["services/order/src/paymentClient.ts"] },
    { "from": "inventory-events", "to": "order-api", "type": "subscribes", "protocol": "Kafka", "confidence": "low", "sourceRefs": ["docs/README.md#events"] }
  ]
}
```

## Quality rules

- Start with high-confidence sources (code, IaC, OpenAPI); layer in lower-confidence sources.
- Every inferred edge must carry `confidence: low` and a `sourceRefs` pointing to the inferred source.
- Unknown nodes are better than missing nodes — flag them as `state: unknown`.
- Don't promote a README-described dependency to `confidence: high` without code evidence.
