"""symbol_identity.py — تنها تعریفِ «این ردیف کدال مالکِ کدام ابزار است».

چرا این فایل متولد شد (Stage 1.2 مأموریت بنیادی، 1405/07/22). «چطور بفهمیم دو
رشته یکی‌اند» چهار جا جدا نوشته شده بود و دو جوابِ مختلف می‌داد:

  * `fts_engine.symbol_aliases()`  → جایگشتِ ي/ك/ى + حذف نیم‌فاصله از **ورودی**
    + حذف یک رقمِ انتهایی. مصرف‌کننده: کوئری‌های تک‌نمادی (کارت/دریل‌دان).
  * `fts_engine.norm_fa(symbol)`   → کلیدِ دسته‌بندی در `bulk_scan` و نقشه‌های
    کل‌بازاری (نام شرکت، m141، ارزش بازار). مصرف‌کننده: قیف/اسکرینر.
  * `api/_core.py:307` و `api/fundamental.py` (۸ جا) → همان اولین.
  * `codal_fetcher` → `norm()`ِ خودش برای ستون‌های نوشتاری.

نتیجهٔ عملیِ اندازه‌گیری‌شده روی همین `market.db` (۱۴۰۵-۰۷-۲۲، فقط‌خواندنی):
  «شهر فرش» → بانکِ کدال دو املا دارد: `'شهر فرش'` (۱ ردیف، درآمد ۱۹٬۱۲۵٬۹۰۹)
  و `'شهر ‌فرش'` (۶ ردیف، با نیم‌فاصله پس از فاصله). جایگشتِ `symbol_aliases`
  نیم‌فاصله را از ورودی **حذف** می‌کند ولی هیچ‌وقت آن را **نمی‌سازد**، پس کارت
  فقط ۱ ردیف می‌بیند و قیف ۷ ردیف. کارت برای آن صادرکننده `2_eps_trend: None`
  می‌دهد چون ۵ سالِ مالیِ حسابرسی‌شده در بانک هست ولی هرگز خوانده نمی‌شوند.
  شمارشِ واگرایی: ۱٬۶۷۵ جفت (نماد×جدول) که یک مسیر ردیف می‌بیند و مسیر دیگر
  نه؛ جهتِ واگرایی همیشه «قیف می‌بیند، کارت نمی‌بیند» است (۰ مورد برعکس).

قاعده (همین فایل، بی‌استثنای دوم):
  ۱) کلیدِ هویت = یکسان‌سازی ي/ك/ى ← فارسی، و حذف **همهٔ** جداسازهای نامرئی و
     فاصله (نیم‌فاصله U+200C، فاصله‌نشکن U+00A0، RLM U+200F، فاصلهٔ معمولی).
     اندازه‌گیری: روی ۵٬۹۸۹ نماد تابلو **صفر برخورد** (۵٬۹۸۹ رشته ← ۵٬۹۸۹ کلید).
     در کدال فقط ۳ گروه اضافه ادغام می‌شوند (`'معيار '`⇄`'معیار'` و دو مورد
     دیگر) که همان‌ها هم یک صادرکننده‌اند.
  ۲) نامزدهای خام از **خودِ بانک** خوانده می‌شوند، نه از تولیدِ جایگشت. دلیلِ
     اندازه‌گیری‌شده: تلاشِ «جایگشتِ فاصله↔نیم‌فاصله» با سقفِ ۹۶ به ۲۱۶ نامزد
     و با سقفِ ۲۵۶ به ۶۴۸ نامزد رسید (سقف فقط نقطۀ برش را جابه‌جا می‌کند) و
     همۀ آن‌ها بی‌شاهد بودند. کوئریِ `SELECT DISTINCT symbol` روی هر منبع یک
     بار (~۳ms) و در حافظه می‌نشیند؛ پس «نامزد» یعنی چیزی که واقعاً در ستون
     نشسته است.
  ۳) پسوندهای خطِ تابلو (`آباد3`، `خودرو2`): فقط **یک رقمِ** انتهایی حذف می‌شود
     و فقط وقتی که ISINِ صادرکننده اجازه دهد. اندازه‌گیریِ همین بانک (بازتولید:
     `tools/symbol_identity_isin_gate.py`): ۹۷۱ نماد با این قاعده به کدال می‌رسند
     — ۷۳۹ با ISINِ هم‌قطار تأیید شده، ۰ رد شده، ۲۳۲ بی‌شاهد. بی‌شاهد بودن
     ریسک است، پس درِ ردپایِ کارت اعلام می‌ماند. حذفِ رقم‌های چندتایی فاجعه است:
     ۱٬۲۸۴ نماد به نامزدی می‌رسید که زیرِ نامش چند صادرکننده با ISINِ متفاوت
     هست (اوراق مشارکت «اراد…» و صندوق‌های «كم ر ۱..۵»). شمارشِ خط‌هایِ خواهر:
     ۷۸۴ پایۀ نام با خواهرِ رقمی درِ تابلو، ۱۹ تای آن‌ها چندِ صادرکننده‌اند؛
     امروز هیچ‌کدام از آن ۱۹ ردیفِ کدالِ زیرِ پایۀ نام ندارند، پس شمارِ الحاق‌ها
     عوض نمی‌شود — این بند **نگهبانِ** روزِ بعد است، نه تغییرِ رفتارِ امروز. پس:
        - ISIN موافق  → بپذیر (evidence='isin-agree')
        - ISIN مخالف  → رد کن، هرگز الحاق نکن (evidence='isin-clash'): هر
          دوصدایی — چندِ صادرکننده زیرِ یکِ پایۀ نام (خودِ پایه و خط‌هایِ
          خواهرش، «كم ر ۱..۵») یا نخواندنِ ISINِ خودِ خط با آن صادرکننده.
        - شاهدی نیست  → بپذیر ولی **اعلام کن** (evidence='no-isin') تا در ردپای
          کارت دیده شود؛ این تنها حالتی است که ریسک دارد و بی‌اعلان نمی‌ماند.
  ۴) هیچ تطبیقِ فازی/تقریبی/نام‌محور در این لایه نیست. اگر دو رشته کلیدِ
     متفاوت دارند، دو ابزارند. (قاعدهٔ_hardِ مرحلۀ 9.3 مأموریت: سفارش هرگز با
     fuzzy match به ابزار دیگر متصل نشود — این لایه همان کلید را به اجرا می‌دهد.)
  ۵) کارت و قیف هر دو **این توابع** را صدا می‌زنند. گاردِ
     `dev/symbol_identity_v1090.py` با AST ثابت می‌کند هیچ خوانندۀ پروداکشنی
     دیگر `norm_fa(symbol)` را برای کلیددنِ نماد مصرف نمی‌کند و هیچ `sym_in`
     بی‌connection باقی نمانده است.

stdlib-only است (الگو: `codal_periods.py`، `codal_units.py`، `price_basis.py`) و
در `fts_terminal.spec` → `hiddenimports` فهرست می‌شود.
"""
from __future__ import annotations

