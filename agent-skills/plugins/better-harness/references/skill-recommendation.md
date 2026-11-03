# Skill Recommendation

Audience: lead only (Step 2.4), after Asset Demand Reconciliation retains a qualified lead.

The lead uses this routed reference only after [Asset Demand Reconciliation](asset-demand-reconciliation.md)
retains a repeated capability-comparison or workflow-ownership lead. It is a
routed reference, not an independently discoverable Skill or delegated Agent.

Finish both passes before returning; do not collapse owner comparison into
Session-only inference or recommend from Pass 1 alone.

Treat workflow shape, capability fit, and durable ownership as semantic
judgments. Names, paths, regexes, counts, repeated phrases, and catalog labels
may route inspection but never decide the answer.

## Pass 1: Infer the Workflow Without Inventory

Use only sanitized Task Episodes, opaque evidence references, provenance, and
bounded observations of requests, actions, checks, recovery, and outcomes. Do
not inspect Skill inventories, owner content, provider catalogs, expected
actions, or the lead's preferred answer.

Compare Episodes by:

- underlying goal, context, target, and stable input shape;
- ordered core stages and meaningful branches;
- output and acceptance boundary;
- validation, stopping, recovery, and failure conditions.

Retain a capability demand when at least two independent, comparable production
runs share the goal, input shape, output, or acceptance boundary. Separately
retain a reusable workflow only when they also share an ordered core and an
output plus validation or stop boundary. A read-only workflow is eligible when
those boundaries are observable; repository changes are not required.
Retries, forks, copied requests, provider replicas, same-Episode turns, generic
verbs, and tool overlap do not establish recurrence. Keep incompatible runs
separate and state when no defensible pattern exists.

Freeze this interpretation before seeing capability evidence. Later inventory
must not rename, merge, expand, or otherwise reshape it.

## Pass 2: Compare Capabilities and Owners

Inspect only plausible owners in the authorized scope. Compare the frozen
workflow with actual instructions, current runtime availability, task-linked
use evidence, project owner excerpts, and declared omissions. Distinguish:

- complete ownership of the trigger, procedure, output, validation, and stop;
- partial ownership with a concrete missing behavior;
- adjacent help that does not own the workflow;
- irrelevant or insufficiently inspected capability.

Choose the smallest durable owner in this order: keep observed coverage, try an
available platform capability, try a configured Skill, adopt a matching
official provider Skill bundle, extend a partial Skill, create a Skill, route
to a non-Skill owner, or request more evidence. Use
[Skill Discovery](../../../references/agent-customize/skill-discovery.md) and
[Loop Discovery](../../../references/loop-engineering/loop-discovery.md) to
resolve that boundary.

For a reuse lead, recommend one bounded trial only when the actual Skill
instructions match the frozen demand, current runtime discovery shows it is
available, and complete-enough task-linked evidence shows no effective relevant
use in the comparable Episodes. Define the trigger, expected output, verifier,
and stop condition for the trial. Global Skill-use volume alone never proves
underuse or relevance.

A Skill owns reusable procedural judgment. Deterministic transforms remain
scripts; runtime, persistence, credentials, approvals, scheduling, hooks,
policy, CI, and external access retain their existing owner families. A name,
configured presence, empty scan, or lexical match does not prove coverage.
Uninspected content and unresolved runtime gates remain unknown.

Recommend creation or extension only when recurring demand, workflow shape,
actual capability content, and the missing behavior are all supported. A single
run, benchmark-only recurrence, direct creation request, or absent catalog row
does not manufacture that evidence. When a matching official provider Skill
bundle already owns the workflow, recommend adopting it rather than duplicating
it as a new project Skill. Do not create, install, edit, or invoke an
asset during this analysis.

## Qoder Capability Overlay

Inspect relevant host-provided Qoder capability metadata only in Pass 2.
Use current runtime discovery; if metadata or instructions are unavailable,
report the coverage as unknown instead of relying on a bundled catalog. Keep IDE, CLI, SDK, main-agent, and subagent surfaces
separate. Catalog metadata improves recall; current discovery, mode, bounded
instructions, and task-linked evidence govern availability and coverage. Never
apply Qoder rows to another provider or infer a gap from partial catalog data.

## Return

Return a compact advisory brief in the user's language. Explain the frozen
workflow, supporting and rejected recurrence, inspected owners, omissions,
recommended smallest owner, rationale, uncertainty, and one verification step.
State whether the smallest route is keep existing coverage, extend a Skill,
create a Skill, use a non-Skill owner, or gather more evidence. Do not leave the
owner route implicit.
Use natural language rather than a fixed schema. Cite only supplied opaque
references and expose no raw prompts, local paths, Session ids, or secrets.

For a qualified reuse route, carry the matched Skill, observed task-linked use
state, present consequence, and bounded trial into Step 3 so the lead can emit
one ordinary `Low` finding for the frozen demand. Do not write a separate
recommendation artifact or raise severity from counts. The lead independently
decides findings, scores, ownership, and action.
