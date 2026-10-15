"""PERF Stage 11 — identical-workload before/after table, built from the captured artifacts.

Numbers are never typed by hand: this reads the two backend probe JSONs and the two
browser-probe JSONs written by be_probe.py / fe_probe.js and emits the paired table, so
the report cannot drift from what was actually measured.

usage: PYTHONIOENCODING=utf-8 python _audit/perf/before_after.py
"""
import io
import json
import os
import sys

OUT = "_audit/perf/BEFORE_AFTER.md"


def pct(before, after):
    if not before:
        return "—"
    return "%+.0f%%" % (100.0 * (after - before) / before)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def backend_table(before, after):
    b = before["dev-8000"]
    a = after["dev-8000"]
    buf = io.StringIO()
    buf.write("| مسیر (dev-8000) | اولین فراخوانیِ قبل | بعد | Δ | میانهٔ قبل | میانهٔ بعد | Δ |\n")
    buf.write("|---|---:|---:|---:|---:|---:|---:|\n")
    for name in b:
        if name not in a:
            continue
        rb, ra = b[name], a[name]
        if "wall_ms" in rb:                       # concurrent scenario
            buf.write("| %s (۴ همزمان) | %.0f ms | %.0f ms | %s | — | — | — |\n"
                      % (name, rb["wall_ms"], ra["wall_ms"], pct(rb["wall_ms"], ra["wall_ms"])))
            continue
        if rb.get("err") or ra.get("err"):
            continue
        buf.write("| %s | %.0f ms | %.0f ms | %s | %.0f ms | %.0f ms | %s |\n"
                  % (name, rb["first_ms"], ra["first_ms"], pct(rb["first_ms"], ra["first_ms"]),
                     rb["p50"], ra["p50"], pct(rb["p50"], ra["p50"])))
    buf.write("\n**حجمِ پاسخ (باید دست‌نخورده بماند):**\n\n")
    buf.write("| مسیر | rawِ قبل | rawِ بعد | gzِ قبل | gzِ بعد |\n|---|---:|---:|---:|---:|\n")
    for name in ("market full", "mstat board", "mstat treemap", "screener", "chart second symbol"):
        if name in b and name in a:
            buf.write("| %s | %s | %s | %s | %s |\n"
                      % (name, format(b[name]["raw"], ","), format(a[name]["raw"], ","),
                         format(b[name]["gz"], ","), format(a[name]["gz"], ",")))
    return buf.getvalue()


def fe_rows(fe):
    out = {}
    for d in fe["phases"]["tabs"]:
        if d.get("tab"):
            out["%s pass%d" % (d["tab"], d["pass"])] = d
    return out