import re
import sqlite3

__all__ = [
    "key", "norm", "variants", "line_variants", "pred", "sources",
    "reset_cache", "cache_info", "identity_stats", "EVIDENCE",
]

# ── ۱) کلید ────────────────────────────────────────────────────────────────
_YA_FA, _YA_AR, _HAMZA = "\u06cc", "\u064a", "\u0649"
_KAF_FA, _KAF_AR = "\u06a9", "\u0643"
# تمام جداسازهای نامرئی/فاصله که در دادهٔ TSETMC و کدال دیده شده‌اند.
_SEP = re.compile("[ \u00a0\u200c\u200f\u200e\u202f]+")

_NORM = str.maketrans({_YA_AR: _YA_FA, _KAF_AR: _KAF_FA, _HAMZA: _YA_FA})


def norm(text) -> str:
    """نوشتارِ مقایسه: عربی←فارسی. تنها همین یک گام، بی‌دست‌زدنِ فاصله."""
    return str(text if text is not None else "").translate(_NORM)


def key(symbol) -> str:
    """کلیدِ هویتِ یک نماد؛ رشتهٔ خالی یعنی «هویت نداریم»."""
    return _SEP.sub("", norm(symbol)).lower()


# ── ۲) نامزدها از خودِ بانک ────────────────────────────────────────────────
# ── دامنه‌ها ───────────────────────────────────────────────────────────────
# «این دو رشته یکی‌اند؟» به این بستگی دارد که **در کدام جهان** می‌پرسیم:
#   CODAL — نمادِ صادرکننده (سه جدولِ کدال). اینجا پسوندهایِ خطِ تابلو معنا دارد
#           و با گیتِ ISIN باز می‌شود (`آباد3` ← `آباد`).
#   BOARD — نمادِ ابزارِ بورس (instruments/price_history/واچلیست). اینجا خودِ
#           همان رشته هویت است و هیچ الحاقی مجاز نیست؛ `خودرو2` ابزارِ دیگری است
#           و هرگز به `خودرو` وصل نمی‌شود.
# بی‌این تفکیک، «یکسان‌سازیِ هویت» یعنی الحاقِ ردیفِ یکِ ابزار به ابزارِ دیگر —
# همان کاری که مرحلۀ 9.3 مأموریت برایِ سفارش ممنوع می‌کند.
CODAL = "codal"
BOARD = "board"
DOMAINS = {
    CODAL: (("financial_statements", "symbol"),
            ("monthly_sales", "symbol"),
            ("codal_notices", "symbol")),
    BOARD: (("instruments", "l_val18"),
            ("price_history", "symbol"),
            ("user_watchlists", "symbol")),
}

