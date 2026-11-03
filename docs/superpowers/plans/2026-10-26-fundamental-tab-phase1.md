# Fundamental Tab Completion (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the fundamental tab exactly match the owner-approved five-indicator methodology: remove non-companies, use FS revenue for service/financial/holding companies, enforce the 1b veto everywhere, keep EPS evidence honest, relabel margins/valuation, restrict mandatory industries to the booklet's three, and remove technical badges while keeping assembly/capital-increase and risk filters.

**Architecture:** One engine path (`fts_engine` + `api/fundamental`) produces the card and the screen rows; the frontend only renders fields and reasons. New logic lives in small helpers (`classify_identity`, `ind1a_fs_growth`, `axis1_state`, `evidence_label`, `margin_tier`, `acceptance_path`) and is covered by offline temp-DB tests plus a read-only live audit. No network calls in Phase 1.

**Tech Stack:** Python 3.12+ / SQLite / FastAPI, React 18 + TypeScript + Zod + Vitest, existing `dev/run_all_tests.py` suite runner.

**Spec:** `docs/superpowers/specs/2026-10-26-codal-fundamental-auto-update-design.md` (sections 3.3–3.6 and Appendix 3 are authoritative).

## Global Constraints

- Branch: `mission/fts-indicator-engineering`; never push, never touch `main`/release tags.
- Preserve the two tracked dirty files: `_audit/app_log.txt` and `dev/fixtures/fts_v10_payloads.json`. Stage only mission files.
- Tests run on a **temp DB**; never write operational `market.db` in tests. Live audits open it read-only (`file:...?mode=ro`).
- Never fabricate a value to fill a gap. Missing/consolidated/insufficient data is `N/A` with a machine-readable reason.
- Universe: 153 non-companies are excluded; ~682 real companies + 57 monthly-only. Strict remaining gaps after backfill: **11 EPS**, **59 margin**, **20 monthly**. 226 production EPS cases are consolidated-only and stay N/A.
- No third-party data source (Rahavard/TradersArena/brsapi/NADPCO); only CODAL + TSETMC.
- No technical badges in the fundamental tab; technical vetoes do not affect fundamental row verdicts. Risk filters (M141/liquidity) stay.
- Assembly near = badge + veto with reason; capital increase = badge only.
- Persian digits in any generated report must come from a script reading artifacts.
- Every task ends with a test run and a commit.

---

## File Structure

- `fts_engine.py` — identity/universe classifier, bulk rows, sector tokens, EPS/margin/valuation helpers.
- `api/fundamental.py` — card engine (`evaluate_v10`), new `ind1a_fs_growth`, N/A/evidence/tier labels, screen endpoint.
- `api/screener.py` — assembly veto and technical funnel stay, but fundamental consumers ignore technical veto fields.
- `bors_config.py` / `fts_thresholds.json` — mandatory/free sector defaults.
- `frontend/src/features/fundamental/api/useFtsScreen.ts` — row schema fields for the new labels/reasons.
- `frontend/src/features/fundamental/ui/FtsScreenTable.tsx` — remove technical badges, render N/A/evidence/tiers, keep assembly/capital.
- `frontend/src/features/fundamental/components/FtsCard.tsx`, `FtsDrillDown.tsx` — same labels/reasons.
- `frontend/src/features/fundamental/api/useFtsConfig.ts`, `ui/FtsSettingsDrawer.tsx` — three mandatory industries.
- `dev/test_fts_universe_v11.py`, `dev/test_ind1_fs_path_v11.py`, `dev/test_ind1b_parity_v11.py`, `dev/test_fts_na_v11.py`, `dev/test_fts_evidence_v11.py`, `dev/test_fts_margin_v11.py`, `dev/test_fts_ind4_v11.py`, `dev/test_fts_sector_v11.py` — offline tests.
- `dev/codal_fundamental_audit.py` — read-only live audit.
- `frontend/src/__tests__/fts-fundamental-badges.spec.tsx`, `frontend/src/__tests__/fts-fundamental-labels.spec.tsx` — UI tests.
- `dev/run_all_tests.py`, `docs/AGENT-INDEX.md` — gate/docs updates.

---

### Task 1: Exclude non-companies from the universe

**Files:**
- Modify: `fts_engine.py` (`company_profile`, `bulk_scan`, add `classify_identity`)
- Modify: `api/fundamental.py` (`evaluate_v10` applicable/verdict)
- Test: `dev/test_fts_universe_v11.py`

**Interfaces:**
- Produces: `classify_identity(symbol: str, sector: str, company_name: str, has_instrument: bool) -> dict` with keys `kind` (`company|non_company|fund`), `applicable: bool`, `reason: str`.
- `bulk_scan` rows gain `identity_kind`, `identity_reason`; non-companies are **not appended** to the output.
- `evaluate_v10` returns `applicable=False`, `verdict="FTS ندارد"`, `identity_kind="non_company"` for non-companies.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_universe_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fts_engine import classify_identity

