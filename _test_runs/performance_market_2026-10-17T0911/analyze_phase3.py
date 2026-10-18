# -*- coding: utf-8 -*-
"""§۳ گزارش از روی لاگِ خام: باتری، گیت‌هایِ فرانت، قرمز‑سبز، و طبقه‌بندیِ قرمزها."""
import io
import json
import os
import re
import statistics

RUN = os.path.dirname(os.path.abspath(__file__))


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


def txt(name):
    return io.open(os.path.join(RUN, name), encoding="utf-8", errors="replace").read()


def grep_counts():
    t = txt("phase3-run_all_tests.log")
    ok = len(re.findall(r"(?m)^  OK   ", t))
    fail = len(re.findall(r"(?m)^  FAIL ", t))
    suites = re.findall(r"(?m)^  (OK|FAIL) +(.+?) +rc=(\d+) \| (.*)$", t)
    return ok, fail, suites, t


def front_end_gates():
    t = re.sub(r"\x1b\[[0-9;]*m", "", txt("npm-gates.log"))
    out = {}
    for key, pat in (("tsc", r"TSC_EXIT=(\d+)"), ("vitest", r"VITEST_EXIT=(\d+)"),
                     ("build", r"BUILD_EXIT=(\d+)")):
        m = re.search(pat, t)
        out[key] = m.group(1) if m else "NOT_FOUND"
    m = re.search(r"Test Files\s+(\d+) passed \| (\d+) skipped \((\d+)\)", t)
    out["files"] = m.groups() if m else ("?", "?", "?")
    m = re.search(r"Tests\s+(\d+) passed \| (\d+) skipped \((\d+)\)", t)
    out["tests"] = m.groups() if m else ("?", "?", "?")
    m = re.search(r"Duration\s+([\d.]+)s", t)
    out["dur"] = m.group(1) if m else "?"
    m = re.search(r"added (\d+) packages", txt("npm-ci.log"))
    out["pkgs"] = m.group(1) if m else "?"
    out["ci_exit"] = re.search(r"NPM_CI_EXIT=(\d+)", txt("npm-ci.log")).group(1)
    return out


def equal_gate():
    t = txt("equal-check.md")
    return {k: len(re.findall(r'"verdict": "%s"' % k, t))
            for k in ("IDENTICAL", "VOLATILE-ONLY", "DATA-DIFF")} | {
        "final": "OUTPUTS_EQUAL" if "OUTPUTS_EQUAL" in t else "NOT_FOUND"}