# کشِ هر اتصال: {id(conn): {"dv": int, "by_key": {key: (raw, …)}, "isin": {key: (seg, …)}}}
# `PRAGMA data_version` بالاخره سینک را می‌بیند (نوشتۀ اتصالِ دیگر ⇒ نسخه عوض
# می‌شود)، پس نقشه بی‌اعتبار نمی‌ماند.
_CACHE: dict = {}

MAX_VARIANTS = 48          # سقفِ پارامترهای IN؛ سقفِ واقعیِ مشاهده‌شده ۳ است


def sources(conn, domain=CODAL) -> tuple:
    """منبع‌هایی که *همین* بانک در این دامنه دارد (snapshotهای ناقص را رد می‌کند)."""
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    out = []
    for t, col in DOMAINS.get(domain or CODAL, ()):
        if t not in have:
            continue
        cols = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % t)}
        if col in cols:
            out.append((t, col))
    return tuple(out)


def _slot(conn):
    """نقشۀ کشیدۀ این اتصال، یا بازسازی وقتی `data_version` عوض شده است.

    کلیدِ کش `id(conn)` است و آدرسِ حافظه درِ CPython بازاستفاده می‌شود: اتصالِ
    بسته‌شدۀ `market.db` می‌تواند جایش را به اتصالِ تازه‌ای از `codal.db` یا یک
    بانکِ آزمونِ درِ حافظه بدهد، و `data_version` فقط می‌گوید «چند بار نوشته
    شده» — نه *کدام* فایل. `_sqlite3.Connection` weakref را نمی‌پذیرد
    (`cannot create weak reference`)، پس خودِ آبجکتِ اتصال درِ درز نگه داشته
    می‌شود و هویت با `is` سنجیده می‌شود: تا نقشه‌ای زنده است آبجکتش آزاد
    نمی‌شود، پس هیچ اتصالِ دیگری idِ او را به ارث نمی‌برد و نقشۀِ اشتباه
    تحویل نمی‌گیرد. کرانِ `len(_CACHE)` درِ `reset_cache`/انداختنِ تازه همین
    ارجاع‌ها را آزاد می‌کند.
    """
    try:
        dv = conn.execute("PRAGMA data_version").fetchone()[0]
    except sqlite3.Error:
        dv = -1
    slot = _CACHE.get(id(conn))
    if slot and slot["conn"] is conn and slot["dv"] == dv:
        return slot
    by_key, by_key_board, isin = {}, {}, {}
    for t, col in sources(conn, CODAL):
        try:
            rows = conn.execute("SELECT DISTINCT %s FROM %s" % (col, t)).fetchall()
        except sqlite3.Error:
            continue
        for (raw,) in rows:
            if raw is None:
                continue
            k = key(raw)
            if not k:
                continue
            lst = by_key.setdefault(k, [])
            if raw not in lst and len(lst) < MAX_VARIANTS:
                lst.append(raw)
    for t, col in sources(conn, BOARD):
        try:
            rows = conn.execute("SELECT DISTINCT %s FROM %s" % (col, t)).fetchall()
        except sqlite3.Error:
            continue
        for (raw,) in rows:
            if raw is None:
                continue
            k = key(raw)
            if not k:
                continue
            lst = by_key_board.setdefault(k, [])
            if raw not in lst and len(lst) < MAX_VARIANTS:
                lst.append(raw)
    try:
        for sym, isin_txt in conn.execute(
                "SELECT l_val18, isin FROM instruments"):
            k = key(sym)
            if not k:
                continue
            seg = (isin_txt or "").strip().upper()
            if seg.startswith("IR") and len(seg) >= 9:
                isin.setdefault(k, set()).add(seg[:9])
    except sqlite3.Error:
        pass
    slot = {"conn": conn, "dv": dv, "by_key": by_key, "by_key_board": by_key_board,
            "isin": isin}
    _CACHE[id(conn)] = slot
    if len(_CACHE) > 8:                       # اتصال‌هایِ زودگذرِ API انباشته نشوند
        for stale in list(_CACHE)[:-8]:
            _CACHE.pop(stale, None)
    return slot


