"""dev/market_swr_v1036.py — تابلو هرگز پایِ بازسازیِ کش نمی‌ایستد (#176)

چرا: بدنۀ «۵۳۲۲ نماد» ۱.۴ ثانیه ساخته می‌شود. پیش از این تغییر، دقیقاً همان
درخواستی که TTLِ کش را می‌شکست باید آن ۱.۴ ثانیه را همگام منتظر می‌ماند — در
ریتمِ پنج‌ثانیه‌ایِ ساعتِ بازار یعنی یکی از هر چهار نفس دیر می‌رسد.

دو
چیز ثابت شده‌اند که یک ویرایشِ بی‌دقت می‌شکند:

  • پاسخِ کهنه بی‌درنگ داده می‌شود و بازسازی به نخِ پس‌زمینه می‌رود،
    و برایِ N درخواستِ هم‌زمانِ کهنه فقط *یک* بازسازی ساخته می‌شود.
  • «کهنه» بی‌سقف نیست: پس از سقفِ کهنگی، _market_from_cache هیچ
    پاسخی نمی‌دهد تا مسیرِ همگام بسازد و خطا را صادقانه به بالا بفرستد
    (قاعدۀ «نبودِ داده هرگز صفرِ سبز نیست»).

گارد به market.db نیاز ندارد: _build_market_response جایِ خودِ واقعی را می‌گیرد،
پس در CI هم بی‌بانک می‌دود.
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.market as M  # noqa: E402

_m_snap = M._market_snapshot
_m_store = M._market_store

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


class FakeRequest:
    def __init__(self, inm=None):
        self.headers = {} if inm is None else {"if-none-match": inm}


class Recorder:
    """جایِ _build_market_response: بشمارد، کمی طول بده، و کش را «تازه» کن."""

    def __init__(self, delay=0.08):
        self.calls = 0
        self.delay = delay
        self.entered = threading.Event()

    def __call__(self, request):
        self.calls += 1
        self.entered.set()
        time.sleep(self.delay)
        M.MARKET_CACHE["body"] = b'{"status":"success"}'
        M.MARKET_CACHE["etag"] = '"etag-new"'
        M.MARKET_CACHE["t"] = time.time()
        from fastapi.responses import Response
        return Response(content=M.MARKET_CACHE["body"], media_type="application/json")


def prime(age_seconds, etag='"etag-old"', body=b'{"cached":true}'):
    M.MARKET_CACHE.clear()
    M.MARKET_CACHE["body"] = body
    M.MARKET_CACHE["etag"] = etag
    M.MARKET_CACHE["t"] = time.time() - age_seconds


def wait_idle(timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with M._MARKET_BUILD_LOCK:
            if not M._MARKET_BUILDING:
                return True
        time.sleep(0.01)
    return False


original_build = M._build_market_response
try:
    # ۱) کشِ تازه: پاسخ از کش، بدونِ هیچ بازسازی
    M._build_market_response = (lambda req: (_ for _ in ()).throw(AssertionError("must not build")))
    prime(1.0)
    r = M._market_from_cache(FakeRequest(), time.time())
    ck("تازه ⇒ ۲۰۰ با X-Cache: HIT", r is not None and r.status_code == 200
       and r.headers.get("x-cache") == "HIT")
    ck("تازه ⇒ همانِ بدنۀ کش", r is not None and r.body == b'{"cached":true}')

    # ۲) If-None-Match هم‌خوان ⇒ صفر بایت
    r304 = M._market_from_cache(FakeRequest('"etag-old"'), time.time())
    ck("etag هم‌خوان ⇒ ۳۰۴", r304 is not None and r304.status_code == 304)
    r200 = M._market_from_cache(FakeRequest('"چیز-دیگر"'), time.time())
    ck("etag ناهم‌خوان ⇒ ۲۰۰ِ کامل", r200 is not None and r200.status_code == 200)

    # ۳) کشِ کهنه ⇒ پاسخِ کهنه + یکِ بازسازی برایِ پنجِ درخواست
    rec = Recorder()
    M._build_market_response = rec
    prime(M.MARKET_CACHE_TTL + 5)
    bodies = [M._market_from_cache(FakeRequest(), time.time()) for _ in range(5)]
    ck("کهنه ⇒ بی‌درنگ پاسخ می‌دهد (منتظرِ ساختن نمی‌نشیند)",
       all(b is not None and b.status_code == 200 for b in bodies))
    ck("کهنه ⇒ برچسبِ X-Cache: STALE", bodies[0].headers.get("x-cache") == "STALE")
    ck("کهنه ⇒ همانِ بدنۀ کهنه فوراً می‌رود (۱.۴ ثانیه نه)",
       bodies[0].body == b'{"cached":true}')
    rec.entered.wait(2.0)
    wait_idle()
    ck("پنجِ درخواستِ کهنه ⇒ دقیقاً یکِ بازسازی", rec.calls == 1)
    again = M._market_from_cache(FakeRequest(), time.time())
    ck("پس از بازسازیِ پس‌زمینه ⇒ کش تازه شده و HIT می‌شود",
       again.headers.get("x-cache") == "HIT")

    # ۴) سقفِ کهنگی: هیچ پاسخی از کش نده، تا خطا صادقانه به بالا برود
    prime(M._MARKET_STALE_CEILING + 60)
    ck("کهنۀ بیش از سقف ⇒ None (مسیرِ همگام و خطایِ واقعی)",
       M._market_from_cache(FakeRequest(), time.time()) is None)

    # ۵) کشِ خالی (نخستین درخواستِ فرایند) ⇒ None
    M.MARKET_CACHE.clear()
    ck("بی‌کش ⇒ None تا همان‌جا ساخته شود",
       M._market_from_cache(FakeRequest(), time.time()) is None)

    # ۶) warm_market_cache: موفق کش را می‌سازد، ناموفق پاکش می‌کند
    M.MARKET_CACHE.clear()
    ok_rec = Recorder(delay=0.0)
    M._build_market_response = ok_rec
    ck("warm_market_cache() موفق ⇒ کش پر می‌شود", M.warm_market_cache() is True
       and M.MARKET_CACHE.get("body") is not None)

    def boom(request):
        raise RuntimeError("دیتابیس نخواند")
    M._build_market_response = boom
    ck("warm_market_cache() ناموفق ⇒ False", M.warm_market_cache() is False)
    ck("warm_market_cache() ناموفق ⇒ کش خالی می‌ماند (کهنۀ بی‌صدا نه)",
       M.MARKET_CACHE.get("body") is None)

    # ۷) تک‌نفرگیِ واقعاً زیرِ بار: دهِ کهنه هم‌زمان ⇒ یکِ ساختن
    calls = []
    gate = threading.Event()

    def slow(request):
        calls.append(1)
        gate.wait(2.0)
        M.MARKET_CACHE["t"] = time.time()

    M._build_market_response = slow
    prime(M.MARKET_CACHE_TTL + 5)
    threads = [threading.Thread(target=lambda: M._market_from_cache(FakeRequest(), time.time()))
               for _ in range(10)]
    for t in threads:
        t.start()
    time.sleep(0.3)
    gate.set()
    for t in threads:
        t.join(3.0)
    wait_idle()
    ck("دهِ درخواستِ هم‌زمانِ کهنه ⇒ یکِ بازسازی", len(calls) == 1)

    # ۷‑ب) عکسِ کش اتمی است. بی‌این، نخِ سازنده می‌تواند بدنۀ تازه را نوشته
    # باشد و etag هنوز کهنه بماند؛ خواننده آن جفت را با هم می‌بیند و به
    # مشتریِ دارندهٔ etagِ کهنه ۳۰۴ می‌دهد، یعنی کاربر «تازه شد» را می‌شنود
    # ولی همان عددِ قدیمی را نگه می‌دارد. پنجرۀ رقابت زیرِ GIL نایاب است، پس
    # اینجا عمداً باز می‌شود (SlowDict بعدِ نوشتنِ body می‌خوابد) و اول ثابت
    # می‌کنیم که خواندنِ *بدونِ قفل* همان پنجره را می‌بیند — وگرنه این شاهد
    # خودش هم می‌توانست هیچ‌وقت قرمز نشود و بی‌ارزش باشد.
    class SlowDict(dict):
        def __setitem__(self, k, v):
            super().__setitem__(k, v)
            if k == "body":
                time.sleep(0.05)

    saved_cache = M.MARKET_CACHE
    try:
        def window_opens():
            M.MARKET_CACHE = SlowDict(body=b'old', etag='"etag-old"', t=time.time())
            done = []

            def writer():
                _m_store(b'new', '"etag-new"', time.time())
                done.append(1)

            tw = threading.Thread(target=writer)
            tw.start()
            time.sleep(0.02)                      # وسطِ نوشتنِ سه کلید
            raw = (M.MARKET_CACHE.get("body"), M.MARKET_CACHE.get("etag"))
            tw.join(2)
            return raw == (b'new', '"etag-old"') and bool(done)

        ck("پنجرۀ رقابت واقعاً وجود دارد (خواندنِ بی‌قفل بدنۀ تازه با etagِ کهنه می‌خواند)",
           window_opens())

        def locked_read_is_clean():
            M.MARKET_CACHE = SlowDict(body=b'old', etag='"etag-old"', t=time.time())
            out = []

            def writer():
                _m_store(b'new', '"etag-new"', time.time())

            tw = threading.Thread(target=writer)
            tw.start()
            time.sleep(0.02)
            out.append(_m_snap())                 # باید پشتِ قفل صبر کند
            tw.join(2)
            return out[0] == (b'new', out[0][1], '"etag-new"')

        ck("خواندنِ قفل‌شده همان جفتِ نشکسته را می‌دهد", locked_read_is_clean())
    finally:
        M.MARKET_CACHE = saved_cache

    # ۸) پیمانشِ source: سینک دیگر فقط باطل نمی‌کند، می‌سازد
    src = open(os.path.join("api", "_sync_market.py"), encoding="utf-8").read()
    ck("پایانِ سینک ⇒ warm_market_cache() نه MARKET_CACHE.clear()",
       "warm_market_cache()" in src and "MARKET_CACHE.clear()" not in src)
    ck("هنگامِ شکستِ سینک هم کش رها نمی‌شود", "warm failed" in
       open(os.path.join("api", "market.py"), encoding="utf-8").read())
    ck("مسیرِ /api/market یک‌بار و همان‌جا ثبت شده",
       open(os.path.join("api", "market.py"), encoding="utf-8").read().count('@router.get("/api/market")') == 1)
finally:
    M._build_market_response = original_build

print()
if FAILS:
    print("MARKET SWR GUARD FAILED: %d" % len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("MARKET SWR GUARD OK")