CASES = [
    ("فولاد", "فلزات اساسي", "فولاد مباركه", True, "company", True),
    ("آگاه بازار", "", "", False, "non_company", False),
    ("آبين", "", "كشت و صنعت آبشيرين", True, "company", True),
    ("خیریه نمونه", "", "موسسه خیریه", True, "non_company", False),
    ("شپنا", "فراورده هاي نفتي", "پالايش نفت اصفهان", True, "company", True),
]
failed = 0
for sym, sec, name, inst, kind, applicable in CASES:
    got = classify_identity(sym, sec, name, inst)
    ok = got["kind"] == kind and got["applicable"] is applicable and got["reason"]
    print(("OK  " if ok else "FAIL"), sym, got)
    failed += 0 if ok else 1
print("FAILURES", failed)
raise SystemExit(1 if failed else 0)
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_universe_v11.py`
Expected: `ImportError: cannot import name 'classify_identity'`.

- [ ] **Step 3: Implement the classifier and wire it**

Add to `fts_engine.py` near `company_profile`:

```python
NON_COMPANY_TOKENS = (
    "صندوق", "اوراق", "اختيار", "اختیار", "حق تقدم", "حق‌تقدم",
    "خیریه", "شهرداری", "فدراسیون", "موسسه", "پرورشگاه", "وقف", "بنیاد",
)


def classify_identity(symbol, sector, company_name, has_instrument):
    """Universe gate: only real operating companies enter the FTS table."""
    sym = str(symbol or "").strip()
    sec = str(sector or "").strip()
    name = str(company_name or "").strip()
    if not has_instrument:
        return {"kind": "non_company", "applicable": False,
                "reason": "no_instrument"}
    text = norm_fa(sec) + " " + norm_fa(name)
    if any(norm_fa(t) in text for t in NON_COMPANY_TOKENS):
        return {"kind": "non_company", "applicable": False,
                "reason": "fund_or_non_operating"}
    if not sec and not name:
        return {"kind": "non_company", "applicable": False,
                "reason": "no_identity"}
    if fund_class_match(sec, name):
        return {"kind": "fund", "applicable": False, "reason": "fund"}
    return {"kind": "company", "applicable": True, "reason": ""}
```

In `bulk_scan`, after building `board_of`/`sector_of`/`cname_of`, compute `identity = classify_identity(key, sector, cname, key in board_of or bool(sector))`; if `identity["kind"] == "non_company"`, `continue`; add `identity_kind`/`identity_reason` to appended rows. In `evaluate_v10`, replace `applicable = (prof or {}).get("kind") != "fund"` with the same identity call (using `company_name`), and if non-company return `applicable=False`, `verdict="FTS ندارد"` with `identity_kind`.

- [ ] **Step 4: Run the test and the existing EPS ladder test**

Run: `python dev/test_fts_universe_v11.py` → all OK.
Run: `python dev/test_fts_v10_ladder.py` → unchanged pass.
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add fts_engine.py api/fundamental.py dev/test_fts_universe_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(fts): exclude non-company identities from the fundamental universe"
```

---

### Task 2: FS-based indicator 1 for service/financial/holding

**Files:**
- Modify: `api/fundamental.py` (add `ind1a_fs_growth`; use it in `evaluate_v10`)
- Modify: `fts_engine.py` (`bulk_scan` i1 path for non-production kinds)
- Test: `dev/test_ind1_fs_path_v11.py`

**Interfaces:**
- Produces: `ind1a_fs_growth(conn, symbol, profile, th=None) -> dict` with `monetary_pct: float|None`, `basis: "fs_interim"|"fs_annual"|None`, `period: str`, `months: int`, `pass: bool`, `data_gap: bool`, `reason: str`.
- `evaluate_v10.indicators["1"]["monetary"]["basis"]` and `bulk_scan` row `i1_basis` expose the basis.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_ind1_fs_path_v11.py
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.fundamental import ind1a_fs_growth

c = sqlite3.connect(":memory:")
c.execute("""CREATE TABLE financial_statements (
  symbol TEXT, title TEXT, period_end TEXT, period_months INTEGER,
  revenue REAL, is_consolidated INTEGER, is_audited INTEGER)""")
