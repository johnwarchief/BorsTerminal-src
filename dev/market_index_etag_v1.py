"""MARKET-INDEX-ETAG v1 — گاردِ ۳۰۴ِ شاخص کل (PERF-R3).

سریِ شاخص ۴٬۳۱۱ کندل / ۷۴۴KB است و هر ورودِ دوباره به صفحهٔ مقایسه یا چارت
همان بدنه را از نو می‌ساخت و می‌فرستاد (p50 ≈۲۹۸ms). حالا پاسخ ETag دارد و
درخواستِ شرطیِ کلاینت ۳۰۴ِ صفر‌بایت می‌گیرد.

پنج چیز باید ثابت بماند:
  ۱) ۲۰۰ِ اول ETag دارد و بدنهٔ کامل/معتبر می‌دهد؛
  ۲) همان ETag ⇒ ۳۰۴ِ خالی (بدونِ ساختِ بدنه)؛
  ۳) refresh ⇒ بدنه و ETag تازه (۳۰۴ِ کهنه سرو نمی‌شود)؛
  ۴) limitهایِ مختلف ETagِ مختلف دارند و ۳۰۴ِ limit=0 برایِ limit=5 معتبر نیست؛
  ۵) کشِ منقضی با If-None-Match هم ۳۰۴ نمی‌شود (دادهٔ کهنه تأیید نمی‌شود).

بی‌شبکه، بی‌market.dbِ واقعی (fetch جعل می‌شود).

usage: python dev/market_index_etag_v1.py
"""
import datetime
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.market_index as MI  # noqa: E402

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


class Req:
    def __init__(self, headers=None, method="GET"):
        self.headers = headers or {}
        self.method = method


def body_json(resp):
    import json
    return json.loads(bytes(resp.body).decode("utf-8"))


def main():
    day0 = datetime.date(2026, 1, 1)
    raw = [{"dEven": int((day0 + datetime.timedelta(days=i)).strftime("%Y%m%d")),
            "xNivInuClMresIbs": 1600 + i, "xNivInuPhMresIbs": 1610 + i,
            "xNivInuPbMresIbs": 1590 + i}
           for i in range(60)]

    def fake_fetch(ins_code=None, **kw):
        return list(raw)

    MI.fetch_tedpix_series = fake_fetch
    MI.INDEX_CACHE.clear()
    MI.INDEX_ETAG.clear()

    r1 = MI.get_index_tedpix(Req(), limit=0, refresh=True)
    e1 = r1.headers.get("etag")
    j1 = body_json(r1)
    ck("۲۰۰ِ اول ETag دارد و بدنهٔ کامل می‌دهد",
       bool(e1) and j1.get("count") == 60 and len(j1.get("candles") or []) == 60,
       "etag=%s count=%s" % (e1, j1.get("count")))

    # بدنهٔ HTTP و خروجیِ سازندهٔ اصلی باید یکی باشند (فقط فیلدهایِ نوسانیِ کش).
    native = MI.build_tedpix_payload(limit=0)
    strip = lambda d: {k: v for k, v in d.items() if k not in ("cached", "cache_age_sec")}
    ck("بدنهٔ HTTP با خروجیِ سازندهٔ اصلی یکی است (هیچ داده‌ای عوض نشد)",
       strip(native) == strip(j1), "%d/%d candles" %
       (len((native.get("candles") or [])), len(j1.get("candles") or [])))

    r2 = MI.get_index_tedpix(Req({"if-none-match": e1}), limit=0, refresh=False)
    ck("همان ETag ⇒ ۳۰۴ِ خالی", r2.status_code == 304 and len(bytes(r2.body)) == 0,
       "status=%s body=%d" % (r2.status_code, len(bytes(r2.body))))

    r3 = MI.get_index_tedpix(Req({"if-none-match": '"bogus"'}), limit=0, refresh=False)
    ck("ETagِ ناهمخوان ⇒ ۲۰۰ با همان ETag", r3.status_code == 200
       and r3.headers.get("etag") == e1, r3.headers.get("etag"))

    r4 = MI.get_index_tedpix(Req(), limit=5, refresh=False)
    e4 = r4.headers.get("etag")
    j4 = body_json(r4)
    ck("limit=5 بدنهٔ برش‌خورده و ETagِ متفاوت دارد",
       len(j4.get("candles") or []) == 5 and e4 != e1, "etag=%s" % e4)
    ck("ETagِ limit=0 برایِ limit=5 معتبر نیست",
       MI._inm_matches(e1, e4) is False and
       MI.get_index_tedpix(Req({"if-none-match": e1}), limit=5).status_code == 200)

    raw.append({"dEven": 20260401, "xNivInuClMresIbs": 1700,
                "xNivInuPhMresIbs": 1710, "xNivInuPbMresIbs": 1690})
    r5 = MI.get_index_tedpix(Req({"if-none-match": e1}), limit=0, refresh=True)
    j5 = body_json(r5)
    ck("refresh ⇒ بدنه و ETag تازه (نه ۳۰۴)",
       r5.status_code == 200 and j5.get("count") == 61
       and r5.headers.get("etag") != e1, "etag=%s" % r5.headers.get("etag"))

    # کشِ منقضی: همان ETag نباید ۳۰۴ بدهد؛ باید تازه بسازد.
    ts, payload = MI.INDEX_CACHE[MI.TEDPIX_INS_CODE]
    MI.INDEX_CACHE[MI.TEDPIX_INS_CODE] = (time.time() - MI.INDEX_CACHE_TTL - 5, payload)
    e5 = r5.headers.get("etag")
    r6 = MI.get_index_tedpix(Req({"if-none-match": e5}), limit=0, refresh=False)
    ck("کشِ منقضی با If-None-Match هم ۳۰۴ نمی‌شود", r6.status_code == 200,
       "status=%s" % r6.status_code)

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("MARKET-INDEX-ETAG: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