def variants(conn, symbol, domain=CODAL) -> tuple:
    """هر نوشتارِ خامی که در این دامنه زیر همان کلید نشسته (خودِ ورودی همیشه هست)."""
    k = key(symbol)
    if not k:
        return ()
    slot = _slot(conn)
    map_name = "by_key" if domain == CODAL else "by_key_board"
    out = list(slot[map_name].get(k, []))
    s = "" if symbol is None else str(symbol)
    if s and s not in out:
        out.insert(0, s)
    return tuple(out[:MAX_VARIANTS])


# ── ۳) پسوندِ خطِ تابلو، با گیتِ ISIN ──────────────────────────────────────
_ONE_DIGIT = re.compile(r"(?<=\D)\d$")
EVIDENCE = ("exact", "same-key", "isin-agree", "no-isin", "isin-clash", "unmatched")


def line_variants(conn, symbol, domain=CODAL):
    """(namzed-ha, evidence) برای نمادهای «خط» تابلو مثل `آباد3`.

    فقط یک رقمِ انتهایی؛ رقم‌های چندتایی هرگز (`اراد275` زیرِ نامزدش هشتاد
    اوراقِ با ISINِ متفاوت دارد — اندازه‌گیری‌شده). بازگشت:
      ((), 'exact')      یعنی بی‌پسوندیم یا نامزد بی‌ردیفِ کدال است
    """
    if domain != CODAL:
        # درِ جهانِ تابلو پسوندِ رقمی هویتِ ابزار است؛ الحاق ممنوع.
        return (), "exact"
    k = key(symbol)
    if not k or len(k) < 3 or not _ONE_DIGIT.search(k):
        return (), "exact"
    base = _ONE_DIGIT.sub("", k)
    if not base or base == k:
        return (), "exact"
    slot = _slot(conn)
    # نامزد فقط وقتی معتبر است که ردیفِ کدال داشته باشد (نه فقط ردیفِ تابلو)
    if not _has_codal_rows(conn, base):
        return (), "exact"
    mine = set(slot["isin"].get(k, ()))
    theirs = set(slot["isin"].get(base, ()))
    for kk, segs in slot["isin"].items():
        # خط‌هایِ خواهرِ همان نام (`كم ر 1` … `كم ر 5`) هم صادرکننده‌اند؛ اگر
        # آن‌ها دو ISINِ متفاوت بدهند، «پایۀ نام» متعلق به چندِ شرکت است و
        # الحاقِ هر کدام به دیگری خطاست — حتی وقتی ISINِ خودِ خط با یکی می‌خواند.
        if kk != base and kk != k and _ONE_DIGIT.search(kk) and _ONE_DIGIT.sub("", kk) == base:
            theirs |= segs
    if len(theirs) > 1:
        return (), "isin-clash"                 # یکِ نام، چندِ صادرکننده ⇒ الحاق ممنوع
    if mine and theirs and not (mine & theirs):
        return (), "isin-clash"                 # ISINِ خودِ خط با صادرکنندۀ نام نمی‌خواند
    ev = "isin-agree" if (mine and theirs) else "no-isin"
    raws = tuple(r for r in slot["by_key"].get(base, ()) if key(r) == base)
    return raws, ev


