"""Overall market index (TEDPIX / شاخص کل بورس) daily OHLC series.

Split out of app.py in the same style as the other api/* modules. Provides the
"whole-market" chart for the technical tab when no symbol is selected.

Source of truth (verified live 2026-09-14):
  https://cdn.tsetmc.com/api/Index/GetIndexB2History/{ins_code}
  -> {"indexB2":[{"insCode":.., "dEven":YYYYMMDD,
                  "xNivInuClMresIbs": <شاخص کل پایانی>,
                  "xNivInuPbMresIbs": <کمترین>,
                  "xNivInuPhMresIbs": <بیشترین>}, ...]}

There is NO mock path here: if TSETMC is unreachable or returns nothing, the
endpoint answers with an honest error (HTTP 502) plus the reason.
"""
from fastapi import APIRouter
from fastapi import Query
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from bors_flags import ORJSONResponse
import datetime
import hashlib
import candle_contract
import price_basis
import time


router = APIRouter()

# ins_code شاخص کل بورس تهران (TEDPIX) در TSETMC.
# تایید شده از صفحه رسمی شاخص و از خود API:
#   https://tsetmc.com/instInfo/32097828799138957
#   https://cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957
TEDPIX_INS_CODE = "32097828799138957"
TEDPIX_SYMBOL = "شاخص کل"
INDEX_CDN_TMPL = "https://cdn.tsetmc.com/api/Index/GetIndexB2History/{code}"
INDEX_SOURCE = "tsetmc:cdn/Index/GetIndexB2History"

# cache کوتاه‌مدت درون‌پروسه‌ای (سبک CHART_CACHE در api/chart.py) تا فشار به CDN کم شود.
INDEX_CACHE = {}          # {ins_code: (fetched_ts, payload)}
INDEX_CACHE_TTL = 600.0   # 10 دقیقه
INDEX_HTTP_TIMEOUT = 25
# ETag پایدارِ بدنهٔ کش‌شده (بدونِ فیلدهایِ نوسانی). کلید: ins_code.
# چرا: سریِ شاخص ۴٬۳۱۱ کندل / ۷۴۴KB است و هر ورودِ دوباره به صفحهٔ مقایسه یا
# چارت، همان بدنه را از نو می‌ساخت و می‌فرستاد (سنجش: p50 ≈۲۹۸ms). با ETag،
# درخواستِ شرطیِ همان کلاینت ۳۰۴ِ صفر‌بایت می‌گیرد و بدنه/تبدیل دیگر ساخته
# نمی‌شود؛ خودِ داده، TTL و شکلِ پاسخ دست‌نخورده است.
INDEX_ETAG = {}           # {ins_code: base_hash}
_ETAG_VOLATILE = ("cached", "cache_age_sec")


