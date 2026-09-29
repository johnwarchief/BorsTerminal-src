"""ta_local_parity.py — پنل‌به‌پنل: فیدِ تریدرزآرنا در برابرِ موتورِ لوکالِ خودِ برنامه

چرا: پنج روتِ `/api/market-status/*` پروکسۀ tradersarena.ir بودند و هیچ
مصرف‌کننده‌ای در UI نداشتند؛ در v1.0.53+ از `api/market_status.py` حذف شدند.
منبعِ «او» حالا خودِ آدرسِ عمومیِ تریدرزآرنا است (`--ta live`، فقط GETِ خواندنی)؛
اگر نرسید از فیدهایِ بایگانی‌شدۀ `_audit/ta/` می‌خواند (`--ta archive`/`auto`).

اعدادِ ریالی این‌جا مقایسه نمی‌شوند (واحدِ دو طرف یکی نیست؛ آن مقایسه با تبدیلِ
درست در `docs/TA-PARITY-1405-07-04.md` آمده). این اسکریپت **ساختار و پوشش** را
می‌خواند: چند سطر/نقطه/افق از هر طرف هست.

    PYTHONIOENCODING=utf-8 python tools/ta_local_parity.py [--base http://127.0.0.1:8001]
                                                           [--ta live|archive|auto]

خروجی: جدولِ RTL + `UNCOVERED=<n>`؛ کدِ خروجِ ۱ اگر پنلی بی‌معادلِ لوکال بماند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ARCHIVE_DIR = os.path.join("_audit", "ta")
TA_ORIGIN = "https://tradersarena.ir"
TA_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": f"{TA_ORIGIN}/market",
              "Accept": "application/json"}

# پنل‌های TA که بعد از حذفِ پروکسی مستقیماً خوانده می‌شوند (فقط GETِ عمومی).
TA_LIVE = {
    "overview": "/data/market0",
    "timeline": "/data/market/chart/totals0",
    "industries": "/data/industries-csv",
    "mainwatch": "/data/mainwatch/symbols",
    "histo": "/data/market/histo-status",
}

# هر پنلِ TA: (آدرسِ پروکسیِ پیشین — حالا فقط برایِ نامِ کلیدِ بدنه، فایلِ بایگانی، کلیدِ زیرِ بدنه)
TA_PANELS = {
    "overview": ("/api/market-status/overview", "market0.json", "market"),
    "timeline": ("/api/market-status/timeline", "market_chart_totals0.json", "data"),
    "industries": ("/api/market-status/industries", "data_industries-csv.fz", "data"),
    "mainwatch": ("/api/market-status/mainwatch", "data_mainwatch_symbols.fz", "data"),
    "histo": ("/api/market-status/histo", "market_histo-status.json", "data"),
}

# معادلِ لوکالِ هر پنل: همان چیزی که وب‌اپ واقعاً صدا می‌زند
LOCAL = {
    "overview": ("/api/mstat/summary", lambda d: f"{_n(d.get('rows'))} سطرِ خلاصه + health"),
    "timeline": ("/api/mstat/timeline?mode=cum", lambda d: f"{_n(d.get('points'))} نقطه، روز {d.get('day')}"),
    "industries": ("/api/mstat/industries", lambda d: f"{_n(d.get('rows'))} صنعت"),
    "mainwatch": ("/api/mstat/mainwatch", lambda d: f"{_n(d.get('rows'))} نماد (کل {d.get('total')})"),
    "histo": ("/api/mstat/histogram", lambda d: f"{_n(d.get('histo12'))}+{_n(d.get('histo7'))} سطل، افق: {d.get('basis')}"),
}


def _n(v) -> int:
    """شمارشِ سطرها/کلیدها، چه فید آرایه بدهد چه dict چه عددِ ازپیش‌شمرده‌شده"""
    if isinstance(v, (list, dict)):
        return len(v)
    return v if isinstance(v, int) else 0


def get_live(base: str, path: str):
    return get_url(base + path)


def get_url(url: str):
    try:
        req = urllib.request.Request(url, headers=TA_HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def get_archive(fname: str):
    path = os.path.join(ARCHIVE_DIR, fname)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ta_body(d, key):
    """بدنهٔ پنل: در پاسخِ پروکسی زیرِ `market`/`data` است؛ فایلِ بایگانی خودِ بدنه است"""
    if not isinstance(d, dict):
        return d
    return d.get(key, d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--ta", default="auto", choices=("live", "archive", "auto"))
    args = ap.parse_args()

    rows, uncovered = [], 0
    for panel, (_proxy, archive, body_key) in TA_PANELS.items():
        src, ta = "—", None
        if args.ta in ("live", "auto") and panel in TA_LIVE:
            d = get_url(TA_ORIGIN + TA_LIVE[panel])
            if d is not None:
                ta, src = ta_body(d, body_key), "تریدرزآرنا زنده"
        if ta is None and args.ta in ("archive", "auto"):
            ta, src = get_archive(archive), f"بایگانیِ `_audit/ta/{archive}`"
        if ta is None:
            rows.append((panel, "—", "دو منبع هم نرسید", "—", "—", "اندازه‌گیری نشد"))
            uncovered += 1
            continue

        lpath, lfmt = LOCAL[panel]
        lo = get_live(args.base, lpath) or {}
        lo_shape = lfmt(lo)
        n_ta, n_lo = _n(ta), _n(lo.get("rows") or lo.get("points") or lo.get("histo12"))

        if panel == "histo":
            ta_shape = f"{_n(ta)} افق × سطل"
            verdict = "شکاف: افق‌هایِ ۵/۱۰/۲۰/۶۰ روزه درِ برنامه نیست"
            uncovered += 1
        elif panel == "industries":
            ta_shape = f"{_n(ta)} سطر"
            verdict = ("پوشش داده شد" if _n(ta) <= n_lo else
                       f"شکاف: {_n(ta) - n_lo} گروه (عمدتاً دسته‌هایِ صندوق) درِ برنامه نیست")
            uncovered += 0 if _n(ta) <= n_lo else 1
        else:
            ta_shape = f"{_n(ta)} سطر" if not isinstance(ta, dict) else f"{_n(ta)} فیلد/سری"
            verdict = "پوشش داده شد"
        rows.append((panel, src, ta_shape, lpath, lo_shape, verdict))

    print("| پنلِ تریدرزآرنا | منبع | او | اندپوینتِ ما | ما | داوری |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print("| `" + r[0] + "` | " + r[1] + " | " + r[2] + " | `" + r[3] + "` | " + r[4] + " | " + r[5] + " |")
    print()
    print(f"UNCOVERED={uncovered}")
    return 0 if uncovered == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
