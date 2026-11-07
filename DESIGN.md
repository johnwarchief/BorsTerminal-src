# BorsTerminal — Frontend Design System

> **Status:** Owner-facing visual direction and implementation contract. Read this file before any user-visible UI redesign or significant component styling change.
>
> **Product target:** a modern, precise, low-latency Iranian-market trading and research workstation — not a generic SaaS admin template.

## 1. What “modern” means here

BorsTerminal must feel deliberately designed: clear hierarchy, consistent spacing, aligned data, reliable interaction states, restrained color, and predictable behavior. A new color palette alone is not a redesign.

The primary environment is a desktop browser/window at **1366×768**. Also verify 1600×900 and 1920×1080; smaller widths must remain usable rather than overflow. Dense market information is a product requirement, but the interface must not become visually noisy or unreadable.

### Desired visual language

- Professional financial workstation: compact, composed, purposeful, high information density with enough separation to scan quickly.
- Neutral dark surfaces with a clear surface hierarchy; one restrained primary accent and semantic colors only where they convey meaning.
- Strong typography hierarchy using the existing Vazirmatn font and current scale; keep important figures readable without oversized headings.
- Consistent control heights, spacing, borders, radii, icons, hover/focus/selected/disabled/loading/error states.
- Use whitespace and subtle separators to group content. Not every section needs to be a floating card.
- Motion should communicate state or improve orientation. Preserve useful existing animations; prefer short, compositor-friendly transitions and honor `prefers-reduced-motion`.
- Show market/data freshness and error states honestly; never use visual polish to imply data is live when freshness is unproven.

### Avoid

- Generic “AI dashboard” styling, cloned landing pages, card grids used for every view, arbitrary gradients, neon glow, heavy glassmorphism, blur on many large panels, oversized empty hero areas, excessive rounded pills, emoji icons, and decoration that competes with market data.
- Inconsistent one-off colors, spacing, border styles, typography, and hand-drawn substitutes for components that should share a common primitive.
- Making tables less dense/readable to create an artificial sense of minimalism.
- Removing product capabilities, chart tools, signals, data columns, navigation, or useful animation as a way to simplify the visual redesign.
- Large-scale restyling without before/after browser evidence.

## 2. Non-negotiable project constraints

- Stack: React 18 + TypeScript + Vite + Tailwind CSS v4; follow the existing Feature-Sliced architecture and ESLint import boundaries.
- Read `AGENTS.md`, `docs/README.md`, this file, and the relevant skill before implementation.
- The existing `frontend/src/shared/styles/tokens.css` and `frontend/src/index.css` contain custom theme and typography contracts. Do not replace either wholesale or run a preset/theme command that overwrites them without first understanding the diff.
- Existing CSS variables that resemble shadcn semantic tokens are **not proof** that shadcn/ui components are installed. Inspect `package.json`, `components.json`, aliases, lockfile and existing primitives before deciding on integration.
- Preserve routing, API contracts, data meanings, FTS rules, chart engine behavior, keyboard interactions, feature capabilities and saved state. A visual change must not change analytical meaning.
- Retain the numeric/RTL guardrails in `skills/bors-frontend-ui-guard/SKILL.md`: use the project's formatting helpers, tabular numerals, correct digit-direction isolation, stable numeric slots and logical layout; do not solve RTL by randomly flipping individual controls.
- Do not regress the app's responsiveness or data density. Prefer existing table virtualization and TanStack tooling over large custom rendered lists.
- Treat faster interaction and lower CPU/GPU cost as part of visual quality. Avoid broad `backdrop-filter`, permanent animated backgrounds, unnecessary chart re-mounts, and expensive effects across every row/card.

## 3. Component-system policy

Use **actual shadcn/ui source components** for suitable shared primitives instead of creating a collection of unrelated hand-styled controls. shadcn/ui is open code that is copied into the project and then owned/customized by the project; it is not a runtime component package that magically changes existing controls.