def _safe_float(v):
    """None/''/NaN/Inf -> 0.0 (TSETMC برای روزهای قدیمی مقادیر صفر یا خالی می‌دهد)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f or f in (float("inf"), float("-inf")):
        return 0.0
    return f


def _d_even_to_iso(d_even):
    """TSETMC dEven (int YYYYMMDD) -> 'YYYY-MM-DD' (میلادی، همان تقویمی که بقیه/سری‌ها دارند)."""
    try:
        s = str(int(d_even))
    except (TypeError, ValueError):
        return None
    if len(s) != 8:
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def fetch_tedpix_series(ins_code=TEDPIX_INS_CODE, timeout=INDEX_HTTP_TIMEOUT):
    """دریافت خام سری روزانه شاخص کل (لیست indexB2) از CDN TSETMC.

    در صورت خطا RuntimeError با علت دقیق (شبکه / کد وضعیت HTTP / پاسخ خالی)
    پرتاب می‌کند و هرگز داده ساختگی برنمی‌گرداند.
    """
    import requests as _rq
    hdr = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://tsetmc.com/",
        "Origin": "https://tsetmc.com",
    }
    url = INDEX_CDN_TMPL.format(code=ins_code)
    try:
        r = _rq.get(url, headers=hdr, timeout=timeout)
    except Exception as e:                      # network / DNS / timeout
        raise RuntimeError(f"TSETMC unreachable: {type(e).__name__}: {e}")
    if r.status_code != 200:
        raise RuntimeError(f"TSETMC HTTP {r.status_code}")
    try:
        data = r.json().get("indexB2")
    except Exception as e:
        raise RuntimeError(f"TSETMC bad JSON: {type(e).__name__}")
    if not data:
        raise RuntimeError("TSETMC payload empty (indexB2 missing/empty)")
    return data


def build_tedpix_payload(ins_code=TEDPIX_INS_CODE, limit=0, force=False):
    """ساخت payload سری روزانه OHLC شاخص کل.

    نگاشت کندل‌ها (برچسب‌ها از همان جدول TSETMC استخراج شده):
      xNivInuClMresIbs -> close  (شاخص کل پایانی)
      xNivInuPhMresIbs -> high   (بیشترین)
      xNivInuPbMresIbs -> low    (کمترین)
      open             -> close روز معاملاتی قبل، clamp‌شده داخل [low, high] روز
                          (شاخص «تیک بازگشایی» واقعی ندارد؛ این مبنا در فیلد
                          open_basis صریح گزارش می‌شود)
    شاخص حجم معاملاتی ندارد، پس volumes خالی و has_volume=False است.

    خروجی dict آمادهٔ JSON با status='success'. در صورت شکست RuntimeError
    پرتاب می‌شود تا مسیر (route) وضعیت HTTP صادقانه برگرداند.
    """
    now = time.time()
    hit = INDEX_CACHE.get(ins_code)
    if not force and hit and (now - hit[0]) < INDEX_CACHE_TTL:
        cached = dict(hit[1])
        cached["cached"] = True
        cached["cache_age_sec"] = round(now - hit[0], 1)
        # مسیرِ hit هم باید از ریزالویِ واحدِ مبن بگذرد، وگرنه پاسخِ کش‌شده متادیتایِ
        # `priceBasis*` ندارد و کندلش حل‌نشده است، برخلافِ پاسخِ تازه (§۱-ث شرطِ ۵:
        # هر سری‌دهنده‌ای درِ پایانِ کار از همین یکِ نقطه می‌گذرد). ترتیبِ برش/مبن
        # مثلِ مسیرِ تازه است تا `count` درِ هر دو حالت معنایِ یکی داشته باشد.
        if limit and limit > 0:
            cached["candles"] = cached["candles"][-limit:]
            cached["count"] = len(cached["candles"])
        return price_basis.resolve_payload(cached)

    raw = fetch_tedpix_series(ins_code)

    rows = []
    for x in raw:
        iso = _d_even_to_iso(x.get("dEven") or 0)
        if not iso:
            continue
        close = _safe_float(x.get("xNivInuClMresIbs"))
        if close <= 0:
            continue
        rows.append({
            "time": iso,
            "close": close,
            "high": _safe_float(x.get("xNivInuPhMresIbs")),
            "low": _safe_float(x.get("xNivInuPbMresIbs")),
        })
    if not rows:
        raise RuntimeError("TSETMC returned rows but none usable (all close<=0)")

    rows.sort(key=lambda r: r["time"])

    candles = []
    prev_close = None
    for r in rows:
        c = r["close"]
        # high/low در ردیف‌های قدیمی صفر می‌آید -> به close برمی‌گردد (H=L=C).
        h = r["high"] if r["high"] > 0 else c
        l = r["low"] if r["low"] > 0 else c
        # close باید داخل بازهٔ گزارش‌شدهٔ روز باشد (اگر TSETMC min/max کج داد، اصلاح می‌شود).
        if h < c:
            h = c
        if l > c:
            l = c
        # شاخص «تیک بازگشایی» واقعی ندارد؛ open = close روز قبل است. Step 4: اینجا
        # `clamp` نبود که قیمتِ منتخب را جابه‌جا کند — همان `widen` مشترک، سایه را
        # باز می‌کند تا کندل ممکن بماند و openِ شاخص دست‌کم‌تر/بیشتر از روز نشود.
        o = prev_close if (prev_close and prev_close > 0) else c
        h, l = candle_contract.widen(o, h, l, c)
        candles.append({
            "time": r["time"],
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            # کارِ #73 قدمِ ۳: برایِ شاخص کل «آخرینِ معامله» معنا ندارد (endpointِ
            # Index/GetIndexB2History آن را نمی‌دهد). پیش از این `last := close` نوشته
            # می‌شد؛ حالا None است و price_basis صریح می‌گوید این سری last ندارد، پس
            # مبنایِ اعمال‌شده closing است با دلیلِ ثبت‌شده — نه یک عددِ جعلی.
            "last": None,
        })
        prev_close = c

    # بودجه/limit هیچ‌وقت پیش ازِ نوشتنِ کش اعمال نمی‌شود: نسخهٔ اول اینجا
    # سری را برش می‌زد و **همان برش‌خورده** را درِ INDEX_CACHE می‌گذاشت، پس هر
    # درخواستِ بعدیِ limit=0 تا TTL سریِ ناقص می‌گرفت (امروز هر دو فراخوان
    # limit=0 می‌فرستند، ولی endpoint بر اساسِ پارامترِ limit باز است).
    payload = {
        "status": "success",
        "symbol": TEDPIX_SYMBOL,
        "ins_code": str(ins_code),
        "source": INDEX_SOURCE,
        "unit": "index_point",
        "has_volume": False,
        "open_basis": "prev_close_clamped_to_range",
        "candles": candles,
        "volumes": [],
        "count": len(candles),
        "first_date": candles[0]["time"] if candles else None,
        "last_date": candles[-1]["time"] if candles else None,
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "cache_ttl_sec": INDEX_CACHE_TTL,
        "cached": False,
    }
    INDEX_CACHE[ins_code] = (now, {k: v for k, v in payload.items()
                                   if k not in ("cached", "cache_age_sec")})
    # مبنایِ قیمت از ریزالویِ واحد می‌گذرد؛ برایِ شاخص نتیجه همیشه closing است و
    # دلیلش (`last_missing:N/N`) درِ همان پاسخ ثبت می‌شود.
    resp = dict(payload)
    if limit and limit > 0:
        resp["candles"] = resp["candles"][-limit:]
        resp["count"] = len(resp["candles"])
    return price_basis.resolve_payload(resp)


def _body_bytes(payload) -> bytes:
    """همان کلاسِ پاسخی که مسیر برمی‌گرداند — تا ETag رویِ همان بایت‌ها باشد."""
    if ORJSONResponse is not None:
        return ORJSONResponse(content=payload).body
    return JSONResponse(content=payload).body


def _remember_etag(ins_code) -> None:
    hit = INDEX_CACHE.get(ins_code)
    if not hit:
        return
    stable = {k: v for k, v in (hit[1] or {}).items() if k not in _ETAG_VOLATILE}
    INDEX_ETAG[ins_code] = hashlib.md5(_body_bytes(stable)).hexdigest()[:16]


def _etag_for(ins_code, limit) -> str | None:
    base = INDEX_ETAG.get(ins_code)
    if not base:
        return None
    try:
        # مبنایِ قیمت بخشی از بدنهٔ resolved است؛ تغییرش باید ETag را عوض کند.
        stamp = hashlib.md5(str(price_basis.current()).encode("utf-8")).hexdigest()[:8]
    except Exception:
        stamp = "nobasis"
    return '"%s-%s-L%d"' % (base, stamp, int(limit or 0))


def _inm_matches(field: str, etag: str) -> bool:
    tag = etag[2:] if etag.startswith("W/") else etag
    for part in str(field or "").split(","):
        p = part.strip()
        if p == "*" or (p[2:] if p.startswith("W/") else p) == tag:
            return True
    return False


def _cache_fresh(ins_code, now=None) -> bool:
    hit = INDEX_CACHE.get(ins_code)
    if not hit:
        return False
    return ((time.time() if now is None else now) - hit[0]) < INDEX_CACHE_TTL


@router.get("/api/index/tedpix")
def get_index_tedpix(request: Request, limit: int = Query(0, ge=0, le=5000),
                     refresh: bool = Query(False)):
    """سری روزانه OHLC شاخص کل بورس تهران (TEDPIX) از CDN TSETMC.

    limit=0 -> کل سری (از 2008)؛ refresh=true -> نادیده گرفتن cache کوتاه‌مدت.
    اگر منبع در دسترس نباشد یا پاسخ خالی/نامعتبر باشد، 502 با علت دقیق برمی‌گردد
    (هرگز داده ساختگی یا عدد جعلی).
    """
    # ۳۰۴ فقط وقتی که کش تازه است: ETagِ کهنه نباید دادهٔ منقضی را تأیید کند.
    if not refresh and _cache_fresh(TEDPIX_INS_CODE):
        etag = _etag_for(TEDPIX_INS_CODE, limit)
        inm = request.headers.get("if-none-match") if request is not None else None
        if etag and inm and _inm_matches(inm, etag):
            return Response(status_code=304, headers={"ETag": etag})
    try:
        payload = build_tedpix_payload(limit=limit, force=bool(refresh))
        # بعد از ساخت (یا hit) یک‌بار هشِ بدنهٔ پایدار را نگه می‌داریم؛ درخواستِ
        # بعدی پیش از هر ساخت/تبدیلی همان را می‌بیند.
        _remember_etag(TEDPIX_INS_CODE)
        etag = _etag_for(TEDPIX_INS_CODE, limit)
        headers = {"ETag": etag} if etag else None
        if ORJSONResponse is not None:
            return ORJSONResponse(content=payload, headers=headers)
        return JSONResponse(content=payload, headers=headers)
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={
            "status": "error",
            "message": str(e),
            "ins_code": TEDPIX_INS_CODE,
            "source": INDEX_SOURCE,
            "has_volume": False,
            "candles": [],
            "count": 0,
        })
