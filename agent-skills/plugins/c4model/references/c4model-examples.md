# C4 Model Examples

Use this reference when a C4/Structurizr task needs examples, view selection, or a concrete model shape.

## Official anchors

- C4 system context diagrams start from the big picture: one software system in scope, its users, and directly connected external systems. See https://c4model.com/diagrams/system-context.
- C4 container diagrams zoom into one software system and show applications/data stores, major technology choices, and inter-container communication. See https://c4model.com/diagrams/container.
- C4 component diagrams zoom into one container and are optional; create them only when they add value and component ownership/evidence is clear. See https://c4model.com/diagrams/component.
- Structurizr is model-based and can keep names, descriptions, relationships, styles, and views consistent across diagrams. It also enforces C4 hierarchy rules. See https://docs.structurizr.com/ai.
- Structurizr workspaces wrap a model plus views; `include *` is the default way to pull related elements into system context/container/component views. See https://docs.structurizr.com/dsl/tutorial.

## DSL Token Grammar

**CRITICAL — each element keyword accepts a fixed maximum number of positional string tokens.**
Exceeding the limit causes a `Too many tokens` parse error.

| Keyword | Positional params | Grammar |
| --- | --- | --- |
| `person` | up to 3 | `person <name> [description] [tags]` |
| `softwareSystem` | up to 3 | `softwareSystem <name> [description] [tags]` |
| `container` | up to 4 | `container <name> [description] [technology] [tags]` |
| `component` | up to 4 | `component <name> [description] [technology] [tags]` |
| `->` relationship | up to 4 | `<from> -> <to> [description] [technology] [tags]` |

**Tags** can be supplied as the last positional string **or** as a `tags "…"` statement inside a `{}` block. Do not supply both; choose one form per element.

```dsl
# Correct — tags as last positional param
customer = person "Customer" "End user." "External"

# Correct — tags as block statement
customer = person "Customer" "End user." {
    tags "External"
}

# WRONG — empty-string placeholder fills the slot, pushing tags to a 4th token
customer = person "Customer" "End user." "" "External"
#                                         ^^  this extra "" causes "Too many tokens"
```

## DSL Structure Rules

The workspace must follow this exact nesting order. Violations cause parse errors.

```
workspace "Name" "Description" {
    model {
        # 1. Declare all elements here
        # 2. Declare all relationships here (inside model, not outside)
    }

    views {
        # 3. Declare all views here (inside workspace, not outside)
        styles { … }
    }
}
```

**Common structural mistakes:**

| Mistake | Symptom |
| --- | --- |
| Putting relationships outside `model {}` | Parse error or relationships not resolved |
| Putting `views {}` outside `workspace {}` | Views block ignored or parse error |
| Using `component` view key without `!identifiers hierarchical` | Component path not resolvable |
| `component` view references a container path with wrong identifier | `Unknown element` error |

With `!identifiers hierarchical`, reference nested elements by full path:

```dsl
# system.container.component
cosy.server.chatService -> cosy.server.agentSystem "Routes"
```

## Example Policy

Examples in this plugin should use standard Structurizr DSL syntax, as shown in the Structurizr docs and playground.

Structurizr-compatible tooling remains useful for preview rendering, but standard Structurizr DSL is the preferred example format. Do not use `.structurizr.js` as the primary example format when teaching users C4 modeling.

## Architect use cases

| Architect question | Prefer this C4 view | Evidence to require |
| --- | --- | --- |
| What is this system, who uses it, and what external systems does it touch? | System Context | product docs, API clients, auth/users, integrations |
| What are the deployable/runtime parts and data stores inside one system? | Container | service manifests, package roots, deployment config, databases, queues |
| Which internal components in one container carry the key responsibility split? | Component | code modules/classes/controllers/repositories with a parent container |
| How does a platform portfolio fit together across teams? | System Landscape | service catalog, ownership map, inter-system APIs/events |
| What changed between current and target architecture? | C4 current/target variants plus summary notes | current evidence, target proposal, explicit assumptions |

## Full Example

Use `examples/c4/big-bank-internet-banking/` as the mature C4 example for this plugin. It uses standard Structurizr DSL syntax and mirrors the Big Bank example shape from `../structurizr4js/examples/big-bank-internet-banking.structurizr.dsl`.
It covers:

- System Landscape.
- System Context.
- Container view.
- Component view for the API Application.
- Evidence metadata on every node and edge.

The standard Structurizr DSL source is:

```text
examples/c4/big-bank-internet-banking/big-bank-internet-banking.dsl
```

## Standard Structurizr DSL Shape

User-facing examples should use standard Structurizr DSL. Note: all relationships are **inside** the `model {}` block and `views {}` is **inside** `workspace {}`.

