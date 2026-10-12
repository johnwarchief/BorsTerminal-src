# -*- coding: utf-8 -*-
"""گاردِ ارجاع‌های `docs/FTS-RULE-ALGORITHM-MAP.md` — مرحلۀ ۳ دورِ تطبیقِ دوم.

سندِ قواعد→الگوریتم، ستونِ «کد» دارد که نامِ تابعِ واقعی را می‌برد. آن نام‌ها
اگر جابه‌جا یا حذف شوند، سند به «رجیستریِ اسمِ بی‌کد» تبدیل می‌شود — چیزی که
مرحلۀ ۹ مأموریت صریحاً ممنوع می‌کند («هیچ قابلیت‌ای فقط در نام باقی نماند»).
این گارد چهار چیز را بر خودِ سند می‌سنجد و پنجم، خودِ گارد را:

  ۱) هر شناسۀ زیرخط‌دارِ ارجاع‌شده درِ سند، واقعاً درِ کد تعریف شده است
     (پسوندمانند `_fts_choch*` با پیشوندِ تعریف‌شده‌ها تطبیق داده می‌شود).
  ۲) ارجاعِ `NAME:LINE` همان سطرِ خودِ تابع را نشانه رفته باشد (شمارۀ سطرِ
     کهنه، خطای ارجاع است نه نکتهٔ ظاهری).
  ۳) هر ردیفِ جدول ستونِ «کد»ِ پر داشته باشد — مگر ردیفی که صریحاً
     `AMBIGUOUS` خورده باشد؛ آن کد ندارد چون قاعدۀ لایۀ ۱ ندارد.
  ۴) برچسبِ ستونِ «کد» با جایِ واقعیِ تعریفِ تابع می‌خواند
     (`engine1`=`api/chart.py`، `CE`=`confidence_engine.py`، `tape`=`api/tape_flags.py`).
     تابعی که در فایلِ دیگری زنده است، به موتورِ اشتباه نسبت داده نمی‌شود.
  ۵) کنترلِ مثبت/منفی: شمارِ تعریف‌ها، ردیف‌ها و ارجاع‌ها سنجیده می‌شود تا
     «سبزِ بی‌معنا» از خواندنِ خالیِ فهرست بیرون نیاید؛ و هر سنجه روی یک
     سندِ دست‌کاری‌شده آزموده می‌شود که باید قرمز شود — گاردی که خطا را نمی‌بیند،
     سبزش دلیلِ درستی نیست.

اجرا:  python dev/test_rule_map_citations.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "FTS-RULE-ALGORITHM-MAP.md")

LABEL_FILE = {
    "engine1": "api/chart.py",
    "CE": "confidence_engine.py",
    "tape": "api/tape_flags.py",
}
FILE_LABEL = {v: k for k, v in LABEL_FILE.items()}

C_NAME = "هر شناسۀ ارجاع‌شدۀ سند درِ کد تعریف شده"
C_LINE = "ارجاع‌های NAME:LINE به سطرِ خودِ تابع می‌رسند"
C_CODE = "هر ردیفِ جدول ستونِ «کد»ِ پر دارد یا صریحاً AMBIGUOUS است"
C_ATTR = "برچسبِ «کد» با فایلِ واقعیِ تعریفِ تابع می‌خواند"


def source_files():
    exts = (".py", ".ts", ".tsx")
    for base in (ROOT, os.path.join(ROOT, "api")):
        for fn in sorted(os.listdir(base)):
            if fn.endswith(exts):
                yield os.path.join(base, fn)
    fe = os.path.join(ROOT, "frontend", "src")
    for dirpath, dirnames, filenames in os.walk(fe):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", "dist")]
        for fn in sorted(filenames):
            if fn.endswith((".ts", ".tsx")):
                yield os.path.join(dirpath, fn)


DEF_RE = re.compile(
    r"\b(?:def|class)\s+(\w+)|\b(?:const|let|function|export const|export function)\s+(\w+)")

defs = {}          # نام → مسیرِ نسبی (نخستین جایِ تعریف)
line_of = {}       # نام → شمارهٔ سطرِ تعریف
files_text = {}
for path in source_files():
    try:
        text = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        continue
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    files_text[rel] = text
    for i, line in enumerate(text.splitlines(), start=1):
        for m in DEF_RE.finditer(line):
            name = m.group(1) or m.group(2)
            if name and name not in defs:
                defs[name] = rel
                line_of[name] = i
    # پایتونِ سطح‌بالا: `X = lambda`, `X: Type =`, و ثابت‌هایِ بزرگ
    for m in re.finditer(r"(?m)^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=\s*", text):
        name = m.group(1)
        if name not in defs:
            defs[name] = rel
            line_of[name] = text[:m.start()].count("\n") + 1


def body_of(doc):
    rows = [l for l in doc.splitlines() if l.startswith("|") and not set(l) <= set("|-: ")]
    return rows[1:]


def code_cells(body):
    """ردیف‌هایِ جدول به‌همراه ستونِ آخر («کد»)."""
    for r in body:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        yield r, cells[0], cells[-1]


def check_all(doc):
    """سنجه‌های ۱ تا ۵ روی هر متنی از سند (سندِ واقعی یا سندِ دست‌کاری‌شده)."""
    res = []
    body = body_of(doc)

    # ── ۱) نام‌هایِ ارجاع‌شده ─────────────────────────────────────────────
    # `NAME*` درِ سند یعنی «هر تابعی با این پیشوند»؛ بی‌ستاره باید نامِ دقیق باشد
    # (پیشوندِ آزاد، `_daily` را به `_daily_setups` می‌چسباند و گارد را کور می‌کند).
    # نامِ پیشِ پسوندِ فایل (`OWNER_RULINGS.md`) ارجاعِ کد نیست.
    cited = []
    for span in re.findall(r"`([^`]+)`", doc):
        for m in re.finditer(r"(_[A-Za-z]\w*)(\*|:\d+)?", span):
            if span[m.end():m.end() + 1] == ".":
                continue
            cited.append((m.group(1), m.group(2) == "*", span))

    missing = []
    for name, star, span in cited:
        if name in defs:
            continue
        if star and any(d.startswith(name) for d in defs):   # `_fts_choch*`
            continue
        if name not in [x[0] for x in missing]:
            missing.append((name, span))
    res.append((C_NAME, not missing,
                " | ".join(f"{n} (از `{s}`)" for n, s in missing[:6])))

    # ── ۲) ارجاع‌های NAME:LINE ────────────────────────────────────────────
    bad_lines = []
    for name, num in re.findall(r"`(_[A-Za-z]\w*):(\d+)`", doc):
        n = int(num)
        where = defs.get(name)
        if where is None:
            bad_lines.append((name, num, "تعریف نشده"))
            continue
        lines = (files_text.get(where) or "").splitlines()
        if not (1 <= n <= len(lines)) or name not in lines[n - 1]:
            bad_lines.append((name, num, f"سطرِ {n}ِ {where} «{name}» را ندارد "
                                         f"(تعریف واقعی: سطرِ {line_of.get(name)})"))
    res.append((C_LINE, not bad_lines,
                " | ".join(f"{n}:{l} → {why}" for n, l, why in bad_lines[:4])))

    # ── ۳) هر ردیف ستونِ «کد»ِ پر دارد (AMBIGUOUS مستثنی) ────────────────
    empty_code = [rule for r, rule, code in code_cells(body)
                  if (not code or code in {"—", "-"}) and "AMBIGUOUS" not in r]
    res.append((C_CODE, not empty_code, "، ".join(empty_code[:5])))

    # ── ۴) برچسبِ موتور با جایِ واقعیِ تابع می‌خواند ──────────────────────
    # ستونِ «کد» سه برچسبِ تعریف‌شده دارد؛ اگر تابعِ ارجاع‌شده در فایلِ آن
    # برچسب‌ها زندگی نکند، سند کاری را به موتورِ دیگری نسبت داده است.
    misattributed = []
    for r, rule, code in code_cells(body):
        labels = {lab for lab in LABEL_FILE
                  if re.search(rf"(?<![\w-]){re.escape(lab)}(?![\w-])", code)}
        hit = None
        for span in re.findall(r"`([^`]+)`", code):
            for m in re.finditer(r"(_[A-Za-z]\w*)(?::\d+)?", span):
                name = m.group(1)
                where = defs.get(name)
                if where is None:               # سنجهٔ ۱ مسئولِ این است
                    continue
                want = FILE_LABEL.get(where)
                if want is not None and want not in labels:
                    got = " / ".join(sorted(labels)) or "بی‌برچسب"
                    hit = (f"{rule}: «{name}» در `{where}` (= {want}) "
                           f"اما برچسبِ ردیف {got} است")
                    break
            if hit:
                break
        if hit:
            misattributed.append(hit)
    res.append((C_ATTR, not misattributed, " | ".join(misattributed[:4])))

    # ── ۵) کنترلِ مثبت: گارد باید بی‌کد را ببیند ──────────────────────────
    # اگر روزی تعریف‌ها خالی خوانده شوند، هر چهار سنجهٔ بالا سبزِ بی‌معنا می‌شوند.
    res.append(("فهرستِ تعریف‌ها پُرخوانده شده (کنترلِ بی‌معنا-سبز)", len(defs) > 500,
                f"{len(defs)} نام"))
    res.append(("سند دست‌کم ۱۵ ردیفِ قاعده دارد", len(body) >= 15, f"{len(body)} ردیف"))
    res.append(("سند دست‌کم ۵ ارجاعِ تابعی دارد", len(cited) >= 5, f"{len(cited)} ارجاع"))
    return res, len(cited)


def negative_control(doc):
    """هر سنجه باید روی سندِ دست‌کاری‌شده قرمز شود؛ وگرنه سبزش دلیلِ درستی نیست."""
    probes = [
        (C_NAME, "`_fts_classify_trend`", "`_fts_nosuch_symbol_at_all`"),
        (C_LINE, "_fts_jet_setup:2208", "_fts_jet_setup:1902"),
        (C_CODE, "| engine1 |", "|  |"),
        (C_ATTR, "engine1 `_fts_exit_layer1`", "tape `_fts_exit_layer1`"),
    ]
    out = []
    for expect, old, new in probes:
        if old not in doc:
            out.append((f"کنترلِ منفیِ {expect}", False,
                        f"لنگرِ «{old}» در سند پیدا نشد — خودِ گارد کور شده"))
            continue
        res, _ = check_all(doc.replace(old, new, 1))
        fired = {n for n, ok_, _ in res if not ok_}
        out.append((f"کنترلِ منفیِ {expect}", expect in fired,
                    "" if expect in fired else "دست‌کاریِ آشکارِ خطا دیده نشد"))
    return out


doc = open(DOC, encoding="utf-8").read()
RES, cited_n = check_all(doc)
RES += negative_control(doc)

fails = [n for n, ok_, _ in RES if not ok_]
for n, ok_, extra in RES:
    print(f"  {'PASS' if ok_ else 'FAIL'}  {n}"
          f"{'  <<< ' + extra if (extra and not ok_) else ''}")
print(f"\n{len(RES) - len(fails)}/{len(RES)} passed"
      f"  ({len(defs)} نمادِ تعریف‌شده، {cited_n} ارجاعِ سند)")
sys.exit(1 if fails else 0)
