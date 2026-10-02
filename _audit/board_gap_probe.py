"""زنده کاویدنِ جدولِ تابلوخوانی: چه ستونی واقعاً پر است، چه ستونی در بانک هست
ولی رویِ صفحه نمی‌آید، و چه چیزی در TSETMC/تریدرزآرنا هست و ما هیچ‌جا نداریم.

    python _audit/board_gap_probe.py

خروجی سه بخش است:
  ۱) نرخِ پُریِ هر ستونِ ردیفِ تابلو (رویِ همان داده‌ای که UI می‌خواند)
  ۲) مقایسهٔ عددِ ما با TSETMC زنده (MarketWatch) برایِ نمادهایِ مشترک
  ۳) جدولِ ستون‌هایِ دیده‌بانِ تریدرزآرنا ↔ آنچه ما به کاربر نشان می‌دهیم
"""
import json
import time
import urllib.request

APP = "http://127.0.0.1:8001"
TA = "https://tradersarena.ir"
MW = "https://cdn.tsetmc.com/api/Screen/GetMarketWatch?market=1&paperTypes[0]=1&showTraded=false"


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/json",
                                               "Referer": "https://cdn.tsetmc.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


rows = get(APP + "/api/market")["data"]
print(f"ردیف‌هایِ تابلو (API): {len(rows)}")

# ── ۱) نرخِ پُری ────────────────────────────────────────────────────────────
KEY = {"symbol", "name", "sector_name", "board", "ins_code", "is_live", "fetched_at"}
stats = []
for col in rows[0]:
    if col in KEY:
        continue
    vals = [r.get(col) for r in rows]
    nonnull = sum(1 for v in vals if v is not None)
    nonzero = sum(1 for v in vals if isinstance(v, (int, float)) and v not in (0, 0.0))
    stats.append((col, nonnull, nonzero))
print("\n== ردیف‌هایی که «صفرِ جعلی» یا «همیشه خالی»اند ==")
suspicious = [(c, nn, nz) for c, nn, nz in stats if nz < 0.02 * len(rows)]
for c, nn, nz in sorted(suspicious, key=lambda t: -t[1]):
    print(f"   {c:<20} نال={nn:>5}  ناصفر={nz:>5}  ({nz / len(rows) * 100:5.1f}٪)")

# ── ۲) TSETMC زنده ─────────────────────────────────────────────────────────
print("\n== مقایسه با TSETMC زنده ==")
try:
    tsetmc = get(MW)
    by_code = {str(x.get("insCode")): x for x in tsetmc}
    print(f"   TSETMC ردیف: {len(by_code)}")
    bad = {"p_last": 0, "p_closing": 0, "vol": 0, "trades": 0, "value": 0}
    checked = 0
    for r in rows:
        x = by_code.get(str(r["ins_code"]))
        if not x:
            continue
        qtj, qtc, ztt = float(x.get("qtj") or 0), float(x.get("qtc") or 0), float(x.get("ztt") or 0)
        if qtj <= 0:
            continue
        checked += 1
        mine_v, mine_val, mine_t = (r.get("q_tot_tran") or 0), (r.get("q_tot_cap") or 0), (r.get("z_tot_tran") or 0)
        if abs(mine_v - qtj) / max(qtj, 1) > 0.005:
            bad["vol"] += 1
        if abs(mine_val - qtc) / max(qtc, 1) > 0.005:
            bad["value"] += 1
        if mine_t != ztt:
            bad["trades"] += 1
        if abs((r.get("p_last") or 0) - float(x.get("pl") or 0)) > 1:
            bad["p_last"] += 1
        if abs((r.get("p_closing") or 0) - float(x.get("pc") or 0)) > 1:
            bad["p_closing"] += 1
    print(f"   نمادِ معامله‌شدهٔ قابلِ سنجش: {checked}")
    for k, v in bad.items():
        if v:
            print(f"   اختلافِ {k}: {v} ردیف")
    if not any(bad.values()):
        print("   ✓ هیچِ اختلافی در حجم/ارزش/تعداد/آخرین/پایانی نیست")
except Exception as e:
    print("   سنجشِ مستقیمِ TSETmc ممکن نشد:", type(e).__name__, str(e)[:160])

# ── ۳) ستون‌هایِ دیده‌بانِ تریدرزآرنا ───────────────────────────────────────
TA_WATCH = ["حجم", "ارزش", "آخرین", "%آخرین", "پایانی", "%پایانی", "سرانه خرید", "سرانه فروش",
            "قدرت خرید", "ورود پول", "حجم تقاضا", "قیمت تقاضا", "قیمت عرضه", "حجم عرضه"]
# همان چیزی که TapeTable به کاربر نشان می‌دهد (features/market/components/TapeTable.tsx HEADERS)
SHOWN = ["نماد و نام", "قیمت آخرین", "تغییر٪", "حجم", "نسبت حجم ماه", "سرانه خرید (م.ت)",
         "سرانه فروش (م.ت)", "قدرت خریدار", "الگوی ساعت"]
print("\n== ستون‌هایِ دیده‌بانِ تریدرزآرنا در برابرِ جدولِ ما ==")
FIELD = {"حجم": "q_tot_tran", "ارزش": "q_tot_cap", "آخرین": "p_last", "%آخرین": "percent_change",
         "پایانی": "p_closing", "سرانه خرید": "buy_i_vol", "سرانه فروش": "sell_i_vol",
         "قدرت خرید": "buyer_power", "حجم تقاضا": "buy_q_vol", "قیمت تقاضا": "buy_q1_px",
         "قیمت عرضه": "sell_q1_px", "حجم عرضه": "sell_q_vol", "تعداد معاملات": "z_tot_tran"}
for col in TA_WATCH + ["تعداد معاملات"]:
    f = FIELD.get(col, "")
    in_api = f in rows[0]
    fill = ""
    if in_api:
        nz = sum(1 for r in rows if r.get(f) not in (None, 0, 0.0))
        fill = f"{nz}/{len(rows)} ناصفر"
    print(f"   {col:<14} در API: {'✓' if in_api else '✗':<2}  {fill:<16}  رویِ صفحه: "
          f"{'✓' if any(col.split()[0] in s for s in SHOWN) else '—'}")
print("   ستون‌هایِ ما که آن‌ها ندارند:", ", ".join(s for s in SHOWN if "نسبت حجم" in s or "الگوی" in s))