rows = [
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1405/06/31", 6, 1500.0, 0, 0),
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1404/06/31", 6, 1000.0, 0, 0),
  ("وبملت", "صورت مالی سالانه", "1404/12/29", 12, 2200.0, 0, 1),
]
c.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?,?,?)", rows)
prof = {"kind": "financial"}
r = ind1a_fs_growth(c, "وبملت", prof)
assert r["basis"] == "fs_interim", r
assert r["months"] == 6, r
assert abs(r["monetary_pct"] - 50.0) < 0.01, r
assert r["pass"] is True, r
c.execute("DELETE FROM financial_statements WHERE period_end='1404/06/31'")
r2 = ind1a_fs_growth(c, "وبملت", prof)
assert r2["data_gap"] is True and r2["reason"], r2
print("OK ind1 fs path")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_ind1_fs_path_v11.py`
Expected: `ImportError`/`AttributeError` for `ind1a_fs_growth`.

- [ ] **Step 3: Implement the FS growth helper**

```python
def ind1a_fs_growth(conn, symbol, profile, th=None):
    """Revenue growth from the income statement for service/financial/holding."""
    th = th or v10_thresholds()
    rows = conn.execute(
        "SELECT period_end, period_months, revenue, title FROM financial_statements "
        "WHERE symbol=? AND revenue>0 AND period_months>0 AND is_consolidated=0 "
        "ORDER BY period_end DESC", (symbol,)).fetchall()
    if not rows:
        return {"monetary_pct": None, "basis": None, "period": "", "months": 0,
                "pass": False, "data_gap": True,
                "reason": "هیچ صورت مالی غیرتلفیقی با درآمد ثبت نشده است."}
    by_key = {}
    for pe, months, rev, title in rows:
        key = (CP.canonicalize(pe) or "", int(months or 0))
        by_key.setdefault(key, _f(rev))
    # Longest interim first, then annual; require the same period one year earlier.
    interims = sorted([(k, v) for k, v in by_key.items() if 0 < k[1] < 12],
                      key=lambda kv: kv[0][0], reverse=True)
    annuals = sorted([(k, v) for k, v in by_key.items() if k[1] >= 12],
                     key=lambda kv: kv[0][0], reverse=True)
    for basis, candidates in (("fs_interim", interims), ("fs_annual", annuals)):
        for (pe, months), now in candidates:
            y, m, d = pe.split("/")[:3]
            prev = f"{int(y)-1}/{m}/{d}"
            prev_val = by_key.get((prev, months))
            if prev_val:
                growth = (now / prev_val - 1.0) * 100.0
                return {"monetary_pct": growth, "basis": basis, "period": pe,
                        "months": months,
                        "pass": growth >= th["monetary_growth_min"],
                        "data_gap": False, "reason": ""}
    return {"monetary_pct": None, "basis": None, "period": "", "months": 0,
            "pass": False, "data_gap": True,
            "reason": "دورهٔ مشابهٔ سال قبل برای صورت مالی موجود نیست."}
```

Wire it in `evaluate_v10`:

```python
if prof["kind"] in ("service", "financial", "holding") and not series:
    growth = ind1a_fs_growth(conn, symbol, prof, th=th)
else:
    growth = ind1a_monetary_growth(conn, symbol, series=series, th=th, profile=prof)
```

For `bulk_scan`, add a `fs_growth` map built once for the affected symbols and use it when `prof["kind"]` is in that set and `recs` is empty; add `i1_basis` to the row. Do not call the per-symbol helper inside the loop.

- [ ] **Step 4: Run tests**

Run: `python dev/test_ind1_fs_path_v11.py` → `OK ind1 fs path`.
Run: `python dev/test_fts_v10_ladder.py` → unchanged.

- [ ] **Step 5: Commit**

```bash
git add api/fundamental.py fts_engine.py dev/test_ind1_fs_path_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(fts): revenue growth from FS for service/financial/holding"
```

---

### Task 3: One 1b veto rule for card and screen

**Files:**
- Modify: `api/fundamental.py` (`axis1_pass`, add `axis1_state`)
- Modify: `fts_engine.py` (`bulk_scan` i1)
- Test: `dev/test_ind1b_parity_v11.py`

**Interfaces:**
- Produces: `axis1_state(monetary: dict, volume: dict) -> tuple[bool|None, str]` where `None` means data gap and the string is the reason.
- `bulk_scan` row gains `i1a_pass`, `i1b_pass`, `i1b_applicable`, `i1b_basis`, `i1_reason`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_ind1b_parity_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.fundamental import axis1_state

mon = {"pass": True, "monetary_pct": 55.0, "data_gap": False}
vol_down = {"applicable": True, "pass": False, "basis": "reported_quantity",
            "reason": "فروش تولیدی کم شده"}
vol_up = {"applicable": True, "pass": True, "basis": "reported_quantity"}
vol_na = {"applicable": False, "pass": False, "basis": "not_applicable"}
assert axis1_state(mon, vol_down) == (False, "فروش تولیدی کم شده")
assert axis1_state(mon, vol_up)[0] is True
assert axis1_state(mon, vol_na)[0] is True
assert axis1_state({"pass": False, "data_gap": True}, vol_up)[0] is None
print("OK 1b parity")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_ind1b_parity_v11.py`
Expected: `ImportError`/`AttributeError`.

- [ ] **Step 3: Implement the shared state and use it in both paths**

```python
def axis1_state(monetary, volume):
    if (monetary or {}).get("data_gap") or (monetary or {}).get("monetary_pct") is None:
        return None, (monetary or {}).get("reason") or "رشد ریالی قابل محاسبه نیست."
    if not (monetary or {}).get("pass"):
        return False, "رشد ریالی زیر کف است."
    v = volume or {}
    if v.get("applicable") is False:
        return True, ""
    if v.get("pass"):
        return True, ""
    return False, v.get("reason") or "رشد تولیدی/تناژ تأیید نشد."


def axis1_pass(monetary, volume):
    state, _ = axis1_state(monetary, volume)
    return bool(state)
```

In `bulk_scan`, replace `i1 = growth is not None and growth >= g_min` with the same state; set `i1 = None` for data gaps; for production companies, compute the volume dict from the existing monthly rows (reuse `ind1b_volume_growth` with the series; if performance is a problem, precompute a map once); add the new row fields. `evaluate_v10` already calls `axis1_pass`; switch it to `axis1_state` for the reason.

- [ ] **Step 4: Run the test and a card/screen parity check**

Run: `python dev/test_ind1b_parity_v11.py`
Run: `python dev/fts_screener_card_parity_v10.py`
Expected: the first OK; the parity script unchanged or updated for the new `None` semantics.

- [ ] **Step 5: Commit**

