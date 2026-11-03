# dev/funnel_body_cache_v1.py — گاردِ بدنهٔ کش‌شدهٔ قیف (مأموریتِ عملکردِ نشستِ بازار)
#
# چرا یکِ گاردِ جدا: تغییرِ این مسیر فقط «سریع‌تر» نیست — دارد بایت‌هایی را که
# خودِ فریم‌ورک می‌ساخت دوباره استفاده می‌کند. پس سه چیز باید قفل شود:
#   ۱) بدنهٔ کش‌شده با بدنهٔ تازه **بایت‌به‌بایت** یکی است (نه «تقریباً»);
#   ۲) `If-None-Match`ِ درست ⇒ ۳۰۴ با صفر بایت، و etagِ اشتباه ⇒ ۲۰۰ِ کامل
#      (وگرنه کش می‌تواند دادهٔ کهنه را «تازه» جا بزند);
#   ۳) دو کلیدِ متفاوت هرگز یکِ بدنه را نمی‌گیرند، و پاسخِ خطا کش نمی‌شود.
#
# گارد به یکِ سرورِ زنده نیاز دارد (پیش‌فرض: ریگِ کنترلیِ ۸۰۲۰). بی‌سرور
# خودش را SKIPPED اعلام می‌کند و صفر برمی‌گرداند — درِ `run_all_tests.py` که
# سرورهایِ dev بسته‌اند، این همان مسیرِ درست است.
#
# اجرا:  python dev/funnel_body_cache_v1.py --port 8020
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8020)
ap.add_argument("--host", default="127.0.0.1")
ARGS = ap.parse_args()
BASE = "http://%s:%d" % (ARGS.host, ARGS.port)

green = red = 0


def ck(name, ok, evidence=""):
    global green, red
    if ok:
        green += 1
        print("ok   %s" % name)
    else:
        red += 1
        print("FAIL %s  ← %s" % (name, str(evidence)[:220]))


def _lower(h):
    """نامِ سرِ HTTP موردی‌ناحساس است؛ dict() آن را حساس می‌کند."""
    return {k.lower(): v for k, v in dict(h).items()}


def post(body, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(BASE + "/api/funnel", data=json.dumps(body).encode("utf-8"),
                                 headers=h, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=180)
        return r.status, _lower(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, _lower(e.headers or {}), (e.read() or b"")
    except Exception as e:
        return None, {}, str(e).encode()


def main():
    try:
        urllib.request.urlopen(BASE + "/api/watchlist", timeout=6).read()
    except Exception as e:
        print("SKIPPED — سروری رویِ %s پاسخ نمی‌دهد (%s); این گارد به بک‌اندِ زنده نیاز دارد"
              % (BASE, type(e).__name__))
        return 0

    # ۱) دو درخواستِ پیاپیِ همان کلید: بدنه باید عیناً یکی باشد
    c1, h1, b1 = post({"preset": "trend"})
    t_warm = time.perf_counter()
    c2, h2, b2 = post({"preset": "trend"})
    warm_ms = (time.perf_counter() - t_warm) * 1000.0
    ck("۱ هر دو درخواست ۲۰۰ و بدنهٔ غیرخالی‌اند",
       c1 == 200 and c2 == 200 and len(b1) > 100000 and len(b2) == len(b1),
       {"http": (c1, c2), "bytes": (len(b1), len(b2))})
    ck("۲ بدنهٔ کش‌شده با بدنهٔ تازه بایت‌به‌بایت یکی است", b1 == b2,
       {"first_bytes_differ_at": next((i for i in range(min(len(b1), len(b2)))
                                      if b1[i] != b2[i]), None)})
    ck("۳ سرِ کش از MISS به HIT رفت (همان کلید، بی‌بازسازی)",
       h1.get("x-cache") == "MISS" and h2.get("x-cache") == "HIT",
       {"X-Cache": (h1.get("x-cache"), h2.get("x-cache"))})
    ck("۴ درخواستِ گرم واقعاً ارزان‌تر است (<۳۰۰ms)", warm_ms < 300, "%.1f ms" % warm_ms)

    # ۵) ۳۰۴ تنها با etagِ درست
    etag = h1.get("etag")
    c3, h3, b3 = post({"preset": "trend"}, {"If-None-Match": etag or ""})
    ck("۵ etagِ درست ⇒ ۳۰۴ با صفر بایت", c3 == 304 and len(b3) == 0,
       {"http": c3, "bytes": len(b3), "xc": h3.get("x-cache")})
    c4, h4, b4 = post({"preset": "trend"}, {"If-None-Match": '"deadbeefdeadbeef"'})
    ck("۶ etagِ نادرست ⇒ ۲۰۰ِ کامل، نه ۳۰۴ (کش کهنه را تازه اعلام نمی‌کند)",
       c4 == 200 and b4 == b1, {"http": c4, "bytes": len(b4)})

    # ۷) جداسازیِ کلید: presetِ دیگر نباید این بدنه را بگیرد
    c5, h5, b5 = post({"preset": "custom", "chain": ["trend"]})
    ck("۷ کلیدِ متفاوت بدنهٔ خودش را دارد (etag مشترک نیست)",
       c5 == 200 and h5.get("etag") != etag,
       {"http": c5, "etag_same_as_trend": h5.get("etag") == etag})

    # ۸) محتوای داوری حفظ شده: شمارش‌ها و هندسهٔ پاسخِ سرد == گرم
    try:
        d1, d2 = json.loads(b1.decode("utf-8")), json.loads(b2.decode("utf-8"))
    except Exception as e:
        d1 = d2 = {}
        ck("۸ بدنهٔ JSONِ معتبر", False, str(e))
    if d1:
        ck("۸ `status_matrix` و `universe` درِ هر دو پاسخ یکی است",
           d1.get("status_matrix") == d2.get("status_matrix")
           and d1.get("universe") == d2.get("universe")
           and len(d1.get("status_matrix") or {}) > 1000,
           {"matrix": (len(d1.get("status_matrix") or {}), len(d2.get("status_matrix") or {}))})
        ck("۹ `timeline` درِ پاسخِ فهرست نمی‌آید (همان `_strip`ِ پیشین)",
           "timeline" not in d1, sorted(d1)[:12])

    # ۱۰) پاسخِ خطا کش نمی‌شود: کلیدِ خراب، سپس همان کلیدِ درست
    c6, h6, b6 = post({"preset": "no-such-preset"})
    e6 = json.loads(b6.decode("utf-8")) if b6[:1] == b"{" else {}
    ck("۱۰ presetِ ناشناخته همان خطایِ پیشین را می‌دهد و بدنهٔ کش نمی‌شود",
       e6.get("status") == "error" and h6.get("x-cache") is None,
       {"status": e6.get("status"), "xc": h6.get("x-cache")})
    c7, h7, b7 = post({"preset": "trend"})
    ck("۱۱ پس ازِ خطا، همان کلیدِ درست بدنهٔ درست را می‌گیرد",
       c7 == 200 and b7 == b1, {"http": c7, "bytes": len(b7)})

    print("\nنتیجه: %d سبز، %d قرمز" % (green, red))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
