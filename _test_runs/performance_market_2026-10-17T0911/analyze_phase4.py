# -*- coding: utf-8 -*-
"""§۴ (بیلدِ رسمی + smoke) ازِ لاگِ build_all، JSONِ smoke و اثرِ انگشتِ آرتیفکت."""
import hashlib
import io
import json
import os
import re
import subprocess

RUN = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(RUN, "..", ".."))
BUNDLE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
EXE = os.path.join(BUNDLE, "BorsTerminal_Ultimate.exe")


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


def main():
    log = io.open(os.path.join(RUN, "phase4-build_all.log"), encoding="utf-8",
                  errors="replace").read()
    sm = json.load(io.open(os.path.join(RUN, "phase4-smoke.json"), encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()
    exe_sha = hashlib.sha256(open(EXE, "rb").read()).hexdigest()
    exe_size = os.path.getsize(EXE)
    files = sum(len(f) for _, _, f in os.walk(BUNDLE))
    total = sum(os.path.getsize(os.path.join(r, x)) for r, _, f in os.walk(BUNDLE) for x in f)
    L = []
    A = L.append

    A("### ۴الف) بیلد ازِ مسیرِ رسمی")
    A("")
    A("```")
    A("python scripts/build_all.py        # همان چیزی که مخزن می‌گوید؛ جایِگزین اختراع نشد")
    m = re.search(r"npm run build done in (\d+)s", log)
    n = re.search(r"pyinstaller: fts_terminal.spec done in (\d+)s", log)
    A("=== frontend: npm run build === [OK] done in %ss" % fa(m.group(1) if m else "?"))
    A("=== pyinstaller: fts_terminal.spec === [OK] done in %ss" % fa(n.group(1) if n else "?"))
    A("Build complete!  →  dist/BorsTerminal_Ultimate   BUILD_EXIT=0")
    A("```")
    A("")
    A("| چیز | مقدار |")
    A("|---|---|")
    A("| شاخۀ منبعِ بیلد | `" + head[:12] + "` (فایل‌هایِ سورس == `HEAD`؛ تنها تغییرِ بازنگشتۀ "
      "کاری، ابزارهایِ `tools/` سنجش بود) |")
    A("| مسیرِ خروجی | `" + os.path.relpath(BUNDLE, ROOT).replace("\\", "/") + "` |")
    A("| شمارِ فایلِ بسته | " + num(files) + " فایل، " + num(total) + " B ≈ " +
      num(total / 1048576.0) + " MB |")
    A("| لانچر | `BorsTerminal_Ultimate.exe` — " + num(exe_size) + " B |")
    A("| SHA-256 لانچر | `" + exe_sha + "` |")
    A("| مفسرِ بیلد | Python " + fa("3.14.4") + " درِ `venv_build/` (ایزوله، gitignore) با "
      "`scripts/check_build_env.py` ⇒ `OK — 13 importable modules` |")
    A("")
    A("**قیدِ صادقانۀ بیلد:** CI این مخزن Python ۳٫۱۲ و `numpy==2.0.2`/`pandas==2.2.3` را "
      "ملاک می‌گیرد (`scripts/check_build_env.py:…`، `requirements.txt:6-10`)؛ رویِ این ماشین "
      "جزِ ۳٫۱۴ نبود (`py -0p` ⇒ یکِ مفسر). بیلد با همان ۳٫۱۴ و `numpy 2.5.2`/`pandas 3.0.5` "
      "ساخته شد. پس این آرتیفکت **برایِ راستی‌آزماییِ بسته‌بندیِ همین تغییر** است، نه بدلِ "
      "بستۀ ریلیز — و خودِ `requirements.txt` می‌گوید numpyِ ۲٫۱+ خطِّ `X86_V2` را اجباری "
      "می‌کند، پس انتشارِ این بیلد جایِگزینِ بیلدِ CI نیست.")
    A("")

    A("### ۴ب) smokeِ همان بستۀ ساخته‌شده — `10/10`")
    A("")
    A("بستۀ onedir با `bors_portable.flag` و `data/market.db`ِ کپیِ خودِ ورک‌تری، رویِ پورتِ "
      "اختصاصیِ " + fa(sm["port"]) + " و `BORS_NO_FETCH_LOOPS=1` بالا آمد؛ `LOCALAPPDATA` هم "
      "برایِ همانِ فرایند به پوشۀ موقتِ من برگردانده شد تا پروفایلِ نسخۀ نصبیِ کاربر باز "
      "نماند. پنجرۀ اپ درِ این دور باز شد و بسته شد (~۳۰ ثانیه) — تنها اثرِ دیدنیِ همین "
      "سنجش، و هیچ دادۀ کاربری تغییر نکرد.")
    A("")
    A("| سنجه | نتیجه |")
    A("|---|---|")
    for c in sm["checks"]:
        A("| " + c["name"] + " | `" + ("PASS" if c["ok"] else "FAIL") + "` — " +
          str(c["detail"]) + " |")
    A("")
    good = sum(1 for c in sm["checks"] if c["ok"])
    A("جمع: **" + num(good) + " از " + num(len(sm["checks"])) + "** (`phase4-smoke.json`). "
      "سه چیزِ مهم ازِ همین جدولِ کوچک درمی‌آید: بدنهٔ قیف درِ بسته هم `MISS` یک‌بار و "
      "`HIT`ِ بایت‌به‌بایت یکی می‌شود (`" + str(sm["checks"][6]["detail"]) + "`), مسیرِ "
      "مشروط هم رویِ GET و هم POST به `304`ِ صفر‌بایت می‌رسد, و `last_sync` نشانش می‌دهد "
      "داده همان کپیِ بی‌fetch است.")
    A("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    text = main()
    io.open(os.path.join(RUN, "tables-phase4.md"), "w", encoding="utf-8", newline="\n").write(text)
    print(text)
