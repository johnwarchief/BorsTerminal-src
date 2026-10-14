"""قراردادِ دادهٔ پنل‌های «وضعیت بازار» (مرجع: Binder1.pdf) رویِ HTTPِ واقعی.

چرا این گارد متولد شد: مرحلۀ ۳ مأموریت می‌گوید هر بلوک باید «پایان‌به‌پایان»
قراردادِ داده‌اش را ثابت کند — نه فقط اینکه JSON برمی‌گردد. پس همین‌جا برایِ هر
پنل سنجیده می‌شود: اندپوینت، یکا، مبنا، فرمول، ساعتِ رویداد، ساعتِ محاسبه،
تازگی نسبت به بالاترین d_evenِ بانک، و اینکه هیچ عددی برایِ منبعِ نرسیده
ساخته نشده باشد.

سه خطِ قرمزی که تست می‌بندد (همان‌ها که درِ فاز ۵F و مرحلۀ ۲ دردسرساز شدند):
· حجمِ سفارش ≠ حجمِ معامله — اگر `buy_order_m_share` با `executed_m_share` یکی
  شد، یعنی یکی از دو مفهوم جای دیگری کپی شده.
· اثر بر شاخص ≠ ٪ رشد قیمت — پنل باید هم `impact_points` و هم `delta_cap_b_toman`
  داشته باشد و `value_field`ش را از خودش بخواند.
· تغییر مالکیت ≠ خالصِ ورودِ پول — یکا باید سهم باشد، نه ریال، و `formula` باید
  `not_to_be_confused` را داشته باشد.
پسماندِ اثرِ شاخص عمداً «راحت» نمی‌شود: اگر جمعِ اثرها دقیقاً تغییرِ رسمی شد،
یعنی جایی برازش (fit) رخ داده و تست می‌ایستد.

اجرا:  ۱) `python app.py`  ۲) `python dev/mstat_status_panels_contract_v1.py`
دست‌نزدن به داده: فقط GET و فقط SELECT رویِ بانکِ read-only.
"""
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

BASE = os.environ.get("BORSTERMINAL_BASE", "http://127.0.0.1:8000")
CHECKS = []


def ck(cond, label, detail=""):
    CHECKS.append((bool(cond), label, detail))


def get(path):
    """JSON واقعی می‌خواهیم: SPA fallback درِ dev، مسیرِ ناشناخته را با ۲۰۰ و
    `index.html` برمی‌گرداند و بی‌این سرِ guard، «۲۰۰ گرفتم» به‌معنایِ «اندپوینت هست» نبود."""
    try:
        with urllib.request.urlopen(BASE + path, timeout=90) as r:
            ctype = (r.headers.get("content-type") or "").lower()
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code, ""
    except Exception as e:  # noqa: BLE001 - گارد باید علتِ قطعی را چاپ کند
        return None, "%s: %s" % (type(e).__name__, e), ""
    if "json" not in ctype:
        return None, "content-type=%s (نه JSON — مسیر ثبت نشده؟)" % ctype, ""
    try:
        return json.loads(body), "", ctype
    except Exception as e:  # noqa: BLE001
        return None, "JSON parse: %s" % e, ""


def num_fields(o, prefix=""):
    """همهٔ مسیرهایِ عددیِ یک پاسخ — برایِ اینکه «بی‌داده» با ۰ اشتباه نشود"""
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            out += num_fields(v, "%s.%s" % (prefix, k))
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            out += num_fields(v, "%s[%d]" % (prefix, i))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        out.append((prefix, o))
    return out


# ── مرجعِ تازگی: بالاترین d_evenِ بانک، مستقیم و read-only
conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
DB_DAY = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
DB_HAS_MCAP = any(r[1] == "market_cap" for r in conn.execute("PRAGMA table_info(market_watch)"))
conn.close()

