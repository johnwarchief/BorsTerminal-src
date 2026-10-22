"""MARKET-ROW v1 — گاردِ ردیفِ تک‌نمادیِ سایدبار (P2-R1).

سایدبار پیش‌تر برایِ یک ردیف، فیدِ کاملِ ۶٫۸MB را می‌کشید. `/api/market/row`
همان ردیفِ آینهٔ تابلو را می‌دهد. این گارد ثابت می‌کند:
  ۱) ردیف با نمادِ درخواستی برمی‌گردد و `p_closing` با کوئریِ مستقیمِ همان
     ردیفِ `market_watch` یکی است؛
  ۲) ETag دارد و درخواستِ شرطی ۳۰۴ِ خالی می‌دهد؛
  ۳) نمادِ ناشناخته `row=None` می‌دهد (نه ردیفِ نمادِ دیگر).

خواندنی؛ بدونِ market.db ⇒ SKIP.

usage: python dev/market_row_endpoint_v1.py
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
    sym, close = sample[0], sample[1]

    r1 = M.market_row(Req(), symbol=sym)
    body = json.loads(bytes(r1.body).decode("utf-8"))
    row = body.get("row") or {}
    etag = r1.headers.get("etag")
    ck("ردیف با همان نماد و p_closing برمی‌گردد",
       row.get("symbol") == sym and float(row.get("p_closing")) == float(close),
       "%s / %s" % (row.get("symbol"), row.get("p_closing")))
    ck("ETag دارد", bool(etag), "etag=%s" % etag)

    r2 = M.market_row(Req({"if-none-match": etag}), symbol=sym)
    ck("همان ETag ⇒ ۳۰۴ِ خالی", r2.status_code == 304 and len(bytes(r2.body)) == 0,
       "status=%s" % r2.status_code)

    r3 = M.market_row(Req(), symbol="__نمادِ‌ناموجود__")
    b3 = json.loads(bytes(r3.body).decode("utf-8"))
    ck("نمادِ ناشناخته ⇒ row=None، نه ردیفِ دیگر", b3.get("row") is None, str(b3)[:100])

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("MARKET-ROW: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
