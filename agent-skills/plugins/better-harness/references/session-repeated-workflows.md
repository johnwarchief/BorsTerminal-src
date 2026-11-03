# Repeated Workflow Discovery

Audience: delegated Agent 1 only (Step 2.1), when repeated procedure demand is in scope.

Use this reference when Session Evidence must decide whether recent requests
contain repeated procedure demand. It is semantic comparison, not a keyword
detector or a request to open raw sessions.

## Analysis Model

- A **session** is a transport container, not one workflow or several runs.
- A **Workflow Run** is one root goal plus its ordered follow-ups, work trace,
  checks, recovery, delivery, and acceptance boundary.
- A **root candidate** is a repeated goal and stable first-prompt input shape.
- A **workflow candidate** also repeats ordered stages and a stop boundary.

Keep confidence in the repeated goal separate from confidence in its procedure.
First prompts may support the former while later actions remain unknown.

## Phase 1: First-Prompt Pass

Read only bounded root summaries, opaque references, independence groups, and
provider labels. Treat each summary as a possible Workflow Run, not proof of
later actions or results.

Cluster roots semantically using all of these dimensions:

1. the user's underlying goal;
2. the target or artifact type;
3. the stable input shape, such as an issue, screenshot, log correlation id,
   failing test, or review link; and
4. the requested acceptance boundary, when one is stated.

Shared words, repositories, paths, product names, or generic verbs such as
fix, analyze, review, test, and submit are insufficient. Keep a cluster only
when at least two distinct comparable Task Episodes support it.

Count independence conservatively:

- prefer roots from different independent contexts;
- `occurrences`, repeated turns, retries, or copied history count as one run;
- several Episodes in one context group do not establish independent demand;
- identical forked roots without independent later traces must be deferred;
- keep provider evidence separate unless the lead explicitly joins it.

If the input reports omitted roots, state that discovery covers only the supplied
portfolio. Never claim that the full 7- or 30-day population was clustered.
Retain only the strongest evidence-supported clusters and representative refs.

## Phase 2: Candidate Expansion

Only after a root cluster passes Phase 1, follow its supplied references to
inspect matching trace, checks, repair, result, and mechanism facts. Never
expand unrelated candidates. Without two linked runs, keep the procedure unknown.

Normalize observed actions into stages such as intake, prepare, inspect,
reproduce, diagnose, approve, modify, verify, recover, deliver, and review.
Preserve their order. A follow-up such as "still wrong" or "submit it" has
meaning only relative to its root and is never a standalone workflow.

Call a stage **core** only when at least two independent runs support it. Keep a
one-run stage **optional**. Treat a pattern as a reusable workflow only when at
least two runs repeat both an ordered core and a verification or stopping
boundary. Missing trace or result evidence stays unknown.

## False-Positive Firewall

- Repeated commit, publish, or review requests alone are a thin delivery tail,
  not proof of the workflow that preceded them.
- Repeated user corrections show friction, but not necessarily a stable
  procedure or the correct reusable intervention.
- Explicit use of an existing Skill is coverage evidence. It is not evidence
  that another Skill should be created.
- A recurring log-inspection step may be a backend diagnosis component without
  proving a complete hotfix workflow.
- Missing checks, outcomes, or assets are unknown; absence in the supplied
  facts is not evidence that the practice is absent.

## Return Contract

Return a compact natural-language brief. For each retained lead, explain the
normalized goal, stable input shape, provider-labelled root refs, core and
optional stages, confidence in the goal and procedure, task-linked Skill use,
evidence limits, and the next evidence needed. A repeated goal may justify a
capability comparison even when its procedure is not stable; clearly separate
that from a supported reusable workflow. Only a retained Phase 1 root cluster
qualifies; rejected grouping cannot become capability demand through a broader
label. Do not expose raw prompts, local paths, or Session ids.

Do not recommend `Create Skill` or `Extend Skill`. The lead must first join the
candidate with Project and Agent Customize evidence, compare existing asset
coverage, and route uncovered repeatable work through Loop Discovery.