```bash
git add api/fundamental.py fts_engine.py dev/test_ind1b_parity_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(fts): make the 1b volume veto identical in card and screen"
```

---

### Task 4: Honest N/A semantics in the screen row and UI

**Files:**
- Modify: `fts_engine.py` (`bulk_scan` row fields/reasons)
- Modify: `frontend/src/features/fundamental/api/useFtsScreen.ts`
- Modify: `frontend/src/features/fundamental/ui/FtsScreenTable.tsx`, `components/FtsCard.tsx`, `ui/FtsDrillDown.tsx`
- Test: `dev/test_fts_na_v11.py`, `frontend/src/__tests__/fts-fundamental-labels.spec.tsx`

**Interfaces:**
- Row adds `i1_na`, `i1_reason`, `i1_basis`, `i1a_pass`, `i1b_pass`, `i1b_applicable`, `i1b_basis`.
- UI renders a gray `N/A` with the reason for `i1_na`/`i3_na`/`i4_na`; never a red ✗ for a missing data row.

- [ ] **Step 1: Write the failing Python test**

```python
# dev/test_fts_na_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.fundamental import axis1_state
state, reason = axis1_state({"monetary_pct": None, "pass": False, "data_gap": True,
                             "reason": "بدون گزارش ماهانه"}, {})
assert state is None and "گزارش" in reason, (state, reason)
print("OK N/A semantics")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_na_v11.py`
Expected: failure until `axis1_state` is wired.

- [ ] **Step 3: Implement row fields and UI**

`bulk_scan`: set `i1_na = (i1 is None)`, `i1_reason = reason`, and the 1a/1b fields; ensure the score counts only `True`. `useFtsScreen.ts`: add nullable fields. `FtsScreenTable.tsx`: in the indicator-1 cell, render `N/A` (gray) when `i1_na`, with `title={i1_reason}`; do the same for `i3_na`/`i4_na`; do not render a red ✗ for `None`. `FtsCard`/`FtsDrillDown`: the same reason text.

- [ ] **Step 4: Run tests**

Run: `python dev/test_fts_na_v11.py`
Run: `cd frontend && npx vitest run src/__tests__/fts-fundamental-labels.spec.tsx`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add fts_engine.py frontend/src/features/fundamental/api/useFtsScreen.ts frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/features/fundamental/components/FtsCard.tsx frontend/src/features/fundamental/ui/FtsDrillDown.tsx dev/test_fts_na_v11.py frontend/src/__tests__/fts-fundamental-labels.spec.tsx
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(fts): show honest N/A reasons instead of false fails"
```

---

### Task 5: EPS evidence labels (annual preferred, best available, consolidated display-only)

**Files:**
- Modify: `fts_engine.py` (`eps_assessment` add `evidence_label`)
- Modify: `api/fundamental.py` (`ind2_eps_track`, `evaluate_v10`)
- Modify: `fts_engine.py` (`bulk_scan` row `eps_evidence_label`)
- Modify: UI card/table/drill-down
- Test: `dev/test_fts_evidence_v11.py`, `frontend/src/__tests__/fts-fundamental-labels.spec.tsx`

**Interfaces:**
- `evidence_label` values: `"سالانهٔ حسابرسی‌شده"`, `"سالانهٔ حسابرسی‌نشده"`, `"برآورد میان‌دوره"`, `"تلفیقی — نمایشی"`, `"دادهٔ ناکافی"`.
- `eps_assessment` keeps `na=True` for any consolidated slot; the series remains displayed.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_evidence_v11.py
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fts_engine import eps_assessment

AUD = "صورت مالی سالانه حسابرسی شده"
CA = "صورت‌های مالی تلفیقی سالانه حسابرسی شده"


def mk():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE financial_statements (
        symbol TEXT, period_end TEXT, period_months INTEGER, title TEXT,
        basic_eps REAL, net_profit REAL)""")
    return c


def add(c, pe, title, eps):
    c.execute("INSERT INTO financial_statements VALUES ('A',?,12,?,?,?)",
              (pe, title, eps, eps * 1000))


c = mk()
for pe, eps in (("1402/12/29", 100), ("1403/12/29", 120), ("1404/12/29", 150)):
    add(c, pe, AUD, eps)
r = eps_assessment(c, "A", 3, "")
assert r["pass"] is True and r["evidence_label"] == "سالانهٔ حسابرسی‌شده", r

c = mk()
for pe, eps in (("1402/12/29", 100), ("1403/12/29", 120), ("1404/12/29", 150)):
    add(c, pe, CA, eps)
r2 = eps_assessment(c, "A", 3, "")
assert r2["na"] is True and r2["evidence_label"] == "تلفیقی — نمایشی", r2

c = mk()
add(c, "1403/12/29", AUD, 120)
add(c, "1404/12/29", AUD, 150)
r3 = eps_assessment(c, "A", 3, "")
assert r3["evidence_label"] == "دادهٔ ناکافی", r3
print("OK evidence labels")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_evidence_v11.py`
Expected: failure until the label is implemented.

- [ ] **Step 3: Implement labels**

Add a mapping in `eps_assessment`:

```python
_EVIDENCE_LABEL = {
    "audited_year_end": "سالانهٔ حسابرسی‌شده",
    "year_end_unaudited": "سالانهٔ حسابرسی‌نشده",
    "year_end_plus_interim": "برآورد میان‌دوره",
    "consolidated_year_end": "تلفیقی — نمایشی",
    "insufficient": "دادهٔ ناکافی",
}
track["evidence_label"] = _EVIDENCE_LABEL.get(tier, "دادهٔ ناکافی")
```

Pass it through `ind2_eps_track`/`evaluate_v10` (`indicators["2"]["evidence_label"]`) and `bulk_scan` (`eps_evidence_label`). UI: show the label under the EPS cell; keep the three values; for consolidated-only show `N/A (تلفیقی)` plus the label.

- [ ] **Step 4: Run tests**

Run: `python dev/test_fts_evidence_v11.py`
Run: `cd frontend && npx vitest run src/__tests__/fts-fundamental-labels.spec.tsx`

- [ ] **Step 5: Commit**

```bash
git add fts_engine.py api/fundamental.py frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/features/fundamental/components/FtsCard.tsx frontend/src/features/fundamental/ui/FtsDrillDown.tsx dev/test_fts_evidence_v11.py frontend/src/__tests__/fts-fundamental-labels.spec.tsx
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(fts): expose EPS evidence tier and keep consolidated values display-only"
```

---

### Task 6: Margin tier labels and financial/holding N/A

**Files:**
- Modify: `api/fundamental.py` (`ind3_gross_margin` add `margin_tier`)
- Modify: `fts_engine.py` (`bulk_scan` row `margin_tier`)
- Modify: UI
- Test: `dev/test_fts_margin_v11.py`

**Interfaces:**
- `margin_tier`: `"below_floor"` (<20), `"floor"` (20–30), `"standard"` (30–50), `"good"` (>=50), `None` for N/A.
- The verdict still uses the 20 floor / 30 standard; 50 is a label only.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_margin_v11.py
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.fundamental import ind3_gross_margin
c = sqlite3.connect(":memory:")
ref = {"revenue": 1000, "gross_profit": 580, "period_end": "1404/12/29",
       "period_months": 12, "title": "صورت مالی سالانه حسابرسی شده"}
r = ind3_gross_margin(c, "الف", ref=ref)
assert r["margin_tier"] == "good" and abs(r["margin_pct"] - 58.0) < 0.1, r
ref2 = {"revenue": 1000, "gross_profit": None, "period_end": "1404/12/29",
        "period_months": 12, "title": "صورت مالی سالانه حسابرسی شده"}
r2 = ind3_gross_margin(c, "ب", ref=ref2)
assert r2["na"] is True and r2["margin_tier"] is None, r2
print("OK margin tiers")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_margin_v11.py`
Expected: `KeyError: 'margin_tier'`.

- [ ] **Step 3: Implement the tier**

```python
def _margin_tier(pct):
    if pct is None:
        return None
    if pct < 20:
        return "below_floor"
    if pct < 30:
        return "floor"
    if pct < 50:
        return "standard"
    return "good"
```

Add `margin_tier` to the result and `bulk_scan` row. UI: show the tier label next to the percentage; keep the 50% label without changing the gate. Task 10's audit records the 59 margin N/A symbols and checks their latest FS for `gross_profit`. If the audit finds a normalized gross-profit row with NULL `gross_profit`, add `r"سود.*ناخالص"` to `PATTERNS["gross_profit"]` and rerun; otherwise leave the parser unchanged. Never fabricate a margin.

- [ ] **Step 4: Run tests**

Run: `python dev/test_fts_margin_v11.py`
Run: `python dev/test_fts_v10_ladder.py`

- [ ] **Step 5: Commit**

```bash
git add api/fundamental.py fts_engine.py frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/features/fundamental/components/FtsCard.tsx dev/test_fts_margin_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(fts): label margin tiers; keep 50% as a display label"
```

---

### Task 7: Indicator 4 acceptance path and annualization label

**Files:**
- Modify: `api/fundamental.py` (`ind4_valuation` add `acceptance_path`, `annualize_label`)
- Modify: `fts_engine.py` (`bulk_scan` row `i4_acceptance_path`, `annualize_months`)
- Modify: UI
- Test: `dev/test_fts_ind4_v11.py`

**Interfaces:**
- `acceptance_path`: `"sales_to_mcap"` | `"profit_potential"` | `None`; `potential_path` is the 40% second route.
- `annualize_label`: `"سالانه‌شده از دورهٔ N ماهه"`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_ind4_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.fundamental import ind4_valuation
annual = {"annual_sales_mrl": 1_000_000.0, "months_used": 6}
gm = {"margin_pct": 50.0}
th = {"sales_to_mcap_min": 0.33, "profit_potential_min": 40.0}
r = ind4_valuation(annual, gm, market_cap_rials=2_000_000.0, th=th)
assert r["acceptance_path"] == "sales_to_mcap", r
assert "۶" in r["annualize_label"] or "6" in r["annualize_label"], r
print("OK ind4 paths")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_ind4_v11.py`
Expected: `KeyError: 'acceptance_path'`.

- [ ] **Step 3: Implement the fields in `ind4_valuation` and `bulk_scan`**

In the `available` return dict of `ind4_valuation`, add:

```python
"acceptance_path": ("sales_to_mcap" if sales_pass else
                    "profit_potential" if pot_pass else None),
"annualize_months": int(annual.get("months_used") or 0),
"annualize_label": ("سالانه‌شده از دورهٔ %d ماهه" % int(annual["months_used"])
                    if annual.get("months_used") else ""),
```

Add `"acceptance_path": None, "annualize_label": ""` to the exempt and
insufficient-data early returns. In `bulk_scan`, the existing `sales_pass`/`pot_pass`
booleans are already computed; add `"i4_acceptance_path": ("sales_to_mcap" if sales_pass
else "profit_potential" if pot_pass else None)` and `"annualize_months": months_used`
to the row. Do not change the 0.33/1.0 or 40% thresholds.

- [ ] **Step 4: Run the test and the existing card/screen parity**

Run: `python dev/test_fts_ind4_v11.py` → `OK ind4 paths`.
Run: `python dev/fts_screener_card_parity_v10.py` → unchanged or updated for the new field.

- [ ] **Step 5: Commit**

```bash
git add api/fundamental.py fts_engine.py frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/features/fundamental/components/FtsCard.tsx dev/test_fts_ind4_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(fts): label indicator 4 acceptance path and annualization"
```

---

### Task 8: Mandatory industries are exactly the booklet's three

**Files:**
- Modify: `bors_config.py` (`mandatory_sectors`)
- Modify: `fts_engine.py` (`MANDATORY_PRICING_TOKENS`)
- Modify: `frontend/src/features/fundamental/api/useFtsConfig.ts` (`FTS_GUIDE_DEFAULTS.mandatory_sectors`)
- Modify: `frontend/src/features/fundamental/ui/FtsSettingsDrawer.tsx`, `components/FtsDrillDown.tsx` (copy)
- Test: `dev/test_fts_sector_v11.py`, frontend settings test

**Interfaces:**
- Mandatory sectors: `["خودرو", "نیروگاه", "لاستیک"]` (matching tokens for car parts, power generation/distribution, tire). Insurance remains a separate veto (`is_insurance_sector`), not a mandatory token.
- Food/drug are allowed; قند و شکر/شوینده are not mandatory.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_sector_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fts_engine import sector_filter, MANDATORY_PRICING_TOKENS, is_insurance_sector
assert sector_filter("خودرو و ساخت قطعات")["pass"] is False
assert sector_filter("عرضه برق، گاز، بخاروآب گرم")["pass"] is False
assert sector_filter("لاستيك و پلاستيك")["pass"] is False
assert sector_filter("محصولات غذايي و آشاميدني به جز قند و شكر")["pass"] is True
assert sector_filter("مواد و محصولات دارويي")["pass"] is True
assert sector_filter("قند و شكر")["pass"] is True
assert sector_filter("شوينده")["pass"] is True
joined = " ".join(MANDATORY_PRICING_TOKENS)
assert "شوینده" not in joined and "قند" not in joined and "بیمه" not in joined
assert is_insurance_sector("بيمه وصندوق بازنشستگي به جزتامين اجتماعي") is True
print("OK sector lists")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_sector_v11.py`
Expected: the current tokens make food/drug or detergent/insurance assertions fail.

- [ ] **Step 3: Update every source of the mandatory list**

- `fts_thresholds.json` → `mandatory_pricing_sectors`: `["خودرو و ساخت قطعات", "عرضه برق، گاز، بخار و آب گرم", "لاستیک و پلاستیک"]`.
- `bors_config.py` → `mandatory_sectors`: `["خودرو", "نیروگاه", "لاستیک"]`.
- `fts_engine.MANDATORY_PRICING_TOKENS`: keep `خودرو`, `نقلیه موتور`, `لاستیک`, `نیروگاه`, `عرضه برق`, `تولید برق`, `توزیع برق`; remove `قند و شکر`, `شوینده`, `بیمه`.
- `frontend/src/features/fundamental/api/useFtsConfig.ts` → `FTS_GUIDE_DEFAULTS.mandatory_sectors`: `['خودرو', 'نیروگاه', 'لاستیک']`.
- `FtsSettingsDrawer.tsx`/`FtsDrillDown.tsx`: remove copy that presents قند و شکر/شوینده/دارو/غذا as booklet-mandatory.
- Do **not** remove the insurance veto: `api/fundamental.risk_gates` keeps `fts_engine.is_insurance_sector(sector)` and `fts_thresholds.json` keeps `"reject_insurance": true`.

- [ ] **Step 4: Run the Python, insurance-gate, and frontend settings tests**

Run: `python dev/test_fts_sector_v11.py` → `OK sector lists`.
Run: `python dev/fund_not_applicable_v1028.py` and `python dev/fts_m141_parity_v97.py` → insurance/gate behavior unchanged.
Add to `frontend/src/__tests__/fts-notebook-parity.spec.tsx`:
```ts
expect(FTS_GUIDE_DEFAULTS.mandatory_sectors).toEqual(['خودرو', 'نیروگاه', 'لاستیک']);
```
Run: `cd frontend && npx vitest run src/__tests__/fts-notebook-parity.spec.tsx`.

- [ ] **Step 5: Commit**

```bash
git add fts_thresholds.json bors_config.py fts_engine.py frontend/src/features/fundamental/api/useFtsConfig.ts frontend/src/features/fundamental/ui/FtsSettingsDrawer.tsx frontend/src/features/fundamental/components/FtsDrillDown.tsx frontend/src/__tests__/fts-notebook-parity.spec.tsx dev/test_fts_sector_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(fts): restrict mandatory industries to the booklet's three"
```

---

### Task 9: Remove technical badges, keep assembly/capital and risk filters

**Files:**
- Modify: `frontend/src/features/fundamental/ui/FtsScreenTable.tsx` (badges at the block that renders `tech_hourglass`, `tech_jet`, `weekly_veto`, `funnel_candidate`, `tech_matrix_desc`)
- Modify: `frontend/src/features/fundamental/routes/FundamentalPage.tsx` (remove technical props/hooks only; keep `assemblyMap`/`capitalMap`)
- Modify: `frontend/src/features/fundamental/api/useFtsScreen.ts` (keep fields for other consumers; no UI use)
- Test: `frontend/src/__tests__/fts-fundamental-badges.spec.tsx`

**Interfaces:**
- The fundamental row verdict is built from the 5 indicators, data status, assembly/capital, and risk filters; `weekly_veto`/`funnel_candidate`/technical fields are ignored in this tab.

- [ ] **Step 1: Write the failing source-guard test**

```ts
// frontend/src/__tests__/fts-fundamental-badges.spec.tsx
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const src = fs.readFileSync(
  path.resolve(process.cwd(), 'src/features/fundamental/ui/FtsScreenTable.tsx'),
  'utf8',
);

