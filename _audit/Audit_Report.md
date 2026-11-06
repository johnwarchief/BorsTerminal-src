# Forensic Audit & Fix Report

## 1. Repository & Architecture Verification
- **Branch:** `main` (Verified)
- **Version:** `1.0.78` (Verified across 6 anchors using `dev/version_anchor_guard.py`)
- **Backend Architecture:** Verified FTS engine at `api/chart.py` and `api/market.py`, including `price_basis.py` for Candle Data.
- **Frontend Architecture:** Verified `frontend/src/features/master/lib/strictGates.ts`, `weeklyFromFts.ts`, and `ftsFunnel.ts`.

## 2. Rule Extraction & Findings
Based on the tests and `OWNER_RULINGS.md`:
- **Weekly Trend Rules:** 
  - Weekly Down/Neutral -> `REJECT`
  - Weekly Up -> `PERMITTED`
- **Daily Rules inside Weekly Up:** 
  - Daily Up -> `JET_OR_PULLBACK_HOLD`
  - Daily Down -> `FIB_CHOCH_STEP_ENTRY`

## 3. Findings & Patches Applied

### 1. FTS Trend Classification Bug (Phase 12 / Dow Theory vs V-Bottom)
**Issue:** `dev/fts_trend_fixtures_v1075.py` was failing on the V-bottom scenario. The stateful Dow Theory logic `_fts_classify_trend` in `api/chart.py` was too strict: it refused to flip to `up` on a `HH + HL` sequence unless the structural High was broken, which caused V-bottom setups to incorrectly register as `down`.
**Fix:** Modified `_fts_classify_trend` to correctly merge Dow Theory bounds with immediate sequence recognition:
- If the last 2 pivots are `HH + HL`, it immediately recognizes `up` (V-bottom).
- If the last 2 pivots are `LH + LL`, it immediately recognizes `down`.
- If mixed (e.g. `LH + HL`), it falls back to the structural `struct_trend`. This ensures a small `LH` inside an uptrend does not flip the trend to `range` or `down` if the structural low is intact (fulfilling the user's explicit rule).
**Validation:** Both `fts_trend_fixtures_v1075` and all 20 tested real-market symbols (e.g., فولاد, خودرو) passed successfully with exact mappings.

### 2. Tape Smart-Money Test Desync
**Issue:** `dev/tape_smartmoney_v1074.py` was failing because it strictly looked for `const FILE_FILTERS = [...]` in `ftsFunnel.ts`. This variable was historically refactored into `PRESET_ENTRY` but the test wasn't updated.
**Fix:** Patched the test to look for the new `PRESET_ENTRY:` which verifies the exact same 5-stage entry funnel constraint.

### 3. Close vs Last & Adjustment Anchors (Phase 5/6)
**Verification:** Code correctly implements `B2`: Display uses `LAST`, but `adjustment_anchor` explicitly uses `CLOSE`. The `test_contract_b2` (which runs in `run_all_tests.py`) passed successfully, proving `last/closing are separate columns; no fabricated last, anchor untouched`.

## 4. Final Delivery
- Unit tests (`dev/run_all_tests.py`) successfully pass.
- Frontend built successfully (`npm run build`).
- `PyInstaller` successfully packaged the backend.
- `Inno Setup` compiler created the final Windows Desktop Installer using `AppVersion=1.0.78`.

**Artifacts Generated:**
- **Installer:** `C:\Users\PCMOD\Desktop\BorsTerminal\installer\out\BorsTerminal_Ultimate_Setup_v1.0.78.exe`
- **Standalone Package:** `dist\BorsTerminal_Ultimate\`
