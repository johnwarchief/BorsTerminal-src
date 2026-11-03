# Bootstrap Capability Recommendation

Audience: main Better Harness agent, only after Project Foundation Bootstrap is applied and validated.

Use this pass to select one small, useful next capability. It routes by SDLC
stage and owner; it is not the report-only
[Skill Recommendation](../references/skill-recommendation.md) pass and cannot
manufacture repeated workflow evidence for that route.

## Evidence Gate

Use the user's current or stated near-term tasks, verified project files and
commands, and inspected capability instructions. Names, remote URLs, framework
or dependency presence, catalog labels, and asset counts may route inspection;
none proves capability fit, absence, installation, or likely use.

## Route by SDLC Stage

Classify the supported demand before selecting a product:

| Stage | Inspect for |
| --- | --- |
| `plan` | Requirements, issue intake, scope, and decision context |
| `design` | Architecture, interfaces, data models, and design review |
| `develop` | Implementation, generation, migrations, and local feedback |
| `test` | Automated checks, browser or device verification, and evidence |
| `deploy` | Release, CI/CD, infrastructure, and cloud delivery |
| `operate` | Diagnostics, observability, incidents, cost, and maintenance |

SCM collaboration can cross several stages. When project-owned configuration
(manifests, infrastructure, or workflows, interpreted by content rather than a
bare name) shows semantically strong cloud-provider use, map the represented
workflow to `deploy`, `operate`, or both and point to the vendor's official
Skill source. A current cloud task raises its priority but is not required for
a bounded advisory; weak evidence such as a provider name in prose produces
none.

| Provider | Strong evidence | Official Skill source |
| --- | --- | --- |
| Azure | `azure.yaml`, Bicep/ARM, Terraform `azurerm`, or `azd` config | https://github.com/microsoft/azure-skills |
| AWS | `cdk.json`, CloudFormation/SAM, Terraform `aws`, or `serverless.yml` provider `aws` | https://github.com/aws/agent-toolkit-for-aws |
| Alibaba Cloud | Terraform `aliyun`, a ROS template, or Serverless Devs config | https://github.com/aliyun/alibabacloud-aiops-skills |
| Tencent CloudBase | `cloudbaserc.json`, CloudBase config, or verified `@cloudbase/*` use | https://github.com/TencentCloudBase/skills |

CloudBase Skills cover CloudBase workflows only; generic Tencent Cloud
configuration is not a CloudBase match. Do not copy install commands (they
drift by host); the next action is to open the official README in a separate
task, and Bootstrap never installs, authenticates, deploys, or mutates cloud
resources. Add future stage-specific sibling references only when they have a
curated owner set and a stable evidence contract.

## Choose the Smallest Durable Owner

| Need | Prefer |
| --- | --- |
| Always-needed project fact | `AGENTS.md` or canonical docs |
| One reproducible operation | Existing CLI or script |
| Mechanically enforceable rule | Lint, test, Hook, CI, or SCM control |
| Stable multi-step judgment | Existing or project Skill |
| External resource access | Existing CLI, MCP, connector, or platform tool |
| Missing current evidence | Observation plan, not a new asset |

Prefer verified existing coverage, then a suitable built-in or platform
capability, an installed matching Skill, an extension to a partial project
Skill, a non-Skill owner, or the smallest missing evidence. Verify instructions
before naming a capability as usable; otherwise label it unverified.

## SCM Route

Use the provider, collaboration-asset, and local-tool evidence collected in
[Project Foundation Phase 3](project-foundation.md#phase-3-connect-agent-tools-to-real-work).
Select a verified GitHub capability or `gh` workflow for supported GitHub work,
and a verified GitLab capability or `glab` workflow for supported GitLab work.
Do not invent a GitLab Skill to mirror a GitHub recommendation or substitute a
provider-specific tool when the platform is unresolved.

Templates collect author evidence; CI, merge checks, approval rules, and
CODEOWNERS enforce policy. A Skill must not impersonate those controls.

## Keep Advice, Findings, and Skill Creation Separate

Direct Bootstrap returns optional advice only. Do not create or modify
`findings.json`, invoke `/create-skill`, or treat a missing capability as a
finding. External discovery, installation, authentication, connection, and
activation require a separate explicit request.

Only a later full Better Harness report may propose `/create-skill`, after the
[Skill Recommendation](../references/skill-recommendation.md) pass establishes:

- two comparable real occurrences, or one costly or high-risk workflow likely
  to recur;
- stable inputs, an ordered procedure, a checkable result, and a supported
  present consequence; and
- no suitable built-in, installed, official provider, existing project, or
  non-Skill owner.

The finding must describe the supported workflow consequence, not the absence
of a Skill. Its repair may use `/create-skill` only for an uncovered
Skill-shaped workflow; do not duplicate an official provider bundle.

## Return

Return at most three candidates ordered by immediate utility. For each include
`Stage`, `Need`, `Evidence`, `Owner`, `Capability`, `Action`, `Verifier`, and
`Boundary`. An official Skill source link may be the capability when
configuration clears the cloud evidence gate above, but it remains
uninstalled and unverified locally until separately inspected.

Return `No capability recommendation` when no candidate clears the evidence
gate. That is a valid low-cost Bootstrap result.
