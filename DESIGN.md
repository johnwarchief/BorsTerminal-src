---
name: BorsTerminal — بازار (v2)
description: Persian RTL trading terminal board — brass-dark, dense operational table, borders over shadows
colors:
  bg: "#101215"
  panel: "#15181c"
  panel-2: "#1a1e23"
  panel-3: "#20252b"
  line: "#2a2f36"
  line-strong: "#363d46"
  text: "#e2ddd2"
  text-2: "#a9a396"
  text-3: "#908a7e"
  accent: "#c9a45c"
  accent-2: "#55bda8"
  accent-ink: "#171307"
  up: "#4fbd8c"
  down: "#e07480"
  flat: "#8f8a80"
  warn: "#d3a04a"
  light-bg: "#efece4"
  light-panel: "#fbf9f5"
  light-line: "#ddd6c8"
  light-text: "#1c1a16"
  light-accent: "#94651a"
typography:
  body:
    fontFamily: "Vazirmatn, Tahoma, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
  row:
    fontFamily: "Vazirmatn, Tahoma, sans-serif"
    fontSize: "11px"
    fontWeight: 400
  row-num:
    fontFamily: "Vazirmatn, Tahoma, sans-serif"
    fontSize: "11px"
    fontWeight: 600
  brand:
    fontFamily: "Vazirmatn, Tahoma, sans-serif"
    fontSize: "12.5px"
    fontWeight: 800
  micro:
    fontFamily: "Vazirmatn, Tahoma, sans-serif"
    fontSize: "9px"
    fontWeight: 400
rounded:
  xs: "2px"
  sm: "3px"
  md: "4px"
spacing:
  xxs: "4px"
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
components:
  tape-chip:
    backgroundColor: transparent
    textColor: "{colors.text-2}"
    rounded: "{rounded.sm}"
    height: "22px"
    padding: "0 7px"
  tape-chip-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.sm}"
    height: "22px"
    padding: "0 7px"
  board-row:
    backgroundColor: transparent
    textColor: "{colors.text}"
    height: "30px"
    padding: "0 8px"
  board-row-selected:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.text}"
    height: "30px"
    padding: "0 8px"
  rail-item:
    backgroundColor: transparent
    textColor: "{colors.text-2}"
    rounded: "{rounded.sm}"
    height: "30px"
    padding: "0 8px"
  rail-item-active:
    backgroundColor: "{colors.panel-3}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: "30px"
    padding: "0 8px"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
---

# BorsTerminal — بازار (v2)

## Overview

An **operate** surface: a dense Persian RTL market board that a trader reads in seconds at market open. The visual language is brass on near-black: quiet panels, hairline borders, one warm accent for selection and structure, red/green reserved for price direction. Density is the feature — 30px rows by default, small type, tabular Persian numerals, no ornament that costs a row. Source of truth: the approved v2 prototype market page (`Desktop\BorsTerminal_migration_v2`, served at 5302) and its live-data preview (`_audit/preview/market_live`, 5303).

## Colors

Dark brass is the default; `data-theme="light"` is the second committed world. Both are normative — never invent a third.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#101215` | `#efece4` | app canvas |
| `panel` | `#15181c` | `#fbf9f5` | strips, toolbars, drawers |
| `panel-2` | `#1a1e23` | `#f4f1e9` | row hover, popovers |
| `panel-3` | `#20252b` | `#eae5da` | active nav, toggles |
| `line` | `#2a2f36` | `#ddd6c8` | hairlines between regions |
| `line-strong` | `#363d46` | `#c7bead` | inputs, focused borders |
| `text` | `#e2ddd2` | `#1c1a16` | primary text |
| `text-2` | `#a9a396` | `#57524a` | secondary text |
| `text-3` | `#908a7e` | `#6f695d` | captions, counts, micro |
| `accent` | `#c9a45c` | `#94651a` | active chip, sort mark, brand |
| `accent-2` | `#55bda8` | `#0f7a68` | sparklines, secondary highlight |
| `up` / `down` | `#4fbd8c` / `#e07480` | `#0d7a45` / `#b02c37` | price direction only |
| `warn` | `#d3a04a` | `#8a5a10` | attention without alarm |
| `flat` | `#8f8a80` | `#6d675c` | zero change |

Soft variants exist for row washes: `--up-soft`, `--down-soft`, `--accent-soft` (≈10–12% alpha of the base).

## Typography

Single family: **Vazirmatn** (served from `/vendor/fonts`, weights 300/400/600/700/900). No second display face.

- Body 12.5px / 400; brand title 12.5px / 800; brand sub 7.5px with 0.16em tracking, Latin, LTR.
- Board rows: 11px (compact), 12px (normal), 13px (comfortable) — driven by the density token, never per-component.
- Numeric cells: 600 weight, `font-variant-numeric: tabular-nums`, Persian digits only (helpers in `shared/lib/fa.ts`).
- Micro text (rail status, clock, chip counts): 9–10px, `text-3`.
- Sorting marks and counts ride the same line as the label; no separate badges row.