# ══════════════════════════════════════════ ۱) پنل‌هایِ موجود (بازگشتِ ناخربانده)
for path, keys in [
    ("/api/mstat/histogram?group=all", ["status", "asof", "basis", "histo12", "known", "nodata", "total", "source"]),
    ("/api/mstat/clientsplit?tab=all", ["status", "asof", "retail", "institutional", "source"]),
    ("/api/mstat/phases", ["status", "red", "green", "source"]),
    ("/api/mstat/industries", ["status", "rows"]),
    ("/api/mstat/mainwatch?group=eq_all", ["status", "asof", "rows", "source"]),
]:
    data, err, _ = get(path)
    ck(data is not None, "%s JSON می‌آید" % path, err)
    if data:
        for k in keys:
            ck(k in data, "%s کلیدِ `%s` را دارد" % (path, k))
        src = data.get("source") or ""
        ck(src.startswith("local:"), "%s منبعش محلی است" % path, src)
        a = data.get("asof") or {}
        if a.get("d_even"):
            ck(a["d_even"] == DB_DAY, "%s به آخرینِ روزِ بانک (-- %s) اشاره می‌کند" % (path, a["d_even"]), "db=%s" % DB_DAY)

# ═══════════════════════════════════════════ ۲) نقشۀ بازار (صفحۀ ۲ و ۱۲)
data, err, _ = get("/api/mstat/treemap?group=eq_all&industry=&metric=value")
ck(data is not None, "treemap JSON می‌آید", err)
if data:
    ck(data.get("status") == "ok", "treemap وضعیتِ ok", str(data.get("status")))
    for k in ["asof", "computed_at", "metric", "metric_label", "metric_unit", "basis", "formula",
              "total_nodes", "shown", "skipped_nodata", "total_size", "rows", "groups", "source"]:
        ck(k in data, "treemap قراردادِ `%s` را دارد" % k)
    rows = data.get("rows") or []
    ck(len(rows) > 0, "treemap ردیفِ واقعی دارد", "n=%d" % len(rows))
    ck(all(isinstance(r.get("size"), (int, float)) and r["size"] > 0 for r in rows),
       "همۀ سطح‌ها > ۰ (خانهٔ صفر درِ چیدمان نمی‌نشیند)")
    ck(all(r.get("tone") in ("pos", "neg", "zero", "nodata") for r in rows),
       "tone از واژۀِ چهارحالتیِ سراسری است")
    ck(all(r.get("unit") == data.get("metric_unit") for r in rows),
       "یکا در هر ردیف با یکایِ معیار یکی است")
    tot = data.get("total_size") or 0
    if tot:
        worst = max(abs(r["size"] / tot * 100 - (r.get("share_pct") or 0)) for r in rows)
        # موتور سه رقمِ اعشار نگه می‌دارد، پس تلورانس = همان گردکردنِ اعلام‌شده
        ck(worst <= 5e-4, "share_pct = size ÷ total_size (فرمولِ اعلامی درست است)", "worst=%.7f" % worst)
    ck(sum(r["size"] for r in rows) <= tot + 1e-6, "جمعِ ردیف‌ها از total_size بیشتر نمی‌شود")
    ck((data.get("formula") or {}).get("pct"), "treemap فرمولِ رنگ را اعلام می‌کند")
    ck(data.get("skipped_nodata") is not None, "treemap شمارۀ بی‌داده‌ها را می‌گوید")

data, err, _ = get("/api/mstat/treemap?group=gold_fund&industry=&metric=value")
ck(data is not None, "treemapِ صندوقِ طلا (صفحۀ ۱۲) JSON می‌آید", err)
if data:
    ck(data.get("group") == "gold_fund", "دامنهٔ قفل‌شده احترام گذاشته می‌شود", str(data.get("group")))
    kinds = {r.get("kind") for r in (data.get("rows") or [])}
    ck(kinds in (set(), {"gold"}) or kinds == {"gold"}, "همۀ ردیف‌هایِ دامنهٔ طلا kind=gold", str(kinds))

if not DB_HAS_MCAP:
    data, err, _ = get("/api/mstat/treemap?group=eq_all&metric=cap")
    ck(data is not None, "treemapِ معیارِ ارزشِ بازار JSON می‌آید", err)
    if data:
        ck(not (data.get("rows") or []), "بی‌ستونِ market_cap ردیفِ جعلی نمی‌سازد")
        ck(data.get("no_source"), "بی‌ستونِ market_cap علتِ بی‌منبع می‌نویسد", str(data.get("no_source"))[:80])

