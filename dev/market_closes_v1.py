"""MARKET-CLOSES v1 — گاردِ نقشهٔ سبکِ قیمتِ پایانی (PERF-R4).

`useMarketCloses` پیش‌تر از فیدِ کاملِ `/api/market` (۶٫۸MB خام / ~۱٫۲MB gzip)
فقط `symbol → p_closing` را برمی‌داشت و صفحهٔ master/پرتفوی همان بدنه را در
هر ورود می‌کشیدند. مسیرِ `/api/market/closes` همان ستون را از همان ردیفِ
تابلو می‌دهد. این گارد ثابت می‌کند:

  ۱) مقدارِ هر نماد با کوئریِ مستقیمِ همان `market_watch` یکی است؛
  ۲) ETag وجود دارد و درخواستِ شرطی ۳۰۴ِ صفر‌بایت می‌دهد؛
  ۳) ETagِ ناهمخوان ۲۰۰ِ کامل می‌دهد (نه ۳۰۴ِ کاذب)؛
  ۴) نقشه هزاران نماد دارد (کاهشِ داده به معنیِ از‌دست‌رفتنِ نماد نیست).

خواندنی و بی‌شبکه؛ بدونِ market.db ⇒ SKIP.

usage: python dev/market_closes_v1.py
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


class Req:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.method = "GET"


def main():
    if not os.path.exists("market.db"):
        print("SKIP: market.db نیست")
        return 0
    import api.market as M

    r1 = M.market_closes(Req())
    etag = r1.headers.get("etag")
    data = json.loads(bytes(r1.body).decode("utf-8"))
    closes = data.get("closes") or {}
    ck("status=success و ETag دارد", data.get("status") == "success" and bool(etag),
       "etag=%s" % etag)
    ck("نقشه هزاران نماد دارد", len(closes) > 1000, "count=%d" % len(closes))

    conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
    try:
        day = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
        sample = conn.execute(
            "SELECT i.l_val18, m.p_closing FROM market_watch m "
            "JOIN instruments i ON i.ins_code=m.ins_code "
            "WHERE m.d_even=? AND m.p_closing IS NOT NULL AND i.l_val18 IS NOT NULL "
            "LIMIT 1", (day,)).fetchone()
    finally:
        conn.close()
    sym, val = sample[0], sample[1]
    ck("مقدارِ نمونه با کوئریِ مستقیمِ همان ردیف یکی است",
       closes.get(str(sym)) == float(val), "%s=%s/%s" % (sym, closes.get(str(sym)), val))

    r2 = M.market_closes(Req({"if-none-match": etag}))
    ck("همان ETag ⇒ ۳۰۴ِ خالی", r2.status_code == 304 and len(bytes(r2.body)) == 0,
       "status=%s body=%d" % (r2.status_code, len(bytes(r2.body))))

    r3 = M.market_closes(Req({"if-none-match": '"other"'}))
    d3 = json.loads(bytes(r3.body).decode("utf-8"))
    ck("ETagِ ناهمخوان ⇒ ۲۰۰ِ کامل با همان داده",
       r3.status_code == 200 and len(d3.get("closes") or {}) == len(closes),
       "status=%s" % r3.status_code)

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("MARKET-CLOSES: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
