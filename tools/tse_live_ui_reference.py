# -*- coding: utf-8 -*-
"""هفت跑出ِ زندهٔ رابطِ سایت (`_audit/tse_live_ui_fN.json`) → قالبِ مرجعِ پارالل.

فایل‌هایِ زنده را `user-browser-use` ازِ خودِ صفحه می‌نویسد: برایِ هر فیلتر
`eval(mw.FilterCode)` رویِ `mw.AllRows` (همان مسیری که جدولِ سایت را می‌سازد) و
در کنارش شمارِ ردیفِ جدولِ دیده‌بان (که با «تنظیمات دیده بان» کم‌وفازله می‌شود).
این ابزار فقط قالب را عوض می‌کند؛ هیچ داوری‌ای اینجا ساخته نمی‌شود.

اجرا:
  PYTHONIOENCODING=utf-8 python tools/tse_live_ui_reference.py
"""
import argparse
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
FILT = [("f0", "clock"), ("f1", "roobi"), ("f2", "susp"), ("f3", "noqteh"),
        ("f4", "jet"), ("f5", "smart"), ("f6", "legal")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="_audit")
    ap.add_argument("--out", default="_audit/tse_live_ui_reference.json")
    a = ap.parse_args()
    codes, meta = {}, []
    for tag, key in FILT:
        p = os.path.join(a.dir, f"tse_live_ui_{tag}.json")
        if not os.path.exists(p):
            raise SystemExit(f"نیست: {p} — اول هفت فیلتر را درِ رابطِ سایت اجرا کن")
        d = json.load(io.open(p, encoding="utf-8"))
        got = [x["code"] for x in d.get("pass") or []]
        if len(got) != d.get("site_filter_pass"):
            raise SystemExit(f"{tag}: شمارِ باقلیست ({len(got)}) با {d.get('site_filter_pass')} نمی‌خواند")
        codes[key] = " ".join(got)
        meta.append({"filter": key, "site_tag": tag, "name": d.get("filterName"),
                     "site_filter_pass": d.get("site_filter_pass"),
                     "site_table_rows": d.get("site_table_rows"),
                     "universe": d.get("universe"), "at": d.get("at"),
                     "symbols": [x["sym"] for x in d.get("pass") or []]})
        print(f"{key:7s} «{d.get('filterName')}» فیلترِ سایت={d.get('site_filter_pass'):4d} "
              f"| جدولِ دیده‌بان={d.get('site_table_rows'):4d} | جامعۀ سایت={d.get('universe')} "
              f"| {d.get('at')}")
    out = {"source": "رابطِ واقعیِ TSETMC (old.tsetmc.com/Loader.aspx?ParTree=15131F) — "
                     "mw.SelectFilter ازِ ردیفِ «فیلترهای ذخیره‌شده در سربرگ»، سپس "
                     "eval(mw.FilterCode) روی mw.AllRows",
           "codes": codes, "runs": meta}
    with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
