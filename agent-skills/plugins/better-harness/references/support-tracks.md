# Support Tracks

Audience: lead only (Step 3), after findings and scores freeze.

Read only the section selected by the calling workflow; co-location does not
combine their entry conditions or authorize another mode.

- [Operationalize](#operationalize)
- [Optimize](#optimize)

## Operationalize

Audience: lead only (Step 3), as the single selected support track.

Use this track only after the lead freezes findings and dimension scores. The
1 -> 60 label describes a user journey, not a score band. This is the
normal route when useful mechanisms exist but supported evidence shows they are
not yet wired into ordinary work or exercised through an observable result.

### Operationalize: Select This Track

Select Operationalize when at least one relevant project or agent mechanism is
present and retained findings establish a `Present -> Wired -> Exercised` gap.
Examples include a documented check with no task route, a runnable command with
no acceptance boundary, or a configured asset with no observed invocation.

Do not select it from counts, a middling score, or missing Session coverage. Use
[Project Harness Evidence](project-harness.md),
[Agent Customize Evidence](agent-customize.md), and
[Findings Quality Gates](findings-review.md) as the canonical owners; do not
duplicate their evidence or eligibility rules here.

### Operationalize: Shape the Recommendation

Prioritize the smallest supported move that advances one real mechanism by one
observable state:

1. connect a present owner to the task entrypoint where an agent needs it;
2. expose the exact command, trigger, or decision boundary;
3. add the cheapest representative verifier and expected result; and
4. name failure, reset, recovery, or escalation behavior when the action has a
   meaningful side effect.

Choose the durable owner from the target rather than naming a fashionable tool.
Use the
[Project Capability Artifact Examples](#project-capability-artifact-examples)
to calibrate `Document`, `Rule`, `Skill`, `Hook`, `Script`, `Test`, `Config`,
`MCP`, or `Code` outputs. Treat these as labels, not evidence that an artifact
is needed.

Each priority move must remain attached to a retained finding and state the
observable end state, smallest owner, verifier, and recovery or approval
boundary. Prefer extending an existing route over introducing a parallel owner.

### Operationalize: Preserve Boundaries

Do not create a new finding, change severity, or rescore a dimension because a
track was selected. Do not claim a mechanism is exercised from presence or
configuration alone. Finding-bound mutation and independent reassessment remain
owned by [Finding-bound Fix](../improvement/finding-bound-fix.md).

## Optimize

Audience: lead only (Step 3), as the single selected support track.

Use this track only after the lead freezes findings and dimension scores. The
60 -> 100 label describes a user journey, not a score band. This track uses
Session outcomes to improve an already operating Harness; it is not a reward
for a high score.

### Optimize: Select This Track

Select Optimize only when the authorized Session evidence is sufficiently
complete for the decision and at least two distinct comparable Task Episodes
support the repeated goal or friction being optimized. A repeated workflow also
requires repeated ordered stages plus a verification or stopping boundary.

Read [Session Evidence](session-evidence.md) and, for workflow candidates,
[Repeated Workflow Discovery](session-repeated-workflows.md). If comparable
Episodes, linked traces, or outcome evidence are unavailable, select
Operationalize or keep the track undetermined instead of extrapolating from a
high score, request count, repeated turn, or one successful session.

### Optimize: Shape the Recommendation

For every supported optimization candidate:

1. state the repeated goal, stable input shape, observed friction, and affected
   outcome without exposing prompts, Session ids, or private paths;
2. distinguish a goal-level lead from a repeated procedure;
3. compare an observed capability, host built-in, configured owner, extension,
   and new owner in that order; and
4. define a later comparable outcome that could confirm or reject the change.

Join repeated demand with existing coverage through
[Asset Demand Reconciliation](asset-demand-reconciliation.md). Route a stable
uncovered procedure through
[Loop Discovery](../../../references/loop-engineering/loop-discovery.md) before
recommending a new Skill, Agent, Hook, automation, or Memory owner.

For a Frontend Bug Reproduction Skill or Backend Bug Diagnosis Skill candidate,
use the [bug-diagnosis procedure shapes](../../../references/agent-customize/skill-discovery.md#bug-diagnosis-skill-examples)
to compare inspected project and session evidence. Examples do not establish
installed coverage. When an inspected owner already covers the repeated demand,
prefer discover, select, invoke, exercise, or narrowly extend it over creating a
duplicate asset.

### Optimize: Preserve Boundaries

Do not promote correlation, retries, copied history, or user corrections into a
stable workflow. Do not claim Loop Effectiveness from the current intervention;
require a later comparable Task Episode with an improved observable outcome.
Optimization guidance cannot expand Session, Memory, user-home, provider, or
mutation authority.

## Project Capability Artifact Examples

Use this catalog when a finding needs one concrete `expectedArtifact` label.
Name what the user receives after the repair, not the tool used to create it.
Keep installation choices, prerequisites, alternatives, and validation detail in
`aiFixPrompt`.

| `expectedArtifact` | What the user receives | Typical examples |
|---|---|---|
| `Document` | A navigable project or architecture reference | component catalog, ownership map, architecture boundary guide |
| `Rule` | Agent-consumed project instructions | scoped `AGENTS.md` route, risk or validation guidance |
| `Skill` | A reusable multi-step workflow | environment doctor, affected validation, local MR review |
| `Hook` | A lifecycle trigger around an existing deterministic action | post-edit focused checks, Stop or pre-push guard |
| `Script` | A deterministic executable helper | cross-platform setup, doctor, reset, or focused-check script |
| `Test` | Executable proof of a behavior or constraint | smoke test, architecture test, schema compatibility check |
| `Config` | A reproducible tool, environment, pipeline, or approval configuration | mise, Dev Container, CI job, tool allowlist, merge approval settings |
| `MCP` | A configured remote-context integration | GitLab project and merge-request connection |
| `Code` | A focused runtime or product implementation | missing behavior that is not better owned by a surface above |

`Reference` maps to `Document`: reference describes the role of the material,
while the concrete artifact delivered to the user is a document. `CLI`,
`Command`, and named tools such as `glab`, Nx, or Trivy are normally detected
tools or prerequisites, not expected artifacts by themselves.
`CI Gate` and `Permission` are outcomes or control boundaries, not artifact
types. Name their concrete carrier instead: usually `Config`, `Test`, `Hook`, or
`Rule`.

### Five-stage examples

| Software Fluency stage | Likely artifact examples |
|---|---|
| Context Map | `Document`, `Rule`, `MCP` |
| Environment Readiness | `Skill`, `Script`, `Config` |
| Fast Feedback | `Skill`, `Hook`, `Script`, `Test` |
| Quality Gates | `Hook`, `Rule`, `Test`, `Config` |
| Change Safety | `MCP`, `Skill`, `Hook`, `Config`, `Rule` |

Prefer the smallest durable owner. For example, a Hook should call an existing
deterministic command; it should not reimplement test selection. A one-time CLI
access gap should not become a Skill until the workflow is repeated and stable.