# ═══════════════════════════════════════ ۳) برترین‌ها و اثر بر شاخص (صفحۀ ۸)
data, err, _ = get("/api/mstat/tops?group=eq_all")
ck(data is not None, "tops JSON می‌آید", err)
if data:
    for k in ["status", "asof", "computed_at", "group_label", "panels", "index",
              "market_total_source", "reconciliation", "blockers", "traded_only", "source"]:
        ck(k in data, "tops قراردادِ `%s` را دارد" % k)
    panels = {p.get("key"): p for p in (data.get("panels") or [])}
    ck(set(panels) >= {"impact_pos", "impact_neg", "most_value", "most_volume"},
       "چهار پنلِ مرجع جدا هستند (نه یک جدولِ مخلوط)", str(sorted(panels)))
    for key, p in panels.items():
        ck(p.get("unit") and p.get("formula") and p.get("value_field"),
           "پنلِ `%s` یکا + فرمول + ستونِ معیار دارد" % key)
        rows = p.get("rows") or []
        if key == "impact_neg":
            # «بیشترین اثرِ منفی» = سربارترینِ کاهنده، پس ترتیبِ صعودیِ عددِ منفی
            expect_order = sorted(rows, key=lambda r: (r.get(p["value_field"]) or 0))
        else:
            expect_order = sorted(rows, key=lambda r: -(r.get(p["value_field"]) or 0))
        ck(rows == expect_order, "پنلِ `%s` بر پایۀ همان ستونِ معیار رتبه شده" % key)
        ck(all(isinstance(r.get("bar_pct"), (int, float)) and 0 <= r["bar_pct"] <= 100 for r in rows if r.get("bar_pct") is not None),
           "میله‌ها از خودِ مقدار می‌آیند (bar_pct در ۰..۱۰۰)")
    ip = (panels.get("impact_pos") or {}).get("rows") or []
    if ip:
        r0 = ip[0]
        ck("impact_points" in r0 and "delta_cap_b_toman" in r0,
           "اثرِ شاخص هر دو سنجه را دارد: تخمینِ واحدی + ارزشِ بازارِ سنجیده")
        ck(abs(r0.get("pct") or 0) > 0 and r0.get("impact_points") is not None,
           "«اثر بر شاخص» با ٪ رشدِ قیمت یکی نیست (دو فیلدِ جدا)")
        ck(r0.get("impact_points") != r0.get("pct"), "عددِ اثر = درصدِ رشد نیست", str(r0.get("impact_points")))
    rec = data.get("reconciliation") or {}
    ck({"sum_of_impacts", "official_index_change", "rel_diff_pct", "meaning"} <= set(rec),
       "پسماندِ اثرِ شاخص با تعریف و عدد اعلام می‌شود")
    if rec.get("sum_of_impacts") and rec.get("official_index_change"):
        rel = abs(rec["sum_of_impacts"] - rec["official_index_change"]) / abs(rec["official_index_change"]) * 100
        ck(abs(rel - abs(rec.get("rel_diff_pct") or 0)) < 0.2,
           "rel_diff_pct با اعدادِ خودِ پاسخ می‌خواند (امضاش نسبت به تغییرِ رسمی)", "rel=%.2f" % rel)
        ck(rel > 0.05, "پسماند صفر نشده (صفر = نشانهٔ برازشِ عمدی)", "rel=%.2f%%" % rel)
        ck(rec.get("meaning"), "پسماند توضیحِ متن دارد")
    bl = {b.get("key") for b in (data.get("blockers") or [])}
    ck("free_float" in bl, "بلوکرِ سهامِ آزادِ شناور ثبت شده", str(bl))
    ff = next((b for b in (data.get("blockers") or []) if b.get("key") == "free_float"), {})
    ck(ff.get("official_attribution_available") is False,
       "announce می‌کند که انتسابِ رسمیِ شاخص در دسترس نیست")