## Layout

- Two columns: rail + workspace. Rail is 208px open, 52px collapsed (`--rail-w`); the workspace never scrolls horizontally as a whole — only the board does.
- Topbar: one 44px row — market state dot, date, command/search, tabs. Micro type, hairline bottom border.
- Market status strip: three persisted modes — `full` (index hero + breadth + retail card + client split, ≈134px at 1366 and ≈158px at ≥2200px), `ribbon` (one 33px line of facts), `minimal` (one line).
- Board toolbar: search + profile (column set) + density + columns popover + saved views + visible-row CSV export; `padding: 0 12px`, content height (~40px). Below 1500px the auxiliary button labels collapse to their accessible icons.
- Tape bar: one 33px row, seven filters + «همه», **multi-select with explicit AND/OR**, counts over the visible base.
- Board: CSS grid, sticky 27px head, rows full-width with `--row-h`; default density `compact`.
  - Densities: compact 30px / 11px, normal 36px / 12px, comfortable 44px / 13px.
  - ≥2200px: compact 34/12, normal 40/13, comfortable 48/14; symbol column widens (`--sym-max` 250/270/290).
- Quick drawer: right-side panel over the board (panel-2), opens on row click; never a centered modal.
- `prefers-reduced-motion` disables transitions — the app must remain usable with motion off.

## Elevation & Depth

Depth comes from **borders and panel steps**, not shadows. Regions are separated by 1px `line`; inputs and focus use `line-strong`. One exception: popovers and the quick drawer may carry a single large, soft shadow to lift them above the board. Never stack shadows on rows, chips, or toolbars.

## Shapes

Square-ish operational geometry: radii 2px (dots/badges), 3px (chips, inputs, nav), 4px (panels, drawer). No pills, no capsule buttons, no organic blobs. Status uses 6px dots; tape badges 6px dots or 9px square chips.

## Components

- **Rail item** — 30px, icon 16px, label 11px; active = `panel-3` with full-strength text; collapsed shows icons only with tooltips.
- **Market clock** — 6px status dot + state label + date, 10px; the dot color carries state, never a colored pill.
- **Status strip** — three modes as above; the mode control is three small buttons (کامل / نوار / کمینه) persisted per user.
- **Toolbar buttons** — 28px high, 1px `line` border, `panel` background; hover raises border to `line-strong`; no filled primary buttons inside the board.
- **Tape chip** — 22px; label + count (count in `text-3`, 10px); each active chip is `accent` fill with `accent-ink` text; multiple chips combine through the visible AND/OR control and «همه» clears them.
- **Board head** — 27px sticky; labels 10.5px `text-3`; sortable labels show ▲/▼ in `accent`; numbers right-aligned in RTL.
- **Board row** — 30px; hairline bottom border at 50% `line`; hover and selection use the `panel-2` wash.
- **Symbol cell** — two lines: code + badges on line one, name in `text-3` 9px on line two; badges cap at 2 (compact), 3 (normal), 4 (comfortable).
- **Badges** — 6px dots or 9px chips; hover opens a preview card with kicker, time, reasons, source; a stale badge shows a 4px age dot.
- **Quick drawer** — panel-2, 1px `line`, opens over the board; sections separated by hairlines; close on Escape/backdrop and return focus to the originating control. Selection and history use `ins_code`, not the display symbol. Order-book depth from an older session is marked «کهنه», its rows are not labelled live, and current-session totals are withheld.
- **Saved board view** — a named popover with one-line input, apply and delete actions; saves filters, chips, AND/OR, columns, query, sort, density and polling. Escape/apply return focus to the trigger; delete moves focus to the name input.
- **CSV export** — only the currently filtered and sorted visible rows, with the table’s own labels, UTF-8 BOM, `sep=;`, and `#` provenance lines for source, board day, sync, revision, profile, sort, query, filters and row count.

## Do's and Don'ts

- **Do** keep every measured value in this file; if a new value is needed, add a token instead of hardcoding.
- **Do** show real data or a labeled gap. Counts come from the visible base (asset filter applied), matching the prototype.
- **Do** use the multi-select tape filters with visible AND/OR; the owner’s 2026 board ruling supersedes the prototype’s single-select behavior.
- **Do** keep the board readable at 1366×768 with compact density; test 1366/1920/2560 before calling a page done.
- **Do** keep one tabbable board row (roving focus: ArrowUp/Down, Home/End; Enter/Space opens); Ctrl/Cmd+K closes the drawer if needed and focuses the search. One row shrinks away ⇒ clamp focus to a remaining row.
- **Don't** add gradients, glassmorphism, glow, or colored pills.
- **Don't** use shadows for hierarchy inside the board; borders and panel steps only.
- **Don't** type Persian digits by hand — always through the digit helpers.
- **Don't** invent thresholds, percentages, or placeholder numbers; an unwired column is hidden from the default profile and marked «وصل نیست» in the columns popover.
- **Don't** change the density tokens per component; density is a single surface-level switch.
