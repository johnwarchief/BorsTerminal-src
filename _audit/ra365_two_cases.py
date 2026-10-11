# _audit/ra365_two_cases.py -- پروندۀِ دو اختلافِ مشخصِ مرحلۀِ ۳
#   ۱) شبهرن در ۲۰۲۶-۰۹-۲۰ (۱۴۰۵-۰۶-۲۹): رویدادِ مرجع از دفترِ جدا، رویدادِ ما، و نسبتِ تعدیل.
#   ۲) ولانا: سه پنجره‌ای که فاکتورِ مرجع درِ آن‌ها ثابت نیست و فاکتورِ ما نمی‌رسد.
# هیچ مقداری ساخته نمی‌شود؛ نسبتِ مرجع مستقیماً از type7/type0 همانِ مرجع خوانده می‌شود.
import json
import io
import sys
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src"
REF = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
PROD = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))


def bar_date(b):
    u = b.get("utc") or b.get("time")
    if isinstance(u, (int, float)):
        sec = u if u < 1e11 else u / 1000.0
        return datetime.fromtimestamp(sec, timezone.utc).date().isoformat()
    s = str(u).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def series(sym, suf):
    e = REF["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {bar_date(b): b for b in (e.get("bars") or [])}


def prod_maps(sym):
    """candle-time -> raw OHLC, and candle-time -> factor, from the live product path."""
    live = PROD[sym]["live"]
    cx = {c["time"]: c for c in live["candles"]}
    fx = {f["time"]: f["factor"] for f in (live.get("factors") or [])}
    return cx, fx, live


def ref_factor(x0, x7, dates):
    out = {}
    for d in dates:
        a, b = x0.get(d), x7.get(d)
        if a and b and a.get("c"):
            out[d] = b["c"] / a["c"]
    return out


def anchored(x0, x7):
    """بازگشتِ (روز‌هایِ مشترکِ دارایِ فاکتور، فاکتورِ نرمال‌شده با لنگرِ روزِ آخر)."""
    days = sorted(set(x0) & set(x7))
    rf = ref_factor(x0, x7, days)
    fdays = sorted(rf)
    anchor = rf[fdays[-1]]
    return fdays, {d: v / anchor for d, v in rf.items()}


def show_events(label, items, key_date, val):
    print(f"  {label}:")
    if not items:
        print("    (خالی)")
    for it in items:
        print(f"    {it.get(key_date)}  {val(it)}")


print("=" * 96)
print("۱) شبهرن — رویداد ۲۰۲۶-۰۹-۲۰")
print("=" * 96)
sym = "شبهرن"
x0, x7 = series(sym, "type0"), series(sym, "type7")
cx, fx, live = prod_maps(sym)
days, rnorm = anchored(x0, x7)

# مرجع: محلی که فاکتورِ نرمال‌شده پرش دارد
print("\n  پرش‌هایِ فاکتورِ مرجع (آستانۀ ۰٫۳٪):")
for i in range(1, len(days)):
    r = rnorm[days[i]] / rnorm[days[i - 1]]
    if abs(r - 1) > 0.003:
        print(f"    {days[i]}  ratio(prev->cur)={r:.6f}  fact_ref={rnorm[days[i]]:.6f}")

# ما: رویدادهایِ ثبت‌شده
evs = live.get("adjustEvents") or []
print("\n  رویدادهایِ تعدیلِ محصول:")
for e in evs:
    print(f"    {e.get('date')}  ratio={e.get('ratio')}  kind={e.get('kind')}  {e.get('note') or ''}")

# فاکتورِ ما در دو طرفِ ۲۰۲۶-۰۹-۲۰
win = [d for d in days if "2026-09-14" <= d <= "2026-09-30"]
print("\n  مقایسه‌ای روزانه (۲۰۲۶-۰۹-۱۴ تا ۰۹-۳۰):")
print("    date        close0_ref  close_ref(type7)  fact_ref  fact_ours   ours/ref  ours_last ours_close")
for d in win:
    a, b = x0.get(d), x7.get(d)
    ours = cx.get(d)
    f_ours = fx.get(d)
    fr = rnorm.get(d)
    ratio = (f_ours / fr) if (fr and f_ours) else None
    print(f"    {d}  {str(a and a.get('c')):>10}  {str(b and b.get('c')):>15}  "
          f"{('%.6f' % fr) if fr else '-':>8}  {('%.6f' % f_ours) if f_ours else '-':>9}  "
          f"{('%.6f' % ratio) if ratio else '-':>8}  {ours and ours.get('last')}  {ours and ours.get('close')}")

# دفترِ رویدادِ مرجع (timescale marks) برای همین نماد
marks = (REF["meta"].get("marks|" + sym) or {})
mj = marks.get("json") or {}
rows = mj.get("data") if isinstance(mj, dict) else None
print("\n  دفترِ رویدادهایِ مرجع (timescale_marks) — حوالی ۱۴۰۵-۰۶:")
if isinstance(rows, list):
    for m in rows:
        txt = json.dumps(m, ensure_ascii=False)
        if "1758" in str(m.get("time", "")) or "2026-09" in txt or "2026-08" in txt:
            print("    " + txt[:300])
else:
    print("    (دفتر در فایل نیست یا شکلش فرق دارد) status=" + str(marks.get("status")))

print("=" * 96)
print("۲) ولانا — سه پنجرۀِ ثابت‌نبودنِ فاکتور")
print("=" * 96)
sym = "ولانا"
x0, x7 = series(sym, "type0"), series(sym, "type7")
cx, fx, live = prod_maps(sym)
days, rnorm = anchored(x0, x7)

# پنجره‌ها: بازه‌هایی که فاکتورِ مرجع در آن‌ها مقدارِ ثابت ندارد
steps = []
for i in range(1, len(days)):
    r = rnorm[days[i]] / rnorm[days[i - 1]]
    if abs(r - 1) > 0.003:
        steps.append((days[i], r, rnorm[days[i - 1]], rnorm[days[i]]))
print(f"  تعدادِ پرشِ مرجع با آستانۀ ۰٫۳٪: {len(steps)}")
for d, r, p, c in steps:
    print(f"    {d}  ratio={r:.6f}  {p:.6f} -> {c:.6f}")

print("\n  رویدادهایِ تعدیلِ محصول:")
for e in (live.get("adjustEvents") or []):
    print(f"    {e.get('date')}  ratio={e.get('ratio')}  kind={e.get('kind')}  {e.get('note') or ''}")

print("\n  جدولِ مقایسه (۲۰ روزِ آخرِ هر پنجره):")
for d, r, p, c in steps:
    idx = days.index(d)
    lo = max(0, idx - 10)
    print(f"  --- پنجره {d} (نسبتِ مرجع {r:.6f}) ---")
    print("    date        fact_ref  fact_ours  ours/ref  c0_ref   c7_ref  ours_close_raw")
    for dd in days[lo:idx + 3]:
        fr = rnorm.get(dd)
        f_ours = fx.get(dd)
        ratio = (f_ours / fr) if (fr and f_ours) else None
        a, b = x0.get(dd), x7.get(dd)
        ours = cx.get(dd)
        print(f"    {dd}  {('%.6f' % fr) if fr else '-':>8}  {('%.6f' % f_ours) if f_ours else '-':>9}  "
              f"{('%.6f' % ratio) if ratio else '-':>8}  {str(a and a.get('c')):>7}  {str(b and b.get('c')):>7}  "
              f"{ours and ours.get('close')}")

with open(f"{ROOT}/_audit/RA365-TWO-CASES-2026-10-12.txt", "w", encoding="utf-8") as fh:
    fh.write("running transcript kept separately; see console log\n")
print("\nپایانِ سنجش.")