# ══════════════════════════════════ ۴) سفارش‌ها و تغییرِ مالکیت (صفحۀ ۹)
data, err, _ = get("/api/mstat/orderflows?group=all")
ck(data is not None, "orderflows JSON می‌آید", err)
if data:
    for k in ["status", "asof", "computed_at", "orders_available", "symbols_with_orders",
              "symbols_in_scope", "unit", "basis", "formula", "totals", "no_source", "source"]:
        ck(k in data, "orderflows قراردادِ `%s` را دارد" % k)
    if data.get("orders_available"):
        t = data.get("totals") or {}
        ck(t.get("buy_order_m_share") != t.get("executed_m_share"),
           "حجمِ سفارش از حجمِ معاملهٔ انجام‌شده جداست", "buy=%s exec=%s" % (t.get("buy_order_m_share"), t.get("executed_m_share")))
        ck("میلیون سهم" in (t.get("order_vs_executed_note") or "") or data.get("unit"),
           "یکایِ سفارش اعلام شده")
        f = data.get("formula") or {}
        ck(f.get("buy_order") and f.get("sell_order") and "q_tot_tran" in json.dumps(f, ensure_ascii=False),
           "فرمولِ سفارش و فرمولِ معامله جدا نوشته شده‌اند", str(sorted(f))[:90])
        for key in ("buy_panels", "sell_panels"):
            p = data.get(key) or {}
            ck(p.get("value_field") and p.get("unit"), "%s ستونِ معیار و یکا دارد" % key)
    else:
        ck(data.get("no_source"), "دفترِ سفارشِ نخورده با علت اعلام می‌شود", str(data.get("no_source"))[:80])

data, err, _ = get("/api/mstat/ownership?group=all")
ck(data is not None, "ownership JSON می‌آید", err)
if data:
    for k in ["status", "asof", "computed_at", "symbols_with_client_data", "unit", "basis",
              "formula", "totals", "client_data_lags_session", "no_source", "source"]:
        ck(k in data, "ownership قراردادِ `%s` را دارد" % k)
    f = data.get("formula") or {}
    ck(f.get("not_to_be_confused"), "مالکیت صریح می‌گوید با پول/سرانه اشتباه نشود")
    ck("سهم" in (data.get("unit") or ""), "یکایِ مالکیت سهم است نه ریال", str(data.get("unit")))
    t = data.get("totals") or {}
    if isinstance(t.get("legal_net_m_share"), (int, float)) and isinstance(t.get("real_net_m_share"), (int, float)):
        ck(abs(t["legal_net_m_share"] + t["real_net_m_share"]) < 1e-6,
           "خالصِ دو گروه قرینه است (جابه‌جاییِ همان سهم)", "%s / %s" % (t["legal_net_m_share"], t["real_net_m_share"]))
    ck(isinstance(data.get("client_data_lags_session"), bool), "تأخیرِ تفکیکِ مشتری اعلام می‌شود")

# ════════════════════════════════════════ ۵) کارت‌های شاخص (صفحۀ ۶/۷)
data, err, _ = get("/api/mstat/indexcards?days=30")
ck(data is not None, "indexcards JSON می‌آید", err)
if data:
    cards = {c.get("key"): c for c in (data.get("cards") or [])}
    ck(set(cards) >= {"tedpix", "equal_weight", "value_weighted_price"},
       "سه کارتِ مرجع هست", str(sorted(cards)))
    for key, c in cards.items():
        ck(c.get("label") and c.get("formula"), "کارتِ `%s` برچسب و فرمول دارد" % key)
        if c.get("available"):
            ck(c.get("unit"), "کارتِ `%s` یکا دارد" % key)
            ck(isinstance(c.get("value"), (int, float)), "کارتِ `%s` عددِ واقعی دارد" % key)
        else:
            ck(c.get("value") is None, "کارتِ ناخوانا صفر نمی‌سازد", str(c.get("value")))
    vw = cards.get("value_weighted_price") or {}
    if vw.get("available") and isinstance(vw.get("value"), (int, float)):
        t = (data.get("trades") or 0)
        ck(vw.get("formula"), "قیمتِ وزنی تعریفِ فرمولش را می‌نویسد (q_tot_cap ÷ q_tot_tran)")
    ck(isinstance(data.get("history_points"), int), "تعدادِ روزهایِ تاریخچه اعلام می‌شود")
    ck(data.get("market_total_source"), "منبعِ ارزشِ بازار اعلام می‌شود", str(data.get("market_total_source")))

