---
name: bors-frontend-design
description: Use for any substantial BorsTerminal UI redesign, new shared component, layout, visual polish, RTL/responsive issue, table readability, theme change, or design review. Triggers before styling or replacing frontend UI.
---

# BorsTerminal Frontend Design — Required Workflow

## Read first

1. Root `AGENTS.md` and `docs/README.md`.
2. Root `DESIGN.md` — canonical product visual direction and acceptance contract.
3. `skills/bors-frontend-ui-guard/SKILL.md` — project-specific RTL, numeric, table and FSD constraints.
4. Relevant page/feature code, shared controls, tokens and existing tests.
5. `skills/bors-live-ui-check/SKILL.md` and chart pixel-check skill when the touched UI needs them.

## Workflow

### 1. Establish reality before editing

- Confirm current branch/commit and inspect the working tree; do not overwrite other agent work.
- Identify the exact route(s), component hierarchy, current design tokens and existing shared primitives.
- Inspect `frontend/package.json`, lockfile, Tailwind v4 setup, aliases, `components.json` (if present) and installed primitive/icon dependencies. Do not infer component-library use from CSS variable names alone.
- Capture a real-browser baseline at 1366×768 before editing. Use Playwright/CDP or the verified browser tool already available in the project; do not assume a different browser MCP is installed.
- Note concrete deficiencies: visual hierarchy, spacing scale, repeated styles, table density/alignment, RTL, control states, overflow, accessibility, rendering/scroll performance.

### 2. Use references intelligently

- Canonical components and CLI: https://github.com/shadcn-ui/ui and https://ui.shadcn.com/docs.
- Dashboard composition examples: https://github.com/shadcndashboard/shadcndashboard.
- Systematic UI review: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines.
- React rendering/bundle performance review: https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices.
- Optional ideation only: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.
- Financial product hierarchy reference only (AGPL-3.0; no copying source code without license review): https://github.com/ghostfolio/ghostfolio.

Use upstream documentation and examples as inputs, not as an excuse to paste an entire template. Check current license, framework and component API before copying any code.

### 3. Plan before implementation

Write a short, specific plan in the task report:
- target route/components;
- current problem and evidence;
- proposed visual hierarchy and token/component changes;
- dependencies/configuration changes required, if any;
- acceptance screenshots, tests and performance checks.

Do not re-theme every route in one uncontrolled sweep. Start with a representative high-value slice (shared app shell plus a core market screen, unless the task specifies another page), verify the design and runtime impact, then propagate shared components consistently.

### 4. Integrate shadcn/ui deliberately

- Prefer the official shadcn skill when the agent environment supports it (current official guidance: `pnpm dlx skills add shadcn/ui`; verify the latest official instructions before running it).
- For project changes, add actual required components through the official CLI where compatible. Review the generated files and dependency changes instead of manually imitating shadcn classes.
- Integrate with Tailwind CSS v4 and current theme tokens. Do not blindly apply a preset, overwrite `tokens.css`/`index.css`, or mix Radix and Base UI primitives without a written reason.
- Inspect and configure `components.json` and import aliases. Current CSS semantic variables do not prove the shadcn component set is configured.
- Use the real component for appropriate shared patterns, then customize typography, density, color, focus and spacing to match `DESIGN.md`. Avoid installing a component just to check a box.
- Use a single consistent icon family; do not use emoji as icons. Keep KLineCharts, Pairlens and all financial/chart domain code unchanged unless the task explicitly calls for chart work.

### 5. Implement a coherent interface, not a cosmetic patch

- Reuse central tokens and primitives. Remove accidental per-page drift when touching the relevant surface, but avoid broad unrequested refactors.
- Include real data and long Persian strings during layout testing.
- Check loading, empty, stale-data, error, disabled, focused, hovered, selected, open-popover/dialog and narrow-width states as applicable.
- Preserve feature affordances and information density. Do not hide columns or tools just to achieve a cleaner screenshot.
- Use CSS logical properties and the existing project number/digit formatters. Follow the existing UI guard for fixed numeric slots and RTL isolation.
- Avoid blur-heavy/glow-heavy surfaces, perpetual motion and effects that increase repainting. Preserve useful animations and respect reduced motion.

### 6. Validate the real browser

At minimum for meaningful UI work:
- capture before/after at 1366×768 and one larger viewport (1600×900 or 1920×1080);
- confirm layout, clipping, overflow, focus-visible, keyboard navigation, RTL, numeric column alignment and menu/dialog positioning;
- verify all existing controls still work and route navigation is unchanged;
- inspect browser console and failed network/API calls;
- run relevant Vitest tests, `npx tsc -b`, and `npm run build`; comply with `AGENTS.md` requirements for the full test gate and server state;
- when the change could affect scroll/animation/rendering, compare a repeatable baseline rather than asserting performance from a screenshot.

### 7. Required completion report

Include:
1. commit(s) and files changed;
2. UI decisions and reused/new components;
3. before/after screenshot locations and viewport sizes;
4. tests/build results;
5. performance measurements if relevant;
6. regressions, limitations and unresolved items.

**Do not mark the task complete without real-browser visual evidence.** A green build is necessary but does not prove a modern, consistent or usable interface.
