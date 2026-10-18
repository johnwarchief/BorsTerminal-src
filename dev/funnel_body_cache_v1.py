# dev/funnel_body_cache_v1.py — گاردِ بدنهٔ کش‌شدهٔ قیف (مأموریتِ عملکردِ نشستِ بازار)
#
# چرا یکِ گاردِ جدا: تغییرِ این مسیر فقط «سریع‌تر» نیست — دارد بایت‌هایی را که
# خودِ فریم‌ورک می‌ساخت دوباره استفاده می‌کند. پس این‌ها باید قفل شود:
#   ۱) بدنهٔ کش‌شده همان بدنهٔ تازه است، به‌علاوهٔ همان `cached_for_ms`ی که
#      `_run` رویِ هر پاسخِ ازِ‌کش می‌گذاشت (قراردادِ پیش از کشِ بدنه);
#   ۲) شرطی‌ها طبقِ RFC 9110 §13.1.2: `If-None-Match`ِ هم‌خوان رویِ GET ⇒ ۳۰۴ِ
#      بی‌بدنه، رویِ POST ⇒ ۴۱۲ِ بی‌بدنه (نه ۳۰۴)، و etagِ نادرست ⇒ ۲۰۰ِ کامل;
#   ۳) سنِ دادهٔ بدنه ازِ زمانِ *ساختِ* payload شمرده می‌شود، نه زمانِ سریال —
#      وگرنه payloadی که فراخوانِ دیگری (ردپا/غربالگری) ساخته تا ~۲×TTL می‌ماند;
#   ۴) درخواست‌هایِ هم‌زمانِ یک کلید فقط یک بار موتور را می‌دوانند؛
#   ۵) دو کلیدِ متفاوت هرگز یکِ بدنه را نمی‌گیرند، و پاسخِ خطا کش نمی‌شود.
#
# گارد به یکِ سرورِ زنده نیاز دارد (پیش‌فرض: ریگِ کنترلیِ ۸۰۲۰). بی‌سرور
# خودش را SKIPPED اعلام می‌کند و صفر برمی‌گرداند — درِ `run_all_tests.py` که
# سرورهایِ dev بسته‌اند، این همان مسیرِ درست است.
#
# اجرا:  python dev/funnel_body_cache_v1.py --port 8020
import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8020)
ap.add_argument("--host", default="127.0.0.1")
ARGS = ap.parse_args()
BASE = "http://%s:%d" % (ARGS.host, ARGS.port)
TTL_S = 8.0

green = red = 0


def ck(name, ok, evidence="", show=False):
    """`show=True` برایِ بندِ زمان‌سنج: عددِ سبز را هم چاپ می‌کند.

    چرا: «۲۰» یک بار قرمز و بارِ بعد سبز شد و لاگِ سبز هیچ عددی نداشت؛ بدونِ
    اندازه درِ سبزها، علّتِ قرمزِ بعدی قابلِ داوری نیست. آستانه را عوض نمی‌کند.
    """
    global green, red
    if ok:
        green += 1
        print("ok   %s%s" % (name, "  [%s]" % str(evidence)[:260] if show else ""))
    else:
        red += 1
        print("FAIL %s  ← %s" % (name, str(evidence)[:260]))


def _lower(h):
    """نامِ سرِ HTTP موردی‌ناحساس است؛ dict() آن را حساس می‌کند."""
    return {k.lower(): v for k, v in dict(h).items()}


def call(path, body=None, headers=None, method=None):
    h = {"Content-Type": "application/json"} if body is not None else {}
    h.update(headers or {})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=h,
                                 method=method or ("POST" if body is not None else "GET"))
    t0 = time.perf_counter()
    try:
        r = urllib.request.urlopen(req, timeout=180)
        out = r.status, _lower(r.headers), r.read()
    except urllib.error.HTTPError as e:
        out = e.code, _lower(e.headers or {}), (e.read() or b"")
    except Exception as e:
        out = None, {}, str(e).encode()
    return out + ((time.perf_counter() - t0) * 1000.0,)


def post(body, headers=None):
    return call("/api/funnel", body, headers)[:3]


AGE = re.compile(rb',"cached_for_ms":(\d+)\}$')


def split_age(b):
    """(بدنهٔ بی‌`cached_for_ms`، سنِ ms یا None)."""
    m = AGE.search(b)
    return (b[:m.start()] + b"}", int(m.group(1))) if m else (b, None)


def until(t):
    d = t - time.time()
    if d > 0:
        time.sleep(d)


def burst(n, fn):
    out = [None] * n
    go = threading.Event()

    def one(i):
        go.wait()
        out[i] = fn()
    ts = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    go.set()
    return ts, out


