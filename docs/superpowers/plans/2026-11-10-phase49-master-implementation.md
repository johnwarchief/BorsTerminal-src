# Phase 4.9.1 — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Phase 4.9.1 with verified historical-data evidence, a new Seed Candidate, and a three-lane CI where Python is data/build tooling only.

**Architecture:** Three independent workstreams. Plan A migrates CI and proves zero-Python runtime. Plan B captures independent reference data and produces step/symbol evidence ledgers. Plan C backfills, rebuilds the Seed Candidate, runs parity, and produces the eight required deliverables. Plan A can run in parallel with B; C starts after B's capture import and ledgers exist.

**Tech Stack:** Go 1.26 (CI 1.27.3), Python 3.12, Node 22, GitHub Actions, SQLite, Tauri v2.

**Spec:** [docs/superpowers/specs/2026-11-10-phase49-full-verification-design.md](../specs/2026-11-10-phase49-full-verification-design.md) — commit `9321eff4`.

## Global Constraints

- Branch: `mission/phase49-full-verification-python-ci-2026-11-10` from `f7fc8e8a`; `main` `9a919e82` untouched.
- No merge, tag, release, force push, visibility change, or operational-DB overwrite.
- Python is allowed only for data engineering, research, offline validation, and build tooling; production runtime remains Tauri v2 + Go + SQLite.
- No fabricated data, no threshold changes, no weakened asserts, no skipped/ignored failures, no hand-edited goldens.
- Raw reference captures and DB files never enter Git; only SHA-256, source, capture date, row counts, series type, normalization method.
- All tests run on isolated copies; only PIDs started by the test may be killed.
- Every committed number must cite an `evidence/*.json` file with SHA-256.
- Verdict vocabulary: `PASS`, `FAIL`, `BLOCKED`, `NOT_MEASURED`, `INSUFFICIENT_EVIDENCE`; final verdict is `PHASE49_COMPLETE_DATA_READY` only if every required criterion passes, otherwise `PARTIAL_WITH_EXPLICIT_BLOCKERS` or `BLOCKED_BY_SOURCE_GAPS`.

## Plan Files and Order

1. **Plan A — CI Migration & Zero-Python:** [2026-11-10-phase49-ci-migration.md](2026-11-10-phase49-ci-migration.md)
   - Independent of data capture. Must finish before final CI.
2. **Plan B — Reference Capture & Verification Ledgers:** [2026-11-10-phase49-verification-ledgers.md](2026-11-10-phase49-verification-ledgers.md)
   - Capture starts first because it feeds verification and backfill.
3. **Plan C — Backfill, Seed Candidate & Final CI:** [2026-11-10-phase49-seed-candidate.md](2026-11-10-phase49-seed-candidate.md)
   - Depends on B's import (Task B3) and symbol/step ledgers (B5–B9); Plan A's workflows are needed for final CI.

## Execution Checkpoints

| Checkpoint | Gate |
| --- | --- |
| C0 Baseline | branch, HEAD, clean tree, ignore rules; `git check-ignore` proof |
| C1 Capture imported | capture SHA/counts recorded; failures named; no raw in Git |
| C2 Ledgers built | 8,280 steps + 28 invalid; 6,103 symbol rows; rules guard green |
| C3 Backfill applied | 6 symbols full; freshness rows only; second run inserts 0 |
| C4 Seed candidate | integrity ok, zero duplicates, SHA/round-trip, parity |
| C5 CI green | final HEAD run; `CI-FINAL-RESULTS.json` with real links |
| C6 Report | 8 deliverables + SHA manifest; verdict justified |

## Shared Working Directories

- `_audit/phase49-full-verification/captures/` — raw reference (ignored)
- `_audit/phase49-full-verification/db/` — working DB copies (ignored)
- `_audit/phase49-full-verification/seed/` — new Seed Candidate (ignored)
- `_audit/phase49-full-verification/ledgers/` — intermediate CSV/JSON (ignored)
- `_audit/phase49-full-verification/evidence/` — small JSON summaries (tracked)
- `docs/opportunity-center/phase49/` — final deliverables (tracked)

## Baseline Task 0 (run before A/B/C)

**Files:**
- Modify: `_audit/.gitignore`
- Create: `_audit/phase49-full-verification/evidence/.gitkeep`

- [ ] **Step 1: Verify branch and clean tree**

Run:
```bash
git rev-parse HEAD
git branch --show-current
git status --short
```
Expected: HEAD `f7fc8e8a771e44b24687921851ccb8f61fda2ee3`; branch `mission/phase49-full-verification-python-ci-2026-11-10`; no output from status.

- [ ] **Step 2: Add explicit ignore rules**

Append to `_audit/.gitignore`:
```gitignore
/phase49-full-verification/captures/
/phase49-full-verification/db/
/phase49-full-verification/seed/
/phase49-full-verification/logs/
/phase49-full-verification/ledgers/
```

- [ ] **Step 3: Prove the rules**

Run:
```bash
git check-ignore -v _audit/phase49-full-verification/captures/x.json
git check-ignore -v _audit/phase49-full-verification/seed/market.db
git check-ignore -v _audit/phase49-full-verification/ledgers/steps.csv
```
Expected: each path matches an ignore rule. If any path is not ignored, stop and fix the pattern before capture.

- [ ] **Step 4: Commit**
```bash
git add _audit/.gitignore
git commit -m "chore(phase49): ignore raw verification capture and working DB paths"
```

## Execution Handoff

After all three plans are complete and the final CI run is recorded, offer the owner the integration decision. Do not merge, tag, or release in this phase.
