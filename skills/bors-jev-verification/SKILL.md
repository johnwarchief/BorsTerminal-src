---
name: bors-jev-verification
description: Legacy Jev verification workflow retained for fallback/migration comparison after the owner's 2026-10-10 request to replace Jev with Laya. Do not treat as the canonical automatic workflow; use only for Jev-specific fallback or explicit comparison.
---

# Bors Jev verification (legacy two-tool close-out)

> **Status as of 2026-10-10:** the owner has since requested migration from Jev to Laya. This document records the prior rule and must not override the newer request. Retain the old tools only until a replacement is tested; do not claim the migration has happened without actual Qoder configuration and end-to-end evidence.

## Overview

Live browser evidence remains required; however, this Jev-specific judgment/browser pairing is now a legacy fallback. Prefer Laya only after its actual decision and browser action are verified. Until then, use existing Playwright/CDP checks and explicitly report the Laya migration as unverified.

## The two halves and their order

| Half | Tool | Answers | Covered by |
|---|---|---|---|
| Judgment | `tools/pilot_ctl.py` | which of two options, am I stuck, is this destructive | this skill |
| Evidence | `tools/jev_ui_check.mts` | did it actually render in the fresh or shipped bundle | `bors-live-ui-check` |

Call the pilot **before** committing to a branch of work, and the browser **after** the code
exists. The pilot ranks; it does not outrank measured evidence - it has picked paths a
database check later disproved, and has been right at low confidence on paths that worked.

## Half 1: the pilot (`tools/pilot_ctl.py`)

Interpreter verified on 2026-09-28: `jev_pilot 0.1.1` imports under `py -3.14`. The project's
build venv (`.venv/Scripts/python.exe`) does **not** have it and must not get it - QA-only
packages stay out of the release interpreter. Confirm with
`py -3.14 -c "import jev_pilot"` before the first call instead of trusting this line.

```bash
PYTHONIOENCODING=utf-8 py -3.14 tools/pilot_ctl.py arbitrate \
  --context "what is being decided, in prose" \
  --option "a=prose description of option A" \
  --option "b=prose description of option B"
```

Other modes: `stuck --history failures.txt` (step summaries - use it before another retry, not
after the fourth one), `guard --action "..." --state "..."` (before anything destructive).

Auth is the `TYPESAFE_API_KEY` env var, read before `~/.jev_pilot/config.json`. Do not use
`save=True`: on Windows its 0600 is a no-op, and a later `icacls /inheritance:r` attempt left
that config file unreachable to everyone including its owner.

### Prose-only gate (mechanical, not convention)

Owner ruling: **no source code is sent to `api.typesafe.ai`.** `pilot_ctl.py` enforces it by
rejecting any `context` or `option` containing `{`, `}`, `;`, a `<tag>`, `=>`, `&&`, `||`,
`self.`, `this.`, a line starting with `import|from|def|class|const|let|var|function|return|export`,
or more than 1200 characters. The refusal looks like a tool error, not a policy message.

- Rejected: `a=setField('clock','minTradeCount', e.target.value); update the modal`
- Accepted: `a=put the two dials in the filter settings panel and let only the table's own
  evaluator read them - the engine stays strict`

A semicolon used purely as punctuation trips the gate too; separate clauses with an em-dash or
comma. Describe the option as *what the owner sees*, never as the diff.

### Reading the verdict

JSON out: `winner`, `confidence`, `probabilities`, `risk`. Low confidence means a weak second
opinion, not a veto, and never permission to skip the browser check. Quote the real numbers
when reporting the decision, in as few words as possible.

## Half 2: pairing, so nothing closes half-done

1. Frame the choice in owner terms (what changes in the table, the badge, the chart), then
   arbitrate. Do not hand the owner an architecture question.
2. Implement.
3. `npm run build` - the harness serves `dist`, so a stale bundle reproduces bugs already
   fixed in source.
4. Run the live check per `bors-live-ui-check` (JEV_CHROME, `MSYS_NO_PATHCONV=1`, hash route)
   and read its own JSON (`href`, `bodyText`) before believing any testid.
5. If the symptom is a missing or zero value rather than a broken layout, run
   `bors-installed-vs-dev-diagnosis` first - that has repeatedly been the installed app's
   data, not the code.
6. Report differences as an RTL table, name the build each claim was proven on (installed exe
   vs source), and state what stayed unproven.

## Ports: discover, do not recall

Local docs disagree on which port is which (installed-app server variously 8000/8001, dev
backend 8001/8002). Never conclude from a remembered port: a wrong port fails every
`/api/*`, and the harness then reports features as absent. Read `vite.config`'s
`server.proxy` target, the uvicorn startup line, and the installed app's own log each time, and
say in the report which backend the evidence came from.

## Failure to cause

| Symptom | Cause | Action |
|---|---|---|
| `ModuleNotFoundError: jev_pilot` | wrong interpreter | use `py -3.14`, not `.venv` |
| input refused | prose gate tripped (`;`, `{}`, code-looking word) | rewrite as prose with em-dashes |
| auth failure | `TYPESAFE_API_KEY` absent in this shell | export it; never re-add `save=True` |
| every testid `null` | the harness broke, not the app | `bors-live-ui-check` steps 2-4 |
| pilot contradicts the DOM | evidence wins | ship the evidence, record the dissent |

## Acceptance

A unit of work is done only when both halves actually ran in it and the numbers and verdicts
are quoted from their real output. If context is about to run out, commit the plan plus a
self-contained hand-off prompt to the repo rather than shipping half-verified work.
