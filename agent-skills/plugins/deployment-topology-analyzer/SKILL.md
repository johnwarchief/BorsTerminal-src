---
name: deployment-topology-analyzer
description: "Deployment and runtime topology analysis. Use when the user needs to understand where software runs, how environments, clusters, networks, CI/CD, cloud resources, runtime instances, scaling, release paths, and operational boundaries fit together."
---

# Deployment Topology Analyzer

Use this skill when the architectural question is: **Where does the system run, how is it connected, and how does it get released or operated?**

Deployment/runtime topology is separate from logical system structure because one service may have multiple environments, regions, clusters, replicas, networks, or release paths.

## Shared Gates

If `explore` has not already loaded them, read:

- `../../references/architecture-contract.md`
- `../../references/architecture-evidence-model.md`
- `../../references/diagram-output-formats.md`

Use `../graphviz/SKILL.md` for infrastructure/resource graphs, release paths, and partial topology maps. Use Structurizr when a small runtime-to-logical C4 view is clearer. Use Mermaid only for compact Markdown-native CI/CD sketches.

Read `../../references/business-application-fitness.md` when deployment topology affects business-critical paths, billing, data isolation, tenant/workspace boundaries, regulated data, or operational readiness for a business application.

## Scene Boundary

Use `deployment-topology-analyzer` for:

- Cloud, Kubernetes, container, process, VM, network, region, account/project, and environment maps.
- CI/CD release paths, image build/deploy chains, promotion gates, rollout strategies, and runtime ownership.
- Runtime observations: instances, pods, service registry, traffic routes, autoscaling, logs, metrics, or incidents.
- Infra risk questions: single points, trust boundaries, environment drift, scaling bottlenecks, and operational gaps.

Do not use it for logical system modeling unless logical nodes are needed to anchor runtime resources.

## Workflow

1. Define runtime scope: environment, cluster, account/project, region, product, release path, or incident window.
2. Gather evidence from IaC, Kubernetes manifests, Docker/Compose, CI/CD files, service discovery, config, cloud inventory, runbooks, traces, metrics, or deployment docs.
3. Separate desired configuration, deployed runtime observations, and assumptions.
4. Map deployable units to infrastructure resources, network routes, storage, queues, secrets, and external dependencies.
5. For business applications, map deployable units and environment differences to business capabilities, critical workflows, data isolation, and tenant/workspace boundaries.
6. If evidence only covers a subset of deployables, such as docs but not customer-facing apps, draw only the confirmed release path and put the other deployables in an `Unknown / validate next` branch.
7. Add release path and ownership where deployment risk is part of the question.
8. Surface drift, single points, unobserved resources, and validation commands.

## View Recipes

- Environment topology: Graphviz DOT.
- Kubernetes/cloud topology: Graphviz with clusters by namespace/account/region.
- CI/CD path: Graphviz DOT by default; Mermaid only for small Markdown-native sketches.
- Runtime-to-logical mapping: C4 plus deployment overlay when small enough.

Read `references/deployment-topology-recipes.md` only when needed.

## Quality Gates

- Label current runtime observations separately from IaC desired state.
- Do not infer production topology from local dev config unless marked low-confidence.
- Do not invent cloud providers, Vercel projects, Kubernetes clusters, databases, CDNs, queues, regions, networks, or secret managers from framework choice, directory names, or common deployment patterns.
- When runtime evidence is missing, produce a useful partial topology: confirmed CI/CD or docs-deploy path plus explicit unknown hosting/infrastructure/release gaps for unevidenced apps.
- Show trust/network/environment boundaries when security or operations matter.
- Include validation gaps for resources that only appear in docs or naming conventions.
- Every deployment node and release edge must cite IaC, manifests, CI/CD files, config, runtime observation, runbook, or docs. Use structured `sourceRefs` for model artifacts; in Markdown reports, cite evidence paths in prose. Missing evidence must be marked assumed or unknown.
- For business applications, identify which business paths or data isolation boundaries are affected by environment, network, release, or scaling decisions.

## Artifacts

These artifacts capture runtime placement, release paths, operational evidence, and deployment risks.

- `deployment-topology.dot|dsl|mmd`: topology source showing runtime units, environments, networks, and infrastructure boundaries.
- `release-path.dot|mmd`: deployment or traffic path view from build/release entry points to running services.
- `runtime-evidence.md`: inventory of IaC, manifests, telemetry, configs, and docs used to support topology claims.
- `deployment-risks.md`: operational risks, missing evidence, scaling gaps, release hazards, and validation steps.

## Summary

Summarize the runtime topology in the way the operational question requires.
Describe where the system runs, how traffic or releases move, which evidence
supports the topology, and where runtime or IaC evidence is missing. Include
artifact paths and validation steps when they are actionable.
