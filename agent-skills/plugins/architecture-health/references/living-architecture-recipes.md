# Living Architecture Updater — Examples

Use this reference when setting up CI-integrated architecture checks or automated model regeneration.

## Architect use cases

| Need | Approach | Output |
| --- | --- | --- |
| Automatically validate that diagrams match code on every PR | CI job runs `validate:all` | PR status check + diff report |
| Automatically update architecture snapshots on every merge | CI job refreshes DSL + diff | `architecture-diff.md` |
| Team wants to know which diagrams are stale | Scheduled consistency validator | `missing-and-stale-items.md` |
| Newcomers need the current system state | Render the latest snapshot from the main branch | Living architecture dashboard |

## CI pipeline example (GitHub Actions)

```yaml
# .github/workflows/architecture-check.yml
name: Architecture Check

on:
  pull_request:
    paths:
      - 'services/**'
      - 'infra/**'
      - 'k8s/**'
      - 'artifacts/*.structurizr.dsl'

jobs:
  validate-architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Validate architecture models
        run: npm run validate:all

      - name: Generate architecture diff
        run: |
          git fetch origin main
          mkdir -p /tmp/architecture
          git show origin/main:artifacts/system.structurizr.dsl > /tmp/architecture/before.structurizr.dsl
          git diff --no-index /tmp/architecture/before.structurizr.dsl artifacts/system.structurizr.dsl > architecture-diff.patch || true

      - name: Upload architecture diff
        uses: actions/upload-artifact@v4
        with:
          name: architecture-diff
          path: architecture-diff.patch
```

## Architecture diff format

```markdown
# Architecture Model Diff

Before: System Architecture (/tmp/architecture/before.structurizr.dsl)
After: System Architecture (artifacts/system.structurizr.dsl)

## Summary

| Item | Added | Removed | Changed |
| --- | ---: | ---: | ---: |
| Nodes | 1 | 0 | 1 |
| Edges | 1 | 1 | 0 |

## Nodes

### Added
- `service.payment-worker` — label=Payment Worker, type=service, confidence=high, state=current

### Changed
- `database.orders-db`
  - technology: `PostgreSQL 14` -> `PostgreSQL 16`

## Edges

### Added
- `order-payment-worker` — type=publishes, from=service.order-api, to=service.payment-worker, confidence=high

### Removed
- `order-payment-gateway` — type=calls, from=service.order-api, to=service.payment-gateway, confidence=medium
```

## CI failure conditions

```markdown
## Architecture Check Failure Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Structurizr DSL parse error | ❌ Fail | Fix DSL |
| Node without any sourceRefs (current-state) | ⚠ Warn | Add evidence or mark as target/unknown |
| Edge with `confidence: unknown` in current-state | ⚠ Warn | Validate or mark as proposed |
| Structurizr DSL parse error | ❌ Fail | Fix DSL source |
| Removed node still referenced by another edge | ❌ Fail | Update edges or restore node |
| Preview cannot render view | ⚠ Warn | Fix the source DSL/DOT/Mermaid artifact |
```

## Quality rules

- CI checks must have clear pass/fail conditions; don't fail on layout changes or cosmetic diffs.
- Semantic diff (node added/removed/changed) is meaningful; whitespace diff in JSON is not.
- Auto-generated updates must not overwrite human-maintained business semantics or descriptions.
- Schedule a monthly review of `unknown`-confidence nodes to prevent them accumulating silently.
- Keep the architecture snapshot in git; it's the only way to produce meaningful diffs over time.

## Qoder plugin skill smoke

Use this when validating that Qoder can discover this repository as a plugin and invoke the intended skill, not just read `SKILL.md` as ordinary files.

```bash
qodercli --cwd <plugin-root> --setting-sources project skills list
qodercli --cwd <plugin-root> --setting-sources project -p "/architecture:dependency-impact-analyzer <request>"
```

The smoke should intentionally call Qoder with the namespaced skill form when the plugin manager exposes namespaced skills:

```text
/architecture:dependency-impact-analyzer
```

Validation rules:

- Use the plugin root as `--cwd` so Qoder loads the local plugin under test.
- Use the fully namespaced skill name when namespaced plugin skills are enabled.
- Allow command execution only for trusted local smoke runs.
- For architecture-analysis tests, inspect generated analysis artifacts and require concrete sourceRefs, project-owned central nodes, module boundaries, risks, and unknowns.
- Keep live agent E2E checks out of ordinary CI unless credentials, cost limits, and trusted-repo boundaries are explicit.
