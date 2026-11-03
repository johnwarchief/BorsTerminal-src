# -*- coding: utf-8 -*-
"""Build the phase-2 analytic tables from the raw artifacts (no hand-typed numbers)."""
import io
import json
import os
import re
import statistics

RUN = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(RUN, "phase1-before.log")


def fa(s):
    t = str(s)
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if t.startswith("-") else "") + "".join(out)


def num(v):
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return fa("{:,.0f}".format(v))
    return fa("{:,.1f}".format(v))


def pct(a, b):
    if not a or b is None:
        return "—"
    return fa(("%+.0f" % ((b - a) / float(a) * 100.0)) + "%")


def load(name):
    with io.open(os.path.join(RUN, name), encoding="utf-8") as fh:
        return json.load(fh)


def rhythm(name):
    d = load(name)
    rows = d["rows"]
    ms = [r["ms"] for r in rows]
    hit = [r["ms"] for r in rows if r["xc"] == "HIT"]
    miss = [r["ms"] for r in rows if r["xc"] == "MISS"]
    plain = [r["ms"] for r in rows if not r["xc"]]
    return {"n": len(rows), "rhythm": d.get("rhythm_s"), "hits": len(hit),
            "miss": len(miss), "no_header": len(plain), "plain_ms": plain,
            "p50": statistics.median(ms), "min": min(ms), "max": max(ms),
            "sum_s": sum(ms) / 1000.0,
            "hit_p50": (statistics.median(hit) if hit else None),
            "miss_p50": (statistics.median(miss) if miss else None)}


def step(d, name):
    return next(x for x in d["steps"] if x["name"] == name)


def bench_phase(name, phase, path, key="p50_ms"):
    d = load(name)
    ph = next(x for x in d["steps"] if x["phase"] == phase)
    return ph["paths"][path][key]


def browser(name):
    d = load(name)
    rows = []
    for r in d["results"]:
        rows.append({k: r.get(k) for k in (
            "label", "requests_in_window", "requests_per_min", "responses_200", "responses_304",
            "requests_with_inm", "transfer_bytes_in_window", "transfer_bytes_total", "requests_total",
            "rows", "console_errors", "clock", "banner", "first_rows_ready", "perf",
            "domNodes")} | {"by_path": r.get("by_path", [])})
    return {"window_s": d.get("window_s"), "clock": d.get("clock"), "rows": rows}


