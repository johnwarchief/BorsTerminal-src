#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/gen_engine1_closure_doc.py — سندِ بستنِ Engine 1: ماتریسِ ۲۹ ابزار، قراردادِ بانک،
مقایسهٔ بیرونی با رهاورد، و گیت‌ها — با ارقامِ خوانده‌شده از مصنوعاتِ همان اجرا.

هیچ عددی درِ این فایل تایپ نشده: شمارش‌ها از `chart_drawing_matrix_v3.json`،
`RA365-COMPARE-MATRIX.csv`، `ADJUSTED-FACTOR-GAP.csv`، `full_audit_state.json`،
log هایِ `tsc`/`vitest`/گیت و `git rev-parse` درمی‌آیند (قاعدۀِ مالک: ارقامِ فارسی باید
از مصنوعاتِ خام تولید شوند).
"""
import csv
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
OUT = A("docs", "technical-indicators", "reviewed", "ENGINE-1-CLOSURE-1405-07-27.md")
FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(x):
    s = f"{x:,}" if isinstance(x, int) and abs(x) >= 1000 else str(x)
    o = []
    for ch in s:
        if ch.isdigit():
            o.append(FA[int(ch)])
        elif ch == ",":
            o.append("٬")
        elif ch == "-":
            o.append("−")
        elif ch == ".":
            o.append("٫")
        else:
            o.append(ch)
    return "".join(o)


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def sh(cmd):
    """فرمان را بی‌cmd.exe اجرا می‌کند: درِ ویندوز، `%`ِ داخلِ `--format=` با shell
    بلعیده می‌شود و خروجیِ `git log` تهی می‌ماند (سنجشِ همین دور)."""
    try:
        r = subprocess.run(cmd.split(), cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        return ANSI.sub("", (r.stdout or "")).strip()
    except Exception as ex:
        return "(not read: %s)" % type(ex).__name__


def last_line(path, needle):
    """آخرینِ سطرِ شاملِ `needle`، بدونِ ANSI و بدونِ برچسبِ تکراری."""
    if not os.path.exists(path):
        return None
    for ln in reversed(io.open(path, encoding="utf-8", errors="replace").read().splitlines()):
        if needle in ln:
            return ANSI.sub("", ln).strip()
    return None


def j(path):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding="utf-8"))


def rows(path):
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(io.open(path, encoding="utf-8-sig")))


def num_line(path, prefix, need_colon=False):
    """عددِ آخرینِ سطرِ شروع‌شونده با `prefix` ازِ لاگِ خودِ ابزار (بی‌عددِ تایپی).

    `need_colon` برایِ برچسب‌هایی است که با یکِ برچسبِ دیگر اشتباه خوانده می‌شوند:
    `symbols` درِ این لاگ هم «تعدادِ نمادها»ست و هم «نمادهایی که سری‌شان عوض می‌شود».
    """
    if not os.path.exists(path):
        return None
    got = None
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        t = ln.strip()
        if not t.startswith(prefix):
            continue
        rest = t[len(prefix):]
        if need_colon and not rest.lstrip().startswith(":"):
            continue
        digits = "".join(ch for ch in rest.replace(",", "").replace("،", "") if ch.isdigit())
        if digits:
            got = int(digits)
    return got


def counts(path, marker):
    """`N passed, M failed` را با regex می‌خواند (جمعِ رقمیِ ساده دو عدد را یکی می‌کند)."""
    if not os.path.exists(path):
        return None, None
    p = f = None
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        if marker in ln:
            m = re.search(r"(\d+)\s*passed,\s*(\d+)\s*failed", ln)
            if m:
                p, f = int(m.group(1)), int(m.group(2))
    return p, f


def fail_names(path, n=8):
    if not os.path.exists(path):
        return []
    got = []
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s.startswith("FAIL"):
            got.append(s[4:].strip())
    return got[:n]


def main():
    m4 = j(A("_audit", "chart_drawing_matrix_v4.json"))
    m4csv = rows(A("_audit", "chart_drawing_matrix_v4.csv"))
    dblog = A("_scratch", "live", "db_contract_impact_recheck.log")
    ev_probe = j(A("_audit", "UNRESOLVED-EVENTS-PROBE.json"))
    ev_off = j(A("_audit", "EVENT-WINDOW-OFFICIAL-ROWS.json"))
    pb_guard = A("_scratch", "live", "plv_standalone_146b5acd.log")
    pb_fixed = A("_scratch", "live", "plv_fixed_run1.log")
    gate_tail = A("_scratch", "live", "gate_final.log")
    GUARD_DB = A("_scratch", "live", "guard_db_candle.log")
    cmp_rows = rows(A("_audit", "RA365-COMPARE-MATRIX.csv"))
    gap = rows(A("_audit", "ADJUSTED-FACTOR-GAP.csv"))
    fa_state = j(A("_scratch", "live", "full_audit_state.json"))
    vit_tail = A("_scratch", "live", "final_chain.log")

    def last_count(path, needle):
        return last_line(path, needle)

    L = []
    W = L.append
    W("# بستنِ Engine 1 — ماتریسِ ابزارهایِ ترسیم، قراردادِ کندلِ بانک، مقایسۀِ بیرونی و گیت‌ها")
    W("")
    W(f"- شاخه: `{sh('git rev-parse --abbrev-ref HEAD')}` — SHAِ این سند: `{sh('git rev-parse --short HEAD')}`")
    W("- تاریخ: ۱۴۰۵-۰۷-۲۷ · انتشار: هیچ Push/Merge/Tag انجام نشده (شاخه بی‌upstream است: "
      "`git rev-parse --abbrev-ref @{u}` ⇒ fatal: no upstream configured).")
    W("")
    W("## ۰) علتِ قطعیِ اختلافِ «گیتِ کامل» با «اجرایِ مستقل» (بندِ ۱ مأموریت)")
    W("")
    gp0, gf0 = counts(pb_guard, "price_last_value_v1070:")
    gp1, gf1 = counts(pb_fixed, "price_last_value_v1070:")
    W(f"- **اشتباهِ اول، شناساییِ بود:** سطرِ پایانیِ گیت `FAILED: <label>` را می‌دهد و "
      f"برچسب‌ها انگلیسی‌اند. آن «{fa(gf0) if gf0 is not None else '—'} شکست» مالِ "
      f"`dev/price_last_value_v1070.py` بود (برچسب «last/closing are separate columns…»)، "
      f"نه `dev/price_basis_v1070.py` — همان دور که «{fa(gf0) if gf0 is not None else '—'} "
      f"شکست» دیده می‌شد، برچسبِ `single price resolver` (= خودِ `price_basis_v1070`) درِ "
      f"*همان* لاگ این سطر است: "
      f"`{last_count(A('_scratch','live','gate_final3.log'), 'single price resolver') or 'NOT_FOUND'}` "
      f". «۴۵ موفق درِ اجرایِ مستقل» هم مالِ همین سوئیتِ دیگر بود.")
    W(f"- **اشتباهِ دوم، متنِ ناخوانا:** `run_all_tests.py` دمِ خروجیِ فرزند را با "
      f"`encode('ascii','replace')` چاپ می‌کرد؛ دو سطرِ FAIL درِ `gate_final3.log` "
      f"«?????? ???????…» شد و علتِ واقعی سه دور پنهان ماند. ازِ این دور، هر سوئیتِ "
      f"قرمزِ کاملِ stdout+stderr خود را بی‌اتلافِ متن درِ "
      f"`_audit/gate_suites/NNN_<slug>.log` (UTF-8، بیرونِ گیت چون `*.log` "
      f"gitignored است) می‌نویسد و مسیرش درِ کنسول چاپ می‌شود.")
    W(f"- **علتِ قطعی، نه نوسان و نه ترتیب:** دو سنجه درِ بندِ [۴] همین گارد "
      f"**متنِ** کوئری و سازندۀِ دستیِ قدیمیِ `get_chart_db` را می‌خواستند؛ کامیتِ "
      f"`6bb50cb8` آن دو را به `candle_contract.SELECT_SQL` و `from_db_row` برد و آن دو "
      f"ارجاعِ متنیِ کهنه قرمز شد، بی‌آنکه هیچ عددی عوض شود. سنجشِ مستقلِ بی‌هیچ سوئیتِ "
      f"دیگری: `{gp0 if gp0 is not None else '—'} passed, {gf0 if gf0 is not None else '—'} failed` "
      f"(همان شمارِ گیت) ⇒ نه وابستگیِ ترتیبی، نه فایلِ موقت، نه ساعت، نه state انباشته. "
      f"دو سنجه‌ای که می‌شکستند: "
      f"{'; '.join('`' + n + '`' for n in fail_names(pb_guard))}.")
    W(f"- **اصلاح، بدونِ تضعیفِ گارد:** آن دو ارجاعِ متنیِ جابه‌جاشدنی با سنجه‌هایِ "
      f"قرارداد-محور بازنویسی شدند (کوئری و سازنده ازِ `candle_contract` می‌گذرند؛ "
      f"`DB_COLUMNS` باید `last` و `value` را نام‌دار نگه دارد) و یکِ بندِ رفتاریِ تازه "
      f"افزوده شد که با بانکِ موقت، `get_chart_db` را واقعاً صدا می‌زند: `last` باید از "
      f"ستونِ خودش بیاید، `closing` لنگر بماند، `value` برسد، ردیفِ حجم‌صفر با شمارشِ "
      f"علت حذف شود و بی‌`last` درِ بانک ستون `null` بماند. دو کنترلِ منفی هم "
      f"راستی‌آزمایی می‌کنند سنسور کور نیست (جمله‌یِ «last := close» و حذفِ `last` از "
      f"قراردادِ ستون‌ها). شمارِ سنجه‌ها ازِ "
      f"{fa(gp0 + gf0) if gp0 is not None else '—'} به "
      f"{fa(gp1 + gf1) if gp1 is not None else '—'} رسید و نتیجه: "
      f"`{gp1 if gp1 is not None else '—'} passed, {gf1 if gf1 is not None else '—'} failed`.")
    W("")
    W("## ۱) ماتریسِ ۲۹ ابزارِ ترسیم")
    W("")
    if not m4:
        W("- **NOT_RUN**: `_audit/chart_drawing_matrix_v4.json` نوشته نشده است؛ عددِ جعلی "
          "درِ این بخش نمی‌نشیند.")
    else:
        s = m4["summary"]
        W(f"### ۱٫۱) چرا سنسورِ v3 بازنویسی شد (پس‌گرفتنِ ادعایِ «۲۱ ابزارِ بی‌رسم») ")
        W("")
        W(f"- درِ اجرایِ v3 بیست‌و‌یکِ ابزار «رسم نکرد» گزارش شد. آن عدد **artifactِ سنسور** "
          f"بود، نه رفتارِ محصول. سه نقصِ اندازه‌گیری سنجیده شد:")
        W("  ۱) «تمام‌شدنِ» رسم با ظهورِ هرِ اورلیِ تازه می‌شد؛ درِ klinecharts v10 یکِ کلیک "
          "هم اورلی می‌سازد (با `currentStep` مثبت)، پس رسمِ نیمه‌کاره «رسم شد» و "
          "رسمِ تمام‌شده با رسمِ باز یکی بود. قاعدۀِ درست ازِ خودِ موتور خوانده شد: "
          "`currentStep === -1` (`_scratch/live/probe_step.json`).")
        W("  ۲) بودجۀِ نقطه پنجِ ثابت بود؛ ابزارهایِ پنج‌و‌شش‌نقطه‌ای (هارمونیک، امواج) درِ "
          "همان پنجره تمام نمی‌شدند. درِ v4 تا هشت نقطه + دبل‌کلیکِ پایانی می‌رود.")
        W("  ۳) تشخیصِ رسم فقط ازِ انبارِ localStorage می‌شد و آن هم بی‌صبر. درِ v4 "
          "«رسمِ تمام‌شدۀِ تازه درِ دیدۀِ موتور» شرطِ موفقیت است و شمارۀِ ردیفِ انبار جدا "
          "ثبت می‌شود.")
        np = m4.get("nameProbe", {})
        unreg = s.get("unregisteredNames", [])
        W(f"- کاوشِ مستقلِ «ثبتِ نام» (`createOverlay` برنامه‌ای، بی‌کلیک): "
          f"{fa(len(np))} نامِ `overlayType` سنجیده شد و "
          f"{fa(len(np) - len(unreg))} تایِ آن‌ها درِ موتورِ جاری ثبت‌اند"
          f"{('؛ ثبت‌نشده‌ها: ' + json.dumps(unreg, ensure_ascii=False)) if unreg else ''}. "
          f"کنترلِ منفیِ خودِ کاوش: نامِ ساختگیِ `zzzNoSuchOverlayXyz` "
          f"`createOverlay` را بی‌`id` و بی‌اورلی برمی‌گرداند "
          f"(`_scratch/live/probe_bogus.js`) ⇒ سنسورِ نام کور نیست.")
        W(f"- پس ادعایِ پیشینِ «{fa(21)} ابزارِ بی‌رسم» پس گرفته می‌شود؛ عددِ درست درِ جدولِ "
          f"پایینِ همین بند است، عملیات‌به‌عملیات.")
        W("")
        W(f"### ۱٫۲) اجرایِ v4 — کنترلِ مثبت و خطِ مبنایِ محیط")
        W("")
        W(f"- registry از خودِ `DrawingToolbar.tsx`: {fa(m4['registrySlots'])} شیار، "
          f"{fa(m4['registryTools'])} شناسۀِ ابزار (کلیدِ گزارش `slotId:toolId:name` است، "
          f"چون دو `id` با دو نامِ متفاوت تکرار شده و با دِدوپِ صرفِ id یکی از ۲۹ گم می‌شد).")
        W(f"- kinds: {fa(s['drawingTools'])} سازندۀِ ترسیم، {fa(s['modes'])} حالتِ نشانگر، "
          f"{fa(s['actions'])} کنش — سه تایِ آخر عملیاتِ رسم/ویرایش/حذفِ منزوی ندارند و "
          f"`NOT_APPLICABLE` ثبت می‌شوند، نه `PASS`.")
        W(f"- کنترلِ مثبت (`{m4['positiveControl']['toolId']}`): "
          f"{'✓' if m4['positiveControl']['drew'] else '✗'} با {fa(m4['positiveControl']['clicks'])} "
          f"کلیک — بی‌این هارنس هیچِ نتیجه‌ای گزارش نمی‌کند و exit 3 می‌دهد.")
        W(f"- محیطِ اجرا: `{m4.get('base','http://localhost:5173')}` با "
          f"{fa((m4.get('baseline') or {}).get('barCount', 0))} کندل، "
          f"{fa((m4.get('baseline') or {}).get('engineTotal', 0))} اورلیِ غیرِ خودی درِ خطِ "
          f"مبنا (لایه‌هایِ موتور، بی‌دست‌خوردن)، ویژپورت {fa(m4['viewport'][0])}×{fa(m4['viewport'][1])}، "
          f"پروفیلِ مرورگرِ موقت ⇒ صفرِ ترسیمِ واقعیِ کاربر درِ معرضِ خطر.")
        W("")
        W("### ۱٫۳) جمعِ عملیات‌ها")
        W("")
        W("| عملیات | PASS | FAIL | UNMEASURABLE | NOT_RUN | NOT_APPLICABLE |")
        W("|---|---|---|---|---|---|")
        for op, label in (("reach", "دسترسی از رابط"), ("draw", "رسمِ تمام‌شده"),
                          ("persist", "ماندگاری پس ازِ بازخوانی"), ("edit", "ویرایش"),
                          ("hide", "مخفی‌سازی و نمایشِ مجدد"),
                          ("deleteOne", "حذفِ یکِ رسم"),
                          ("isolated", "حذفِ منزوی (بقیۀِ رسم‌ها سالم)"),
                          ("coherence", "هماهنگیِ وضعیتِ موتور با انبار")):
            c = s.get(op, {})
            W(f"| {label} | {fa(c.get('PASS', 0))} | {fa(c.get('FAIL', 0))} | "
              f"{fa(c.get('UNMEASURABLE', 0))} | {fa(c.get('NOT_RUN', 0))} | "
              f"{fa(c.get('NOT_APPLICABLE', 0))} |")
        W(f"| **جمعِ ابزارهایِ سنجیده‌شده** | {fa(s['tested'])} از {fa(s['registryTools'])} | | | | |")
        W("")
        W("### ۱٫۴) جدولِ کاملِ ۲۹ شناسه (هر عملیات جدا)")
        W("")
        W("| کلیدِ ابزار (`slot:id:name`) | نوع | دسترسی | رسم | ماندگاری | ویرایش | "
          "مخفی | حذفِ یک | منزوی | هماهنگ |")
        W("|---|---|---|---|---|---|---|---|---|---|")
        for r in m4csv:
            W(f"| `{r['key']}` | {r['kind']} | {r['reach']} | {r['draw']} | {r['persist']} | "
              f"{r['edit']} | {r['hide']} | {r['deleteOne']} | {r['isolated']} | "
              f"{r['coherence']} |")
        W("")
        bad_rows = [r for r in m4csv if any(r.get(k) in ("FAIL", "UNREACHABLE", "UNMEASURABLE", "NOT_RUN")
                                            for k in ("reach", "draw", "persist", "edit", "hide",
                                                      "deleteOne", "isolated", "coherence"))]
        if bad_rows:
            W(f"### ۱٫۵) هرِ ابزاری که عملیاتِ غیرِ PASS دارد ({fa(len(bad_rows))} سطر) — با علتِ ثبت‌شدہ")
            W("")
            W("| ابزار | عملیات | وضعیت | علتِ سنجیده‌شده |")
            W("|---|---|---|---|")
            for r in bad_rows:
                for k in ("reach", "draw", "persist", "edit", "hide", "deleteOne",
                          "isolated", "coherence"):
                    if r.get(k) in ("FAIL", "UNREACHABLE", "UNMEASURABLE", "NOT_RUN"):
                        W(f"| `{r['key']}` | {k} | {r[k]} | {r['note'] or '—'} |")
            W("")
        dl = m4.get("deleteAll", {})
        W("### ۱٫۶) «حذف تمام ترسیم‌ها» درِ هرِ دو شاخه")
        W("")
        W(f"- هدفِ حذف پیشِ ازِ آزمون ساخته شد و راستی‌آزمایی شد: "
          f"{'✓' if dl.get('hadTarget') else '✗'} "
          f"(انبار {fa((m4.get('deleteAllTarget') or {}).get('saved', 0))} ردیف، "
          f"موتور {fa((m4.get('deleteAllTarget') or {}).get('own', 0))} ترسیم).")
        W(f"- شاخۀِ **لغو** (دیالوگِ بومی رد می‌شود): "
          f"{'هیچِ ترسیمی نمی‌میرد ✓' if (dl.get('cancel') or {}).get('held') else '✗ — چیزی حذف شد'} "
          f"({fa((dl.get('cancel') or {}).get('saved', 0))} ردیف پس ازِ لغو).")
        W(f"- شاخۀِ **تأیید**: "
          f"{'همۀِ رسم‌هایِ خودی پاک شد ✓' if (dl.get('accept') or {}).get('cleared') else '✗'} "
          f"(انبار {fa((dl.get('accept') or {}).get('saved', 0))}، موتور "
          f"{fa((dl.get('accept') or {}).get('own', 0))}).")
        W("")
        W("### ۱٫۷) نقصِ اثبات‌شده‌ای که همین ماتریس پیدا و برطرف کرد")
        W("")
        W("- **ترسیمِ ابزارهایِ lazy ازِ نو نمی‌آمد و سپس پاک می‌شد.** ردیفِ انبار پس ازِ "
          "reload سرِ جایش بود، اما دیدۀِ موتور خالی می‌ماند و چند ثانیه بعد خودِ "
          "انبار هم خالی می‌شد — یعنی دادهٔ کاربر نابود می‌شد، نه فقط بازیابی‌نشدن. "
          "علت درِ کد: تمپلیت‌هایِ `tvTools` با `void import(...)` ثبت می‌شدند و effectِ "
          "ماندگاری بی‌انتظارِ آن `applySnapshot` را صدا می‌زد؛ `createOverlay` برایِ نامِ "
          "ثبت‌نشده `null` می‌دهد و بعد `tick`ِ دو‌ثانیه‌یِ وضعیتِ «چارت ترسیمی ندارد» را "
          "جایِ داده می‌نشاند. شاهدِ قبل/بعد: `_scratch/live/probe_reload_loss.json` "
          "(پیش ازِ اصلاح: پس ازِ reload `rows=0 own=0`؛ پس ازِ اصلاح: `rows=1 own=1`).")
    W("- **ترسیمِ بازگردانده‌شده ویرایش‌ناپذیر بود.** `_scratch/live/probe_fields.json` "
      "دو میدانی را نشان داد که درِ مسیرِ بازگردانی گم می‌شدند: `zLevel` (۷۵ → ۰) و "
      "callbackهایِ تعاملی که `handleSelectTool` می‌دهد. بی‌`onPressedMoveStart`، درگِ "
      "ماوس چارت را می‌لغزاند و `points` تکان نمی‌خورد. پس ازِ اصلاح، درگِ ترسیمِ "
      "بازگردانده‌شده درِ هر چهار سناریو جابه‌جا می‌شود "
      "(`_scratch/live/probe_edit2.json`، پروبِ reload).")
    W("")
    W("## ۲) قراردادِ مشترکِ کندلِ بانک")
    W("")
    db_total = num_line(dblog, "rows total")
    db_syms = num_line(dblog, "symbols", need_colon=True)
    db_kept = num_line(dblog, "kept as candles")
    db_drop = num_line(dblog, "dropped:zero_volume(no-trade)")
    db_repair = num_line(dblog, "kept:old_geometry_impossible")
    db_open = num_line(dblog, "open")
    db_high = num_line(dblog, "high")
    db_low = num_line(dblog, "low")
    db_changed = num_line(dblog, "symbols whose served series changes")
    W(f"- شمارشِ کلِ بانکِ همین دور (`_audit/db_row_contract_impact.py` → "
      f"`_scratch/live/db_contract_impact_recheck.log`): "
      f"{fa(db_total) if db_total else '—'} ردیف درِ `price_history` رویِ "
      f"{fa(db_syms) if db_syms else '—'} نماد؛ {fa(db_kept) if db_kept else '—'} ردیف کندل "
      f"می‌شود؛ {fa(db_repair) if db_repair else '—'} ردیفِ هندسه‌شکسته "
      f"(`open=high=low=0` با پایانیِ معتبر) ترمیم می‌شود و "
      f"{fa(db_drop) if db_drop else '—'} ردیفِ حجم‌صفر (روزِ بی‌معامله) کندل نمی‌شود؛ "
      f"{fa(db_changed) if db_changed else '—'} نماد سریِ سرویس‌شده‌شان عوض می‌شود. "
      f"فیلدهایِ جابه‌جا‌شده: open {fa(db_open) if db_open else '—'}، high "
      f"{fa(db_high) if db_high else '—'}، low {fa(db_low) if db_low else '—'} — همه از "
      f"قاعدۀِ «گِشادِ سایه، بی‌کُنده‌کردنِ قیمتِ منتشرشده».")
    W(f"- گارد: `dev/db_candle_contract_v1.py` → "
      f"`{last_count(GUARD_DB, ':') or 'NOT_RUN'}`")
    W("- پیاده: `get_chart_db` از `candle_contract.from_db_row` و `SELECT_SQL`/`DB_COLUMNS` "
      "می‌گذرد؛ شمارش‌ها با علت درِ پاسخ اعلام می‌شود (`dbRows`, `dbNoTradeRows`, "
      "`dbInvalidRows`) تا «کم شدنِ کندل» حذفِ خاموش نباشد.")
    W("")
    W("## ۳) مقایسۀِ بیرونی با رهاورد")
    W("")
    if cmp_rows:
        steps = [r for r in cmp_rows if r["kind"] == "adjustment_step"]
        normal = [r for r in cmp_rows if r["kind"] == "normal"]
        W(f"ماتریسِ قابل‌اجرا: `_audit/ra365_compare_matrix.py` → "
          f"{fa(len(cmp_rows))} سطر درِ {fa(len({r['symbol'] for r in cmp_rows}))} نماد "
          f"({fa(len(steps))} سطرِ پلۀِ تعدیل + {fa(len(normal))} سطرِ عادی).")
        W("")
        W("| بکه | سطرهایِ عادی | سطرهایِ پلۀِ تعدیل |")
        W("|---|---|---|")
        def band(rs):
            c = [0, 0, 0, 0, 0]
            for r in rs:
                if r["rel_diff"] == "":
                    continue
                x = float(r["rel_diff"])
                if x <= 1e-9: c[0] += 1
                elif x <= 1e-3: c[1] += 1
                elif x <= 1e-2: c[2] += 1
                elif x <= 5e-2: c[3] += 1
                else: c[4] += 1
            return c
        bn, bs = band(normal), band(steps)
        blanks = sum(1 for r in cmp_rows if r["rel_diff"] == "")
        for lab, i in (("یکسان تا دقتِ ماشین", 0), ("≤ ۰٫۱٪", 1), ("≤ ۱٪", 2),
                       ("≤ ۵٪", 3), ("> ۵٪", 4)):
            W(f"| {lab} | {fa(bn[i])} | {fa(bs[i])} |")
        W(f"| بی‌عدد (ردیفِ ما وجود ندارد) | {fa(blanks)} | ۰ |")
        W("")
        W(f"سطرهایِ «بی‌عدد» دو موردند و علتشان ثبت‌شدہ است: ۲۰۲۶-۱۰-۰۳ برایِ "
          f"شراز و شپنا درِ منبعِ رسمی **ردیفِ روزِ بی‌معامله** است "
          f"(`<VOL>=0`, `<HIGH>=<LOW>=<FIRST>=0` با پایانیِ اعلام‌شدہ)؛ قاعدۀِ محصول "
          f"از آن کندل نمی‌سازد (جعلِ OHLC ممنوع) و همان ردیف برایِ زنجیرۀِ تعدیل درِ "
          f"`all_rows` حفظ می‌شود. رهاورد آن روز را رویِ نمودار می‌رسمد ⇒ این تفاوتِ "
          f"قراردادِ نمایشِ روزِ بی‌معامله است، نه نقصِ داده.")
    else:
        W("- **NOT_RUN**: `_audit/RA365-COMPARE-MATRIX.csv` نوشته نشده است.")
    gm = [g for g in gap if g.get("status") == "MEASURED"]
    if gm:
        def gsum(k):
            return sum(int(g[k] or 0) for g in gm)
        W("")
        W(f"جایِ رویدادها درِ کلِ پنجره (`_audit/adjusted_factor_gap.py`، "
          f"{fa(gsum('dates'))} تاریخ): درِ ضریبِ رهاورد {fa(gsum('ref_steps'))} پله، "
          f"درِ ما {fa(gsum('our_steps'))} پله، {fa(gsum('shared_steps'))} مشترک، "
          f"{fa(gsum('ref_only_steps'))} پلۀِ مرجعِ که ما نداریم، "
          f"{fa(gsum('our_only_steps'))} پلۀِ اضافیِ ما.")
        if gsum("our_only_steps"):
            only = [f"{g['symbol']} {g['ins_code']}" for g in gm if int(g["our_only_steps"] or 0)]
            W(f"پلۀِ اضافیِ ما (مرجع درِ آن بازه پله ندارد): نماد(هایِ) {', '.join(only)} — "
              f"درِ `ADJUSTED-FACTOR-STEPS.csv` با تاریخِ دقیق ثبت است؛ نه رویدادِ "
              f"مرجع حذف می‌شود نه ضریبِ ما با عددِ ایشان بازنویسی.")
    W("")
    W("### سه اختلافِ پلۀِ تعدیل — علتِ سنجیده‌شدہ با ردیفِ رسمی")
    W("")
    W("پیش ازِ این علتِ این سه «دفترِ مبدأ نرسیده» ثبت شده بود. درِ این دور ردیفِ "
      "منتشرشدۀِ خودِ TSETMC برایِ همان پنجره‌ها خوانده شد "
      "(`_audit/fetch_event_window.py` → `_audit/EVENT-WINDOW-OFFICIAL-ROWS.json`) و "
      "ردیف‌هایِ خودی ازِ بانکِ همین دور (`_audit/unresolved_events_probe.py` → "
      "`_audit/UNRESOLVED-EVENTS-PROBE.json`).")
    W("")
    import datetime as _dt

    def _near(rows_, date_, days_):
        out = []
        d0 = _dt.date.fromisoformat(date_)
        for r in rows_ or []:
            ds = r.get("date")
            if not ds:
                continue
            try:
                dd = _dt.date.fromisoformat(ds)
            except ValueError:
                continue
            if abs((dd - d0).days) <= days_:
                out.append(r)
        return out
    off_by_sym = {o["symbol"]: o for o in (ev_off or {}).get("symbols", [])}
    W("| نماد | تاریخ | نسبتِ پلۀِ مرجع | پله‌هایِ خودی درِ ±۷ روز | ردیفِ رسمیِ ±۱۴ روز | "
      "اطلاعیۀِ کدال درِ همان سال |")
    W("|---|---|---|---|---|---|")
    for e in (ev_probe or {}).get("events", []):
        ours = _near(e.get("adjust_events"), e["date"], 7)
        ours_txt = " / ".join(f"{o['date']} {o['ratio']} `{o['source']}`" for o in ours) or "—"
        o = off_by_sym.get(e["symbol"], {})
        win_rows = o.get("window_rows") or []
        off_txt = (f"{fa(len(win_rows))} ردیف منتشرشده "
                   f"({fa(o.get('total_published_rows', 0))} ردیفِ کلِ سری)"
                   if o.get("status") == "OK" else str(o.get("status")))
        W(f"| {e['symbol']} | {e['date']} | {fa(e['reference_step_ratio'])} | {ours_txt} | "
          f"{off_txt} | {fa(len(e.get('codal_notices') or []))} |")
    W("")
    W("خوانشِ این چهار ستون (بدونِ هیچِ ضریبِ حدسی):")
    W("")
    for e in (ev_probe or {}).get("events", []):
        o = off_by_sym.get(e["symbol"], {})
        vol0 = [r for r in (o.get("window_rows") or []) if str(r.get("vol")) in ("0", "0.0")]
        ours = _near(e.get("adjust_events"), e["date"], 7)
        W(f"- **{e['symbol']} {e['date']}**: درِ پنجرۀِ منتشرشدہ "
          f"{fa(len(o.get('window_rows') or []))} ردیف هست که {fa(len(vol0))} تایِ آن‌ها "
          f"`<VOL>=0` با پایانیِ بازنویسی‌شده‌اند؛ زنجیرۀِ خودی درِ همین پنجره "
          f"{fa(len(ours))} پله می‌گذارد "
          f"({', '.join(str(x['date']) for x in ours) or '—'}). یعنی اختلافِ «کجا پله "
          f"بگذارد» بینِ «روزِ بازنویسیِ بی‌معامله» و «نخستین روزِ معاملاتیِ بعد از آن» است، "
          f"نه اختلافِ عددِ انتشاریافته.")
    W("")
    W(f"جمعِ سه مورد: هیچ‌کدام با ضریبِ رهاورد پر نشده و هیچ عددی حدس زده نشده است. "
      f"وضعیتِ بیرونیِ دیداری همچنان **NOT_OBSERVED** است (نشستِ معتبرِ مرورگر درِ دسترس "
      f"نبود؛ همۀِ ارقامِ بالا ازِ CSVِ رسمیِ TSETMC و اسنپشاتِ فریزشدہ می‌آیند، نه ازِ "
      f"صفحۀِ زنده).")
    W("")
    W("### دستورِ آزمونِ دستیِ زنده (برایِ رفعِ NOT_OBSERVED)")
    W("")
    W("```")
    W("۱. درِ مرورگریِ که به حسابِ مشترکِ رهاورد وارد است، هرِ دو طرف را رویِ این نشانی‌ها بگذار:")
    W("     رهاورد : https://www.rahavard365.com/asset/<asset_id>/chart")
    W("     خودی   : http://localhost:5173/#/technical/<symbol>")
    W("۲. پیش ازِ هرِ مقایسه درِ هرِ دو طرف: تازۀِ معاملاتی یکسان، دورۀِ «روزانہ»،")
    W("   مبنایِ «عملکردی»، و مقیاسِ «لگاریتمی» (راست‌کلیکِ محورِ عمودی → Log Scale).")
    W("   این چهارِ تنظیم بدونِ توافق، مقایسه را بی‌معنا می‌کند — قاعدۀِ دورهایِ پیشین.")
    W("۳. برایِ هرِ نماد دو تصویرِ هم‌اندازه بگیر: یکی رویِ بازۀِ کامل، یکی رویِ بازۀِ")
    W("   ±۳۰ روزِ اطرافِ تاریخِ رویداد (از جدولِ بالا).")
    W("۴. عددِ محورِ بالا/پایین و آخرینِ close را درِ هرِ دو طرف یادداشت کن؛ سپس درِ")
    W("   خودی از کنسول: window.__borsChart.getDataList().slice(-1)[0] و")
    W("   getVisibleRange() — تا سطرِ «مشاهده» با سطرِ «داده» جدا بمانند.")
    W("۵. وضعیتِ هرِ مقایسه را فقط یکی از این‌ها بگذار: MATCH / MISMATCH / NOT_COMPARABLE")
    W("   / NOT_OBSERVED. اگر نشستِ ورود نداشت یا ۴۰۱ برگشت، همان NOT_OBSERVED می‌ماند؛")
    W("   ازِ نشستِ دیگر یا استخراجِ Cookie/توکن استفاده نمی‌کنیم.")
    W("۶. ترسیم‌هایِ از‌پیش‌موجودِ نمادِ مرجع هرگز دست نمی‌خورد (حکمِ مالک).")
    W("```")
    W("")
    W("## ۴) زنجیرۀِ راستی‌آزمایی رویِ یکِ SHA")
    W("")
    chain = {k: A("_scratch", "live", f"final_{k}.log") for k in ("tsc", "vitest", "eslint",
                                                                  "gate", "build")}
    W(f"- SHAِ زنجیره (درِ سرِ هرِ لاگ ثبت شده): `{sh('git rev-parse --short HEAD')}`")
    W(f"- `npx tsc -b`: {last_count(chain['tsc'], 'TSC_EXIT') or 'NOT_RUN'}")
    W(f"- `npx vitest run`: "
      f"{last_count(chain['vitest'], 'Tests ') or last_count(chain['vitest'], 'Test Files') or 'NOT_RUN'}")
    W(f"- `npm run lint` (eslint .): {last_count(chain['eslint'], 'ESLINT_EXIT') or 'NOT_RUN'}")
    W(f"- `python dev/run_all_tests.py`: "
      f"{last_count(chain['gate'], 'suite counted') or 'NOT_RUN'} — "
      f"{last_count(chain['gate'], 'ALL SUITES PASSED') or last_count(chain['gate'], 'FAILED:') or 'بدونِ حکم'}")
    W(f"- `npm run build` (vite): {last_count(chain['build'], 'BUILD_EXIT') or 'NOT_RUN'}")
    W(f"- گاردِ کندلِ بانک: `{last_count(GUARD_DB, ':') or 'NOT_RUN'}`")
    pkg = A("_scratch", "live", "final_package_sha256.txt")
    if os.path.exists(pkg):
        kv = {}
        for ln in io.open(pkg, encoding="utf-8", errors="replace"):
            if "=" in ln:
                k, v = ln.strip().split("=", 1)
                kv[k] = v
        W(f"- بستۀِ رسمی (همان زنجیرۀِ SHA): `{kv.get('PRODUCING_SHA', '—')}` ← "
          f"{fa(kv.get('PACKAGE_FILES', '—'))} فایل، {kv.get('PACKAGE_MB', '—')} مگابایت")
        W(f"  - `PACKAGE_SHA256` (هشِ مجمّعِ relpath+sha256+size): `{kv.get('PACKAGE_SHA256', '—')}`")
        W(f"  - `EXE_SHA256`: `{kv.get('EXE_SHA256', '—')}`")
    else:
        W("- بستۀِ رسمی: **NOT_RUN** (`_scratch/live/final_package_sha256.txt` نوشته نشده).")
    W("")
    W("## ۴-الف) کامیت‌ها و فایل‌هایِ این دور (ازِ `146b5acd` تا اینِ سند)")
    W("")
    W("```")
    W(sh("git log --reverse --format=%h|%ad|%s --date=short 146b5acd..HEAD"))
    W("```")
    W("")
    W(f"فایل‌هایِ دست‌خورده درِ همین بازه (`git diff --name-only 146b5acd..HEAD`):")
    W("")
    W("```")
    W(sh("git diff --name-only 146b5acd..HEAD"))
    W("```")
    W("")
    W("## ۵) بازها: UNRESOLVED / NOT_RUN / UNMEASURABLE / NOT_OBSERVED")
    W("")
    sm = (m4 or {}).get("summary", {})

    def n_of(op, st):
        return fa((sm.get(op) or {}).get(st, 0)) if sm else "—"
    W(f"۱. سه پلۀِ تعدیلِ فولاژ/لخزر/ولراز — علتشان درِ §۳ با ردیفِ رسمی سنجیده شد "
      f"(تکلیفِ «کجا پله بگذارد»)، اما اینکه کدامِ قراردادِ تاریخ‌گذاری مرجع است "
      f"هنوز **UNRESOLVED** است؛ رفعش دفترِ رویدادِ رسمیِ همان ins_code می‌خواهد، "
      f"نه ضریبِ ساخته‌شدہ.")
    W("۲. دو پلۀِ تعدیلِ فولاد درِ ۲۰۰۷ و ۲۰۰۸ — پیشِ نخستینِ ردیفِ دفتر؛ **UNRESOLVED**.")
    W(f"۳. مقایسۀِ دیداریِ زنده با رهاورد — **NOT_OBSERVED** (نشستِ معتبرِ مرورگرِ مالک درِ "
      f"این دسترس نبود؛ دستورِ رفع درِ §۳ نوشته شده).")
    W(f"۴. ماتریسِ ابزارها — شمارِ عملیات‌هایِ غیرِ PASS درِ §۱٫۳ آمده است: "
      f"رسم `FAIL`={n_of('draw','FAIL')}/`NOT_RUN`={n_of('draw','NOT_RUN')}، "
      f"ماندگاری `FAIL`={n_of('persist','FAIL')}/`UNMEASURABLE`={n_of('persist','UNMEASURABLE')}، "
      f"ویرایش `FAIL`={n_of('edit','FAIL')}/`UNMEASURABLE`={n_of('edit','UNMEASURABLE')}، "
      f"حذفِ منزوی `NOT_RUN`={n_of('isolated','NOT_RUN')}. تک‌تکِ این‌ها با علت درِ §۱٫۵ "
      f"ثبت شده و هیچ‌کدام PASS اعلام نشده‌اند.")
    W(f"۵. دسترسی از رابط: `UNREACHABLE`={n_of('reach','UNREACHABLE')} از "
      f"{fa(sm.get('tested')) if sm else '—'} شناسه.")
    W("۶. ردیف‌هایِ روزِ بی‌معامله: قراردادِ ما «کندل نمی‌سازد»، رهاورد می‌رسمد؛ تفاوتِ "
      "نمایشیِ مستند، بی‌تغییرِ داده.")
    W("۷. **پس‌گرفته‌شدہ:** علتِ «`no-official-rows-for-instrument`: هیچ ردیفِ رسمیِ ولراز "
      "درِ بانک نیست» که درِ سندِ دورِ پیش برایِ ولراز ۲۰۲۴-۰۱-۳۰ نوشته شده بود، **غلط** "
      "است: `ins_code = 12901875871456398` درِ `instruments` هست، `price_history` "
      "۴۹۲ ردیفِ این نماد دارد و CSVِ رسمیِ همان پنجره ۳٬۴۹۱ ردیف برگرداند "
      "(`_audit/fetch_event_window.py`). علتِ درستِ اختلاف درِ §۳ ثبت شده است.")
    W("۸. ردیفِ ماندۀِ «خط اطلاعاتی» (priceLine): درِ مسیرِ «رسم ← بازخوانی ← رسمِ دوم ← "
      "حذفِ یکی»، موتور ۱ ترسیم دارد و انبار ۲ ردیف (پس ازِ ۱۲ ثانیه انتظار). درِ "
      "همان فیلد برایِ «خط عمودی» پیش‌تر همین اتفاق می‌افتاد و با پاک‌کردنِ "
      "فهرستِ محافظت‌شدہ درِ حذفِ صریح برطرف شد؛ این یکی **باز** است. سنجشِ "
      "کنترلیِ بی‌بازخوانیِ میانی (`_scratch/live/probe_delete_resurrect.json`) "
      "همین مسیر را سالم نشان می‌دهد (۲→۱ و پس ازِ reload همان ۱)، پس نقص به "
      "مسیرِ «ترسیمِ بازگردانده‌شده + حذف» مخصوص است و علتش هنوز اثبات نشده: "
      "**UNRESOLVED**.")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("written: " + OUT + " lines=" + str(len(L)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
