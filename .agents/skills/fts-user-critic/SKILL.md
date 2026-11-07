---
name: fts-user-critic
description: Reads the primary FTS booklet (docs/جزوه FTS.pdf, 34 pages) and FTS.CHART_3.pdf (4 pages) completely, applies OWNER_RULINGS, then critiques the current BorsTerminal fundamental and chart UI as an end user with page-cited, screenshot-backed findings. Use for "نقد FTS"، "بررسی کاربری بنیادی/چارت"، "تطبیق با جزوه"، indicator naming/formula/period-detail audits, or any request to judge the app from a real user's perspective.
argument-hint: "[fundamental|chart|all] [symbol...]"
---

# FTS User Critic

## Overview

Act as a demanding but fair end user of BorsTerminal who has the primary FTS
booklet in hand. Read the primary sources completely, inspect the live UI, and
report where the product fails to let a user understand or trust the five
fundamental indicators or the FTS chart. The deliverable is evidence, not
opinion: every finding cites a booklet page or an explicit owner ruling, and
shows the actual UI state.

## Non-negotiables

- **Primary sources first:** `docs/جزوه FTS.pdf` (34 image pages) and
  `docs/FTS.CHART_3.pdf` (4 pages). Read **all** pages visually. Transcriptions
  are search aids; when they disagree with the PDF, the PDF wins.
- **Precedence:** booklet/chart → explicit `docs/fts-notes/OWNER_RULINGS.md`
  ruling → derived specs/audits → transcriptions. Read
  `docs/README.md` and `docs/fts-notes/README.md` before judging.
- **No invented rules or thresholds.** If the source is silent or ambiguous,
  write `AMBIGUOUS` and do not report it as a defect.
- **Live evidence only.** Do not claim a UI behavior, number, contrast, theme,
  or missing detail without a screenshot, DOM/testid, or API field captured from
  the current checkout.
- **Critique as a user, verify as an auditor.** "I cannot answer X from this
  screen" is a valid finding; "the formula is wrong" needs the page and the
  actual number.
- **No code changes by default.** This skill produces a report and a prioritized
  fix list. Only edit code when the owner explicitly asks for fixes.
- Date and version every report; never reuse a stale audit as current truth.

## Inputs and outputs

Inputs:
- Scope: `fundamental`, `chart`, or `all` (default `all`); optional symbols.
- App URL if a dev server is already running; otherwise start one (see below).
- Optional: old app for comparison (`frontend/`), current v2 (`frontend-v2/`).

Output directory: `_audit/rebuild/fts-critic/<YYYY-MM-DD>/` containing:
- `booklet-ledger.md` — one row per booklet page and per chart page.
- `screenshots/` — 1366×768 and 1920×1080, both app themes, table/cockpit/chart.
- `evidence.json` — DOM testids, API fields, exact values.
- `report.md` — Persian critique using `references/report-template.md`.

## Workflow

### 1. Baseline

1. Record branch, `git rev-parse HEAD`, date, and scope.
2. Identify whether the served app is this checkout (check the Vite module path
   or a known new label). Never audit a different worktree by accident.
3. Read `docs/README.md`, `docs/fts-notes/README.md`, and
   `docs/fts-notes/OWNER_RULINGS.md` fully.

### 2. Read the primary sources completely

1. Read `docs/جزوه FTS.pdf` **all 34 pages**. Use `Read` with page ranges
   (e.g. `pages:"1-17"`, then `"18-34"`). The booklet has no text layer, so
   visual reading is mandatory. If PDF rendering is unclear, render pages:
   `python .agents/skills/fts-user-critic/scripts/render_pdf_pages.py --pdf
   "docs/جزوه FTS.pdf" --out "_audit/rebuild/fts-critic/<date>/pages/booklet"
   --pages 1-34 --dpi 120`
   then Read each PNG.
2. Read `docs/FTS.CHART_3.pdf` **all 4 pages** (it has text; also verify the
   visual layout).
3. For search only, grep `docs/fts-notes/transcription_*.md` and
   `docs/fts-notes/jozve_FTS_handwritten_pages_*.md`. Do not treat a transcript
   as authority.
4. Write `booklet-ledger.md` with one row per page:
   `page | section | rule/claim (short) | formula/threshold | owner override | ambiguity`.
   Every page must appear, even if the note is "cover/no rule".
5. Extract the five fundamental rules (F1–F5), the chart rules (T1) and the
   selection rules (S) that the UI claims to implement.

### 3. Load owner expectations

Read `references/owner-expectations.md`. Treat each item as an explicit test
case, even when it is a UX expectation rather than a booklet rule. The current
owner expectations include:
- EPS must expose each period's growth amount and percentage.
- Indicator 1's 1a and 1b must be checked and shown separately and correctly.
- Indicator 1 must show this period's sales and the previous comparable period.
- Light/dark must follow the app theme; no separate data-surface theme.
- Indicator 4 is named «پتانسیل سود تا آخر سال» and its headline is the final
  potential-profit percentage from the formula.
