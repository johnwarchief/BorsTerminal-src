---
name: init
description: Initialize or refresh repository AGENTS.md from durable, non-obvious, project-specific evidence. Use when asked to run /init, create or update AGENTS.md, or bootstrap coding-agent instructions. Do not use for dependency installation, project scaffolding, or environment setup.
---

# Init AGENTS.md

Create the smallest useful repository instruction set. Treat `AGENTS.md` as an operating contract for coding agents,
not as a second README or generated architecture document.

## Desired outcome

- Create `AGENTS.md` only when the repository contains durable guidance worth loading for most tasks.
- Preserve valid human-authored constraints and make the smallest useful change to an existing file.
- Use nested files only when a subtree has materially different commands, boundaries, or workflows.
- Make no file change when the existing guidance is sufficient or no durable guidance exists.

## Admission test

Include an instruction only when it is broadly applicable within its scope, non-obvious, action-changing, durable, and
backed by repository evidence or explicit user input. Ask:

> If this line disappeared, would a capable coding agent be meaningfully more likely to make a mistake?

If not, omit it or point to the source of truth.

## Workflow

### 1. Resolve scope

- Determine the launch directory, repository or worktree root, requested scope, and exact target files. Do not assume
  these are the same.
- Map root, nested, and override instruction files plus repository-local rules for other agent hosts.
- Do not copy personal or global instructions from home-directory configuration unless explicitly requested.
- Do not inspect unrelated directories outside the repository to enrich `AGENTS.md`.

### 2. Inspect evidence before editing

Prefer current sources of truth:

- existing agent instructions and repository rules;
- `README`, contribution, architecture, development, and operational documentation;
- manifests, lockfiles, task runners, workspace configuration, CI, and presubmit workflows;
- code-generation, migration, release, deployment, and local-development configuration; and
- a few representative source or test files only when configuration does not resolve a concrete question.

Classify each instruction-looking file as either active for the selected host and scope or evidence-only. Do not claim
duplication, conflict, precedence, or context pressure unless the selected host loads both sources. If loading behavior
is unknown and affects the result, preserve the files and report the uncertainty.

Inspect narrowly. Do not run a full build or test suite merely to populate instructions. Run a lightweight local command
only when it safely resolves material uncertainty.

When a candidate is long, several instruction surfaces overlap, Qoder loading behavior matters, or the runtime debug
route is non-obvious, read [Agent Instructions Review](../../references/agent-customize/agents-md-review.md) before
drafting. It is the canonical owner for length gates, host-aware comparison, overlap review, and observability criteria.

### 3. Extract decision-changing guidance

Look for:

- canonical install, build, lint, typecheck, test, start, and focused-test commands, including required ordering,
  prerequisites, working directories, and expensive or CI-only checks;
- non-obvious ownership, layering, public API, generated-file, schema, and configuration boundaries;
- repository-specific conventions or required helpers that automation does not already enforce;
- migration, codegen, dependency, credential, production, release, and destructive-operation boundaries;
- conditional routes to deeper architecture, testing, runbook, or module guidance; and
- for runtime, service, asynchronous, UI, or E2E systems, the minimal AI-debug route: logging owner, local reproduction,
  focused test, readable output, correlation mechanism, and safe-access boundaries.

Record a repository owner for each command, version, path, and boundary. Commands must be complete and copy-pasteable;
do not put metavariables, ellipses, or pseudo-commands in code spans. For non-portable commands, state the working
directory and supported operating system or shell. In cross-platform repositories, prefer a repository-owned wrapper or
verified platform variants over one observed invocation.

Treat `must`, `never`, and `ask before` as policy, not inference. Use them only when explicit user input or a current
repository owner establishes the rule. Do not promote a generated draft, local observation, or isolated mistake into
permanent policy.

If an important fact remains uncertain, omit it unless it materially affects the file. Then ask one focused question or
report the missing evidence rather than guessing.

### 4. Choose the hierarchy

- Put only always-needed, repo-wide guidance in the root `AGENTS.md`.
- Add a nested file only for a genuine local delta; do not repeat the root.
- Respect verified host discovery and precedence semantics. Do not rely on nested loading when the selected host does
  not support or has not proven it.
- Prefer a short conditional pointer to a canonical owner over copied instructions.
- Do not create symlinks or duplicate policy into `CLAUDE.md`, `GEMINI.md`, Cursor rules, or Copilot instructions unless
  the user requests a multi-tool setup.

### 5. Compose a compact operating brief

Use only headings supported by high-value content; there is no required template. Put exact commands and critical risk
rules early. Prefer direct imperative bullets, one operational idea per bullet, and a brief reason for surprising rules.
Apply the canonical length gates linked above whenever the root is not obviously compact.

Exclude directory tours, product summaries, obvious stack facts, generic best practices, mechanically enforced style,
transient task state, personal preferences, secrets, speculative commands, placeholders, and duplicated documentation.

### 6. Update existing files conservatively

- Treat existing instructions as user-owned policy, not generated scratch output.
- Preserve valid explicit constraints and prefer a minimal diff over a rewrite.
- Refresh commands or paths only when current evidence proves they are stale.
- Do not silently weaken `MUST`, `NEVER`, security, release, migration, or ownership rules.
- Preserve and report conflicts between policy and repository evidence unless the user asks to reconcile them.
- Do not normalize every agent-instruction system as a side effect of `/init`.

### 7. Verify

Re-read the result and diff. Confirm that:

- commands are complete, current, scoped, and traceable;
- normative policies have an explicit source;
- active-source classification matches verified host behavior;
- referenced paths exist and root or nested scopes do not contradict;
- no personal configuration, secrets, transient facts, or redundant docs leaked into the file;
- critical commands and risk rules are easy to find; and
- every remaining line changes an agent decision or prevents a plausible mistake.

If the repository already provides an `AGENTS.md` validator or linter, run its narrow local check. Do not install a tool
solely for this initialization. Do not claim that the current host loaded the new file without using its reload mechanism
or a fresh session.

## Final response

Report the files created or updated, key evidence used, important uncertainty not guessed, and whether no change was
needed. Do not paste the whole file unless requested; the file itself is the deliverable.