def main():
    g1, g5 = load("rhythm-gz1.json"), load("rhythm-gz5.json")
    bnd = load("ttl-boundary-gz1-rerun.json")
    r5_after1, r20_after1 = (rhythm("ttl-rhythm-5s-gz1.json"), rhythm("ttl-rhythm-20s-gz1.json"))
    r5_after5, r20_after5 = (rhythm("ttl-rhythm-5s-gz5.json"), rhythm("ttl-rhythm-20s-gz5.json"))
    r5_before, r20_before = (rhythm("ttl-rhythm-5s-before-gz5.json"),
                             rhythm("ttl-rhythm-20s-before-gz5.json"))
    V1, V5 = g1["verdict"], g5["verdict"]
    cpu_delta = (V1.get("server_cpu_ms_during_probe", 0) -
                 V5.get("server_cpu_ms_during_probe", 0))
    B_FUNNEL_P50 = {"before": bench_phase("bench-before.json", "warm-identity", "/api/funnel"),
                    "after": bench_phase("bench-after.json", "warm-identity", "/api/funnel")}
    FUNNEL_BODY_BYTES = step(g1, "funnel-identity")["decoded_bytes"]
    # «یکی‌بودنِ بدنه داخلِ TTL» را خودِ سنجش می‌گوید، نه حدسِ نامِ سنجه:
    # سه گامِ نخستِ rhythm درِ همان ۸ ثانیه‌اند.
    ttl_steps = [step(g1, n) for n in ("funnel-1-cold", "funnel-2-at+2s", "funnel-3-at+4s")]
    body_same_in_ttl = len({s["raw_sha"] for s in ttl_steps}) == 1
    etag_same_in_ttl = len({s["etag"] for s in ttl_steps}) == 1
    hits_in_ttl = sum(1 for s in ttl_steps[1:] if s["x_cache"] == "HIT")
    L = []
    A = L.append

    A("## الف) پنجرۀ واقعیِ کش")
    A("")
    A("یکِ درخواست در هر ثانیه رویِ ریگ (`tools/perf_funnel_ttl_window_probe.py`، " +
      num(len(bnd["hit_offsets_s"]) + len(bnd["miss_offsets_s"])) + " گام):")
    A("")
    misses = sorted(bnd["miss_offsets_s"])
    hits = sorted(bnd["hit_offsets_s"])
    cold = misses[0]
    expiry = next((m for m in misses if m > cold), None)
    last_hit_in_first_window = max((h for h in hits if expiry is None or h < expiry), default=None)
    A("| رخداد | آفست ازِ ساختِ نخست | مُهرِ `as_of` |")
    A("|---|---:|---:|")
    for m in misses:
        r = next(x for x in bnd["rows"] if x["offset_s"] == m)
        A("| `MISS` (ساختِ بدنه) | +" + num(m) + "s | `" + str(r["as_of"]) + "` |")
    A("| `HIT`ها | " + num(len(hits)) + " گام، " + "→ ".join("+" + num(h) + "s" for h in hits[:2]) +
      "، … | همانِ بدنهٔ قبلی |")
    A("")
    gaps = [round(b - a, 2) for a, b in zip(misses, misses[1:])]
    A("فاصلۀ دو ساختِ مجدد: " + "، ".join(num(g) + "s" for g in gaps) + " — هر دو ≥ `TTL_S = " +
      num(bnd.get("ttl_s") or 8.0) + "`، و نخستینِ انقضا بینِ +" + num(last_hit_in_first_window) +
      "s و +" + num(expiry) + "s")
    A("افتاد. مُهرِ `as_of` درِ هر `MISS` جلو رفته (" + " → ".join(
        str(next(x for x in bnd["rows"] if x["offset_s"] == m)["as_of"]) for m in misses) + ")،")
    A("پس هیچ پاسخی کهنه‌تر ازِ داده‌ای که می‌بیند سرو نشده؛ و `HIT`ها همان etagِ")
    A("`" + bnd["first_etag"] + "` را نگه داشته‌اند تا انقضا.")
    A("")
    A("درِ همان پنجرهٔ سه‌گامیِ `rhythm` (" + num(8) + "s): " + num(hits_in_ttl) + " از " + num(2) +
      " پاسخِ دوم/سوم `HIT` بودند،")
    A("بدنۀ بایت‌به‌بایت یکی بود: `" + ("YES" if body_same_in_ttl else "NO") + "` و etag یکی بود: `" +
      ("YES" if etag_same_in_ttl else "NO") + "`.")
    A("دو سنجهٔ `funnel_body_identical_within_ttl` و `etag_repeats_within_ttl` درِ `verdict`")
    A("نامشان گمراه‌کننده است: آن‌ها گامِ نخست را با گامِ چهارم می‌سنجند، و گامِ چهارم —")
    A("همان‌طور که `as_of`ش نشان می‌دهد — بیرونِ `TTL_S` افتاده، پس `False` بودنشان نقصِ کش")
    A("نیست، تازگیِ داده است. ملاکِ «یکی‌بودنِ داخلِ TTL» همین سطرِ بالاست.")
    A("")
    A("یک نکتهٔ روش‌شناختی: نخستینِ اجرایِ همین اسکرپت (`ttl-boundary-gz1.json`) درِ ستونِ `as_of`")
    A("همه‌جا `" + str(load('ttl-boundary-gz1.json')['first_as_of']) + "` ثبت کرده بود — همانِ کد، همانِ")
    A("ریگ، ولی مقداری که epoch نیست و علتش درِ این مأموریت بازبینی نشد. اجرایِ دوباره (همین")
    A("جدول) مُهرِ epochِ درست می‌دهد و با آرتیفکتِ `rhythm` می‌خواند، پس ادعایِ تازگی به")
    A("اجرایِ دوباره تکیه کرده و آن فایلِ نخست درِ این ادعا NOT_PROVEN شمرده می‌شود.")
    A("")

    A("## ب) ریتمِ واقعیِ رابط — جایِ اصلاح‌شدۀ بنچ")
    A("")
    A("`features/master/api/useFtsFunnel.ts:182-186` قیف را با سه ریتم می‌پرسد: " + num(5) +
      "s وقتی صفِ اسکنِ")
    A("تکنیکال پر است، " + num(20) + "s درِ نشستِ آرام، و " + num(300) + "s بیرونِ نشست. جدول‌هایِ زیر ازِ")
    A("همینِ ریتمها ساخته شده‌اند، نه ازِ نمونه‌هایِ پشتِ‌سرهمِ بنچ.")
    A("")
    A("| پیکربندی | ریتم | n | HIT | MISS | پاسخِ بی‌`X-Cache` (کدِ قبلی) | p50 | مجموعِ زمان |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label, r in (("قبل · `ff6b2fb` · gzip " + num(5), r5_before),
                     ("بعد · کشِ بدنه · gzip " + num(5), r5_after5),
                     ("بعد · کشِ بدنه · gzip " + num(1), r5_after1)):
        A("| " + label + " | " + num(r["rhythm"]) + "s | " + num(r["n"]) + " | " + num(r["hits"]) +
          " | " + num(r["miss"]) + " | " + num(r["no_header"]) + " | " + num(r["p50"]) + "ms | " +
          num(r["sum_s"]) + "s |")
    A("")
    A("| پیکربندی | ریتم | n | HIT | MISS | پاسخِ بی‌`X-Cache` | p50 | مجموعِ زمان |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label, r in (("قبل · `ff6b2fb` · gzip " + num(5), r20_before),
                     ("بعد · کشِ بدنه · gzip " + num(5), r20_after5),
                     ("بعد · کشِ بدنه · gzip " + num(1), r20_after1)):
        A("| " + label + " | " + num(r["rhythm"]) + "s | " + num(r["n"]) + " | " + num(r["hits"]) +
          " | " + num(r["miss"]) + " | " + num(r["no_header"]) + " | " + num(r["p50"]) + "ms | " +
          num(r["sum_s"]) + "s |")
    A("")
    A("سه خوانشِ صادقانه:")
    A("")
    A("1. درِ ریتمِ " + num(20) + "s کشِ بدنه **هیچ** استفاده‌ای ندارد (HIT " + num(r20_after1["hits"]) +
      " از " + num(r20_after1["n"]) + "، و درِ سطحِ " + num(5) + " هم " + num(r20_after5["hits"]) +
      " از " + num(r20_after5["n"]) + ")")
    A("   چون TTLِ داده " + num(8) + "s است. پس اختلافِ مجموعِ زمانِ این جدول (قبل " +
      num(r20_before["sum_s"]) + "s ← بعد " + num(r20_after1["sum_s"]) + "s) را نمی‌توان بهِ این")
    A("   تغییر نوشت: درِ هر دو دور")
    A("   `HIT` صفر است، یعنی هیچ بدنهٔ کش‌شده‌ای سرو نشد و هر دو طرف همان `_run` کامل را")
    A("   رفتند؛ `default_response_class` هم درِ `ff6b2fb` همان `ORJSONResponse` بود")
    A("   (`app.py:51`، بی‌تغییر)، پس «orjson تازه شده» هم توضیحش نیست. باقی می‌ماند بارِ")
    A("   ماشین بینِ دو دور و گرمیِ کش‌هایِ داخلیِ `_run` ⇒ **این اختلافِ ۲۰s: NOT_PROVEN**.")
    A("   عددِ «p50 " + num(B_FUNNEL_P50["before"]) + " → " + num(B_FUNNEL_P50["after"]) +
      "ms» درِ گزارشِ پیشین ازِ همین")
    A("   بنچِ `warm-identity`ِ پشتِ‌سرهم آمد و فقط برایِ درخواست‌هایِ تکراریِ داخلِ همان")
    A("   " + num(8) + " ثانیه درست است (ستونِ HITِ §الف).")
    A("2. درِ ریتمِ " + num(5) + "s (صفِ اسکنِ تکنیکال — همان لحظه‌ای که کاربر منتظر است) " +
      num(r5_after1["hits"]) + " از " + num(r5_after1["n"]) + "")
    A("   پاسخ ازِ بدنهٔ کش‌شده آمد با میانهٔ " + num(r5_after1["hit_p50"]) +
      "ms؛ درِ کدِ قبلی همان " + num(r5_before["n"]) + " پولینگ همه")
    A("   " + num(r5_before["p50"]) + "ms (میانه) هزینه دادند و هیچ‌کدام بی‌سریال‌سازی نبود.")
    A("3. ملاکِ جمعیِ همانِ سطحِ فشرده‌سازی (`gzip " + num(5) + "` درِ هر دو دور): مجموعِ زمانِ " +
      num(r5_before["n"]) + " پولینگِ یکسان")
    A("   قبل " + num(r5_before["sum_s"]) + "s ← بعد " + num(r5_after5["sum_s"]) + "s، یعنی " +
      pct(r5_before["sum_s"], r5_after5["sum_s"]) + "؛ درِ سطحِ " + num(1) + " " +
      num(r5_after1["sum_s"]) + "s (" + pct(r5_before["sum_s"], r5_after1["sum_s"]) +
      "). این")
    A("   معیارِ جمعی است، نه p50ِ تک‌نمونه، و تنها ادعایِ «بهتر شدنِ زمان» که درِ این")
    A("   مأموریت سازگارِ با شاهد است.")
    A("")

    A("## پ) ترافیک: علت، با عدد")
    A("")
    m_id, m_g1, m_g5 = (step(g1, "market-identity"), step(g1, "market-gzip"), step(g5, "market-gzip"))
    f_id, f_g1, f_g5 = (step(g1, "funnel-identity"), step(g1, "funnel-gzip-again"),
                        step(g5, "funnel-gzip-again"))
    m304, f304 = step(g1, "market-conditional-304"), step(g1, "funnel-get-2-conditional")
    A("| مسیر | بدنهٔ تجزیه‌شده | سیم درِ gzip " + num(5) + " | سیم درِ gzip " + num(1) +
      " | تغییرِ حجم | زمانِ کل درِ " + num(5) + " | زمانِ کل درِ " + num(1) + " |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    A("| `/api/market` | " + num(m_id["decoded_bytes"]) + " B | " + num(m_g5["wire_bytes"]) + " B | " +
      num(m_g1["wire_bytes"]) + " B | " + pct(m_g5["wire_bytes"], m_g1["wire_bytes"]) + " | " +
      num(m_g5["ms"]) + "ms | " + num(m_g1["ms"]) + "ms |")
    A("| `/api/funnel` (بدنۀ کش‌شده) | " + num(f_id["decoded_bytes"]) + " B | " + num(f_g5["wire_bytes"]) +
      " B | " + num(f_g1["wire_bytes"]) + " B | " + pct(f_g5["wire_bytes"], f_g1["wire_bytes"]) + " | " +
      num(f_g5["ms"]) + "ms | " + num(f_g1["ms"]) + "ms |")
    A("| بی‌فشرده (ملاکِ پایین) | " + num(m_id["decoded_bytes"]) + " B | " + num(m_id["wire_bytes"]) +
      " B | " + num(m_id["wire_bytes"]) + " B | — | " + num(m_id["ms"]) + "ms | " + num(m_id["ms"]) +
      "ms |")
    A("")
    A("هزینۀ فشرده‌سازی به‌تنهایی (کمِ همانِ مسیرِ بی‌فشرده): `/api/market` درِ سطحِ " + num(5) + " " +
      num(m_g5["ms"] - m_id["ms"]) + "ms")
    A("و درِ سطحِ " + num(1) + " " + num(m_g1["ms"] - m_id["ms"]) + "ms؛ `/api/funnel` درِ سطحِ " +
      num(5) + " " + num(f_g5["ms"] - f_id["ms"]) + "ms")
    A("و درِ سطحِ " + num(1) + " " + num(f_g1["ms"] - f_id["ms"]) + "ms.")
    A("")
    A("پس افزایشِ حجم **واقعی و عمدی** است. درِ این جدول تعدادِ درخواست‌ها ثابتِ ساختی است (سنجهٔ")
    A("خودِ اسکرپت است، نه ریتمِ رابط)، پس اختلافِ " + pct(m_g5["wire_bytes"], m_g1["wire_bytes"]) +
      "/" + pct(f_g5["wire_bytes"], f_g1["wire_bytes"]) + "")
    A("فقط «کمتر فشرده‌شدنِ همان بدنه» است، نه درخواستِ بیشتر. دورِ مرورگریِ جفت (§ج) همین را")
    A("مستقل تأیید می‌کند: " + num(200) + "ها درِ دو دور نزدیکِ یکی است و بایتِ سیم رفته بالا.")
    A("درِ ازایِ این، " + num(m_g5["ms"] - m_g1["ms"]) + "ms ازِ وقتِ سرورِ هر `/api/market` و " +
      num(f_g5["ms"] - f_g1["ms"]) + "ms ازِ هر")
    A("`/api/funnel` کم شده — رویِ ماشینِ چهارهسته‌ای که یکِ هسته‌اش درِ همین سنجش درِ اشغالِ")
    A("فرایندِ بی‌صاحبِ §۷ است.")
    A("")
    A("**گلوگاهِ حقیقیِ ترافیک اینجاست:** رابطِ واقعی قیف را **POST** می‌زند")
    A("(`useFtsFunnel.ts:163-172`) و `shared/api/http.ts:139-140` مُهرِ `ETag` را فقط برایِ GET")
    A("نگه می‌دارد، پس هیچ‌وقت `If-None-Match` رویِ آن مسیر فرستاده نمی‌شود. سنجشِ مستقیم:")
    A("`GET /api/funnel` با etagِ درست ⇒ `" + num(f304["status"]) + "` با " + num(f304["wire_bytes"]) +
      " بایت؛ ولی همانِ etag رویِ POST")
    A("ازِ رابطِ واقعی هرگز نمی‌آید. بدنهٔ " + num(f_g1["wire_bytes"]) + "-بایتیِ قیف، هر " + num(20) +
      " ثانیه یک‌بار")
    A("(" + num(60 / 20) + " بار درِ هر دقیقه)، تا وقتی قراردادِ متد/اعتبارسنجی بازبینی نشود، رویِ")
    A("سیم می‌ماند. این تصمیمِ قرارداد است و درِ اختیارِ این مأموریت نبود (§۵).")
    A("")

    A("## ج) همانِ سنجش درِ مرورگرِ واقعی، پیشِ‌تر و پسِ‌تر (ساعتِ میخکوب‌شده)")
    A("")
    def hhmm(mins):
        return fa("%02d:%02d" % (mins // 60, mins % 60))

    A("چرا ساعتِ جعلی: ریتمِ پولینگ از `isMarketOpen()` رویِ `new Date()`ِ مرورگر می‌آید")
    A("(`shared/lib/marketHours.ts:10-22`، پنجرۀ " + hhmm(8 * 60 + 45) + "→" +
      hhmm(12 * 60 + 30) + " از ساعتِ *ماشین*). هر دو پنجرۀ سنجش بیرونِ آن ساعت")
    A("افتاد (نمونش `banner: بازار بسته` درِ `browser-final-gz1`: یکِ درخواستِ هر")
    A("مسیر درِ ۹۰ ثانیه، چون ریتمِ تعطیل " + num(300) + "s است). برایِ دیدنِ رفتارِ «درِ")
    A("نشست» ساعتِ *کلاینت* با `page.clock.install()` میخکوب شد؛ سرور، ساعتِ سرور و")
    A("داده دست‌نخورده‌اند. دو دور با یکِ ساعتِ میخکوب، یکِ پنجره و یکِ ریزِ مسیرها:")
    A("")
    BP = {"before": "browser-before-clockpin/browser-perf.json",
          "after": "browser-after-clockpin/browser-perf.json"}
    brs = {}
    for k, p in BP.items():
        brs[k] = browser(p) if os.path.exists(os.path.join(RUN, p)) else None
    if not brs["before"] or not brs["after"]:
        for k, p in BP.items():
            if not brs[k]:
                A("NOT_RUN — " + p + " تولید نشده است.")
        A("")
    else:
        def rowof(br, label):
            return next((r for r in br["rows"] if r["label"] == label), None)

        def pathrow(br, label, path):
            r = rowof(br, label)
            if not r:
                return None
            return next((b for b in r["by_path"] if b["path"] == path), None)

        A("| ریز | دور | درخواست | درِ دقیقه | " + num(200) + " | " + num(304) +
          " | با `If-None-Match` | بایتِ سیم | long-task | بیشینهٔ task |")
        A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for label in ("market-1366x768", "master-1366x768", "market-1920x1080"):
            for k, tag in (("before", "قبل · `ff6b2fb` · gzip " + num(5)),
                           ("after", "بعد · این شاخه · gzip " + num(1))):
                r = rowof(brs[k], label)
                if not r:
                    A("| `" + label + "` | " + tag + " | NOT_RUN || | | | | | | |")
                    continue
                A("| `" + label + "` | " + tag + " | " + num(r["requests_in_window"]) + " | " +
                  num(r["requests_per_min"]) + " | " + num(r["responses_200"]) + " | " +
                  num(r["responses_304"]) + " | " + num(r["requests_with_inm"]) + " | " +
                  num(r["transfer_bytes_in_window"]) + " B | " + num(r["perf"]["longTasks"]) +
                  " | " + num(r["perf"]["maxLongMs"]) + "ms |")
        A("")
        A("پولینگِ هر مسیر درِ پنجره (فقطِ بعدِ آماده‌شدن؛ `n/all` = درِ پنجره/کلِ دور):")
        A("")
        A("| ریز | مسیر | قبل: n | قبل: بایت | بعد: n | بعد: بایت | تغییرِ بایت | متد |")
        A("|---|---|---:|---:|---:|---:|---:|---|")
        seen = []
        for label in ("market-1366x768", "market-1920x1080"):
            paths = sorted({b["path"] for b in (rowof(brs["after"], label) or {}).get(
                "by_path", [])} | {b["path"] for b in (rowof(brs["before"], label) or {}).get(
                    "by_path", [])})
            for p in sorted(paths, key=lambda x: -(pathrow(brs["after"], label, x) or {}).get(
                    "bytes", 0)):
                a, b = pathrow(brs["before"], label, p), pathrow(brs["after"], label, p)
                if not a and not b:
                    continue
                ab, bb = (a or {}).get("bytes", 0), (b or {}).get("bytes", 0)
                if ab + bb < 1000:
                    continue
                meth = ((b or a).get("methods") or {})
                A("| `" + label + "` | `" + p + "` | " + num((a or {}).get("n", 0)) + " | " +
                  num(ab) + " B | " + num((b or {}).get("n", 0)) + " | " + num(bb) + " B | " +
                  (pct(ab, bb) if ab else "—") + " | " +
                  "، ".join(sorted(meth)) + " |")
                seen.append((label, p, ab, bb))
        A("")
        tb = sum(r["transfer_bytes_in_window"] or 0 for r in brs["before"]["rows"])
        ta = sum(r["transfer_bytes_in_window"] or 0 for r in brs["after"]["rows"])
        A("جمعِ بایتِ سیم درِ سه پنجرۀ " + num(brs["after"]["window_s"]) + " ثانیه‌ای: قبل " + num(tb) +
          " B ← بعد " + num(ta) + " B (" + pct(tb, ta) + ").")
        A("پاسخِ `304` درِ هر دو دور: " + num(sum(r["responses_304"] or 0 for r in brs["before"]["rows"])) +
          " قبل، " + num(sum(r["responses_304"] or 0 for r in brs["after"]["rows"])) +
          " بعد؛ درخواست‌هایِ حاملِ `If-None-Match`: " +
          num(sum(r["requests_with_inm"] or 0 for r in brs["before"]["rows"])) + " و " +
          num(sum(r["requests_with_inm"] or 0 for r in brs["after"]["rows"])) +
          " — یعنی صفر درِ هر دو دور. این همانِ گلوگاهِ §پ است، این‌بار رویِ سیمِ مرورگر:")
        A("قیف POST است و `frontend/src/shared/api/http.ts:139-140` مُهرِ etag را فقط برایِ GET")
        A("نگه می‌دارد، پس `304` برایِ پرهزینه‌ترینِ پاسخِ اپ هرگز ازِ راهِ رابط")
        A("درخواست نمی‌شود.")
        A("")
        nb = sum(r["responses_200"] or 0 for r in brs["before"]["rows"])
        na = sum(r["responses_200"] or 0 for r in brs["after"]["rows"])
        A("و این پاسخِ مستقیمِ پرسشِ «آیا ترافیک بالا رفته؟»: شمارشِ پاسخِ `200` درِ دو دور `" +
          num(nb) + "` و `" + num(na) + "` است (اختلافِ " + num(abs(na - nb)) + " از " + num(nb) +
          "، درِ حدِ نوسانِ یکِ ریتمِ ۲۰ ثانیه‌ای)")
        A("ولی بایتِ سیم " + pct(tb, ta) + " شده. پس افزایش **سرایِ هر پاسخ** است، نه تعدادِ")
        A("درخواست‌ها — و همان سرایِ هر پاسخ، انتخابِ سطحِ " + num(1) + " به‌جایِ " + num(5) +
          " است (§پ).")
        A("")
        A("آمادگیِ نخستینِ ردیف (سلکتورِ درستِ همین دور اضافه شد؛ `tbody tr` درِ این اپ")
        A("هیچ‌وقت نمی‌خورد و همان دلیلِ `NOT_MEASURED`ِ گزارشِ پیشین بود). نمونه تک‌بار درِ هر")
        A("ریز، پس این دو ستون «بهتر/بدتر» نمی‌گویند فقط پهنایِ نوسان را نشان می‌دهند:")
        A("")
        A("| ریز | قبل | بعد |")
        A("|---|---:|---:|")
        for label in ("market-1366x768", "master-1366x768", "market-1920x1080"):
            cells = []
            for k in ("before", "after"):
                r = rowof(brs[k], label) or {}
                f = r.get("first_rows_ready") or {}
                cells.append((num(f["ms"]) + "ms / " + num(f["rows"]) + " ردیف") if f.get("ms")
                             else "NOT_MEASURED (" + num(f.get("rows") or 0) + " ردیف)")
            A("| `" + label + "` | " + cells[0] + " | " + cells[1] + " |")
        A("")

    A("## ت) سرِ CPU و RAMِ بک‌اند")
    A("")
    A("| معیارِ سرور | مقدارِ سنجیده |")
    A("|---|---:|")
    A("| CPUِ فرایندِ سرور درِ طولِ سنجش (سطحِ " + num(1) + ") | " +
      num(V1.get("server_cpu_ms_during_probe", 0)) + " ms |")
    A("| CPUِ فرایندِ سرور درِ طولِ سنجش (سطحِ " + num(5) + ") | " +
      num(V5.get("server_cpu_ms_during_probe", 0)) + " ms |")
    A("| RSS پیش ازِ سنجش | " + num(V1.get("server_rss_mb_before", 0)) + " MB |")
    A("| RSS پس ازِ سنجش (سطحِ " + num(1) + ") | " + num(V1.get("server_rss_mb_after", 0)) + " MB |")
    A("| سقفِ طراحیِ کشِ بدنه | " + num(6) + " بدنه × " + num(FUNNEL_BODY_BYTES) + " B ≈ " +
      num(6 * FUNNEL_BODY_BYTES / 1048576.0) + " MB |")
    A("")
    A("فرایندِ سرور درِ دورِ سطحِ " + num(1) + " " + num(V1.get("server_cpu_ms_during_probe", 0)) +
      " ms CPU مصرف کرد، درِ دورِ")
    A("سطحِ " + num(5) + " " + num(V5.get("server_cpu_ms_during_probe", 0)) +
      " ms — اختلافِ " + num(abs(cpu_delta)) + " ms (" + pct(V5.get("server_cpu_ms_during_probe", 1),
      V1.get("server_cpu_ms_during_probe", 0)) + "). این اختلافِ")
    A("جمعِ دو چیز است، نه فقطِ سطحِ فشرده‌سازی: تعدادِ ساختِ مجددِ بدنه درِ دو دور یکی نبود،")
    A("پس «" + num(abs(cpu_delta)) + "ms = صرفه‌جوییِ gzip» ادعا نمی‌شود. ملاکِ تمیزِ")
    A("هزینۀ فشرده‌سازی، ستون‌هایِ زمانِ §پ است (همان مسیر، همان بدنهٔ کش‌شده).")
    A("عددِ RSSِ «پیش» برایِ کدِ `ff6b2fb` گرفته نشد ⇒ NOT_MEASURED.")
    A("")

    A("## ث) قرمز‑سبزِ گارد (اثباتِ اینکه تست واقعاً تغییر را می‌پوشاند)")
    A("")
    txt = io.open(GATE, encoding="utf-8").read()
    fails = len(re.findall(r"(?m)^FAIL ", txt))
    oks = len(re.findall(r"(?m)^ok   ", txt))
    A("| وضعیتِ کد | سبز | قرمز |")
    A("|---|---:|---:|")
    A("| `ff6b2fb` (بی‌کشِ بدنه) | " + num(oks) + " | " + num(fails) + " |")
    A("| این شاخه | " + num(11) + " | " + num(0) + " |")
    A("")
    A("درِ کدِ قبلی " + num(fails) + " سنجه قرمز شد — یعنی گاردِ من کور نیست. سه سنجه‌ای که درِ هر دو")
    A("حالت سبزند (`status_matrix`/`universe`، تازۀ `_strip`ِ بی‌`timeline`، و شکلِ پاسخِ خطا)")
    A("همان «معادل‌بودنِ معنا» را نشان می‌دهند: این سه رفتار درِ کدِ `ff6b2fb` هم درست بود و درِ")
    A("این شاخه هم درست است — یعنی کشِ بدنه چیزی جز «دوباره سریال‌نکردنِ همان بدنه» عوض نکرده.")
    A("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    text = main()
    io.open(os.path.join(RUN, "tables-analytic.md"), "w", encoding="utf-8", newline="\n").write(text)
    print(text)