- Indicator 3 is named «حاشیه سود ناخالص».
Record any conflict between an owner expectation and the booklet; do not
silently harmonize them.

### 4. Inspect the app as a user

1. Discover routes/components from `docs/AGENT-INDEX.md`,
   `frontend-v2/src/features/fundamental/`, and the chart/FTS feature directory.
2. Start the app only if needed. Use a free port; do not kill another worktree's
   server. Verify the served checkout before capturing.
3. Load `playwright-cli` (project skill) for browser control and screenshots;
   load `impeccable` for visual/UX heuristics when judging hierarchy, clarity,
   density, theming, and motion.
4. Capture at least:
   - Fundamental table: compact + comfortable, paper/ink or app theme as
     implemented, 1366 and 1920.
   - Symbol cockpit: a normal producer, a holding/bank, and a data-gap or
     not-applicable symbol; top, middle, and bottom panels.
   - Chart FTS tab: weekly gate, trend, pullback/fib/CHoCH/range/hourglass or
     whichever layers are visible; at least two symbols with different trends.
   - Settings drawer and theme switch.
5. For each capture, record the URL, viewport, theme, symbol, visible values,
   relevant `data-testid`s, and API payload fields in `evidence.json`.
6. Use the user's questions as navigation: "Can I see why?", "Can I see the
   previous period?", "Can I see the final percentage?", "Does the theme follow
   the app?", "Is 1a/1b separate?", "Is EPS growth per period?"

### 5. Compare and classify

For every indicator/rule, fill a scorecard:
`name | source page | formula | threshold | inputs shown | period detail |
status semantics (pass/fail/N/A/unknown) | why/evidence | verdict`.

Findings use three severities:
- **Blocker:** wrong rule/number/name/semantics, fabricated value, missing 1a/1b,
  or a user cannot reach the required conclusion at all.
- **Major:** necessary detail is absent or buried (previous period, per-period
  growth, why, final potential %), or theme/density behavior contradicts the
  owner's expectation.
- **Minor:** clarity, ordering, labeling polish, redundant text, small
  inconsistency that does not change the conclusion.

Every finding must include:
`id | severity | area | source (page/ruling) | expected | actual | evidence
(screenshot/DOM/API) | user-voice critique | suggested direction | confidence`.
Do not propose a formula or threshold not present in the sources.

### 6. Report

Use `references/report-template.md`. Write in Persian, concise and specific.
Start with the top blockers a real user would hit, not with a code summary.
Include:
- one-paragraph verdict;
- the source ledger summary;
- five-indicator scorecard;
- findings grouped by severity with evidence links;
- chart FTS section;
- owner-expectation checklist (pass/fail/not-tested);
- source conflicts and ambiguities;
- prioritized fix list (P0/P1/P2) with the smallest user-visible outcome;
- what was tested, what was not, and the exact checkout/date.

Finish in chat with the top 3 blockers and a link to `report.md`.

## Critique rubric (what a real user needs)

For each fundamental axis, the user should be able to answer without opening the
booklet:
1. What is the rule and the threshold?
2. What are the inputs for **this** period and the **previous comparable** period?
3. What is the computed value, and how far is it from the threshold?
4. Did it pass/fail/N/A/unknown, and **why**?
5. For EPS: what was each period's EPS and period-over-period growth %?
6. For indicator 1: what are 1a and 1b separately; is 1b applicable? what is the
   combined verdict?
7. For indicator 4: what is the final potential-profit % (the headline), and
   what are the sales and market-cap inputs?
8. For indicator 5: what is the pricing regime and the sector rule?
9. Does the theme follow the app, and is the status readable in both themes?

For the chart, the user should be able to answer:
- What is the weekly gate and why is entry allowed/rejected?
- What is the trend structure and the active branch?
- What setup is active (pullback/jet/fib/CHoCH/range/hourglass/point-hunt)?
- What level triggers entry/exit, and is it drawn?
- Which claims are source rules and which are implementation additions?

## Guardrails

- Never present a derived spec as the booklet. Cite the booklet page; if using
  `FTS-RULE-ALGORITHM-MAP.md`, label it derived.
- Never say "PASS" for visual/UX without a screenshot and a measured effect.
- Do not conflate unknown/data-gap with fail; do not zero-fill missing values.
- Do not criticize a rule the booklet does not contain without marking it as an
  owner/UX expectation.
- If the current app and the old app disagree, report both and label which one
  is the migration target.
- Leave the repo clean except the evidence directory; no push.

## Resources

- `references/source-precedence.md` — where each source sits and how to resolve
  conflicts.
- `references/owner-expectations.md` — the owner's explicit examples and the
  key F1–F5 thresholds.
- `references/report-template.md` — Persian report structure and finding fields.
- `scripts/render_pdf_pages.py` — render PDF pages to PNG for visual reading.