# ════════════════════════════════ ۶) طلا، سکه و صندوقِ طلا (صفحاتِ ۱/۳/۱۰/۱۱/۱۲)
data, err, _ = get("/api/mstat/gold?history_days=60")
ck(data is not None, "gold JSON می‌آید", err)
if data:
    for k in ["status", "asof", "computed_at", "unit", "basis", "symbols", "symbols_count",
              "total_value_b_toman", "history_days", "history_source", "no_source",
              "access_limits", "source"]:
        ck(k in data, "gold قراردادِ `%s` را دارد" % k)
    syms = data.get("symbols") or []
    ck(all(s.get("cls") in ("fund", "other", "stock", "etf") for s in syms),
       "طبقهٔ هر ابزارِ طلا از خودِ موتور می‌آید")
    ck(all(s.get("tone") in ("pos", "neg", "zero", "nodata") for s in syms), "tone در واژۀ سراسری است")
    ck(len(data.get("no_source") or []) >= 5, "بی‌منبع‌هایِ مرجع (اونس/تورم/…) صریح اعلام شده",
       "n=%d" % len(data.get("no_source") or []))
    for n in data.get("no_source") or []:
        ck(n.get("why"), "بی‌منبعِ `%s` علت دارد" % n.get("key"))
    for a in data.get("access_limits") or []:
        ck(a.get("why"), "محدودیتِ دسترسیِ `%s` فقط ثبت می‌شود و دور زده نمی‌شود" % a.get("key"))
    blob = json.dumps(data, ensure_ascii=False)
    for forbidden in ("BTCUSD", "XAUTBHR", "USDTBHR"):
        ck(forbidden not in blob, "نمادِ بی‌ردیفِ مرجع (%s) جعل نشده" % forbidden)

# ════════════════════════════════════════ ۷) سریِ مقایسه (صفحۀ ۱۳)
data, err, _ = get("/api/mstat/series?symbols=%D8%B9%D9%8A%D8%A7%D8%B1,%D9%81%D9%88%D9%84%D8%A7%D8%AF&days=365")
ck(data is not None, "series JSON می‌آید", err)
if data:
    for k in ["status", "computed_at", "days", "unit", "basis", "symbols", "series",
              "points", "no_source", "first_date", "last_date"]:
        ck(k in data, "series قراردادِ `%s` را دارد" % k)
    ck("خام" in (data.get("basis") or ""), "مبدأِ سری صریح «پایانیِ خام» است نه «بازدهیِ تعدیل‌شده»",
       str(data.get("basis")))
    ser = data.get("series") or {}
    ck(all(len(v) == data.get("points", {}).get(k, -1) for k, v in ser.items()),
       "points با طولِ همان سری می‌خواند")
    ck(all(all(isinstance(p.get("v"), (int, float)) and p["v"] > 0 for p in v[:20]) for v in ser.values()),
       "هیچ نقطۀ قیمتیِ صفر/منفی ساخته نشده")
    ck(all(v for v in ser.values()), "هر نمادِ درخواستی سری برگردانده (عيار و فولاد)")

data, err, _ = get("/api/mstat/series?symbols=%D9%86%DB%8C%D9%85%D8%A7%D8%AF%DB%8C%D9%86%D8%AC%D8%A7&days=30")
ck(data is not None, "seriesِ نمادِ ناموجود JSON می‌آید", err)
if data:
    ck(data.get("no_source"), "نمادِ بی‌ردیف درِ no_source با علت می‌آید نه خط", str(data.get("no_source"))[:80])

# ══════════════════════════════ ۸) پخشِ تک‌درخواستی (/api/mstat/board)
data, err, _ = get("/api/mstat/board")
ck(data is not None, "board JSON می‌آید", err)
if data:
    for k in ["treemap", "tops", "orderflows", "ownership", "indexcards", "gold"]:
        ck(k in data, "board پنلِ `%s` را در یک سفر می‌آورد (round-tripِ واحدِ تب)" % k)
    ck((data.get("treemap") or {}).get("status") in ("ok", "error"), "پنل‌هایِ board یا ok‌اند یا خطای اعلام‌شده")

# ═══════════════════════════════════ چاپِ نتیجه
fails = [c for c in CHECKS if not c[0]]
for ok, label, detail in CHECKS:
    if not ok:
        print("FAIL  %s  %s" % (label, ("| " + detail) if detail else ""))
print("-" * 70)
print("بررسی: %d  |  سبز: %d  |  سرخ: %d" % (len(CHECKS), len(CHECKS) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
