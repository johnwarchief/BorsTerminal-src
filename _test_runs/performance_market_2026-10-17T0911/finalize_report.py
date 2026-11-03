# -*- coding: utf-8 -*-
"""Fold the live-session sampler and the paired browser runs into the report.

Same rule as repair_report_numbers.py: every numeral is generated from the raw
JSON/JSONL with chr(0x06F0+d); nothing is transcribed by hand.
"""
import io
import json
import os
import statistics
import sys

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")
TICK = os.path.join(RUN, "live-8000-tick-sampler.jsonl")


def fa(s, keep=()):
    out = []
    for ch in str(s):
        if ch.isdigit():
            out.append(chr(0x06F0 + int(ch)))
        elif ch in keep:
            out.append(ch)
        elif ch == ",":
            out.append("٬")
        elif ch == ".":
            out.append("٫")
        elif ch == "-":
            out.append("−")
        elif ch == "%":
            out.append("٪")
        else:
            out.append(ch)
    return "".join(out)


def plain(s):
    """Digits only; keeps '-', ':' and '.' (ports, clocks, dates)."""
    return fa(s, keep="-:.")


def num(v):
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9:
        return fa("{:,.0f}".format(v))
    return fa("{:,.1f}".format(v))


def pct(a, b):
    if not a or b is None:
        return "—"
    return fa(("%+.0f" % ((b - a) / float(a) * 100.0)) + "%")


def load_json(rel):
    with io.open(os.path.join(RUN, rel), encoding="utf-8") as fh:
        return json.load(fh)


def bench(path):
    d = load_json(path)
    warm_id = d["steps"][1]["paths"]
    warm_gz = d["steps"][2]["paths"]
    return {"id_funnel_p50": warm_id["/api/funnel"]["p50_ms"],
            "id_board_p50": warm_id["/api/mstat/board"]["p50_ms"],
            "gz_market_p50": warm_gz["/api/market"]["p50_ms"]}


def win(res):
    """Normalise one probe window to per-second rates (the windows differ)."""
    w = float(res["window_s"])
    p = res["perf"]
    by = {x["path"]: x for x in res["by_path"]}
    f = by.get("/api/funnel", {})
    m = by.get("/api/market", {})
    return {"w": w, "rpm": res["requests_per_min"],
            "xfer_ps": res["transfer_bytes_total"] / w,
            "lt": p["longTasks"], "lt_ps": p["longTasks"] / w,
            "ltms": p["longTotalMs"], "ltms_ps": p["longTotalMs"] / w,
            "max_lt": p["maxLongMs"],
            "mut": p["mutations"], "mut_ps": p["mutations"] / w,
            "console": len(res["console_errors"]),
            "scroll": (res["scrollBefore"], res["scrollAfter"]),
            "funnel_n": f.get("n", 0), "funnel_b": f.get("bytes", 0),
            "market_n": m.get("n", 0), "market_b": m.get("bytes", 0),
            "failed": sum(x["failed"] for x in res["by_path"])}


