---
name: risk-quality-reviewer
description: "Architecture risk and quality review. Use when the user needs an evidence-backed architecture review, quality attribute assessment, technical debt map, risk register, fitness-function view, or prioritized remediation plan."
---

# Risk Quality Reviewer

Use this skill when the architectural question is: **Is this architecture healthy enough for its goals, and where are the risks?**

It combines architecture review, risk/technical debt, and quality attributes because they share the same review evidence and remediation workflow.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../graphviz/SKILL.md` for risk networks and `../c4model/SKILL.md` when risks need to overlay system/container boundaries.

Read `../../references/business-application-fitness.md` when the review is about a business application, business-domain understanding, AI/agent readiness, end-to-end path coverage, business-rule safety, or validation readiness.

## Scene Boundary

Use `risk-quality-reviewer` for:

- Architecture review before launch, migration, funding, or major refactor.
- Technical debt, complexity, coupling, test gaps, outdated dependencies, operational risk, or security/privacy exposure.
- Quality attributes: performance, availability, reliability, scalability, maintainability, testability, security, observability.
- Fitness functions, guardrails, remediation priorities, and review-ready findings.

Do not use it as the first step when the system structure is unknown; start with `system-modeler` or a focused flow/deployment analysis.

## Git Change Evidence

For PR, ADR, release, or architecture-change reviews, use git to scope the review before assigning risk. The diff is evidence for what changed; it is not by itself evidence that a risk exists.

PR or branch against a base branch:

Replace `origin/main` with the actual PR base branch when needed, such as `origin/master`.

```bash
base=$(git merge-base HEAD origin/main)
git log --oneline --decorate "$base"..HEAD
git diff --check "$base"...HEAD
git diff --name-status --diff-filter=AMRT --find-renames "$base"...HEAD
git diff --stat --find-renames "$base"...HEAD
```

Focus architecture-risk review on control-plane, contract, runtime, and quality-gate files:

```bash
git diff --find-renames "$base"...HEAD -- package.json package-lock.json pnpm-lock.yaml yarn.lock
git diff --find-renames "$base"...HEAD -- Dockerfile docker-compose.yml ".github/workflows/*" "infra/**" "config/**"
git diff --find-renames "$base"...HEAD -- "docs/adr/**" "docs/architecture/**" "openapi/**" "proto/**" "schemas/**"
git diff --find-renames "$base"...HEAD -- "tests/**" "test/**" "spec/**" "**/__tests__/**" "**/*.test.*" "**/*.spec.*"
```

Use changed dependency manifests, CI/CD files, IaC, schemas, public contracts, tests, and ADRs to seed review findings. Then validate each risk with code/config/runtime/docs evidence before assigning severity, likelihood, impact, owner, or remediation priority.

## Workflow

1. Define review goal, stakeholder, risk tolerance, and quality attributes that matter.
2. Gather evidence from architecture model, code, configs, tests, dependencies, incidents, metrics, docs, ADRs, and deployment/runtime surfaces.
3. Identify risks and quality gaps with evidence, confidence, likelihood, impact, owner, and validation path.
4. Map risk clusters to affected nodes/edges/capabilities and separate current defects from target-state assumptions.
5. Prioritize remediation by blast radius, business impact, reversibility, and effort.
6. Produce a review artifact that includes diagrams, finding table, caveats, and next checks.
7. For business applications, include Business Application Fitness findings covering business model clarity, data/state understanding, end-to-end path grounding, agent instruction use, and business validation readiness. Use a numeric scorecard only when the user or evaluation harness asks for scoring.

## View Recipes

- Risk/technical debt heatmap: Graphviz DOT or Markdown matrix.
- Quality attribute scenario map: Markdown plus Graphviz DOT when relationships matter.
- Architecture review board: current view, risk overlay, recommendations.

Read these only when needed:

- `references/risk-tech-debt-recipes.md`
- `references/quality-attribute-recipes.md`
- `references/architecture-review-recipes.md`

## Quality Gates

- Do not call an issue a risk without evidence or an explicit assumption.
- Keep likelihood, impact, confidence, and owner separate.
- Avoid generic quality checklists; tie each finding to the stated architecture goal.
- Recommendations must include validation or acceptance criteria.
- For business applications, structure findings around domain entities, workflows, permissions, tenancy/workspace boundaries, lifecycle states, and regression paths before generic framework concerns.
- Business-app risks must cite evidence for domain entities, workflows, permissions, data lifecycle, tests, or agent instructions. If evidence is missing, label the item as an assumption or unknown and name the validation step. Use structured `sourceRefs` when the output is an evidence model or traceability artifact.

## Artifacts

These artifacts capture the architecture review, prioritized risks, quality scenarios, and remediation plan.

- `architecture-review.md`: evidence-backed review narrative with findings, severity, confidence, and affected architecture goals.
- `risk-quality.dot|mmd`: diagram source connecting quality attributes, architecture elements, and observed risks.
- `risk-map.dot|mmd`: focused risk relationship map for hotspots, dependencies, impact paths, or technical debt clusters.
- `quality-scenarios.md`: quality-attribute scenarios with stimulus, response, measurement, and evidence requirements.
- `remediation-plan.md`: prioritized remediation actions with owner assumptions, validation gates, and sequencing notes.
- `architecture-understanding.md` or `business-readiness-findings.md`: business-domain understanding or agent-readiness findings when Business Application Fitness applies.

## Summary

Write the review summary around risk and decision usefulness. Lead with the
highest-priority findings, explain the evidence and affected quality
attributes, and separate confirmed risks from gaps or assumptions. Include
artifact paths, remediation priorities, and next actions when they are useful.
