"""pulse_ta_parity.py — جدولِ تطبیقِ «نبض بازار» با تریدرزآرنا، سطر‌به‌سطر.

چرا این ابزار: «تطبیقِ کامل» یعنی هر سطرِ ما با **ردیفِ هم‌نامِ خودش** در
تریدرزآرنا بسزد، نه با یک عددِ کلی (هویت‌های جبری و دلیلش:
docs/TA-SCOPE-DECODE.md). پیانگِ خامِ دو طرف را `tools/pulse_ta_snapshot.py`
می‌گیرد؛ اینجا همان اعداد را در یک خطا٪ ترجمه می‌کند تا رفعِ دامنه
سنجیدنی باشد، نه حدس.

فقط خواندنی: کوئری `mode=ro` رویِ بانک + یک GETِ عمومیِ TA (بی‌لاگین، بی‌عددِ
واردشده). هیچ عددی از تریدرزآرنا به برنامه وارد نمی‌شود.

اجرا:  PYTHONIOENCODING=utf-8 python tools/pulse_ta_parity.py [--db PATH]
                                            [--json _audit/pulse_ta_parity.json]
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import mstat_engine as ME                                           # noqa: E402

TA_URL = "https://tradersarena.ir/data/market0"
TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/market"}
RIAL_TO_BT = 1e10          # ریال → میلیارد تومان (تأیید: tools/ta_local_parity.py)

# سطرهایِ تریدرزآرنا ← سطرهایِ جدولِ ما (ردیفِ هم‌نام، نه عددِ کلی)
PAIRS = [
    ("m",   "کل بازار",                 "all",         "ارزش"),
    ("m",   "کل بازار",                 "all",         "جریان"),
    ("st",  "سهام و حق تقدم",            "stock_right", "ارزش"),
    ("sf",  "صندوق‌های سهامی و مختلط",     "eq_fund",     "ارزش"),
    ("nsf", "صندوق درآمد ثابت",           "fixed_fund",  "ارزش"),
    ("lf",  "صندوق‌های اهرمی",            "lev_fund",    "ارزش"),
    ("cf",  "صندوق‌های طلا",              "gold_fund",   "ارزش"),
    ("scf", "صندوق‌های نقره",             "silver_fund", "ارزش"),
    ("afl", "سهام و واحدهایِ سهمی",        "eq_all",      "ارزش"),
]
IDX = {"ارزش": 1, "جریان": 5}


def ta_feed():
    req = urllib.request.Request(TA_URL, headers=TA_HDR)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    if isinstance(d, list):
        d = d[0] if d else {}
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--json", default=os.path.join(ROOT, "_audit", "pulse_ta_parity.json"))
    args = ap.parse_args()
    db = args.db or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                                 "BorsTerminal Ultimate", "market.db")
    if not os.path.exists(db):
        print("بانک پیدا نشد:", db)
        return 2
    try:
        ta = ta_feed()
    except Exception as e:                                          # noqa: BLE001
        print("تریدرزآرنا در دسترس نیست:", type(e).__name__, e)
        return 3
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        s = ME.summary(conn)
    finally:
        conn.close()
    ours = {r["key"]: r for r in s["rows"]}
    meta = s["asof"]
    lines = []
    out = {"taken_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "ta_day": ta.get("j"), "ta_hour": ta.get("d"), "app_asof": meta,
           "rows": []}
    for key, ta_label, our_key, metric in PAIRS:
        arr = ta.get(key) or []
        if len(arr) <= IDX[metric]:
            continue
        theirs = float(arr[IDX[metric]] or 0.0) / RIAL_TO_BT
        mine = float(ours.get(our_key, {}).get("value_b_toman") or 0.0) \
            if metric == "ارزش" else float(ours.get(our_key, {}).get("money_flow_b_toman") or 0.0)
        err = (mine - theirs) / theirs if theirs else None
        out["rows"].append({"ta_row": key, "ta_label": ta_label, "our_key": our_key,
                            "metric": metric, "ta_bt": round(theirs, 1),
                            "our_bt": round(mine, 1),
                            "err_pct": None if err is None else round(err * 100, 2)})
        lines.append((key, ta_label, ours[our_key]["label"], theirs, mine, err))

    # هویتِ جبریِ خودِ TA — اگر این بشکند، رمزگشاییِ ما بی‌اعتبار است
    ident = {}
    for i in (1, 5):
        try:
            s_sum = sum(float((ta.get(k) or [0] * 18)[i] or 0.0)
                        for k in ("st", "sf", "nsf"))
            ident["i%d" % i] = {"m": float(ta["m"][i]) / RIAL_TO_BT,
                                "st+sf+nsf": s_sum / RIAL_TO_BT}
        except Exception:                                           # noqa: BLE001
            pass

    # ترکیب‌هایِ اثبات‌شدنی: تقسیمِ زیرگونهٔ صندوق از نام حدس است، ولی *گروه*های
    # آن باید با او بخوانند — همین‌جا همان تفکیکِ دو سطرِ هم‌خانواده سنجیده می‌شود.
    conn2 = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    conn2.row_factory = sqlite3.Row
    rows2, _meta2 = ME.enrich(conn2)
    conn2.close()

    def our_sum(pred):
        return sum((_r["_m"].get("val") or 0.0) for _r in rows2 if pred(_r)) / RIAL_TO_BT

    def ta_sum(keys):
        return sum(float((ta.get(k) or [0] * 18)[1] or 0.0) for k in keys) / RIAL_TO_BT

    combos = [
        ("ص.سهامی + درآمدِ ثابت", ta_sum(("sf", "nsf")),
         our_sum(lambda r: r["cls"] == "fund" and r["kind"] in
                 ("equity", "fof", "etf", "mixed", "fixed"))),
        ("طلا + نقره + کالا", ta_sum(("cf", "scf")),
         our_sum(lambda r: r["cls"] == "fund" and r["kind"] in
                 ("gold", "silver", "commod"))),
        ("اهرمی (تنها)", ta_sum(("lf",)),
         our_sum(lambda r: r["cls"] == "fund" and r["kind"] == "lev")),
    ]

    print("تریدرزآرنا %s %s | بانک %s"
          % (out["ta_day"], out["ta_hour"], json.dumps(meta, ensure_ascii=False)[:120]))
    print("%-6s %-26s %-26s %14s %14s %8s" % ("ردیف", "برچسب TA", "سطرِ ما",
                                              "TA (م.ت)", "ما (م.ت)", "خطا"))
    for key, ta_label, our_label, theirs, mine, err in lines:
        print("%-6s %-26s %-26s %14s %14s %s"
              % (key, ta_label, our_label, f"{theirs:,.1f}", f"{mine:,.1f}",
                 "—" if err is None else "%+.2f%%" % (err * 100)))
    print("\nهویتِ جبریِ TA (m = st+sf+nsf):")
    for k, v in ident.items():
        print("  %-3s m=%s  st+sf+nsf=%s" % (k, f"{v['m']:,.1f}", f"{v['st+sf+nsf']:,.1f}"))
    print("\nگروه‌هایِ صندوق (تقسیمِ زیرگونه حدس است؛ گروه باید بخواند):")
    out["combos"] = []
    for label, theirs, mine in combos:
        err = (mine - theirs) / theirs if theirs else None
        out["combos"].append({"label": label, "ta_bt": round(theirs, 1),
                              "our_bt": round(mine, 1),
                              "err_pct": None if err is None else round(err * 100, 2)})
        print("  %-26s TA=%14s  ما=%14s  %s"
              % (label, f"{theirs:,.1f}", f"{mine:,.1f}",
                 "—" if err is None else "%+.2f%%" % (err * 100)))
    out["identity"] = ident
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("\n→", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