def main():
    try:
        urllib.request.urlopen(BASE + "/api/watchlist", timeout=6).read()
    except Exception as e:
        print("SKIPPED — سروری رویِ %s پاسخ نمی‌دهد (%s); این گارد به بک‌اندِ زنده نیاز دارد"
              % (BASE, type(e).__name__))
        return 0

    time.sleep(TTL_S + 0.5)     # هر ورودیِ مانده ازِ اجرایِ قبلی باید منقضی شده باشد

    # ۱) دو درخواستِ پیاپیِ همان کلید
    c1, h1, b1 = post({"preset": "trend"})
    t_warm = time.perf_counter()
    c2, h2, b2 = post({"preset": "trend"})
    warm_ms = (time.perf_counter() - t_warm) * 1000.0
    base2, age2 = split_age(b2)
    ck("۱ هر دو درخواست ۲۰۰ و بدنهٔ غیرخالی‌اند",
       c1 == 200 and c2 == 200 and len(b1) > 100000,
       {"http": (c1, c2), "bytes": (len(b1), len(b2))})
    ck("۲ پاسخِ سازنده `cached_for_ms` ندارد؛ پاسخِ ازِ‌کش دارد و ۰ ≤ سن < TTL",
       split_age(b1)[1] is None and age2 is not None and 0 <= age2 < TTL_S * 1000,
       {"first_age": split_age(b1)[1], "second_age": age2})
    ck("۳ بدنهٔ ازِ‌کش، بی‌`cached_for_ms`، بایت‌به‌بایت همان بدنهٔ تازه است", base2 == b1,
       {"first_bytes_differ_at": next((i for i in range(min(len(b1), len(base2)))
                                      if b1[i] != base2[i]), None)})
    ck("۴ سرِ کش از MISS به HIT رفت (همان کلید، بی‌بازسازی)",
       h1.get("x-cache") == "MISS" and h2.get("x-cache") == "HIT",
       {"X-Cache": (h1.get("x-cache"), h2.get("x-cache"))})
    ck("۵ درخواستِ گرم واقعاً ارزان‌تر است (<۳۰۰ms)", warm_ms < 300, "%.1f ms" % warm_ms)
    etag = h1.get("etag") or ""
    ck("۶ etag ضعیف است (بایت‌هایِ دو پاسخ فقط درِ `cached_for_ms` فرق دارند) و ثابت می‌ماند",
       etag.startswith('W/"') and h2.get("etag") == etag, (etag, h2.get("etag")))

    # ۷-۹) شرطی‌ها، RFC 9110 §13.1.2
    cg, hg, bg, _ = call("/api/funnel?preset=trend", headers={"If-None-Match": etag})
    ck("۷ GET با etagِ درست ⇒ ۳۰۴ِ بی‌بدنه", cg == 304 and len(bg) == 0 and hg.get("etag") == etag,
       {"http": cg, "bytes": len(bg), "etag": hg.get("etag")})
    cp, hp, bp = post({"preset": "trend"}, {"If-None-Match": etag})
    ck("۸ POST با etagِ درست ⇒ ۴۱۲ِ بی‌بدنه، نه ۳۰۴", cp == 412 and len(bp) == 0,
       {"http": cp, "bytes": len(bp), "xc": hp.get("x-cache")})
    c4, h4, b4 = post({"preset": "trend"}, {"If-None-Match": '"deadbeefdeadbeef"'})
    ck("۹ etagِ نادرست ⇒ ۲۰۰ِ کامل (کش کهنه را تازه اعلام نمی‌کند)",
       c4 == 200 and split_age(b4)[0] == b1, {"http": c4, "bytes": len(b4)})

    # ۱۰) جداسازیِ کلید: presetِ دیگر نباید این بدنه را بگیرد
    c5, h5, b5 = post({"preset": "custom", "chain": ["trend"]})
    ck("۱۰ کلیدِ متفاوت بدنهٔ خودش را دارد (etag مشترک نیست)",
       c5 == 200 and h5.get("etag") != etag,
       {"http": c5, "etag_same_as_trend": h5.get("etag") == etag})

    # ۱۱-۱۲) محتوای داوری حفظ شده
    try:
        d1, d2 = json.loads(b1.decode("utf-8")), json.loads(b2.decode("utf-8"))
    except Exception as e:
        d1 = d2 = {}
        ck("۱۱ بدنهٔ JSONِ معتبر", False, str(e))
    if d1:
        ck("۱۱ `status_matrix` و `universe` درِ هر دو پاسخ یکی است",
           d1.get("status_matrix") == d2.get("status_matrix")
           and d1.get("universe") == d2.get("universe")
           and len(d1.get("status_matrix") or {}) > 1000,
           {"matrix": (len(d1.get("status_matrix") or {}), len(d2.get("status_matrix") or {}))})
        ck("۱۲ `timeline` درِ پاسخِ فهرست نمی‌آید (همان `_strip`ِ پیشین)",
           "timeline" not in d1, sorted(d1)[:12])

    # ۱۳-۱۴) پاسخِ خطا کش نمی‌شود
    c6, h6, b6 = post({"preset": "no-such-preset"})
    e6 = json.loads(b6.decode("utf-8")) if b6[:1] == b"{" else {}
    ck("۱۳ presetِ ناشناخته همان خطایِ پیشین را می‌دهد و بدنهٔ کش نمی‌شود",
       e6.get("status") == "error" and h6.get("x-cache") is None,
       {"status": e6.get("status"), "xc": h6.get("x-cache")})
    c7, h7, b7 = post({"preset": "trend"})
    ck("۱۴ پس ازِ خطا، همان کلیدِ درست بدنهٔ درست را می‌گیرد",
       c7 == 200 and split_age(b7)[0] == b1, {"http": c7, "bytes": len(b7)})

    # ۱۵-۱۷) سنِ بدنه ازِ ساختِ payload: ردپا (`_run(full=True)`) کلیدِ trend را
    # می‌سازد؛ بدنهٔ POSTِ بعدی ازِ همان payload است و نباید ازِ ساخت+TTL بگذرد.
    time.sleep(TTL_S + 0.5)
    t0 = time.time()
    ct, _ht, _bt, trace_ms = call("/api/funnel/trace?preset=trend&symbol=__none__")
    until(t0 + 5.0)
    ca, ha, ba = post({"preset": "trend"})
    _, age_a = split_age(ba)
    ck("۱۵ بدنهٔ ساخته‌شده ازِ payloadِ ردپا سنِ واقعیِ آن را می‌گوید (۳۰۰۰ تا ۸۰۰۰ms)",
       ct == 200 and ca == 200 and age_a is not None and 3000 <= age_a < TTL_S * 1000,
       {"trace": (ct, round(trace_ms)), "post": ca, "xc": ha.get("x-cache"), "age": age_a})
    until(t0 + TTL_S + 1.0)
    cb, hb, bb = post({"preset": "trend"})
    ck("۱۶ پس ازِ ساخت+TTL همان بدنه دیگر سرو نمی‌شود (MISS، نه HIT)",
       cb == 200 and hb.get("x-cache") == "MISS",
       {"http": cb, "xc": hb.get("x-cache"), "age": split_age(bb)[1],
        "s_since_trace_start": round(time.time() - t0, 2)})
    ck("۱۷ پاسخِ ساخته‌شده درِ همین درخواست `cached_for_ms` ندارد",
       split_age(bb)[1] is None, split_age(bb)[1])

    # ۱۸-۲۰) هم‌زمانی: شش درخواستِ هم‌زمانِ یک کلیدِ سرد ⇒ یک ساخت
    for label, fn in (("POST", lambda: call("/api/funnel", {"preset": "trend"})),
                      ("GET", lambda: call("/api/funnel?preset=trend"))):
        time.sleep(TTL_S + 0.5)
        ts, out = burst(6, fn)
        time.sleep(0.25)
        cv, _hv, _bv, cheap_ms = call("/api/update/version")
        for t in ts:
            t.join()
        xcs = [o[1].get("x-cache") for o in out]
        build_ms = max(o[3] for o in out)
        ck("۱۸ %s ×۶ هم‌زمان ⇒ دقیقاً یک MISS" % label,
           all(o[0] == 200 for o in out) and xcs.count("MISS") == 1,
           {"x_cache": xcs, "ms": [round(o[3]) for o in out]}, show=True)
        ck("۱۹ %s ×۶: همهٔ بدنه‌ها، بی‌`cached_for_ms`، یکی‌اند" % label,
           len({split_age(o[2])[0] for o in out}) == 1, len({split_age(o[2])[0] for o in out}))
        ck("۲۰ %s: درخواستِ ارزانِ هم‌زمان پشتِ ساختِ قیف نمی‌ماند (< نصفِ زمانِ ساخت)" % label,
           cv == 200 and cheap_ms < build_ms / 2,
           {"cheap_ms": round(cheap_ms), "build_ms": round(build_ms),
            "ratio": round(cheap_ms / max(build_ms, 1e-9), 3)}, show=True)

    # ۲۱) HEAD: این مسیر HEAD را نمی‌پذیرد (۴۰۵)، پس شاخۀ («GET», «HEAD») درِ `api/funnel.py`
    # امروز غیرقابل‌دسترس است. سنجه قراردادِ *واقعی* را قفل می‌کند: HEAD بی‌بدنه می‌ماند و
    # POSTِ شرطی هرگز ۳۰۴ نمی‌گیرد. اگر روزی HEAD فعال شود، همین بند رنگش عوض می‌شود و
    # تصمیمِ صریح می‌خواهد (بندِ ۸ همان ممنوعیت را رویِ POST می‌پاید).
    hv, hh, hb, _hms = call("/api/funnel?preset=trend")
    et = _lower(hh).get("etag")
    c2, _h2, b2, _ = call("/api/funnel?preset=trend", headers={"If-None-Match": et}, method="HEAD")
    c3, h3, b3, _ = call("/api/funnel", {"preset": "trend"}, headers={"If-None-Match": et})
    ck("۲۱ HEAD بی‌بدنه می‌ماند (امروز 405) و POSTِ شرطی 304 نمی‌گیرد",
       hv == 200 and not b2 and c3 != 304,
       {"get": hv, "head": c2, "head_bytes": len(b2), "post_cond": c3,
        "post_xc": _lower(h3).get("x-cache")}, show=True)

    print("\nنتیجه: %d سبز، %d قرمز" % (green, red))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
