# Findings Quality Gates

Audience: lead only (Step 3-4). Use this checklist while drafting `findings.json`.
Do not launch another Agent or
reconciliation pass, edit the target, or repair a finding.

## Inputs and Boundary

Use the scope, authority, Step 1 baseline, three briefs, analyzer JSON envelope,
draft `findings.json`, and adjacent `canvas.json` only if the provider produced
one. Open only candidate-named target files or command declarations when
necessary. Do not reopen raw
Sessions, Memory bodies, private caches, or project history, and do not
rerun asset scanners.

Briefs are candidates, not truth. The analyzer owns machine facts; the
lead owns selection, severity, scores, promotion, and prose.

## Review Gates

Any failed gate blocks rendering.
Inspect every reader-visible JSON string; no-copy instructions do not sanitize
embedded data.

1. **Evidence eligibility:** Retain only an observed consequence, explicit
   requirement, Project-proven wiring gap, deterministic present defect, or
   bounded Skill reuse.
   Counts, search absence, similarity, unavailable evidence, detector `none`, and
   future-only risk remain leads. A benign current value or absent governance
   asset is not a present defect. Resolve aliases to one canonical asset and
   discard examples; a linter classification is candidate evidence, not a
   governing requirement. Unreviewed Session or Learning Capture gaps stay in
   the boundary. Reuse requires two comparable production Episodes with a present
   consequence, complete-enough task-linked evidence showing no effective
   relevant use, and inspected available Skill instructions matching the trial.
2. **Concrete reader value:** Apply five title gates:
   - **Standalone:** Make the problem clear without reading `reason`.
   - **Consequence-first:** State what becomes hard, unsafe, uncertain, or
     possible; do not lead with a missing mechanism.
   - **Reader language:** Do not make a dimension, review, coverage, detector, or
     evidence state the subject.
   - **Evidence-bounded:** Make no claim stronger than the retained evidence;
     title the present consequence, not a more severe future scenario.
   - **Defer unsupported:** Defer a candidate with no supported reader
     consequence; never invent or merely polish one.
   Keep fact/inference/owner/provider/uncertainty in `reason`; numbers do not
   imply severity.
   Provider-only evidence stays provider-labelled; cross-provider synthesis
   cannot turn one provider's absence into a project defect.
3. **Fact consistency:** Repeated counts come from the same canonical envelope.
   Different populations name their scope and measurement basis. The overview,
   dimensions, findings, and coverage rows do not contradict one another.
   Reject inventory-count, zero, or inferred-absence causes. If inspection
   proves no owner, the repair cannot claim one exists.
4. **Asset accountability:** Every authorized nonzero Rules, Skills, MCP,
   Memory, Agent, Hook, Command, Workflow, and Plugin surface appears in
   coverage. `inspectedSurfaces` contains only content actually opened. Exact
   integrity candidates are accounted for; similarity leads are not promoted.
   Inventory never proves selection, use, usefulness, or outcome.
   When Memory volume is high, require a bounded disposition for exact
   collisions, near matches, conflict/staleness, and unknown coverage: confirmed,
   metadata lead, unobserved, or deferred. Do not demand Memory-body proof outside
   authority; a count alone is not a disposition. An exact same-scope title
   collision is an ordinary `Low` governance finding unless corroborated current
   impact justifies a higher severity; near matches remain deferred. Trace every
   stable repeated Session procedure through content-backed existing coverage,
   regardless of Skill count. Two distinct comparable Episodes plus a verified
   uncovered owner chain require a Low finding; unknown or uninspected coverage
   remains deferred. A verified existing-Skill reuse route requires one `Low`
   finding per demand; report an unexercised route, not a missing Skill or failed task.
5. **Privacy:** Output contains no secret, prompt, stable Session id,
   absolute home path, or Memory title/path. Render authorized non-Memory home
   paths as `~/...`; source rows stay project-relative. Long-session rows keep
   only anonymous alias, role, duration, and failure aggregates; review
   regenerates the private packet without locators.
6. **Executable repair:** Every command, tool, owner, and capability in an
   `aiFixPrompt` was discovered in the target or provider contract. External
   writes are explicit authorization preconditions. Credential repair includes
   revocation or rotation; never assume reference syntax, profiles, restarts, or
   provider actions before discovery and authority. Memory collision repair stays
   metadata-only until scope and bodies are verified; merge or deletion requires
   separate authority. Qoder Memory uses the discovered `SearchMemory` ->
   `update_memory` route; project Wiki or Knowledge Cards use a discovered
   `/knowledge` handoff. Never edit generated Memory directly. For exact
   collisions plus many near-title leads, review a bounded batch and report the
   remaining count.
7. **Score discipline:** Confirmed Memory or Skill integrity findings remain
   pending in Asset Health / Repair Progress until independent repair review.
   Counts, configuration, or same-window repair never earn Learning Capture or
   Loop Effectiveness credit. Memory credit requires retrieval, relevance,
   application, and a later improved outcome; Skill credit requires selection,
   task-relevant invocation, validation, and a later improved outcome. Enforce
   the Agent Work Loop Learning Capture ceilings: uncovered applicable demand
   stays at 59 or lower, current-task exercise without later comparison at 74
   or lower, and 100 requires a later comparable improved outcome. An adequately
   reviewed no-candidate window does not require either asset.
8. **Candidate promotion:** New reports do not write `summary.suggestions`.
   Eligible candidates become ordinary `Low` findings with a consequence, owner,
   expected output, verifier, `aiFixPrompt`, and dimension links. A verified try-
   existing Skill route qualifies only under gate 1 and stays `Low`; other
   opportunities without a present consequence remain deferred. Skill or Memory
   promotion still requires two comparable Episodes and the observed -> built-in
   -> configured -> extend -> create ladder. Never invent `/` or `$` syntax.

Retain every distinct supported finding. Five is a coverage floor, not a target.
Keep independent consequences or owners beyond five; only three priority moves
are ranked. Sparse evidence may yield fewer. Reject filler, duplicates, and
unsupported absence claims.

## Stop

Render only after every gate passes and each omission is an exact merge,
unsupported lead, or explicit defer.