```dsl
workspace "Internet Banking" "Evidence-backed C4 model." {
    !identifiers hierarchical

    model {
        # Elements
        customer = person "Personal Banking Customer" "Uses online banking."
        banking = softwareSystem "Internet Banking System" "Allows customers to view balances and make payments." {
            web = container "Web Application" "Browser-facing app." "React"
            api = container "API Application" "Handles account/payment APIs." "Node.js" {
                authController = component "Auth Controller" "Handles login and token refresh." "Express Router"
                accountService = component "Account Service" "Business logic for accounts." "Node.js"
                paymentService = component "Payment Service" "Processes payment transactions." "Node.js"
                ledgerRepo = component "Ledger Repository" "Data access for ledger records." "Node.js"
            }
            ledger = container "Ledger Database" "Stores ledger records." "PostgreSQL" {
                tags "Database"
            }
        }
        email = softwareSystem "Email System" "Sends notifications." {
            tags "External"
        }

        # Relationships (inside model, not outside)
        customer -> banking "Uses"
        banking -> email "Sends email via" "SMTP"

        # Container-level: system.container -> system.container
        banking.web -> banking.api "Calls account/payment APIs" "JSON/HTTPS"
        banking.api -> banking.ledger "Reads and writes ledger records" "SQL"

        # Component-level: system.container.component -> system.container.component
        # CRITICAL: With !identifiers hierarchical, ALL relationship references must
        # use the full dot-path starting from the top-level model variable.
        #   CORRECT: banking.api.authController -> banking.api.accountService
        #   WRONG:   api.authController -> api.accountService  (fails: "source element does not exist")
        banking.web -> banking.api.authController "Authenticates users" "JSON/HTTPS"
        banking.api.authController -> banking.api.accountService "Delegates account lookups"
        banking.api.accountService -> banking.api.ledgerRepo "Reads account data"
        banking.api.paymentService -> banking.api.ledgerRepo "Writes payment records"
        banking.api.ledgerRepo -> banking.ledger "Reads/writes via SQL" "JDBC"
    }

    views {
        systemContext banking "SystemContext" "The system and its users." {
            include *
            autoLayout lr
        }

        container banking "Containers" "The major runtime containers." {
            include *
            autoLayout lr
        }

        # Component view key must also use full path: system.container
        component banking.api "ApiComponents" "Components inside the API Application." {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }
            element "Database" {
                shape cylinder
            }
            element "External" {
                background #999999
                color #ffffff
            }
        }
    }
}
```

## Component view rule

Only create a component view when:

- the user asks for internals of one container, or code evidence clearly identifies stable internal responsibilities;
- every component has a parent container;
- the component view is smaller and more useful than a dense dependency graph;
- the summary says whether components are current-state evidence, target design, or inferred.

With `!identifiers hierarchical`, the component view key must use the full dotted path to the container:

```dsl
component banking.api "ApiComponents" "…" { include * }
# NOT: component api "ApiComponents" "…" { include * }
```

If these conditions are not met, generate a container view plus a Graphviz dependency map instead.

## Hierarchical Identifier Pitfalls

When using `!identifiers hierarchical`, ALL element references in relationships and views must use the **full dot-path from the top-level model variable**. This is the most common source of "does not exist" errors.

| Nesting level | Reference pattern | Example |
| --- | --- | --- |
| Person/System (top-level) | `variableName` | `customer -> banking` |
| Container (2 levels) | `system.container` | `banking.web -> banking.api` |
| Component (3 levels) | `system.container.component` | `banking.api.authController -> banking.api.accountService` |

**Common mistakes:**

```dsl
# WRONG — omits the system prefix, Structurizr cannot resolve "webApp.loginPage"
webApp.loginPage -> webApp.uiPrimitives "Uses"

# CORRECT — full path from model root variable
mallFe.webApp.loginPage -> mallFe.webApp.uiPrimitives "Uses"
```

```dsl
# WRONG — omits the system prefix for container reference inside a component relationship
api.authController -> api.accountService "Calls"

# CORRECT
banking.api.authController -> banking.api.accountService "Calls"
```

The rule applies uniformly to:
- Relationship source and destination (`from -> to`)
- Component view container references (`component banking.api`)
- Cross-container component relationships (`banking.web -> banking.api.authController`)

## Useful Delivery

Write `artifacts/internet-banking.structurizr.dsl` as the canonical source and
pair it with `artifacts/internet-banking.architecture-understanding.md`.
Open the DSL file with Qoder's Structurizr DSL viewer when the user needs a
visual preview. For documentation and examples, prefer `.dsl` over derived
exports.
