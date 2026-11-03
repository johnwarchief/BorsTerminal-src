# _audit/ra365_ledger_ab.py -- آزمونِ کنترل‌شدۀ قاعدۀ تیزکردنِ ضریبِ تعدیل با دفترِ مبدأ
# چرا: سنجشِ «پیش/پس» با دو ضبطِ زنده قابلِ اتکا نیست — بازوِ زنده هر بار از TSETMC
# تازه می‌خواند، پس خودِ داده‌یِ پایه جابه‌جا می‌شود و جابه‌جایی با اثرِ قاعدۀِ ما
# قاطی می‌شود (همان چیزی که بدترشدنِ لخزر را «تقصیرِ رفع» نشان داد). اینجا کندل‌ها
# و رویدادهایِ **یک ضبطِ ثابت** (پیش از رفع) مبنای‌اند و فقط قاعدۀِ تیزکردن عوض
# می‌شود؛ پس هر اختلاف، مستقیماً اثرِ همان قاعده است.
# قاعدۀِ محاسبه از خودِ محصول می‌آید (`api/chart.py:_factors_from_events`) تا عددِ
# تست با عددِ رابط یکی باشد.
import json
import io
import sys

sys.path.insert(0, ".")
if "utf8" not in (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", ""):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone, timedelta          # noqa: E402
from api.chart import _factors_from_events, _ledger_events_for   # noqa: E402

REF = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))
BASE = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
TOL = 0.0005


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref_series(sym):
    e = REF["bars"].get(f"{sym}|type7|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def dparse(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def sharpen(events, ledger, window, tol, mode):
    """بازنویسیِ رویدادهایِ دیده‌شده با ردیفِ مبدأِ هم‌خوان.

    mode:
      collapse  = ردیف‌هایِ چندتکه‌ای که به یک ردیفِ مبدأ می‌خورند حذف می‌شوند (رفعِ اول)
      one2one   = فقط وقتی یک رویداد تنها صاحبِ آن ردیف است عددِ مبدأ می‌نشیند
      ratio     = مثلِ one2one ولی تاریخِ رویداد دست‌نخورده می‌ماند (ضریب فقط)
    """
    ev = [dict(e) for e in (events or [])]
    for _e in ev:
        _e["_d0"] = str(_e["date"])
    if not ev or not ledger:
        return ev
    claims = {}
    for i, e in enumerate(ev):
        try:
            d0, r0 = dparse(e["date"]), float(e.get("ratio") or 0)
        except Exception:
            continue
        if r0 <= 0:
            continue
        best = None
        for lr in ledger:
            dd = abs((dparse(lr["date"]) - d0).days)
            if dd > window:
                continue
            if abs(lr["ratio"] / r0 - 1.0) > tol:
                continue
            key = (dd, 0 if lr["kind"] == "priceAdjust" else 1)
            if best is None or key < best[0]:
                best = (key, lr)
        if best:
            claims[i] = best[1]
    owners = {}
    for i, lr in claims.items():
        owners.setdefault(lr["date"] + "|" + lr["kind"], []).append(i)
    out = []
    for i, e in enumerate(ev):
        lr = claims.get(i)
        if not lr:
            e["source"] = "base-price-discontinuity"
            out.append(e)
            continue
        solo = len(owners[lr["date"] + "|" + lr["kind"]]) == 1
        if mode == "collapse" or (mode in ("one2one", "ratio") and solo):
            e["ratio"] = round(lr["ratio"], 8)
            e["source"] = lr["kind"]
            if mode != "ratio":
                e["date"] = lr["date"]
        else:
            e["source"] = "base-price-discontinuity"
        out.append(e)
    if mode == "collapse":
        seen, keep = set(), []
        for e in out:
            if e.get("source") in ("priceAdjust", "shareChange"):
                k = str(e["date"]) + "|" + str(e["source"])
                if k in seen:
                    continue
                seen.add(k)
            keep.append(e)
        out = keep
    out.sort(key=lambda x: str(x["date"]))
    return out


def measure(events_by_sym, tag):
    errs, per, hit, n = [], {}, 0, 0
    for c in CORPUS:
        sym = c["sym"]
        rf = ref_series(sym)
        live = BASE[sym]["live"]
        # کندل‌ها درِ ضبط از تازه‌ترین به کهنه‌اند؛ حلقۀِ فاکتورascending می‌خواهد
        ts = sorted(cc["time"] for cc in live["candles"])
        fac = dict(zip(ts, _factors_from_events(ts, events_by_sym[sym])))
        base = {cc["time"]: cc.get("last") for cc in live["candles"]}
        se = []
        for d in sorted(set(rf) & set(base)):
            pv = (base[d] or 0) * fac.get(d, 1.0)
            rel = abs(rf[d] - pv) / rf[d] if rf[d] else 0.0
            se.append(rel)
            errs.append(rel)
            if abs(rf[d] - pv) <= max(abs(rf[d]) * TOL, 0.6):
                hit += 1
            n += 1
        se.sort()
        per[sym] = (len(se), q(se, 0.5), q(se, 0.9))
    errs.sort()
    return {"tag": tag, "bars": n, "within_tol": 100.0 * hit / n if n else 0.0,
            "median": 100 * q(errs, 0.5), "p90": 100 * q(errs, 0.9),
            "p99": 100 * q(errs, 0.99), "max": 100 * (errs[-1] if errs else 0.0), "per": per}


def q(a, p):
    return a[min(len(a) - 1, max(0, int(round(p * (len(a) - 1)))))] if a else float("nan")


RAW = {c["sym"]: (BASE[c["sym"]]["live"].get("adjustEvents") or []) for c in CORPUS}
LED = {c["sym"]: _ledger_events_for(c["sym"]) for c in CORPUS}

# درِستیِ harness: بازسازیِ فاکتور از رویدادِ خام باید همان فاکتورِ ضبط‌شده بدهد
bad = 0
for c in CORPUS:
    live = BASE[c["sym"]]["live"]
    ts = sorted(cc["time"] for cc in live["candles"])
    got = _factors_from_events(ts, RAW[c["sym"]])
    cap = {f["time"]: f["factor"] for f in (live.get("factors") or [])}
    for t, f in zip(ts, got):
        if t in cap and abs(cap[t] - f) > 1e-9:
            bad += 1
print(f"بازتولیدِ فاکتورِ ضبط‌شده از رویدادها: {bad} اختلاف (باید صفر باشد)")

# پلِ «harness ↔ کدِ محصول»: قاعدۀِ V10 باید عیناً تابعِ واقعیِ محصول باشد، وگرنه
# این جدول چیزی دربارهٔ آنچه سرو می‌شود نمی‌گوید (همان رویدادها، همان دفترِ واقعی).
from api.chart import _sharpen_events_with_ledger   # noqa: E402
_key = lambda es: [(str(e["date"])[:10], round(float(e["ratio"]), 8),
                    str(e.get("source"))) for e in sorted(es, key=lambda x: str(x["date"]))]
pdiff = 0
for s in RAW:
    prod = _sharpen_events_with_ledger(s, RAW[s])[0]
    if _key(prod) != _key(sharpen(RAW[s], LED[s], 10, 0.001, "ratio")):
        pdiff += 1
print(f"اختلافِ V10 با `_sharpen_events_with_ledger` درِ محصول: {pdiff} نماد (باید صفر باشد)")

VARIANTS = [("V0 کنترل (بدونِ تیزکردن)", dict(mode=None)),
            ("V1 رفعِ اول: پنجره ۱۰، تلورانس ۱٪، جمعِ تکه‌ها", dict(w=10, t=0.01, mode="collapse")),
            ("V2 فقط یک‌به‌یک: پنجره ۱۰، تلورانس ۱٪", dict(w=10, t=0.01, mode="one2one")),
            ("V3 یک‌به‌یک، ضریبِ تنها (تاریخ نمی‌چرخد)", dict(w=10, t=0.01, mode="ratio")),
            ("V4 یک‌به‌یک، پنجره ۵", dict(w=5, t=0.01, mode="one2one")),
            ("V5 یک‌به‌یک، تلورانس ۰٫۳٪", dict(w=10, t=0.003, mode="one2one")),
            ("V6 یک‌به‌یک، تلورانس ۰٫۱٪", dict(w=10, t=0.001, mode="one2one")),
            ("V7 فقط هم‌تاریخ (پنجره ۰)، تلورانس ۱٪", dict(w=0, t=0.01, mode="ratio")),
            ("V8 پنجره ۲ روز، تلورانس ۱٪، ضریبِ تنها", dict(w=2, t=0.01, mode="ratio")),
            ("V9 پنجره ۲ روز، تلورانس ۰٫۲٪، ضریبِ تنها", dict(w=2, t=0.002, mode="ratio")),
            ("V10 قاعدۀِ فعلیِ محصول (پنجره ۱۰، ۰٫۱٪، ضریبِ تنها)",
             dict(w=10, t=0.001, mode="ratio"))]

res = []
for tag, kw in VARIANTS:
    if kw.get("mode") is None:
        ev = {s: [dict(x) for x in RAW[s]] for s in RAW}
    else:
        ev = {s: sharpen(RAW[s], LED[s], kw["w"], kw["t"], kw["mode"]) for s in RAW}
    r = measure(ev, tag)
    r["events"] = sum(len(v) for v in ev.values())
    r["ev_n"] = {s: len(v) for s, v in ev.items()}
    r["sharpened"] = sum(1 for v in ev.values() for e in v
                         if e.get("source") in ("priceAdjust", "shareChange"))
    r["shifted"] = sum(1 for v in ev.values() for e in v
                       if e.get("source") in ("priceAdjust", "shareChange")
                       and str(e["date"]) != e.get("_d0", str(e["date"])))
    res.append(r)

ref_per = res[0]["per"]
print("\n" + "=" * 118)
print(f"{'variant':52s} {'درتلورانس':>10s} {'میانه':>9s} {'p90':>9s} {'p99':>9s} {'بیشینه':>9s} {'رویداد':>7s} {'تیز':>5s} {'چرخشِ‌تاریخ':>8s}")
for r in res:
    print(f"{r['tag']:52s} {r['within_tol']:9.2f}٪ {r['median']:8.4f}٪ {r['p90']:8.4f}٪ "
          f"{r['p99']:8.4f}٪ {r['max']:8.4f}٪ {r['events']:7d} {r['sharpened']:5d} {r['shifted']:8d}")

for r in res[1:]:
    better = sum(1 for s in ref_per if r["per"][s][1] < ref_per[s][1] - 1e-12)
    worse = sum(1 for s in ref_per if r["per"][s][1] > ref_per[s][1] + 1e-12)
    print(f"\n{r['tag']}:  بهتر {better}  بدتر {worse}  بی‌تغییر {len(ref_per)-better-worse}")
    for dlt, s in sorted(((r["per"][s][1] - ref_per[s][1], s) for s in ref_per), reverse=True)[:4]:
        if dlt > 1e-12:
            print(f"   بدتر: {s:8s} میانه {100*ref_per[s][1]:.4f} → {100*r['per'][s][1]:.4f} "
                  f"({100*dlt:+.4f}٪)  رویداد {len(RAW[s])}→{r['ev_n'][s]}")
