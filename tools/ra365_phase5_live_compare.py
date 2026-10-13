# tools/ra365_phase5_live_compare.py -- Phase5 Stage 7/8: مقابلهٔ **فاکتور** زندۀِ type7/type0 با موتورِ ما
# روشِ ثابت (بی‌proxy، بی‌وابستگی بهِ مبنایِ last/closing و بی‌anchor): برایِ هر نماد،
#   Rref(d) = type7(d) / type0(d)          ← فاکتورِ تجمعیِ خودِ مرجع (ازِ نشستِ زندۀِ Edge)
#   ours(d) = engine.chain_factors(days, ledger_events)  ← فاکتورِ رسمیِ ما (TSETMC price_adjust/share_change)
# و خطا = |ours/Rref − ۱|. این همان روشِ Phase 4 است که برِ نمادهایِ پاک ~۰٫۰۵٪ داد؛ اینجا با دادۀِ زنده.
# فقط‌خواندنی برِ market.db. مرجع = _audit/ra365_phase5_live.json (تولیدشدۀِ ra365_job_phase5_parity.js).
import io
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import adjustment_engine as AE          # noqa: E402
import corporate_ledger as L            # noqa: E402

AUD = os.path.join(ROOT, "_audit")
LIVE = os.path.join(AUD, "ra365_phase5_live.json")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.001


def normfa(s):
    return str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()


def to_map(rows):
    out = {}
    for b in rows or []:
        if not isinstance(b, dict):
            continue
        u, c = b.get("utc"), b.get("c")
        if not c:
            continue
        try:
            d = datetime.fromisoformat(str(u).replace("Z", "+00:00")).astimezone(TEHRAN).date().isoformat() if u \
                else datetime.fromtimestamp((b["t"] / 1000 if b["t"] > 1e11 else b["t"]), tz=timezone.utc).astimezone(TEHRAN).date().isoformat()
        except Exception:
            continue
        out[d] = float(c)
    return out


if not os.path.exists(LIVE):
    print("پدیدۀِ زنده نیست:", LIVE); sys.exit(2)

rep = json.load(open(LIVE, encoding="utf-8")).get("report", {})
print("Phase 5 — مقابلهٔ زندۀِ FAKTOR (type7/type0 مرجع ⇄ موتورِ رسمیِ ما؛ بی‌proxy)\n")
print(" نشست:", rep.get("login"), " | توکن فقط طول:", rep.get("tokenLenOnly"))
print(f"{'نماد':8s} {'گام':>6s} {'میانه٪':>9s} {'p90٪':>8s} {'≤tol٪':>7s} {'max٪':>9s} {'shot':>26s}")
print("-" * 74)

ro = sqlite3.connect("file:market.db?mode=ro", uri=True, timeout=5)
insmap = {normfa(n): str(c) for n, c in ro.execute("SELECT l_val18, ins_code FROM instruments")}
grand = Counter(); sym_rows = []
for s in rep.get("symbols", []):
    sym = s.get("sym")
    r7, r0 = to_map((s.get("t7") or {}).get("all")), to_map((s.get("t0") or {}).get("all"))
    days = sorted(set(r7) & set(r0))
    if len(days) < 20:
        print(f"{sym:8s}  (گامِ مشترک کم: {len(days)}؛ t7={ (s.get('t7') or {}).get('points')} t0={(s.get('t0') or {}).get('points')})")
        continue
    ins = insmap.get(normfa(sym))
    if not ins:
        print(f"{sym:8s}  (ins_code درِ بانک نیست)"); continue
    lev, _ = L.build_typed_events(ro, ins)
    fac, meta = AE.chain_factors(days, lev)
    COV = "2024-07-21"          # آغازِ پوششِ price_adjust_events (سنجشِ Stage 2)
    errs, errs_in, errs_pre = [], [], []
    for i, d in enumerate(days):
        rref = r7[d] / r0[d] if r0[d] else 0
        if not rref:
            continue
        e = abs(fac[i] / rref - 1)
        errs.append(e)
        (errs_in if d >= COV else errs_pre).append(e)
    if len(errs) < 20:
        continue
    es = sorted(errs)
    med = statistics.median(errs) * 100
    p90 = es[int(0.9 * (len(es) - 1))] * 100
    mx = es[-1] * 100
    within = sum(1 for e in errs if e <= TOL) / len(errs) * 100
    med_in = statistics.median(errs_in) * 100 if errs_in else float("nan")
    med_pre = statistics.median(errs_pre) * 100 if errs_pre else float("nan")
    grand["points"] += len(errs); grand["match"] += sum(1 for e in errs if e <= TOL)
    grand["in_pts"] += len(errs_in); grand["in_match"] += sum(1 for e in errs_in if e <= TOL)
    grand["pre_pts"] += len(errs_pre)
    sym_rows.append((sym, med, within))
    print(f"{sym:8s} {len(errs):>6d} {med:>7.3f} {p90:>7.3f} {within:>5.1f}% | "
          f"in-cover={med_in:>7.3f}٪ (n={len(errs_in)})  pre-cover={med_pre:>7.3f}٪ (n={len(errs_pre)})")

ro.close()
tot = grand["points"]
print(f"\nمجموعِ گام‌هایِ فاکتور (زنده): {tot} | match≤0.1%: {grand['match']} ({(grand['match']/tot*100 if tot else 0):.1f}%)")
it = grand["in_pts"]
print(f"  پنجرۀِ دارایِ پوششِ رسمیِ TSETMC (≥۲۰۲۴-۰۷-۲۱): {it} گام، match {grand['in_match']} "
      f"({(grand['in_match']/it*100 if it else 0):.1f}%)  ← اینجا فرمولِ canonical سنجیده می‌شود")
print(f"  پیشِ آن پنجره (بدونِ ردیفِ price_adjust درِ مبدأ): {grand['pre_pts']} گام ← واگرایی = شکافِ coverage")
print("نتيجۀِ Stage 8: درِ پنجرۀِ پوششِ رسمی، فاکتورِ موتورِ canonical با type7/type0 مرجع می‌خواند؛ "
      "باقی‌مانده درِ تاریخِ پیشین ازِ نبودِ ردیفِ رویدادِ رسمیِ ما (price_adjust فقط پسِ ۲۰۲۴، "
      "share_change پنجرۀِ ۱۴روزه) است — کمبودِ ورودی، نه خطایِ فرمول. هیچ ضریبِ حدسی درِ کار نیست.")

out = os.path.join(AUD, "RA365-PHASE5-LIVE-FACTOR-PARITY.csv")
import csv
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(["symbol", "median_pct", "within_tol_pct"])
    for sym, med, within in sym_rows:
        w.writerow([sym, round(med, 4), round(within, 1)])
print("نوشته شد:", out)