describe('fundamental tab badge separation', () => {
  it('does not render technical badges', () => {
    expect(src).not.toMatch(/استراتژی ساعت شنی FTS فعال/);
    expect(src).not.toMatch(/ستاپ جت FTS/);
    expect(src).not.toMatch(/ممنوعیت ورود FTS/);
    expect(src).not.toMatch(/هر سه گامِ قیف/);
  });
  it('keeps assembly and capital increase', () => {
    expect(src).toMatch(/assembly/i);
    expect(src).toMatch(/capital/i);
  });
});
```

- [ ] **Step 2: Run it and verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/fts-fundamental-badges.spec.tsx`
Expected: the technical-badge assertions fail on the current file.

- [ ] **Step 3: Remove the badges and the technical props**

In `FtsScreenTable.tsx`, delete the `<span>` blocks whose `title` is
`استراتژی ساعت شنی FTS فعال...`, `ستاپ جت FTS...`, `ممنوعیت ورود FTS...`, and the
funnel badge `هر سه گامِ قیف...`; remove the reads of `r.tech_*`, `r.weekly_veto`,
`r.funnel_candidate` and `r.tech_matrix_desc` from this component. In
`FundamentalPage.tsx`, remove the technical props/hooks that only fed those badges
(keep `upcoming`/`assemblyMap`/`capitalMap`). Keep `AssemblyBadge`, the capital-increase
badge, and the M141/liquidity filter rows. The `useFtsScreen.ts` schema may keep the
fields for the technical tab; the fundamental table must not render them.

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/__tests__/fts-fundamental-badges.spec.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/features/fundamental/routes/FundamentalPage.tsx frontend/src/features/fundamental/api/useFtsScreen.ts frontend/src/__tests__/fts-fundamental-badges.spec.tsx
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(fundamental): remove technical badges; keep assembly/capital"
```

**Exact removal targets:** the `<span>` blocks with titles `استراتژی ساعت شنی FTS فعال`, `ستاپ جت FTS`, `ممنوعیت ورود FTS`, and the funnel badge (`هر سه گامِ قیف`), plus the `tech_*`/`weekly_veto` reads in `FtsScreenTable`. Keep `AssemblyBadge` and the capital-increase badge; keep `m141`/`min_trade_val` filter rows.

---

### Task 10: Accuracy audit, parity, and final gate

**Files:**
- Create: `dev/codal_fundamental_audit.py`
- Modify: `dev/fts_screener_card_parity_v10.py` (new fields/N/A/1b/evidence/sector)
- Modify: `frontend/src/__tests__/fts-notebook-parity.spec.tsx` (five indicators, N/A, labels, no technical badges)
- Modify: `dev/run_all_tests.py` (register new suites)
- Modify: `docs/AGENT-INDEX.md` (via `python tools/build_agent_index.py`)
- Test: all suites

**Interfaces:**
- `dev/codal_fundamental_audit.py` opens `market.db` read-only, samples ≥30 real companies across production/bank/insurance/service/holding/consolidated-only/monthly-only, checks provenance (tracing_no/URL/publish_date), sanity (revenue>0, gross<=revenue, EPS/net sign, period not future, unit), and writes `_audit/codal-fundamental-audit-YYYY-MM-DD.md`; exits 1 if a hard sanity check fails, prints counts.
- The audit must print the strict gap counts (11 EPS / 59 margin / 20 monthly) and the 153 non-company exclusion; it must not hard-code a 100% claim.

- [ ] **Step 1: Write the audit script with these checks**

```python
# dev/codal_fundamental_audit.py
import datetime
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fts_engine as E

DB = os.path.join(ROOT, "market.db")
conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
rows = E.bulk_scan(conn)