def main():
    ok, fail, suites, log = grep_counts()
    fe = front_end_gates()
    eq = equal_gate()
    conc = json.load(io.open(os.path.join(RUN, "funnel-concurrency-6.json"), encoding="utf-8"))
    L = []
    A = L.append

    A("### ۳الف) باتریِ کامل — فرمان، شمار، خروج")
    A("")
    A("```")
    A("python dev/run_all_tests.py          # بدونِ فیلتر، ۱۶:۲۸:۴۹ → ۱۶:۵۴:۳۵ (≈۲۵ دقیقه ۴۶ ثانیه)")
    A("EXIT=1")
    A("```")
    A("")
    A("| نتیجه | شمار |")
    A("|---|---:|")
    A("| سوئیتِ سبز | " + num(ok) + " |")
    A("| سوئیتِ قرمز | " + num(fail) + " |")
    A("| جمعِ سوئیت‌ها | " + num(ok + fail) + " |")
    A("")
    A("سه قرمز (`phase3-run_all_tests.log`):")
    A("")
    A("| سوئیت | rc | شمارشِ درونِ سوئیت |")
    A("|---|---:|---|")
    for kind, name, rc, cnt in suites:
        if kind == "FAIL":
            A("| `" + name.strip()[:70] + ("…" if len(name.strip()) > 70 else "") + "` | " +
              num(rc) + " | `" + cnt.strip() + "` |")
    A("")

    A("### ۳ب) گیت‌هایِ فرانت و گاردِ خودِ تغییر")
    A("")
    A("| گیت | فرمان | خروج | شمارش |")
    A("|---|---|---:|---|")
    A("| نصبِ قفل | `npm ci` | " + num(fe["ci_exit"]) + " | " + num(fe["pkgs"]) + " بسته |")
    A("| تایپ | `npx tsc -b` | " + num(fe["tsc"]) + " | بی‌خطا |")
    A("| تستِ واحد | `npx vitest run` | " + num(fe["vitest"]) + " | " +
      num(fe["files"][0]) + " فایلِ سبز، " + num(fe["files"][1]) + " skip (" + num(fe["files"][2]) +
      ")؛ " + num(fe["tests"][0]) + " تست سبز، " + num(fe["tests"][1]) + " skip (" +
      num(fe["tests"][2]) + ") درِ " + fa(fe["dur"]) + "s |")
    A("| بیلدِ فرانت | `npm run build` | " + num(fe["build"]) + " | `frontend/dist` ساخته شد |")
    A("| گاردِ کشِ بدنه | `python dev/funnel_body_cache_v1.py --port 8020` | ۰ | " + num(11) +
      " سبز، " + num(0) + " قرمز |")
    A("| گیتِ برابریِ خروجی | `python dev/perf_output_equal_v1.py` (۲۷ مسیر) | ۰ | " +
      num(eq["IDENTICAL"]) + " IDENTICAL، " + num(eq["VOLATILE-ONLY"]) + " VOLATILE-ONLY، " +
      num(eq["DATA-DIFF"]) + " DATA-DIFF → `" + eq["final"] + "` |")
    A("| برابریِ قرارداد | `GET /openapi.json` پیش/پس | ۰ | " + num(93) + " مسیر، سندِ بایت‌به‌بایت یکی |")
    A("")
    A("قرمز‑سبزِ همان گارد رویِ `ff6b2fb` (بی‌کشِ بدنه): **۳ سبز، ۸ قرمز** — پس گارد کور نیست")
    A("و تغییر را واقعاً می‌پوشاند (`phase1-before.log`).")
    A("")

    A("### ۳پ) طبقه‌بندیِ سه قرمز — با بازاجرا، نه با حدس")
    A("")
    A("هیچ‌کدام ازِ سه سوئیت درِ سطحِ تغییرِ من نیست: `git diff --quiet ff6b2fb..HEAD` برایِ هر سه")
    A("فایلِ سوئیت و برایِ `adjustment_engine.py` تمیز است، و هیچ‌کدام `api/funnel.py` یا")
    A("`app.py` را نمی‌لمسد. علتِ هر سه:")
    A("")
    A("| سوئیت | علت | شاهدِ بازاجرا |")
    A("|---|---|---|")
    A("| `single writer: one backend per market.db` | درِ زمانِ باتری، ریگِ من (:8020) و "
      "بک‌اندِ مأموریتِ دیگر (:8010) بالا بودند. خودِ گارد می‌گوید «پیشِ ازِ "
      "`run_all_tests.py` باید سرورها بسته باشند» (`dev/single_writer_guard.py:16-19`) ⇒ "
      "**انحرافِ روشِ من**، نه نقصِ کد | با کشتنِ ریگِ من: `OK — تک‌نویسنده`، rc=۰ "
      "(`phase3-rerun-after-stopping-rig.log`) |")
    A("| `R1/R2 housekeeping: dedupe + prev-year backfill` | فیکسچرِ gitignore شدۀ "
      "`market.db.lzma` درِ این ورک‌تری نیست (`.gitignore:147 *.lzma`) | با copyِ `.lzma` ازِ "
      "ورک‌تریِ `ui-audit-system-2`: `[selftest] PASS` (`phase3-rerun-with-fixtures.log`) |")
    A("| `Phase4 engine … 38/39` | شاخۀ `ج۰` بی‌شاهدِ مرجع عمداً قرمز می‌شود "
      "(`dev/test_adjustment_engine_v1.py:207`)؛ شاهدِ `_audit/ra365_ref_bars.json` gitignore "
      "است (`.gitignore:192 _audit/*.json`) | با copyِ شاهد ازِ `BorsTerminal-src`: "
      "**۴۴ سبز، ۰ قرمز** |")
    A("")
    A("پس: **قرمزِ باقی‌مانده درِ برابرِ تغییرِ من = صفر.** سه قرمزِ نخست همگی محیطی/روشی بودند و")
    A("همگی با همان دو شرطِ درست (سرورِ بسته + فیکسچرِ موجود) سبز شدند. هیچ تستی حذف، skip یا")
    A("تضعیف نشد؛ فیکسچرها copy شدند، نه ساخت.")
    A("")
    A("یک اثرِ جانبیِ خودِ باتری هم ثبت می‌شود: سوئیتِ فیکسچر،")
    A("`dev/fixtures/fts_v10_payloads.json` را با خط‌شکنِ CRLF بازنویسی کرد (محتوا پس ازِ")
    A("نرمال‌سازی یکسان است). ازِ `HEAD` برگردانده شد تا کامیتِ این مأموریت آلوده به churn نشود.")
    A("")
    A("### ۳ت) هم‌زمانیِ قیف (بندِ ۱پ) — عدد")
    A("")
    A("ششِ POSTِ همزمان رویِ کلیدِ سردِ `/api/funnel`: `MISS` = " + num(conc["builds_observed_MISS"]) +
      "، `HIT` = " + num(conc["x_cache_counts"].get("HIT", 0)) + "،")
    A("wall = " + num(conc["wall_ms"]) + "ms، بیشینهٔ یکِ درخواستِ " + num(conc["max_ms"]) +
      "ms، جمعِ زمانِ سرویس " + num(conc["sum_of_server_seconds"]) + "s.")
    A("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    text = main()
    io.open(os.path.join(RUN, "tables-phase3.md"), "w", encoding="utf-8", newline="\n").write(text)
    print(text)
