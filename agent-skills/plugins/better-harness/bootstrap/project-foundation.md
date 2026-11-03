# Project Foundation Bootstrap

Audience: main Better Harness agent, immediately after an explicit direct initialization route.

Use this route to establish a small, project-specific Minimum Viable Harness.
Do not run the Better Harness report workflow: do not collect an evidence
bundle, launch review agents, create findings, assign scores, or render a
report.

Bootstrap proves only that a mechanism is Present or Wired:

```text
Bootstrap            -> Present / Wired
Representative task  -> Exercised
Later comparable task -> Outcome-supported
```

## Contents

- [Guided Interaction and Authority](#guided-interaction-and-authority)
- [Inspect the Project](#inspect-the-project)
- [Phase 1: Create the Project Entry Map](#phase-1-create-the-project-entry-map)
- [Phase 2: Connect Core Knowledge to Task Paths](#phase-2-connect-core-knowledge-to-task-paths)
- [Cover Spec and Delivery Routes](#cover-spec-and-delivery-routes)
- [Apply and Validate](#apply-and-validate)
- [Phase 3: Connect Agent Tools to Real Work](#phase-3-connect-agent-tools-to-real-work)
- [Phase 4 (Optional): Exercise One Real Task](#phase-4-optional-exercise-one-real-task)
- [Finish](#finish)

## Guided Interaction and Authority

Treat an explicit `/better-harness init`, `/better-harness bootstrap`, or
equivalent initialization request as task-local authority to create or update
only the repository guidance needed by this route. It does not authorize
dependency installation, external writes, SCM setting changes, credential
access, Hooks, MCP connections, CI activation, release work, or production
operations.

Default to a guided flow for a first-time user. Use `AskUserQuestion` when the
runtime exposes it; otherwise ask the same short question in normal chat. Use
one plain-language question with two or three concrete choices, explain any
unfamiliar term in one sentence, and do not ask for facts already resolved from
the project.

`AskUserQuestion` is Bootstrap workflow machinery. Never persist its name,
checkpoint choices, confirmation text, or novice explanation in `AGENTS.md`.
Complete the read-only project exploration before the first routine checkpoint;
questions resolve human preferences, evidence conflicts, or scope choices, not
package managers, commands, module roots, or documents that the repository can
answer.

Use these checkpoints:

1. **Foundation plan, before writing.** Show the detected purpose and project
   boundaries, proposed root or nested guidance files, verified commands and
   document routes, unknowns, validation plan, and excluded actions. Ask the
   user to choose `Review a compact draft` (recommended for a first Bootstrap),
   `Apply the smallest verified guide`, or `Adjust or stop`.
2. **Draft approval, only when requested.** Show the proposed headings plus the
   actual high-signal rules and commands, not a placeholder template. Ask the
   user to apply, revise, or stop.
3. **Result review, after validation.** Explain what changed and what remains
   unobserved. Ask the user to accept the receipt, request an adjustment, or
   review optional next Skills or one representative task. A choice starts no
   installation, external configuration, or new task in this route.

Use at most two routine `AskUserQuestion` calls plus the conditional draft
approval. Ask again only when a material ambiguity would change persisted
guidance or scope. Skip routine checkpoints only when the user explicitly asks
for non-interactive execution and every planned change is clear, additive, and
bounded. In a non-interactive runtime, continue only under that same condition;
otherwise stop with the unresolved question.

Inspect before writing. Preserve existing instruction content and unrelated
worktree changes. Stop before replacing an ambiguous instruction owner,
resolving contradictory project facts by guessing, or changing an externally
visible control.

## Inspect the Project

Explore the project before drafting `AGENTS.md`. Inspect only project-scoped
evidence needed to build the foundation:

- the user goal and explicit constraints;
- existing root and nested instruction files;
- manifests, lockfiles, tool-version files, and script definitions;
- README, CONTRIBUTING, architecture, design, test, operations, and ADR docs;
- repository topology, module boundaries, generated paths, and sensitive areas;
- CI definitions, PR or MR templates, CODEOWNERS, and review instructions; and
- Git remotes and repository-owned SCM files.

Record a source for every command, version, path, and boundary. Project facts
outrank framework conventions. When sources conflict, prefer the narrower
current owner only when its scope and authority are clear; otherwise stop and
name the conflict. Never infer architecture, ownership, or commands from a
directory or framework name alone.

## Phase 1: Create the Project Entry Map

Only after exploration and the foundation-plan checkpoint, create a short root
`AGENTS.md` when none exists. When one exists, make the smallest merge that
closes verified entry gaps; do not replace it with a generated template.

`AGENTS.md` is ordinary Markdown with no required headings. Treat it as a
concise operating guide for coding agents that complements the human README
and routes deeper knowledge. Do not start from a universal section template.
Draft only the sections supported by project evidence, putting exact commands
and critical risk boundaries before optional overview or repository context.

Before drafting, read [AGENTS.md Review](../../../references/agent-customize/agents-md-review.md)
and apply its quality gates:

- write only actual, copy-pasteable project commands; never put metavariables,
  angle-bracket tokens, ellipses, or pseudo-commands inside code formatting;
- state the working directory and supported operating system or shell for each
  non-portable command; for multiple platforms, give a neutral wrapper rule or
  concrete forms instead of promoting one observed invocation;
- keep a `must`, `never`, or `ask before` rule only when the user or a project
  owner establishes it; otherwise omit it and report the missing policy;
- copy an exact version or CI detail only when it changes an agent decision and
  its current owner is linked; otherwise route to the owner;
- turn a directory list into conditional edit or validation routing, not a
  repository tour; and
- do not turn one local observation or generated draft into project policy.

Reject and revise the candidate before writing when any command is incomplete,
platform-ambiguous, or unverified; any normative rule lacks a project source;
or any paragraph merely repeats README, manifest, architecture, or directory
facts without preventing a non-inferable agent mistake. Keep evidence
provenance in the Bootstrap working notes; do not add a `Source` column unless
it helps future agents. Prioritize:

- exact commands and completion evidence that matter;
- conditional routes to the main code, test, and document owners;
- repository-specific traps, generated surfaces, and public-API boundaries;
- approval boundaries for credentials, migrations, releases, production, and
  irreversible changes.

Use these pattern sources for structure, never for project facts:

- the [AGENTS.md open format](https://agents.md/) for free-form Markdown,
  common high-value topics, and nested scope;
- [Apache Airflow](https://github.com/apache/airflow/blob/main/AGENTS.md) for
  exact environment wrappers, commands, architecture, and security boundaries;
- [Temporal Java SDK](https://github.com/temporalio/sdk-java/blob/main/AGENTS.md)
  for a concise repository map, focused tests, and review checklist; and
- [OpenAI Codex](https://github.com/openai/codex/blob/main/AGENTS.md) for
  directory-scoped rules, explicit prohibitions, and focused-before-full checks.

Do not include generic language tutorials, full directory trees, duplicated
README or architecture prose, style common sense, unverified commands, copied
Skill instructions, or rules derived from one isolated mistake. When concrete
calibration is needed, compare fragments against
[Good AGENTS.md Examples](../../../references/agent-customize/agents-md-review.md#good-examples)
without copying facts from the examples.

## Phase 2: Connect Core Knowledge to Task Paths

Turn existing authoritative documents into conditional routes. Do not append a
bare link catalog. Write short conditions such as:

- read the architecture owner before changing module or dependency boundaries;
- read the design owner before changing a public interface or interaction;
- read the testing owner before choosing broader or slower checks;
- read the runbook before diagnosing an operational failure; and
- read contribution or release guidance before changing delivery behavior.

Keep one canonical owner for each fact. `AGENTS.md` routes to the owner; it does
not repeat the owner's explanation. Prefer stable repository-relative links and
verify each persisted target. If a useful document does not exist, report the
gap as a possible follow-up instead of generating placeholder content.

Create a nested `AGENTS.md` only when a module has independent context such as
its own manifest, build target, deployment unit, domain boundary, public API,
test command, generated surface, risk boundary, or CODEOWNERS scope. A nested
guide contains only local differences. The open format gives the closest guide
precedence, but rely on nesting only after the selected runtime's loading
behavior is verified; otherwise route the local owner from the root guide.

## Cover Spec and Delivery Routes

Address both concerns in every foundation, and name a gap when no owner exists:

- **Spec.** Where change intent is recorded and reviewed before code: spec,
  ADR, RFC, issue template, or design doc owner, its naming rule, and when an
  agent must write one instead of coding directly.
- **Delivery.** How change reaches users: the CI entry command, the merge
  gate, the deploy trigger, and the approval boundary an agent must not cross.

Persist each as a route to the verified owner. Never emit a heading for an
unowned process; report it as a gap in the receipt instead.

## Apply and Validate

Before editing, form a bounded file plan from the inspected facts. Apply the
smallest coherent patch and preserve user organization when it remains usable.

Validate at minimum:

1. every persisted link resolves;
2. every persisted path exists or is explicitly described as a future output;
3. every command is concrete and copy-pasteable, with no unresolved
   metavariable, placeholder, ellipsis, or shell-significant template token;
4. every command has a source, declared working directory, and honest platform
   or shell boundary consistent with the repository's supported environments;
5. every safely runnable command is exercised from that directory, starting
   with the cheapest representative check;
6. skipped commands name the blocking condition without being reported as
   passed;
7. every normative rule has a user or project source, and root guidance does
   not duplicate README, manifest, architecture, or directory facts without a
   non-inferable operational reason;
8. root and nested instructions do not duplicate or contradict one another;
9. no unresolved template variables, credentials, private machine paths, or
   conflicting package-manager claims remain; and
10. existing user content and unrelated worktree changes remain intact.

Reapply the AGENTS.md Review criteria to the final candidate. Do not write or
finish with a confirmed unsafe, stale, non-portable, speculative, or
non-executable instruction; a short file and valid links alone do not pass the
quality review.

Do not install dependencies merely to validate Bootstrap. Do not claim a
command works from manifest presence alone. If no command is safely runnable,
retain static verification and label runtime behavior unobserved.

## Phase 3: Connect Agent Tools to Real Work

Enter this phase only after the foundation is applied and validated. Keep it
read-only and pass supported candidates to
[Capability Recommendation](capability-recommendation.md); do not install,
authenticate, connect, or activate a tool.

From the repository root, inspect repository-local remote URLs with
`git config --local --get-regexp "^remote\..*\.url$"`. Prefer Git's
cross-platform config interface over `cat .git/config`: `.git` may be a
worktree pointer. Record only sanitized host/provider evidence; never persist
credentials, tokens, userinfo, or private remote URLs in guidance or receipts.

Corroborate the host candidate with task-relevant collaboration assets:

- GitHub: `.github/` workflows, issue or PR templates, CODEOWNERS, and merge
  checks;
- GitLab: `.gitlab-ci.yml`, MR templates, CODEOWNERS, approval rules, and
  pipeline configuration; and
- unresolved: remotes and repository-owned evidence conflict or identify no
  provider.

Resolve the provider first; if unresolved, probe no provider CLI. Then probe
`gh --version` for GitHub or `glab --version` for GitLab, and never probe or
recommend the other provider's CLI for parity.
Inspect any runtime-discoverable Skill, MCP/connector, or platform tool before
calling it usable. Recommend a verified capability only for an actual or
stated near-term issue, PR/MR, code-review, release, or CI task that it
supports; hosting alone produces no recommendation.
If a useful tool is absent, offer installation as a separate explicit task.
Templates collect author evidence, while CI, merge checks, approval rules, and
CODEOWNERS enforce policy; a tool or Skill must not impersonate those controls.

## Phase 4 (Optional): Exercise One Real Task

Offer exactly one hands-on exercise after Phase 3; never start it automatically.
Keep uncommitted work separate with `git status --short`, summarize the latest
commit with `git show --stat --summary HEAD`, then inspect only its bounded diff,
changed code, tests, and current owners needed to understand the change.

Prefer a review exercise when the commit is a completed bounded change whose
correctness, regression coverage, documentation, or packaging can be checked.
Prefer a plan exercise only when the evidence establishes a real unfinished
follow-up, risk, or next increment. Do not manufacture backlog work from churn,
commit wording, TODO text, or an old diff alone.

Verify the exact trigger and instructions exposed by the current runtime before
recommending them. Treat `/plan`, `/review`, `/ultra-review`, and similarly named
entries as candidates, not portable Skill names. If no trigger is verified,
offer the task as a plain-language prompt and label the trigger unverified.

Return `Try`, `Why`, `Scope`, `Done when`, and `Boundary`. Make `Try` one
copy-pasteable sentence grounded in the inspected change, keep it read-only for
review or planning, and require a separate user choice before execution. Return
`No representative task recommendation` when no bounded useful exercise exists.

## Finish

At the result-review checkpoint, return a compact receipt containing changed
guidance files, a short beginner-oriented tour, the project sources used,
commands and links verified, skipped checks, and remaining conflicts. Label the
result Present or Wired. Do not claim Exercised unless one representative real
task actually loaded and followed the new routes, and do not claim outcome
improvement without a later comparable task.
