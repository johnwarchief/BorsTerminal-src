# System Landscape Visualizer — Examples

Use this reference when generating system landscape views.

## Architect use cases

| Question | Prefer this view | Evidence to require |
| --- | --- | --- |
| Which systems exist? Who owns them? Where are the boundaries? | System Landscape (L1) | Service catalog, CODEOWNERS, and team topology |
| Who does this system communicate with? Who are the users? | System Context (L1) | API clients, auth/user docs, and integration docs |
| How do systems inside the platform collaborate? | System Landscape + trust boundaries | Event bus, API gateway, and deployment inventory |

## Artifact Delivery

Write `artifacts/ecommerce-landscape.structurizr.dsl` as the C4 source and
`artifacts/ecommerce-landscape.architecture-understanding.md` as the reading
guide. Open the DSL with Qoder's Structurizr DSL viewer when a preview is
needed.

## Quality rules

- Show team ownership on every system node when CODEOWNERS or team topology is available.
- External systems go on the boundary; label them clearly as external.
- Keep the landscape to one zoom level; don't show containers in the landscape view.
- If two teams both claim ownership of the same system, flag it as a governance gap rather than picking arbitrarily.