1. First audit the current design tokens, shared components, import aliases and exact dependency versions.
2. Follow the official shadcn/ui CLI/skill documentation. Choose one primitive family (Radix or Base UI) deliberately; do not mix primitive families casually.
3. Integrate incrementally with the existing Tailwind v4 theme. Inspect every generated CSS/config/dependency diff. Do not blindly run an initializer or preset that overwrites the current theme.
4. Add components only when they solve an actual shared need: Button, Input, Select, Tabs, Badge, Tooltip, DropdownMenu, Dialog/Sheet, Popover/Command, Skeleton, Alert and consistent form primitives are likely candidates. Select the exact set after code inspection.
5. Use a consistent icon library (Lucide is a reasonable candidate) rather than mixing SVG styles or emoji; add dependencies only after inspecting the lockfile and licensing.
6. Keep the chart rendering engine and domain-specific chart overlays/tools intact. shadcn/ui is for surrounding controls, menus, dialogs, settings, panels and layout primitives, not a replacement for KLineCharts or financial chart logic.
7. Build reusable project components under the current architecture. Avoid importing template components across architectural boundaries or copying an entire starter app into the repository.

## 4. Reference projects — use the right part, not the whole app

- **shadcn/ui** — https://github.com/shadcn-ui/ui — the canonical source for accessible, customizable UI primitives and the official CLI. MIT. Adopt suitable components/patterns; configure them to BorsTerminal tokens.
- **shadcndashboard/shadcndashboard** — https://github.com/shadcndashboard/shadcndashboard — React/Vite + TypeScript + Tailwind v4 + shadcn dashboard, with a published MIT license. Use it to inspect shared dashboard shell, table, form, responsive and theme patterns. It advertises React 19, while BorsTerminal currently uses React 18; port patterns selectively and verify compatibility rather than copying the full app.
- **vercel-labs/agent-skills** — https://github.com/vercel-labs/agent-skills — MIT. Its `web-design-guidelines` skill provides a systematic interface/accessibility review; `react-best-practices` focuses on React performance. Treat them as audit checklists, not substitutes for product design.
- **nextlevelbuilder/ui-ux-pro-max-skill** — https://github.com/nextlevelbuilder/ui-ux-pro-max-skill — MIT. Optional source of design-system ideas and searchable style/pattern guidance. Its output is not authoritative; inspect the result critically and require before/after screenshots. Never allow a general-purpose style recipe to replace this file's financial-terminal requirements.
- **ghostfolio/ghostfolio** — https://github.com/ghostfolio/ghostfolio — open-source wealth-management product useful for studying financial information hierarchy and portfolio storytelling. Its repository is AGPL-3.0 and the frontend is Angular/Material, so use it as a visual/product reference only; do not copy code into BorsTerminal without a deliberate license review.
- Existing BorsTerminal chart behavior reference: `docs/CHART-PARITY-REFERENCE.md`. It governs chart affordances, not the overall visual theme.

External templates are examples, not sources of truth. Inspect the current upstream version and license before copying code/assets. Reference links, versions and capabilities can change; verify before adding dependencies.

## 5. Visual acceptance contract

For a meaningful visual change, the agent must:

1. Record the exact route, current commit, viewport size and current screenshot before changing code.
2. State the design problem in concrete terms (hierarchy, layout, density, consistency, interaction, RTL or accessibility), not only “make it modern”.
3. Identify existing components/tokens to reuse and propose the smallest coherent design-system change before implementation.
4. Implement a complete, coherent slice — not just repaint buttons. Check real content, dense tables, empty/loading/error states, open menus/dialogs, selected states and long Persian labels.
5. Capture before/after screenshots from the **real browser** at 1366×768 and at least one larger viewport. Unit tests or jsdom snapshots alone do not prove visual quality.
6. Check RTL, keyboard/focus, text clipping, numeric alignment, horizontal overflow, chart sizing and console/network errors.
7. Run relevant Vitest tests, `npx tsc -b` and `npm run build`; use the project's required full gate when appropriate. Report each result truthfully.
8. Compare user-visible wait time and resource behavior when styling might affect rendering. Do not claim “faster” without repeatable measurement.
9. Report changed files, screenshots/evidence, tests, regressions and unresolved items. Do not declare success if the actual browser view has not been inspected.

A UI task is not accepted merely because the TypeScript build passes or the agent says it looks better. Acceptance requires a coherent result visible in the running application and evidence against the criteria above.
