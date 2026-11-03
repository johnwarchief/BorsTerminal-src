# Qoder CLI integration

This reference translates upstream actions for Qoder CLI. Use only tools and parameters actually exposed by the current session; runtime, user, and project instructions take precedence over this plugin.

- Invoke a skill with `Skill`, using the exact discovered name (normally `superpowers:<skill-name>`). If native invocation is unavailable, read the installed `skills/<skill-name>/SKILL.md` with `Read`. Never invent a missing tool.
- Read/write/edit/search/run commands with `Read`, `Write`, `Edit`, `Glob`, `Grep`, and `Bash` as exposed by the session.
- Track progress with `TodoWrite`, or the available `TaskCreate`/`TaskUpdate`/`TaskList` tools. If unavailable, use a plan file.
- Dispatch subagents with `Agent` when exposed, or `Task` on a version that exposes that name. Use an available general-purpose agent and include the full implementer/reviewer prompt or its absolute file path. The upstream `code-reviewer` wording describes a role, not a guaranteed registered agent type.
- Use model selection, background execution, resume and messaging only if supported by the live tool schema. Do not send another platform's parameters or hardcoded model IDs. If model selection is unavailable, record that the session model is inherited. If resume is unavailable, start a fresh agent with the prior report, ledger and open findings and record this fallback.
- If subagents are unavailable or prohibited by the user/project, execute sequentially with the same verification and review criteria; explain that independent subagent review was not performed. Do not spawn nested reviewers or implementers.
- Resolve supporting script paths from the loaded skill's directory; execute them with the target repository as the working directory. Do not change into the plugin directory before running repository-oriented SDD helpers.
- Follow the user's repository instructions and existing worktree conventions (including AGENTS.md and qoder.md where applicable). Upstream .worktrees/ is a fallback, not an override of a prescribed task worktree path.
- Node.js must be available on PATH for startup injection and the optional visual companion. Git and Bash are needed for Git/SDD helpers; Windows users need Git Bash for those helpers. Additional test-writing utilities may require Python or Graphviz. Never silently install system dependencies.
- The optional visual companion is started only when the user accepts its offer. This startup hook never starts a server or sends network requests.

Runtime scope: validate TUI, headless, SDK/ACP and remote modes separately; plugin availability and tool sets can differ. A source/schema check is not evidence that every runtime supports every feature.