def _has_codal_rows(conn, k: str) -> bool:
    """آیا کلید `k` در جدول‌های کدال ردیفی دارد؟ (روی همان نقشۀ کشیده)"""
    slot = _slot(conn)
    for raw in slot["by_key"].get(k, ()):
        for t, col in (("financial_statements", "symbol"), ("monthly_sales", "symbol")):
            try:
                n = conn.execute("SELECT 1 FROM %s WHERE %s=? LIMIT 1" % (t, col),
                                 (raw,)).fetchone()
            except sqlite3.Error:
                continue
            if n:
                return True
    return False


# ── ۴) شرطِ SQL ────────────────────────────────────────────────────────────
def pred(conn, col: str, symbol, domain=CODAL):
    """(شرح SQL, پارامترها) — جایگزینِ `symbol_aliases` + `IN`ِ دستی.

    ایندکس‌پسند می‌ماند (`col IN (?,?…)`)؛ هیچ تابعی در WHERE نمی‌نشیند.
    بی‌کلید ⇒ `1=0`، یعنی همان «بدون داده» که پیش‌تر رفتارِ درست بود.
    ردپا را `evidence()` می‌گوید تا رابط بتواند بنویسد «از راهِ ISIN» یا
    «بی‌شاهدِ ISIN».
    """
    al = list(variants(conn, symbol, domain))
    extra, _ev = line_variants(conn, symbol, domain)
    for x in extra:
        if x not in al:
            al.append(x)
    if not al:
        return "1=0", []
    return "%s IN (%s)" % (col, ",".join("?" * len(al))), al


def evidence(conn, symbol, domain=CODAL) -> str:
    """چطور به ردیف‌ها رسیدیم: same-key | isin-agree | no-isin | isin-clash | unmatched.

    پیش ازِ دامنه‌ای‌بودنِ این لایه، پاسخ همیشه `same-key` بود: `instruments` هم
    در همان نقشه بود و نامِ خودش را پیدا می‌کرد، پس سنسور هیچ‌وقت چیزی نمی‌دید.
    حالا هر دامنه نقشۀ جدا دارد و این تابع واقعاً می‌گوید الحاق از کدامِ راه بوده.
    """
    k = key(symbol)
    slot = _slot(conn)
    mp = slot["by_key"] if domain == CODAL else slot["by_key_board"]
    if mp.get(k):
        return "same-key"
    extra, ev = line_variants(conn, symbol, domain)
    if extra:
        return ev
    # «الحاق رد شد» با «هیچ نامزدی نبود» یکی نیست: ردپایِ رد (`isin-clash`) باید درِ
    # کارت دیده شود، وگرنه یکِ الحاقِ خطرناکِ جلوگرفته‌شده دقیقاً مثلِ نبودِ داده
    # خوانده می‌شود — همان جایی که سنسور کور می‌شود.
    return ev if ev == "isin-clash" else "unmatched"


def reset_cache(conn=None) -> int:
    """پاک کردنِ نقشه (پس ازِ سینکِ کدال یا درِ آزمون‌ها). تعدادِ زدوده‌شده را برمی‌گرداند."""
    if conn is None:
        n = len(_CACHE)
        _CACHE.clear()
        return n
    return 1 if _CACHE.pop(id(conn), None) is not None else 0


def cache_info() -> dict:
    return {"connections": len(_CACHE),
            "keys": sum(len(v["by_key"]) for v in _CACHE.values()),
            "with_isin": sum(len(v["isin"]) for v in _CACHE.values())}


def identity_stats(conn) -> dict:
    """سرشماریِ قابلِ بازتولیدِ خودِ همین قرارداد (برایِ گارد و گزارشِ سلامت)."""
    slot = _slot(conn)
    multi = {k: v for k, v in slot["by_key"].items() if len(v) > 1}
    return {"distinct_keys": len(slot["by_key"]),
            "keys_with_multiple_spellings": len(multi),
            "max_spellings_one_key": max((len(v) for v in slot["by_key"].values()), default=0),
            "board_keys": len(slot["by_key_board"]),
            "keys_with_isin": len(slot["isin"]),
            "sources_codal": ["%s.%s" % s for s in sources(conn, CODAL)],
            "sources_board": ["%s.%s" % s for s in sources(conn, BOARD)]}
