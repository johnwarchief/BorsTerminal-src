# _audit/ra365_phase4_validate.py -- Phase 4 Stage 8: اجرایِ collectِ **پیش‌ثبت‌شده** درِ برابرِ مرجع
# فقط `_audit/ra365_phase4_validation_manifest.json` را می‌خواند (نمادها از پیش با معیارِ ساختاری
# تعیین شده‌اند). سؤالِ درستِ Stage 8: «برایِ آن نقاطی که **همهٔ ورودی‌هایِ رسمیِ لازم** درِ دسترس است،
# آیا فرمولِ canonical سریِ عملکردیِ رهاورد (type7/type0) را بازتولید می‌کند؟» پس:
#   • «نقطۀِ fully-determined» = روزی که هیچِ رویدادِ future آن incomplete/unknown نباشد.
#   • رویدادهایِ incomplete بهِ علتِ تفکیک می‌شوند: آورده (کمبودِ offer_price) / مرجعِ سودِ بی‌پنجره
#     (artifactِ برشِ snapshot، نه کمبودِ واقعیِ TSETMC) / سایر.
# هیچ ضریبِ حدسی زده نمی‌شود؛ موتور برایِ ورودیِ مفقود ratio نمی‌زند. مرجعِ read-onlyِ آفلاین.
import io
import json
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AUD = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AUD)
sys.path.insert(0, REPO)
import adjustment_engine as AE  # noqa: E402

R = json.load(open(f"{AUD}/ra365_ref_bars.json", encoding="utf-8"))
MAN = json.load(open(f"{AUD}/ra365_phase4_validation_manifest.json", encoding="utf-8"))
TOL = MAN["_tolerance"]["err_rel"]
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def tdate(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tdate(b): b["c"] for b in e["bars"] if b.get("c")}


def to_engine_events(sym, days, x0):
    """markها → رویدادهایِ موتور. آورده بی‌offer_price (incomplete صادقانه). مرجعِ سود = آخرینِ خامِ
    پیش ازِ رویداد؛ اگر رویداد پیشِ پنجره باشد، P=None → موتور incomplete می‌کند (artifactِ snapshot)."""
    data = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    ev = []
    for m in data:
        d = (m.get("date_time") or "")[:10]
        mid = str(m.get("id"))
        if "capital-change" in mid:
            cc = m["capital_change"]
            pc, nc = cc.get("previous_capital", 0), cc.get("new_capital", 0)
            if (cc.get("contribution_percent") or 0):
                ev.append({"kind": AE.KIND_CAPITAL_CONTRIBUTION, "date": d,
                           "previous_capital": pc, "new_capital": nc})
            elif pc and nc and nc > pc:
                ev.append({"kind": AE.KIND_CAPITAL_RESERVE, "date": d,
                           "previous_capital": pc, "new_capital": nc})
        elif mid.startswith("dps"):
            D = m["dps"].get("pure_dps") or 0
            prior = [x0[k] for k in days if k < d]
            ev.append({"kind": AE.KIND_CASH_DIVIDEND, "date": d,
                       "reference_price": prior[-1] if prior else None, "dividend_per_share": D})
    return ev


print("Phase 4 Stage 8 — collectِ پیش‌ثبت‌شده:", len(MAN["samples"]), "نماد  |  تلورانس", f"{TOL:.1%}", "\n")
hdr = (f"{'نماد':7s} {'وضعیت':22s} {'fully_det':>9s} {'میانه٪':>8s} {'≤tol٪':>7s} "
       f"{'آورده':>5s} {'مرجع_ناقص':>9s} {'سایر':>5s}")
print(hdr)
print("-" * len(hdr))
rows = []
for s in MAN["samples"]:
    sym = s["symbol"]
    x0, x7 = series(sym, "type0"), series(sym, "type7")
    days = sorted(set(x0) & set(x7))
    ev = to_engine_events(sym, days, x0) if days else []
    fac, meta = AE.chain_factors(days, ev)
    prov = meta["provenance"]

    def blocked(d):
        return any(p["date"] > d and p["status"] != AE.OK for p in prov)

    errs_full = []
    for i, d in enumerate(days):
        rref = x7[d] / x0[d] if x0[d] else 0
        if rref and not blocked(d):
            errs_full.append(abs(fac[i] / rref - 1))
    n_full = len(errs_full)
    med = statistics.median(errs_full) * 100 if errs_full else float("nan")
    within = (sum(1 for e in errs_full if e <= TOL) / n_full * 100) if n_full else 0.0

    # تفکیکِ عللِ incomplete (فقطِ رویدادهایِ داخلِ/نزدیکِ پنجره که رویِ نقاط اثر دارند)
    reasons = Counter(p["status"] for p in prov if p["status"] != AE.OK)
    n_contrib = sum(1 for p in prov if p["status"] == "incomplete:offer_price")
    n_refp = sum(1 for p in prov if p["status"] == "incomplete:reference_price")
    n_other = sum(v for k, v in reasons.items() if k not in ("incomplete:offer_price", "incomplete:reference_price"))

    if s["expected"] == "CONTROL_NO_EVENT":
        verdict = "CONTROL_NO_EVENT ✓" if all(abs(f - 1) < 1e-9 for f in fac) else "CONTROL FAIL"
    elif n_full and med <= TOL * 100:
        verdict = "MATCH(determined) ✓" if not (n_contrib or n_other) else "MATCH+GAP"
    else:
        verdict = "UNVERIFIED"
    rows.append((sym, s["expected"], verdict, n_contrib + n_other))
    medstr = f"{med:8.4f}" if errs_full else "     n/a"
    print(f"{sym:7s} {verdict:22s} {n_full:>9d} {medstr} {within:>6.1f}% {n_contrib:>5d} {n_refp:>9d} {n_other:>5d}")

print("\nخلاصه:")
n_match = sum(1 for r in rows if r[2].startswith("MATCH"))
n_ctrl = sum(1 for r in rows if r[2].startswith("CONTROL_NO_EVENT"))
n_unver = sum(1 for r in rows if r[2] == "UNVERIFIED")
print(f"  MATCH رویِ نقاطِ fully-determined={n_match}  CONTROL={n_ctrl}  UNVERIFIED={n_unver}")
print("  تفسیر: «MATCH+GAP» = فرمول رویِ نقاطِ کامل‌ورودی درِ 0.1% بازتولید می‌شود، ولی نماد رویدادهایی")
print("  دارد که ورودیِ لازمِ رسمی‌شان مفقود است (آورده → offer_price). «UNVERIFIED» = حتی رویِ نقاطِ")
print("  fully-determined هم اختلافی باقی است و باید با مرجعِ رسمیِ قیمتِ مبنایی (p_closingِ TSETMC) و")
print("  نه proxyِ خامِ پنجره‌بریده، بازبررسی شود. هیچ‌جا ضریبِ حدسی درِ موتور نمی‌نشیند.")