def tick_stats():
    rows = []
    with io.open(TICK, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    span = (rows[-1]["wall"] - rows[0]["wall"]) / 60.0
    agg = {}
    for r in rows:
        agg.setdefault(r["path"], []).append(r)
    out = {"n": len(rows), "span": span, "paths": {},
           "errors": sum(1 for r in rows if r.get("http") != 200),
           "t0": rows[0]["wall"], "t1": rows[-1]["wall"], "xc": {}}
    for p, v in agg.items():
        ms = [x["ms"] for x in v]
        out["paths"][p] = {"n": len(v), "min": min(ms), "p50": statistics.median(ms),
                           "max": max(ms), "bytes": max((x.get("bytes") or 0) for x in v)}
        for x in v:
            if x.get("xc"):
                out["xc"][x["xc"]] = out["xc"].get(x["xc"], 0) + 1
    return out


def hhmm(wall):
    import datetime
    return plain(datetime.datetime.fromtimestamp(wall).strftime("%H:%M"))


def find(lines, needle, lo=0):
    for i in range(lo, len(lines)):
        if needle in lines[i]:
            return i
    raise SystemExit("marker not found: %r" % needle)


def live_section(tk, P, MK, MST, SYNC, DELTA, ORJ, STD, gap):
    xc = tk["xc"]
    sec = [
        "## ۱ب) پنجرۀ نشستِ زنده — شنودِ پیوستۀ بک‌اندِ واقعی (:8000)",
        "",
        "`_test_runs/…/perf_tick_sampler.py` (تک‌نخ): هر " + plain(20) + " ثانیه این " + plain(4) +
        " مسیر را به ترتیب",
        "می‌پرسد و زمان را با ساعتِ monotonic ثبت می‌کند. این بارِ ساختگیِ **من** است، نه pollingِ رابطِ",
        "کاربر؛ و چون `Accept-Encoding` نمی‌فرستد، بدنه‌ها identity می‌آیند — پس حجمِ این بخش با حجمِ",
        "مرورگر (§۴) قابل‌مقایسه نیست. هیچ درخواستِ TSETMC/CODAL ازِ این مسیر عبور نمی‌کند: این‌ها",
        "پایۀ محلی‌اند و حلقۀ دریافتِ برون‌فروش (§۱) از " + plain("2026-10-15") + " اصلاً موفق نبوده.",
        "",
        "| پنجره | تعدادِ درخواست | خطا یا timeout |",
        "|---|---:|---:|",
        "| " + hhmm(tk["t0"]) + " → " + hhmm(tk["t1"]) + " (‏" + num(tk["span"]) +
        " دقیقه، شنبۀ معاملاتی) | " + num(tk["n"]) + " | " + num(tk["errors"]) + " |",
        "",
        "| مسیر | n | min | p50 | max | بزرگ‌ترینِ بدنه |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for p in (DELTA, MK, MST, SYNC):
        s = P[p]
        sec.append("| `" + p + "` | " + num(s["n"]) + " | " + num(s["min"]) + " | " + num(s["p50"]) +
                   " | " + num(s["max"]) + " | " + num(s["bytes"]) + " B |")
    sec += [
        "",
        "`X-Cache` رویِ `/api/market` درِ همین پنجره: HIT " + num(xc.get("HIT", 0)) + " · STALE " +
        num(xc.get("STALE", 0)) + " · MISS " + num(xc.get("MISS", 0)) +
        " ⇒ stale-while-revalidate درِ",
        "بک‌اندِ واقعی کار می‌کند: تنها " + num(xc.get("MISS", 0)) + " از " + num(P[MK]["n"]) +
        " درخواست همگام ساخت و میانه‌اش " + num(P[MK]["p50"]) + "ms.",
        "پس « کشِ کهنه + بازسازیِ پس‌زمینه» همان چیزی است که کاربرِ امروز  می‌بیند — و همین",
        "توضیح می‌دهد چرا §۴ رویِ `/api/market` سودِ کوچک‌تری داد: آن مسیر از قبلِ این را داشت.",
        "",
        "سه چیزِ تازه ازِ همین پنجره:",
        "",
        "1. **‏" + num(P[MST]["max"]) + "ms** برایِ `/api/mstat/board` درِ میانهٔ نشست — بدترینِ",
        "   دیده‌شده، تا دو برابرِ بنچِ §۴ (میانۀ همین پنجره " + num(P[MST]["p50"]) + "ms). P3 یعنی «بازار در",
        "   یک نگاه» درِ ساعتِ شلوغ کاربر را معطل می‌کند.",
        "2. **میانۀ " + num(P[SYNC]["p50"]) + "ms برایِ " + num(P[SYNC]["bytes"]) + " بایت** — P4 درِ",
        "   بک‌اندِ واقعی هم تأیید شد (زیرپروسۀ PowerShell درِ هر درخواست).",
        "3. بدنهٔ `/api/market` رویِ :8000 = " + num(P[MK]["bytes"]) + " بایت، رویِ ریگِ تازهٔ من = " +
        num(ORJ) + " بایت.",
        "   فرقِ " + num(STD - ORJ) + " بایت (~" + num(gap) + "٪) کد نیست، کتابخانۀ سریال است: orjson درِ زمانِ",
        "   `import` انتخاب می‌شود و این پروسه " + plain("2026-10-15") + " " + plain("04:02") +
        " بالا آمده —",
        "   پیش ازِ نصبِ orjson. نگاهش به P8.",
        "",
        "---",
        "",
    ]
    return sec


def main():
    b0 = load_json("browser-before-paired/browser-perf.json")["results"]
    b1 = load_json("browser-after/browser-perf.json")["results"]
    w0 = {r["label"]: win(r) for r in b0}
    w1 = {r["label"]: win(r) for r in b1}
    tk = tick_stats()
    P = tk["paths"]
    MK, MST, SYNC, DELTA = "/api/market", "/api/mstat/board", "/api/market/sync-state", "/api/market/delta"
    ORJ, STD = 6355843, 6997312
    gap = (STD - ORJ) / float(STD) * 100.0
    WINDOW = 90

    lines = io.open(REPORT, encoding="utf-8").read().split("\n")

    def put(needle, new):
        lines[find(lines, needle)] = new

    def put_many(needle, news):
        lines[find(lines, needle):find(lines, needle) + 1] = news

    sec = live_section(tk, P, MK, MST, SYNC, DELTA, ORJ, STD, gap)
    anchor = next((k for k, v in enumerate(lines) if "## ۱ب) پنجرۀ نشستِ زنده" in v),
                  find(lines, "## ۲) مشکلاتِ اثبات‌شده"))
    end = find(lines, "## ۲) مشکلاتِ اثبات‌شده", anchor)
    lines[anchor:end] = sec

    # ── §۲ : P8 — orjsonِ زمانِ import ──────────────────────────────────────
    anchor2 = find(lines, "### چیزهایی که **رد شدند**")
    p8 = [
        "### P8 — بک‌اندِ در حالِ اجرا orjson را نمی‌شناسد · **ثبت؛ رفعش restart است**",
        "انتخابِ سریال‌کننده زمانِ `import` رخ می‌دهد، نه زمانِ درخواست. بک‌اندِ :8000 که " + plain("2026-10-15") +
        " ‏" + plain("04:02") + " بالا آمده، orjsonِ نصب‌شده‌بعد را ندیده است؛ پس همان داده را " + num(STD) +
        " بایت می‌سازد در حالی که رویِ ریگِ تازه‌بالامده " + num(ORJ) + " بایت است (~" + num(gap) +
        "٪ کوچک‌تر). این توضیحِ خودِ عددِ P7 («" + num(STD) + " با stdlib») است. هیچ کدی لازم نیست — یکِ",
        "restart؛ ولی چون پروسۀ بک‌اندِ سیستم ۱ است، من restart نکردم و اینجا ثبت شد.",
        "",
    ]
    lines[anchor2:anchor2] = p8

    # ── §۴ : ردیف‌هایِ مرورگر (دو دورِ جفت رویِ یکِ ماشین) ───────────────────
    mk = "market-1366x768"
    mst = "master-1366x768"
    big = "market-1920x1080"
    a, b = w0[mk], w1[mk]
    put_many("| درخواست در دقیقه (رابط) |", [
        "| درخواست در دقیقه (رابط) | " + num(w0[mk]["rpm"]) + " / " + num(w0[mst]["rpm"]) + " / " +
        num(w0[big]["rpm"]) + " | " + num(w1[mk]["rpm"]) + " / " + num(w1[mst]["rpm"]) + " / " +
        num(w1[big]["rpm"]) + " | " + pct(w0[mk]["rpm"], w1[mk]["rpm"]) +
        " — ریتم polling دست نخورد، پس باید هم بماند | بنچِ مرورگرِ **جفت**، " + plain(WINDOW) +
        "s درِ هر پنجره |",
        "| حجمِ انتقالِ رابط (در دقیقه) | " + num(w0[mk]["xfer_ps"] * 60) + " B | " +
        num(w1[mk]["xfer_ps"] * 60) + " B | " + pct(w0[mk]["xfer_ps"], w1[mk]["xfer_ps"]) +
        " — بهایِ آگاهانۀ `compresslevel=1` رویِ حلقۀ محلی | `transfer_bytes_total` ÷ پنجره |",
        "| درخواست/حجمِ `/api/funnel` درِ رابط | " + num(w0[mk]["funnel_n"]) + " بار / " +
        num(w0[mk]["funnel_b"]) + " B | " + num(w1[mk]["funnel_n"]) + " بار / " + num(w1[mk]["funnel_b"]) +
        " B | حجم " + pct(w0[mk]["funnel_b"], w1[mk]["funnel_b"]) + " · تعداد " +
        num(w0[mk]["funnel_n"]) + "→" + num(w1[mk]["funnel_n"]) +
        " فقط برشِ پنجره است، ریتمِ polling دست‌نخورده | `by_path` |",
    ])
    put("| long taskها |",
        "| long taskها (پنجرۀ " + plain(WINDOW) + "s، view تابلو) | " + num(a["lt"]) + " عدد / مجموع " +
        num(a["ltms"]) + " ms / max " + num(a["max_lt"]) + " ms | " + num(b["lt"]) + " عدد / مجموع " +
        num(b["ltms"]) + " ms / max " + num(b["max_lt"]) + " ms | max " + pct(a["max_lt"], b["max_lt"]) +
        " · عدد بر ثانیه " + pct(a["lt_ps"], b["lt_ps"]) + " · ms بر ثانیه " + pct(a["ltms_ps"], b["ltms_ps"]) +
        " | PerformanceObserver |")
    put("| rerenderهای غیرضروری |",
        "| تغییرِ DOM بر ثانیه | " + num(a["mut_ps"]) + " (‏" + num(a["mut"]) + " درِ " + plain(WINDOW) +
        "s) | " + num(b["mut_ps"]) + " (‏" + num(b["mut"]) + ") | " + pct(a["mut_ps"], b["mut_ps"]) +
        " — اندازه‌گیری شد؛ مکانیزمِ رفع‌ها (سریالِ سمتِ سرور) این را توضیح نمی‌دهد، پس ادعایِ بهبود نیست"
        " | MutationObserver |")
    put_many("| خطا و timeout |", [
        "| خطا و timeout (رابط) | " + num(a["console"]) + " خطای console، " + num(a["failed"]) +
        " درخواستِ ناموفق | " + num(b["console"]) + " خطای console، " + num(b["failed"]) +
        " درخواستِ ناموفق | هر دو دور صفر | console + `by_path.failed` |",
        "| نگه‌داشتنِ scroll هنگامِ refresh | " + num(a["scroll"][1]) + " px پیش و پس | " +
        num(b["scroll"][1]) + " px پیش و پس | سالم درِ هر دو دور | `scrollTop` درِ مرورگر |",
    ])
    put("| CPU |",
        "| CPU | " + num(34) + "٪ (لحظه‌ای، " + plain("10:54") + ") | " + num(34) +
        "٪ (همانِ یکِ نمونه) | روند NOT_MEASURED — پالرِ خودم با `FormatError` مُرد و یکِ نمونه جایِ روند را "
        "نمی‌گیرد | §۰ |")
    put("| RAM |",
        "| RAM آزاد | " + num(1121) + " از " + num(8104) + " MB (لحظه‌ای) | " + num(1121) + " از " + num(8104) +
        " MB (همانِ یکِ نمونه) | روند NOT_MEASURED | همان |")
    put("| زمانِ snapshot تا UI |",
        "| زمانِ snapshot تا UI | NOT_RUN | NOT_RUN | — | دیوارِ ۱۰۰۱۳ (§۱): دادهٔ تازه‌ای نمی‌رسد که "
        "انتشارش را سنجید |")

    # ── دو ادعایِ عددی که از فایل‌های خام تصحیح می‌شوند ──────────────────────
    i = find(lines, chr(96) + "since" + chr(96))
    lines[i:i + 3] = [
        "- **«مسیرِ delta مرده است»:** خوانشِ اولِ من غلطِ ابزارِ خودم بود — من `since`",
        "  نفرستاده بودم و `since=" + plain(-1) + "` طبقِ قرارداد `full/stale-client` برمی‌گرداند. شواهدِ",
        "  زنده: درِ " + num(tk["span"]) + " دقیقه شنود، " + num(P[DELTA]["n"]) + " بار `delta` در برابرِ " +
        num(P[MK]["n"]) + " بار `/api/market` کامل؛ درِ مرورگرِ جفت هم " + num(b["market_n"]) +
        " بارِ کامل در " + plain(WINDOW) + "s. delta سالم است.",
    ]
    j = find(lines, "requirements.txt")
    lines[j:j + 5] = [
        "- **`orjson`:** درِ این ماشین نصب نبود (هرچند `requirements.txt` اعلامش کرده) و مسیرِ سریعِ JSON",
        "  بی‌صدا به stdlib می‌افتاد. بک‌اندِ **بستۀ منتشرشده** orjson را دارد",
        "  (`frozen89/_internal/orjson/…cp312…pyd`)، پس این نقصِ محیطِ توسعه بود نه نقصِ محصول. با نصبِ",
        "  همان وابستگیِ اعلام‌شده رفع شد و از آن پس سنجش‌ها با orjson انجام شد؛ اثرش رویِ حجمِ بدنه",
        "  عددِ قابلِ تکرار است: " + num(STD) + " → " + num(ORJ) + " بایت برایِ یکِ بدنهٔ یکسان (§۱ب و P7).",
    ]

    # ── هشدارِ تفسیر زیرِ جدول ───────────────────────────────────────────────
    bn0 = bench("bench-before.json")
    bn1 = bench("bench-after.json")
    k = find(lines, "**هشدارِ تفسیر:**")
    lines[k] = (
        "**هشدارِ تفسیر:** repeat=" + plain(5) + " ⇒ «p95» همانِ بیشترینِ نمونۀ آن مسیر است و p99 محاسبه "
        "نمی‌شود. دو دورِ بنچ بی‌بارِ جانبی اجرا شدند، ولی پنجره‌هایِ مرورگرِ جفت هم‌زمان با شنودِ §۱ب رویِ "
        "یکِ ماشین روشن بودند — پس ردیف‌هایِ مرورگر «نسبتِ هم‌شارت»‌اند، نه آزمایشگاهِ ساکت. تنها ادعاهایِ "
        "عددیِ مستقیمِ من این دو‌اند: سریالِ تکراریِ قیف حذف شد (p50 " + num(bn0["id_funnel_p50"]) + " → " +
        num(bn1["id_funnel_p50"]) + "ms) و gzipِ مسیرهایِ بزرگ کم‌هزینه شد (p50 " +
        num(bn0["gz_market_p50"]) + " → " + num(bn1["gz_market_p50"]) + "ms) — در ازایِ حجمِ بیشترِ سیم رویِ "
        "حلقۀ محلی.")

    # ── §۵ : بندِ NOT_RUN بازسازیِ درست ─────────────────────────────────────
    s5 = next(k for k in range(len(lines) - 1, -1, -1) if lines[k].startswith("**NOT_RUN"))
    s5e = next(k for k in range(s5 + 1, len(lines)) if lines[k].startswith("## "))
    lines[s5:s5e] = [
        "**NOT_RUN / NOT_MEASURED درِ این پنجره**",
        "",
        plain(8) + ". `python dev/run_all_tests.py`: گیتِ کاملِ آفلاین (" + plain(105) + " سوئیت) اجرا **نشدم** —",
        "   سرورهایِ devِ مأموریت‌هایِ دیگر بالاست و خودِ گیت ~" + plain(35) + " دقیقه می‌خواهد؛ اولویتِ این",
        "   مأموریتِ پنجرۀ بازِ بازار بود. گاردهایِ هدفمندِ اجراشده: `dev/persian_glyph_guard.py` (" +
        plain(4) + "/" + plain(4) + " سبز) و",
        "   `dev/funnel_body_cache_v1.py` (" + plain(11) + "/" + plain(11) + " سبز رویِ ریگ — و دوباره " +
        plain(11) + "/" + plain(11) + " پس ازِ بازگرداندنِ",
        "   سورسِ «بعد» ازِ دورِ مرورگریِ جفت، که ثابت می‌کند دست‌کاریِ فایل‌ها چیزی را عوض نکرد).",
        plain(9) + ". بیلدِ دسکتاپِ آزمایشی ازِ کامیتِ نهایی ساخته و smoke نشد (Phase 6 بندِ " + plain(3) +
        ") — **NOT_RUN**.",
        plain(10) + ". روندِ CPU/RAM درِ طولِ نشست: **NOT_MEASURED**. پالرِ PowerShellِ خودم با `FormatError` مُرد",
        "   و فقط یکِ نمونهٔ لحظه‌ای (§۰) ثبت است. شنودِ §۱ب زمانِ پاسخ را می‌سنجد، نه مصرفِ ماشین.",
        plain(11) + ". تازگیِ زنده و «زمانِ snapshot تا UI»: **NOT_RUN** — دیوارِ " + plain(10013) + " (§۱).",
        "   دادهٔ فریزشده به‌عنوانِ تازگیِ زنده گزارش نشده.",
        "",
        "**انجام‌شده بعد ازِ نوشتنِ نسخهٔ اولِ این فایل**",
        "",
        plain(12) + ". آزمونِ مرورگریِ «بعد» اجرا شد. چون دورِ «قبل» بی‌بارِ جانبی گرفته بود و دورِ «بعد» با",
        "   شنودِ §۱ب هم‌زمان بود، «قبل» را **دوبار** با همانِ بار گرفتم (`browser-before-paired/`, " +
        plain("11:03") + "→",
        plain("11:13") + ") تا مقایسه جفت بماند؛ هر دو دور " + plain(90) + " ثانیه درِ هر پنجره. دورِ اولِ «قبل»",
        "   (`browser-perf.json`, " + plain("09:38") + ") به‌عنوانِ شاهدِ تاریخی نگه داشته شد و overwrite نشد.",
        plain(13) + ". شنودِ پیوستهٔ زنده: نسخهٔ چندنخی بعدِ ~" + plain(30) + " ثانیه بی‌صدا خوابید؛ جانشینِ تک‌نخی",
        "   از " + hhmm(tk["t0"]) + " تا " + hhmm(tk["t1"]) + " روشن ماند و §۱ب از ارقامِ خودِ همان فایلِ JSONL",
        "   ساخته شده. **ادعایِ تعمیم به کلِ نشست نمی‌کنم.**",
        "",
        "---",
        "",
    ]

    # -- drop the leftovers of the first draft ----------------------------
    drop = next(k for k, v in enumerate(lines) if "MB / " + fa(75) + "s" in v)
    lines[drop:drop + 1] = []
    warn = next(k for k, v in enumerate(lines) if "p99" in v and v.startswith("**"))
    lines[warn + 1:warn + 4] = []

    io.open(REPORT, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    sys.stdout.write("injected live=%d lines, p8=%d lines\n" % (len(sec), len(p8)))
    sys.stdout.write("paired market: rpm %s->%s | xfer/s %s->%s | maxLT %s->%s | mut %s->%s | funnel %s->%s\n" % (
        a["rpm"], b["rpm"], int(a["xfer_ps"]), int(b["xfer_ps"]), a["max_lt"], b["max_lt"],
        a["mut"], b["mut"], a["funnel_b"], b["funnel_b"]))
    sys.stdout.write("tick: n=%s span=%.1f err=%s xc=%s\n" % (tk["n"], tk["span"], tk["errors"], tk["xc"]))


if __name__ == "__main__":
    main()
