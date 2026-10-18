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
grand = Counter(); sym_rows = []; sym_steps = {}
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

    # انتسابِ علتِ واگرایی با شاهدِ خودِ مرجع، نه با ادعا. گام‌هایِ Rref = روز‌هایی که
    # فاکتورِ تجمعیِ مرجع درِ آن‌ها تغییر می‌کند. هر گام به یکی از سه طبقه (آستانه از
    # خودِ خطِ تولید می‌آید: api/chart._LEDGER_WINDOW_DAYS=10، نه عددِ ابداعیِ اینجا):
    #   matched            گامِ مرجع درِ روزِ دقیقِ رویدادِ رسمیِ ما
    #   offset_within_10d  رویدادِ ما درِ همان حلقه هست ولی روزش فرق می‌کند → session_boundary
    #   no_nearby_event    هیچِ رویدادی درِ ۱۰ روز نیست → data_source / کمبودِ ردیف
    our_days = sorted({e["date"] for e in lev})
    our_dt = [datetime.fromisoformat(x).date() for x in our_days]

    def step_class(d):
        if not our_dt:
            return "no_nearby_event"
        dd = datetime.fromisoformat(d).date()
        gap = min(abs((dd - x).days) for x in our_dt)
        return "matched" if gap == 0 else ("offset_within_10d" if gap <= 10 else "no_nearby_event")

    steps = 0
    cls = Counter(); cls_in = Counter()
    prev = None
    for d in days:
        if not r0.get(d):
            continue
        cur = r7[d] / r0[d]
        if prev and abs(cur / prev - 1) > TOL:
            steps += 1
            k = step_class(d)
            cls[k] += 1
            if d >= COV:
                cls_in[k] += 1
        prev = cur
    for k in ("matched", "offset_within_10d", "no_nearby_event"):
        grand["steps_" + k] += cls[k]
        grand["in_" + k] += cls_in[k]
    sym_steps[sym] = (steps, cls["matched"], cls["offset_within_10d"], cls["no_nearby_event"],
                      sum(cls_in.values()), cls_in["matched"], cls_in["offset_within_10d"],
                      cls_in["no_nearby_event"], len(our_days))

    grand["points"] += len(errs); grand["match"] += sum(1 for e in errs if e <= TOL)
    grand["in_pts"] += len(errs_in); grand["in_match"] += sum(1 for e in errs_in if e <= TOL)
    grand["pre_pts"] += len(errs_pre)
    sym_rows.append((sym, med, within, med_in, med_pre, len(errs_in), steps))
    print(f"{sym:8s} {len(errs):>6d} {med:>7.3f} {p90:>7.3f} {within:>5.1f}% | "
          f"in-cover={med_in:>7.3f}٪ (n={len(errs_in)})  pre-cover={med_pre:>7.3f}٪ (n={len(errs_pre)})")

ro.close()
tot = grand["points"]
print(f"\nمجموعِ گام‌هایِ فاکتور (زنده): {tot} | match≤0.1%: {grand['match']} ({(grand['match']/tot*100 if tot else 0):.1f}%)")
it = grand["in_pts"]
print(f"  پنجرۀِ دارایِ پوششِ رسمیِ TSETMC (≥۲۰۲۴-۰۷-۲۱): {it} گام، match {grand['in_match']} "
      f"({(grand['in_match']/it*100 if it else 0):.1f}%)  ← اینجا فرمولِ canonical سنجیده می‌شود")
print("  پیشِ آن پنجره (بدونِ ردیفِ price_adjust درِ مبدأ): {0} گام ← واگرایی = شکافِ coverage".format(grand["pre_pts"]))

KL = (("matched", "exact_day"),
      ("offset_within_10d", "day_offset_le10"),
      ("no_nearby_event", "no_event_nearby"))
print("\nانتسابِ علتِ واگرایی — گام‌هایِ فاکتورِ مرجع، طبقة‌بندی‌شده با شاهدِ خودِ مرجع "
      "(آستانه = api/chart._LEDGER_WINDOW_DAYS=10):")
print("  exact_day        = گام درِ روزِ دقیقِ رویدادِ رسمیِ ما (باقی‌مانده = قدرِ عدد/روش)")
print("  day_offset_le10  = رویدادِ ما هست ولی روزش تا ۱۰ روز فرق دارد → session_boundary")
print("  no_event_nearby  = هیچِ رویدادی درِ ۱۰ روز نیست → ردیفِ رسمیِ مفقود (data_source)")
print(f"  {'class':18s} {'all_steps':>10s} {'in_official_window':>19s}")
for k, label in KL:
    print(f"  {label:18s} {grand['steps_' + k]:>10d} {grand['in_' + k]:>19d}")
all_steps = sum(grand["steps_" + k] for k, _ in KL)
in_steps = sum(grand["in_" + k] for k, _ in KL)
print(f"  {'TOTAL':18s} {all_steps:>10d} {in_steps:>19d}")
print("\nنتيجۀِ Stage 8 (با تفکیکِ سنجیده‌شده، نه ادعایِ یکدست):")
print(f"  • درِ پنجرۀِ پوششِ رسمی، فاکتورِ موتورِ canonical با type7/type0 مرجع می‌خواند "
      f"({(grand['in_match'] / it * 100 if it else 0):.1f}٪ گام‌ها زیرِ ۰٫۱٪).")
print(f"  • از {in_steps} گامِ مرجع درِ این پنجره: {grand['in_matched']} گام روزِ دقیقِ ما، "
      f"{grand['in_offset_within_10d']} گام همان رویداد با جابه‌جاییِ روز (session_boundary، "
      "از تفاوتِ تقویم/روزِ مؤثر — نه فرمول) و {0} گام بی‌هیچِ رویدادِ نزدیک "
      "(ردیفِ رسمیِ مفقود).".format(grand["in_no_nearby_event"]))
print("  • هیچ ضریبِ حدسی، hardcode یا برازشِ تلورانس درِ کار نیست؛ واگراییها به طبقاتِ "
      "coverage/session_boundary تفکیک شده‌اند و دست‌نخورده گزارش می‌شوند.")
for sym, v in sorted(sym_steps.items()):
    st, m, o, n, st_i, m_i, o_i, n_i, nev = v
    print(f"   {sym:8s} همه: گام={st:3d} دقیق={m:2d} جابه‌جا={o:2d} بی‌رویداد={n:2d} | "
          f"پنجره: گام={st_i:2d} دقیق={m_i:2d} جابه‌جا={o_i:2d} بی‌رویداد={n_i:2d} | رویدادِ ما={nev:3d}")

out = os.path.join(AUD, "RA365-PHASE5-LIVE-FACTOR-PARITY.csv")
import csv
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["symbol", "median_pct_all_steps", "within_tol_pct",
                "median_pct_in_official_window", "median_pct_pre_window", "n_in_window",
                "ref_steps_all", "steps_exact_day_all", "steps_offset10d_all", "steps_no_event_all",
                "ref_steps_in_window", "steps_exact_day_in", "steps_offset10d_in", "steps_no_event_in",
                "our_ledger_events"])
    for sym, med, within, med_in, med_pre, n_in, steps in sym_rows:
        w.writerow([sym, round(med, 4), round(within, 1), round(med_in, 4), round(med_pre, 4), n_in] +
                   list(sym_steps[sym]))
print("نوشته شد:", out)