inst, sector, names = {}, {}, {}
for l18, l30, sec in conn.execute(
        "SELECT l_val18, l_val30, COALESCE(sector_name,'') FROM instruments"):
    for x in (l18, l30):
        if x:
            inst.setdefault(E.norm_fa(x), (l30 or l18, sec))
            if sec:
                sector.setdefault(E.norm_fa(x), sec)
for sym, nm in conn.execute("SELECT symbol, company_name FROM financial_statements"):
    names.setdefault(E.norm_fa(sym), nm)
ms = {E.norm_fa(s) for s, in conn.execute("SELECT DISTINCT symbol FROM monthly_sales")}

all_annual = {r[0] for r in conn.execute(
    "SELECT DISTINCT symbol FROM financial_statements WHERE period_months>=12")}
nonco = 0
for s in all_annual:
    key = E.norm_fa(s)
    ident = E.classify_identity(s, sector.get(key, ""), names.get(key, ""), key in inst)
    if ident["kind"] == "non_company":
        nonco += 1

strict = []
for r in rows:
    if not r.get("applicable"):
        continue
    key = E.norm_fa(r["symbol"])
    ident = E.classify_identity(r["symbol"], r.get("sector_name") or "",
                                names.get(key, ""), key in inst)
    if ident["kind"] == "non_company":
        continue
    strict.append(r)

eps, margin, monthly = [], [], []
for r in strict:
    key = E.norm_fa(r["symbol"])
    prof = E.company_profile(r.get("sector_name") or "", names.get(key, ""))
    if (r.get("eps_data_gap") and not r.get("eps_consolidated")
            and (r.get("eps_years_available") or 0) < 3):
        eps.append(r["symbol"])
    if prof["kind"] == "production" and r["i3_pass"] is None:
        margin.append(r["symbol"])
    if prof["kind"] == "production" and r["i1_pass"] is False and key not in ms:
        monthly.append(r["symbol"])

issues = []
for r in strict[:30]:
    fs = conn.execute(
        "SELECT tracing_no, url, period_end, revenue, gross_profit, net_profit, "
        "basic_eps, is_consolidated FROM financial_statements WHERE symbol=? "
        "ORDER BY period_end DESC LIMIT 3", (r["symbol"],)).fetchall()
    for tn, url, pe, rev, gp, np_, epsv, cons in fs:
        if not url:
            issues.append((r["symbol"], tn, "missing_url"))
        if rev is not None and rev < 0:
            issues.append((r["symbol"], tn, "negative_revenue"))
        if gp is not None and rev is not None and gp > rev:
            issues.append((r["symbol"], tn, "gross_gt_revenue"))
        if epsv is not None and np_ is not None and ((epsv > 0) != (np_ > 0)):
            issues.append((r["symbol"], tn, "eps_net_sign"))
        if pe and str(pe)[:4] > "1405":
            issues.append((r["symbol"], tn, "future_period", pe))

out = os.path.join(ROOT, "_audit",
                   "codal-fundamental-audit-%s.md" % datetime.date.today().isoformat())
with open(out, "w", encoding="utf-8") as f:
    f.write("# CODAL fundamental audit\n\n")
    f.write("- rows: %d\n- strict companies: %d\n- excluded non-companies: %d\n"
            % (len(rows), len(strict), nonco))
    f.write("- strict eps gaps: %d\n- strict margin gaps: %d\n- strict monthly gaps: %d\n"
            % (len(eps), len(margin), len(monthly)))
    f.write("- sanity issues: %d\n" % len(issues))
    for issue in issues[:50]:
        f.write("- %s\n" % (issue,))
print("audit", out, "rows", len(rows), "strict", len(strict), "nonco", nonco,
      "eps", len(eps), "margin", len(margin), "monthly", len(monthly),
      "issues", len(issues))
conn.close()
raise SystemExit(1 if issues else 0)
```

- [ ] **Step 2: Run the audit read-only**

Run: `python dev/codal_fundamental_audit.py`
Expected: a report path; hard sanity failures = 0; strict gaps printed; 153 excluded.

- [ ] **Step 3: Run the full gate**

Run: `python dev/run_all_tests.py` (the suite runner; it may take several minutes).
Run: `cd frontend && npx vitest run` (all frontend tests).
Expected: all pass; any failure is fixed in the owning task, not silenced.

- [ ] **Step 4: Commit**

```bash
git add dev/codal_fundamental_audit.py dev/fts_screener_card_parity_v10.py frontend/src/__tests__/fts-notebook-parity.spec.tsx dev/run_all_tests.py docs/AGENT-INDEX.md
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "test(fts): add the five-indicator audit and parity gate"
```

---

## Self-Review Checklist (run after writing)

- [ ] Every spec requirement (universe, FS 1a, 1b veto, N/A, EPS evidence, margin tiers, 4 path, three industries, technical badges, assembly/capital, risk filters, audit) maps to a task above.
- [ ] No placeholder steps; each task has a concrete test and a commit.
- [ ] Names are consistent: `classify_identity`, `ind1a_fs_growth`, `axis1_state`, `evidence_label`, `margin_tier`, `acceptance_path`.
- [ ] No hard-coded 100% claim; N/A reasons are printed.
- [ ] Tests use temp DBs; the live audit is read-only.

## Execution Handoff

After the plan is saved, choose: **Subagent-Driven (recommended, fresh subagent per task + review)** or **Inline Execution (this session, batch checkpoints)**.
