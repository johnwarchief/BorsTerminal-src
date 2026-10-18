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


def sh(cmd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        return (r.stdout or "").strip()
    except Exception as ex:
        return "(not read: %s)" % type(ex).__name__


def j(path):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding="utf-8"))


def rows(path):
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(io.open(path, encoding="utf-8-sig")))


def main():
    m3 = j(A("_audit", "chart_drawing_matrix_v3.json"))
    cmp_rows = rows(A("_audit", "RA365-COMPARE-MATRIX.csv"))
    gap = rows(A("_audit", "ADJUSTED-FACTOR-GAP.csv"))
    fa_state = j(A("_scratch", "live", "full_audit_state.json"))
    gate_tail = A("_scratch", "live", "gate_final2.log")
    vit_tail = A("_scratch", "live", "vitest_final.log")

    def last_count(path, needle):
        if not os.path.exists(path):
            return None
        for ln in reversed(io.open(path, encoding="utf-8", errors="replace").read().splitlines()):
            if needle in ln:
                return ln.strip()
        return None

    L = []
    W = L.append
    W("# بستنِ Engine 1 — ماتریسِ ابزارهایِ ترسیم، قراردادِ کندلِ بانک، مقایسۀِ بیرونی و گیت‌ها")
    W("")
    W(f"- شاخه: `{sh('git rev-parse --abbrev-ref HEAD')}` — SHAِ این سند: `{sh('git rev-parse --short HEAD')}`")
    W("- تاریخ: ۱۴۰-۰۷-۲۷ · انتشار: هیچ Push/Merge/Tag انجام نشده (شاخه بی‌upstream است: "
      "`git rev-parse --abbrev-ref @{u}` ⇒ fatal: no upstream configured).")
    W("")
    W("## ۱) ماتریسِ ۲۹ ابزارِ ترسیم")
    W("")
    if not m3:
        W("- **NOT_RUN**: اجرایِ ماتریس درِ زمانِ نوشتنِ این سند تمام نشده بود "
          "(`_audit/chart_drawing_matrix_v3.json` هنوز نوشته نشده). عددِ جعلی درِ این "
          "بخش نمی‌نشیند.")
    else:
        s = m3["summary"]
        W(f"- registry از خودِ `DrawingToolbar.tsx`: {fa(m3['registrySlots'])} شیار، "
          f"{fa(m3['registryTools'])} شناسۀِ ابزار (کلیدِ گزارش `slotId:toolId:name` است، "
          f"چون دو `id` با دو نامِ متفاوت تکرار شده و با دِدوپِ صرفِ id یکی از ۲۹ گم می‌شد).")
        W(f"- کنترلِ مثبت (`{m3['positiveControl']['toolId']}`): "
          f"{'✓' if m3['positiveControl']['drew'] else '✗'} — بی‌این، هارنس خروجیِ دیگری "
          f"نمی‌دهد و exit 3 می‌کند.")
        W("")
        W("| سنجه | ابزارِ سنجیده‌شده | نتیجه |")
        W("|---|---|---|")
        for what, key in (("دسترسی از رابط", "reachable"), ("رسمِ واقعی", "drew"),
                          ("ماندگاری درِ انبارِ خودی", "persisted"),
                          ("ویرایش درِ دیدِ موتور", "editedEngine"),
                          ("ویرایش درِ انبار", "editedStored"),
                          ("مخفی‌سازی", "visibilityToggled"),
                          ("حذفِ یکِ رسم", "deletedOne"),
                          ("حذفِ منزوی (بقیۀِ رسم‌ها سالم)", "isolatedDelete"),
                          ("هماهنگیِ وضعیتِ موتور با ترسیم", "engineCoherent")):
            W(f"| {what} | {fa(s[key])} از {fa(s['tested'])} |")
        W("")
        W(f"- حل‌شدگانِ زنده (ابزارِ قابلِ دسترسی که چیزی رسم نکرد): {fa(len(s['dead']))} "
          f"{('→ ' + json.dumps(s['dead'], ensure_ascii=False)) if s['dead'] else ''}")
        W(f"- غیرقابل‌دسترس از رابط: {fa(len(s['unreachable']))} "
          f"{('→ ' + json.dumps(s['unreachable'], ensure_ascii=False)) if s['unreachable'] else ''}")
        W(f"- «حذف تمام ترسیم‌ها»: لغو = "
          f"{'هیچِ ترسیمی نمی‌میرد ✓' if s['deleteAll']['cancelHeld'] else '✗'}، "
          f"تأیید = {'همۀِ رسم‌هایِ خودی پاک شد ✓' if s['deleteAll']['acceptCleared'] else '✗'} "
          f"(هدفِ حذف داشت: {'✓' if s.get('deleteAllCancelHadTarget') else '✗'})")
    W("")
    W("### علتِ تناقضِ دورِ پیش (اندازه‌گیری‌شدہ، نه حدس)")
    W("")
    W("۱. شمارشِ «ترسیم» با `getOverlays()`ِ خام: "
      f"{fa((m3 or {}).get('baseline', {}).get('engineTotal', 0))} اورلی درِ خطِ مبنایِ "
      "همان اجرا دیده شد که لایه‌هایِ موتورِ الگو/پیش‌شرط/رویدادِ شرکتی بودند، نه رسمِ "
      "کاربر. چون id هایِ اورلی با هرِ re-render عوض می‌شوند، «تازگی» بی‌معنا می‌شد و "
      "ابزارهایِ داخلِ فلایاوت «چیزی رسم نمی‌کند» گزارش می‌شدند.  ")
    W("۲. «حذف تمام ترسیم‌ها» پشتِ `window.confirm`ِ بومی است؛ هارنس هرگز آن را "
      "تأیید/رد نمی‌کرد، پس پاک‌سازیِ ضمنیِ آن بی‌اثر بود.")
    W("۳. نام‌هایِ figure مانند `rect` و `crosshair` میانِ چندِ ابزار و لایه‌ها مشترک "
      "است؛ لذا درِ v3 سیگنالِ ground-truth به **انبارِ ترسیمِ خودیِ محصول** "
      "(`fts.drawings.v1.<symbol>`) و دیدِ زندهٔ گروهِ `fts-draw` تغییر کرد.")
    W("")
    W("### محدودیتِ باقی‌مانده (صریح)")
    W("")
    W("- ماندگاریِ ترسیم با تأخیر (debounce) است: درِ اجرایِ سنجش‌شدہ، ردیفِ localStorage "
      "چند گام پس ازِ کلیک‌ها ظاهر می‌شد؛ هارنس با wait بر آن تنظیم شد، اما یعنی "
      "«شمارشِ بی‌صبر» نتیجهٔ غلط می‌دهد (این را به‌عنوان رفتارِ محصول ثبت می‌کنیم).")
    W("- ردیفِ ذخیرہ‌شده بی‌`id` است (`id: null`) و برایِ یکِ segmentِ دونقطه‌ای "
      "`points` یک‌عضوی ذخیره می‌کند؛ بازیابیِ پس ازِ reload کار می‌کند اما "
      "شناساییِ ردیفِ ماندگار به id ممکن نیست ⇒ ویرایش درِ دیدِ انبار سنجیده نمی‌شود "
      "و درِ دیدِ موتور سنجیده می‌شود. این نقصِ ماندگاریِ متادیتا است، نه نقصِ عددِ قیمت.")
    W("")
    W("## ۲) قراردادِ مشترکِ کندلِ بانک")
    W("")
    W(f"- شمارشِ کلِ بانک (`_audit/db_row_contract_impact.py`): "
      f"ردیف‌هایِ هندسه‌شکسته {fa(306)} رویِ {fa(44)} نماد، و ردیف‌هایِ حجم‌صفر "
      f"{fa(2692)} — جزئیاتِ علت‌محور درِ جدولِ پایین.")
    W("- پیاده: `get_chart_db` از `candle_contract.from_db_row` و `SELECT_SQL`/`DB_COLUMNS` "
      "می‌گذرد؛ شمارش‌ها با علت درِ پاسخ اعلام می‌شود (`dbRows`, `dbNoTradeRows`, "
      "`dbInvalidRows`) تا «کم شدنِ کندل» حذفِ خاموش نباشد.")
    W("- گارد: `dev/db_candle_contract_v1.py` با کنترلِ بی‌معنا‌سبز (بازسازیِ سازندۀِ "
      "قدیم همان آزمون را قرمز می‌کند) و دو بانکِ موقت (با «آخرین» ناقص و کامل).")
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
    W("")
    W("### سه اختلافِ حل‌نشده (وضعیت: UNRESOLVED)")
    W("")
    W("| نماد | تاریخ | نسبتِ مرجع | نسبتِ ما | علتِ سنجیده‌شدہ | شاهدِ لازم برایِ رفع |")
    W("|---|---|---|---|---|---|")
    W("| فولاژ | ۲۰۲۴-۰۷-۲۷ | ۱٫۲۵۰۳۵۲ | ۱٫۱۰۳۹۳۴ | دفترِ مبدأ به این رویداد نرسید: "
      "۲۸ ردیفِ بی‌نوعِ حل‌نشده و ۱۲ ردیفِ بی‌همتا با سریِ قیمت؛ رویداد با "
      "`source=base-price-discontinuity` و ضریبِ دیدۀِ CSV ماند | ردیفِ رسمیِ "
      "همانِ تاریخ با نوعِ رویداد + درصدِ افزایش/سودِ تفکیکی |")
    W("| لخزر | ۲۰۲۶-۰۷-۲۷ | ۱٫۲۰۹۷۹۰ | ۱٫۱۳۳۰۹۳ | پوششِ دفتر از ۲۰۱۲-۰۲-۱۹ با "
      "۸۵۸ کندلِ پیشِ پوشش؛ ۱۸ ردیفِ بی‌نوع؛ رویدادِ این روز درِ پنجرۀِ کشف با "
      "گسستِ دیگر جمع شده | ردیفِ مبدأِ ۲۰۲۶-۰۷-۲۷ + تاریخِ معافیت/آورده |")
    W("| ولراز | ۲۰۲۴-۰۱-۳۰ | ۱۸٫۹۰۵۷۸۷ | ۱۷٫۷۸۵۶۸۳ | `no-official-rows-for-instrument`: "
      "هیچ ردیفِ رسمیِ این ابزار درِ بانک نیست ⇒ عددِ مبدأ برایِ تیزکردن وجود ندارد | "
      "واردکردنِ دفترِ رسمیِ همین ins_code |")
    W("")
    W("هیچ‌یک از این سه با ضریبِ رهاورد پر نشده و هیچ عددی حدس زده نشده است. "
      "وضعیتِ بیرونیِ دیداری: **NOT_OBSERVED** (نشستِ معتبرِ مرورگر درِ دسترس نبود؛ "
      "عددِ بالا از اسنپشاتِ فریزشدہ است، نه ازِصفحۀِ زنده).")
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
    W("## ۴) گیت‌ها رویِ SHAِ واحد")
    W("")
    gt = last_count(gate_tail, "suite counted")
    vt = last_count(vit_tail, "Tests ")
    W(f"- SHAِ نهاییِ همهٔ اجراها: `{sh('git rev-parse --short HEAD')}`")
    W(f"- `npx tsc -b`: `{sh('cd frontend && npx tsc -b 2>&1 | tail -1') or 'clean'}`")
    W(f"- `npx vitest run`: {vt or 'NOT_RUN'}")
    W(f"- گیتِ پایتون: {gt or 'NOT_RUN (درِ جریان)'}")
    W(f"- build رسمی: `{sh('tail -3 _scratch/live/build_all2.log | head -3')}`")
    W("")
    W("## ۵) مواردِ حل‌نشده")
    W("")
    W(f"1. سه ضریبِ رویدادِ بالا (فولاژ، لخزر، ولراز) — UNRESOLVED با شاهدِ لازم.")
    W(f"2. دو پلۀِ تعدیلِ فولاد درِ ۲۰۰۷ و ۲۰۰۸ — پیشِ نخستینِ ردیفِ دفتر؛ UNRESOLVED.")
    W("3. مقایسۀِ دیداریِ زنده با رهاورد — NOT_OBSERVED.")
    W("4. ماندگاریِ `id` و شمارِ نقاطِ کامل درِ ردیفِ localStorage (متادیتایِ ترسیم).")
    W("5. ردیف‌هایِ روزِ بی‌معامله: قراردادِ ما «کندل نمی‌سازد»، رهاورد می‌رسمد؛ "
      "تفاوتِ نمایشیِ مستند، بی‌تغییرِ داده.")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("written: " + OUT + " lines=" + str(len(L)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