def frontend_table(before, after):
    b, a = fe_rows(before), fe_rows(after)
    buf = io.StringIO()
    buf.write("| سناریو (مرورگرِ واقعی، dev-8000) | click→readyِ قبل | بعد | Δ | longtaskِ قبل/بعد | "
              "TBTِ قبل/بعد | فریمِ >۱۰۰msِ قبل/بعد |\n")
    buf.write("|---|---:|---:|---:|---:|---:|---:|\n")
    for k in b:
        if k not in a:
            continue
        rb, ra = b[k], a[k]
        buf.write("| %s | %.0f ms | %.0f ms | %s | %d/%d | %d/%d | %d/%d |\n"
                  % (k, rb["clickToReady"], ra["clickToReady"],
                     pct(rb["clickToReady"], ra["clickToReady"]),
                     rb["longtasks"], ra["longtasks"], rb["tbt"], ra["tbt"],
                     rb["frames"]["over100"], ra["frames"]["over100"]))
    for label, key in (("cold #1", 0), ("cold #2", 1), ("cold #3", 2)):
        rb, ra = before["phases"]["cold"][key], after["phases"]["cold"][key]
        buf.write("| %s (FCP — نشانۀ «دادهٔ قابل‌استفاده» درِ /master نصب نمی‌شود) | %.0f ms | %.0f ms | %s "
                  "| %d/%d | %d/%d | %d/%d |\n"
                  % (label, rb["firstContentfulPaint"], ra["firstContentfulPaint"],
                     pct(rb["firstContentfulPaint"], ra["firstContentfulPaint"]),
                     rb["longtasks"], ra["longtasks"], rb["tbt"], ra["tbt"],
                     rb["frames"]["over100"], ra["frames"]["over100"]))
    hb, ha = before["phases"]["heavy"], after["phases"]["heavy"]
    buf.write("| سناریویِ سنگین: بازکردنِ تبِ وضعیت بازار / ۱۲ اسکرول | %.0f / %.0f ms | %.0f / %.0f ms | %s "
              "| %d/%d | %d/%d | %d/%d |\n"
              % (hb["openMs"], hb["scrollMs"], ha["openMs"], ha["scrollMs"],
                 pct(hb["openMs"] + hb["scrollMs"], ha["openMs"] + ha["scrollMs"]),
                 hb["longtasks"], ha["longtasks"], hb["tbt"], ha["tbt"],
                 hb["frames"]["over100"], ha["frames"]["over100"]))
    buf.write("\n> **سطرهایِ «استراتژی FTS» قابلِ مقایسه نیستند:** نشانۀِ آمادگیِ اینِ تب درِ "
              "harness اشتباه بود (`master-open-funnel` / `funnel-chain-row` درِ اینِ صفحه وجودِ ندارند) "
              "و درِ هرِ دوِ سنجشِ قبل و بعد تاِ پایانِ پنجره نصب نشد؛ عددِ ۳۵٫۱ s درِ هرِ دوِ ستون "
              "پنجرۀِ timeout است نهِ زمانِ کاربر. سنجشِ درستِ همینِ مسیرِ فرود "
              "(`_audit/perf/master_landing_check.js` + `MASTER_LANDING.json`) نشان می‌دهد "
              "`[data-testid=\"fts-funnel-workspace\"]` باِ ۶ خانۀِ شمارش تاِ ~۵ ثانیه می‌نشیند و "
              "هیچِ درخواستِ معلق‌ای نمی‌ماند؛ اماِ طرفِ «قبل» باِ همینِ نشانۀِ درست **سنجیده نشد** "
              "(NOT MEASURED).\n")
    return buf.getvalue()


def main():
    before_be = load("_audit/perf/BE_BASELINE_BEFORE.json")
    after_be = load("_audit/perf/BE_BASELINE.json")
    before_fe = load("_audit/perf/FE_BASELINE_BEFORE.json")
    after_fe = load("_audit/perf/FE_AFTER_DEV.json")
    boot = load("_audit/perf/BOOT_TIMELINE.json") if os.path.exists("_audit/perf/BOOT_TIMELINE.json") else None

    md = ["# مقایسهٔ قبل/بعد با workload یکسان — همین لپ‌تاپ، بازار بسته\n",
          "- backend: `_audit/perf/be_probe.py` (۳ تکرار برای هر مسیر، dev-8000)",
          "- frontend: `_audit/perf/fe_probe.js` (Edge، سناریوی cold + چرخۀ تب + چارت + سناریویِ سنگین)",
          "- هر دو جدول از خودِ فایل‌هایِ اندازه‌گیری‌شده ساخته می‌شوند؛ هیچ عددی دست‌نویس نیست.\n",
          "## ۱) backend — تأخیرِ همان مسیرها\n",
          backend_table(before_be, after_be)]
    if boot:
        md.append("\n## ۲) تفکیکِ راه‌اندازی (پس ازِ اصلاح)\n")
        md.append("| رخداد | زمان |\n|---|---:|\n")
        md.append("| گوشیهاییِ پورت (Backend Ready) | %.2f s |\n" % boot["port_ready_s"])
        md.append("| اولینِ پاسخِ API | %.2f s (%.0f ms) |\n" % (boot["first_api_s"], boot["first_api_ms"]))
        md.append("| اولینِ دادهٔ بازارِ قابل‌استفاده (`/api/market`) | %.2f s (%.0f ms) |\n"
                  % (boot["market_board_s"], boot["market_board_first_ms"]))
        md.append("| warmِ اسکرینر | %s |\n" % ("به پسِ سینکِ بازار موکول شد (یک بیلد، نه دو تا)"
                                                if "screener warm deferred to sync" in boot["markers"]
                                                else "درِ همانِ بوت اجرا شد"))
        for k in ("market-sync done", "screener cache warmed"):
            if k in boot["markers"]:
                md.append("| %s | %.1f s |\n" % (k, boot["markers"][k]))
    md.append("\n## ۳) frontend — همانِ workload، مرورگرِ واقعی\n")
    md.append(frontend_table(before_fe, after_fe))
    text = "".join(md)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print("\nwrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
