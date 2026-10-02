# -*- coding: utf-8 -*-
"""market_state.py — حالتِ داغِّ تابلو در RAM.

سه کار این ماژول است، و هر سه از یک سندِ سنجش می‌آیند (docs/fts-notes/
LIVE_MARKET_AUDIT.md، اندازه‌گیری ۱۴۰۵-۰۷-۱۱):

۱. **دِلتا برایِ نوشتن.** تیکِ زنده پیش‌ازین کلِ ~۵٬۴۵۱ ردیف تابلو را هر پنج
   ثانیه با `INSERT OR REPLACE` بازنویسی می‌کرد. حالا فقط ردیفی نوشته می‌شود
   که فیلدِ *نوشته‌شدنی‌اش* عوض شده باشد.
۲. **شمارندۀ revision.** بی‌تغییر ⇒ بی‌rebuild. بازسازیِ تابلو ~۳۹۰ms CPU و
   ~۴ مگابایت JSON است؛ بیشترِ سیکل‌هایِ پنج‌ثانیه‌ای چیزی عوض نمی‌کنند.
۳. **آینۀ خواندنِ زنده.** `api/market.py` ردیف‌هایِ نشست را از اینجا برمی‌دارد
   و SQLite فقط برایِ لایۀ ایستا/تاریخ خوانده می‌شود؛ `/api/market/delta` هم
   از همین‌جا می‌فهمد «از ویرایشِ N تا چه ردیف‌هایی تکان خورد».

قراردادها
=========
* کلید = `ins_code` (کلیدِ primaryِ market_watch).
* **امضا رویِ همان ستون‌هایی است که واقعاً نوشته می‌شوند.** تیکِ پس از بستنِ
  بازار (۱۲:۳۰–۱۵:۳۰) فقط ستون‌هایِ عددی را UPDATE می‌کند و صف‌ها را دست
  نمی‌زند؛ اگر امضا کلِ tuple باشد، تغییرِ یک صفِ بی‌نوشتن «تغییر» حساب می‌شود،
  نوشتنِ واقعی چیزی عوض نمی‌کند و کش بی‌دلیل می‌سوزد.
* RAM هیچ‌وقت جلوتر از دیسک نمی‌رود: `commit()` بعد از commitِ موفقِ SQLite
  صدا می‌شود، و `_FULL`/`_PATCH` فقط همان ستون‌هایی را نگه می‌دارند که در
  UPDATE/INSERT رفته است. پس «تابلوی RAM» == «محتوای market_watch».
* `prime()` انتهای هر سینکِ کامل: آن‌جا instruments/boards/client_type هم
  بازنویسی می‌شوند، پس لایۀ ایستایِ تابلو باید بسوزد (`sync_count` بالا می‌رود).
* بی‌خطرترین حالتِ شکست: RAM خالی (بوت تازه) ⇒ هرچیز «تغییر» و بازسازیِ کامل
  از SQLite = رفتارِ پیشین.
"""
from __future__ import annotations

import threading
import time

_LOCK = threading.RLock()

# آخرین ردیفِ **کاملاً نوشته‌شده** برایِ هر نماد (INSERT OR REPLACE یا سینکِ کامل).
_FULL: dict = {}
# ستون‌هایی که از آخرینِ نوشتنِ کامل به‌بعد بی‌UPDATEِ کامل عوض شده‌اند
# (مسیرِ پس از بستنِ بازار). {ins_code: {نامِ ستون: مقدار}}
_PATCH: dict = {}
# امضایِ آخرینِ نوشتن، جدا از ردیف: امضا فقط ستون‌هایِ نوشته‌شدنیِ آن حالت را
# می‌بیند، ولی ردیف باید کامل بماند.
_SIG: dict = {}

_SESSION_DAY = 0
_SYNC_COUNT = 0
# «یک نویسدۀ ایستا چیزی در price_history/tape_history عوض کرد». سازندۀ قابِ
# تابلو به این شمارنده هم نگاه می‌کند، چون آن دو جدول پنجره‌هایِ نمایش را
# می‌سازند و تیکِ زنده هرگز آن‌ها را نمی‌نویسد — سینکِ کندل درِ بوت و
# refresh_tape_history از همین‌جا خبر می‌دهند.
_STATIC_REV = 0
_REVISION = 0
_LAST_CYCLE_AT = ""
_STATS = {"cycles": 0, "rows_seen": 0, "rows_written": 0, "nochange_cycles": 0,
          "last_cycle_s": 0.0, "last_changed": 0, "started_at": time.time()}

# ژورنالِ دِلتا: [(revision, (codes...))] — برایِ «از ویرایشِ N تا چه عوض شد».
# سقفِ تعدادِ سیکل نهایی است، نه زمانی: اگر ژورنال چرخید و کلاینتی خیلی عقب
# مانده باشد، `changed_since` None می‌دهد و سروِکننده «بدنۀ کامل» می‌فرستد —
# هیچ‌وقت دلتایِ ناقص از ژورنالِ چرخیده ساخته نمی‌شود.
_JOURNAL: list = []
_JOURNAL_MAX = 240

# اشتراکِ عمقِ بازار: نمادهایی که UI واقعاً باز کرده است.
_SUBS: dict = {}

_IDX = None
_GET = {}


def cols() -> dict:
    """نام → شاخصِ tupleِ market_watch (تک‌منبع: خودِ `test_tsetmc.MW_COLS`)."""
    global _IDX
    if _IDX is None:
        try:
            import test_tsetmc as _T
            _IDX = {c: i for i, c in enumerate(_T.MW_COLS)}
        except Exception:
            _IDX = {}
    return _IDX


def _getter(fields):
    """itemgetterِ شاخص‌هایِ `fields` بی‌`fetched_at` (زمانِ برداشت دلیلِ تغییر نیست)."""
    key = tuple(fields) if fields is not None else None
    g = _GET.get(key)
    if g is None:
        import operator
        c = cols()
        idx = [c[f] for f in (key if key is not None else c) if f != "fetched_at"]
        g = operator.itemgetter(*idx) if len(idx) != 1 else (lambda r, i=idx[0]: (r[i],))
        _GET[key] = g
    return g


def _sig(row, fields):
    try:
        return _getter(fields)(row)
    except IndexError:
        return tuple(row)


# ستون‌هایی که تیکِ «پس از بستن» واقعاً UPDATE می‌کند (test_tsetmc.tick_live).
# هر تغییرِ دیگری در آن پنجره نوشتنی نیست، پس در امضا هم نمی‌آید.
AFTER_HOURS_FIELDS = ("h_even", "p_closing", "p_last", "price_min", "price_max",
                      "q_tot_tran", "q_tot_cap", "z_tot_tran", "price_change",
                      "market_cap", "market_cap_src")


def _stored_sig(code, fields):
    """امضایِ *همان مجموعه‌ستون* که حالا سنجیده می‌شود.

    حالتِ نوشتن درِ روز عوض می‌شود (۱۲:۳۰: از INSERTِ کامل به UPDATEِ عددی). اگر
    امضایِ حالتِ پیشین را با امضایِ حالتِ تازه مقابله کنیم، هر دو طولش فرق دارد و
    «تغییر» می‌شود — یعنی درِ لحظۀِ عوض‌شدنِ حالت، یک‌بار کلِ ۵٬۴۵۱ ردیف دوباره
    نوشته می‌شوند. پس امضا از ردیفِ RAMِ همان حالت بازسازی می‌شود؛ و اگر ردیفی
    فقط patch است (بی‌ردیفِ کامل)None می‌ماند و نوشتنِ احتیاطی اتفاق می‌افتد.
    """
    v = _SIG.get(code)
    if v is None:
        return None
    key, s = v
    if key == _key_of(fields):
        return s
    base = _FULL.get(code)
    return None if base is None else _sig(base, fields)


def _key_of(fields):
    return tuple(fields) if fields is not None else None


def diff(rows, fields=None) -> list:
    """ردیف‌هایی که ستون‌هایِ نوشته‌شدنی‌شان با آخرین وضعیتِ دیسک فرق دارد.

    RAM را به‌روز **نمی‌کند** — فراخوان باید پس از commitِ موفقِ SQLite
    `commit()` صدا بزند، وگرنه شکستِ نوشتن با «نوشته شد» یکی می‌شود.
    """
    with _LOCK:
        return [w for w in rows if _stored_sig(w[0], fields) != _sig(w, fields)]


def commit(rows, fields=None) -> int:
    """تأییدِ نوشتن: امضا، ردیفِ زنده، روزِ نشست و ژورنال.

    `fields=None` یعنی «کلِ tuple نوشته شد» (مسیرِ INSERT OR REPLACE و سینکِ
    کامل)؛ در غیر این صورت فقط همان ستون‌ها (مسیرِ UPDATE پس از بستن).
    برمی‌گرداند تعدادِ ردیفِ تغییریافته — صفر یعنی بی‌کارِ CPU، بی‌revision.
    """
    global _REVISION, _SESSION_DAY
    n = 0
    codes = []
    k = _key_of(fields)
    with _LOCK:
        for w in rows:
            s = _sig(w, fields)
            if _stored_sig(w[0], fields) == s:
                continue
            _SIG[w[0]] = (k, s)
            _store(w, fields)
            d = w[1]
            if d and d > _SESSION_DAY:
                _SESSION_DAY = d
            codes.append(w[0])
            n += 1
        if n:
            _REVISION += 1
            _JOURNAL.append((_REVISION, tuple(codes)))
            if len(_JOURNAL) > _JOURNAL_MAX:
                del _JOURNAL[:len(_JOURNAL) - _JOURNAL_MAX]
        _STATS["rows_written"] += n
        return n


def _store(w, fields) -> None:
    """RAM را دقیقاً به «آنچه رویِ دیسک رفت» می‌رساند."""
    code = w[0]
    c = cols()
    if fields is None:
        _FULL[code] = tuple(w)
        _PATCH.pop(code, None)
        return
    base = _FULL.get(code)
    if base is None:
        p = _PATCH.setdefault(code, {})
        for f in fields:
            i = c.get(f)
            if i is not None and i < len(w):
                p[f] = w[i]
        return
    lst = list(base)
    for f in fields:
        i = c.get(f)
        if i is not None and i < len(w):
            lst[i] = w[i]
    _FULL[code] = tuple(lst)


def prime(rows) -> int:
    """سینکِ کامل: هرچه فرستادی «نوشته‌شده» و لایۀ ایستا «سوخته».

    `_save_market_snapshot` و `main()` بعد از commit صدا می‌زنند؛ آن‌ها
    instruments/boards/client_type را هم بازنویسی می‌کنند — چیزی که دلتایِ تیک
    هرگز نمی‌بیند، پس `sync_count` بالا می‌رود تا کوئریِ تابلو از SQLite بخواند.
    """
    global _SYNC_COUNT, _SESSION_DAY
    with _LOCK:
        for w in rows:
            _SIG[w[0]] = (None, _sig(w, None))
            _FULL[w[0]] = tuple(w)
            d = w[1]
            if d and d > _SESSION_DAY:
                _SESSION_DAY = d
        _PATCH.clear()
        _SYNC_COUNT += 1
        return _SYNC_COUNT


def note_cycle(seen: int, changed: int, elapsed_s: float) -> None:
    """یک سیکلِ موفق از TSETMC دیده شد — «زمانِ تابلو» همین است، نه fetched_at."""
    global _LAST_CYCLE_AT
    with _LOCK:
        _LAST_CYCLE_AT = time.strftime("%Y-%m-%d %H:%M:%S")
        _STATS["cycles"] += 1
        _STATS["rows_seen"] += seen
        _STATS["last_changed"] = changed
        _STATS["last_cycle_s"] = round(elapsed_s, 4)
        if not changed:
            _STATS["nochange_cycles"] += 1


def revision() -> int:
    with _LOCK:
        return _REVISION


def sync_count() -> int:
    with _LOCK:
        return _SYNC_COUNT


def note_static_change() -> None:
    """«لایۀ ایستایِ تابلو سوخت» — سازندۀ تابلو باید دوباره از SQLite بخواند.

    نویسندگانِ `price_history`/`tape_history` بیرونِ سینکِ کامل (نخِ کندل در
    بوت، refresh خودِ [ih]) این را صدا می‌زنند. بی‌آن، قابِ ایستا تا اولین
    سینکِ کامل کهنه می‌ماند — و پنجرۀ «میانگین حجم/کفِ ۲۹ نشست» عددِ دیروز
    را زیرِ تاریخِ امروز نشان می‌داد.
    """
    global _STATIC_REV
    with _LOCK:
        _STATIC_REV += 1


def static_rev() -> int:
    with _LOCK:
        return _STATIC_REV


def session_day() -> int:
    with _LOCK:
        return _SESSION_DAY


def last_cycle_at() -> str:
    with _LOCK:
        return _LAST_CYCLE_AT


def stats() -> dict:
    with _LOCK:
        out = dict(_STATS)
        out.update({"revision": _REVISION, "sync_count": _SYNC_COUNT,
                    "session_day": _SESSION_DAY, "symbols": len(_SIG),
                    "full_rows": len(_FULL), "patched": len(_PATCH),
                    "journal": len(_JOURNAL), "subscribed": len(_SUBS),
                    "last_cycle_at": _LAST_CYCLE_AT})
        return out


def changed_since(rev: int):
    """codes تغییرکرده از ویرایشِ `rev` تا حالا.

    None یعنی «ثابت کردنش ممکن نیست» (ژورنال چرخیده یا کلاینت جلوتر است) ⇒
    سروِکننده باید بدنۀ کامل بفرستد، نه دلتایِ ناقص.
    """
    with _LOCK:
        return _between(rev, _REVISION)


def codes_between(lo: int, hi: int):
    """codes با lo < revision <= hi — همان چیزی که در آینهٔ ساخته‌شده بازتاب دارد."""
    with _LOCK:
        return _between(lo, hi, cap=hi)


def _between(lo: int, hi: int, cap=None):
    if cap is None:
        cap = _REVISION
    if lo == hi:
        return set()
    if lo > cap or hi > _REVISION:
        return None
    if not _JOURNAL or _JOURNAL[0][0] - 1 > lo:
        return None
    out = set()
    for r, codes in _JOURNAL:
        if lo < r <= hi:
            out.update(codes)
    return out


def overlay_codes(since_rev: int) -> set:
    """codesی که قابِ ایستا باید رویشان overlay کند.

    ژورنالِ چرخیده اینجا فاجعه نیست (برخلافِ endpoint): «همه را دوباره بنفش
    کن» همان چیزی است که کوئریِ SQLite می‌داد، پس بی‌صحتی ولی با کارِ بیشتر.
    """
    with _LOCK:
        got = _between(since_rev, _REVISION)
        return set(_FULL) | set(_PATCH) if got is None else got


def live_rows(codes):
    """(ردیف‌هایِ کامل, patchها) برایِ `codes` — همان چیزی که رویِ دیسک است."""
    with _LOCK:
        full = {k: _FULL[k] for k in codes if k in _FULL}
        patch = {k: dict(v) for k, v in _PATCH.items() if k in codes and k not in full}
        return full, patch


def rows_for(codes) -> dict:
    """ردیف‌هایِ کاملِ `codes` (codes می‌تواند یک iterable یا تنها روزِ نشست باشد)."""
    with _LOCK:
        if isinstance(codes, int):
            return {k: v for k, v in _FULL.items() if v[1] == codes}
        return {k: _FULL[k] for k in codes if k in _FULL}


def max_h_even(day: int = 0) -> int:
    """بیشترینِ h_evenِ نمادهایِ همین نشست — «ساعتِ تابلو»یِ واقعی."""
    with _LOCK:
        d = day or _SESSION_DAY
        best = 0
        for v in _FULL.values():
            if (not d or v[1] == d) and v[2] and v[2] > best:
                best = v[2]
        return int(best or 0)


def live_view(ins_code: str):
    """آخرین ستون‌هایِ ثانیه‌ای یک نماد — برایِ سازندۀ کندلِ درون‌روز."""
    with _LOCK:
        r = _FULL.get(ins_code)
        p = _PATCH.get(ins_code)
        c = cols()
        if r is None and not p:
            return None
        out = []
        for f in _TICK_FIELDS:
            i = c.get(f)
            if i is None:
                out.append(None)
                continue
            if p and f in p:
                out.append(p[f])
            else:
                out.append(None if r is None or i >= len(r) else r[i])
        return tuple(out)


def row_of(ins_code: str):
    with _LOCK:
        return _FULL.get(ins_code)


_TICK_FIELDS = ("p_closing", "p_last", "q_tot_tran", "q_tot_cap", "z_tot_tran",
                "price_change", "h_even", "d_even", "fetched_at")


def subscribe_orderbook(ins_code: str) -> None:
    """اشتراکِ عمق: کارِ عمق فقط برایِ نمادهایی که UI باز کرده انجام می‌شود."""
    with _LOCK:
        _SUBS[ins_code] = time.time()


def subscriptions(max_age_s: float = 900.0) -> frozenset:
    """اشتراک‌هایِ زنده — اشتراکِ بی‌صاحیب (بستۀ پنجره) بعد از max_age می‌میرد."""
    now = time.time()
    with _LOCK:
        dead = [k for k, t in _SUBS.items() if now - t > max_age_s]
        for k in dead:
            _SUBS.pop(k, None)
        return frozenset(_SUBS)


def reset() -> None:
    """تست‌ها/بازنشانیِ سخت: کل حالتِ داغ خالی می‌شود (هرچیز «تازه» حساب می‌شود)."""
    global _REVISION, _SYNC_COUNT, _SESSION_DAY, _LAST_CYCLE_AT
    with _LOCK:
        _FULL.clear()
        _PATCH.clear()
        _SIG.clear()
        _JOURNAL.clear()
        _SUBS.clear()
        _REVISION = 0
        _SYNC_COUNT = 0
        _SESSION_DAY = 0
        _LAST_CYCLE_AT = ""
        _STATS.update({"cycles": 0, "rows_seen": 0, "rows_written": 0,
                       "nochange_cycles": 0, "last_cycle_s": 0.0,
                       "last_changed": 0, "started_at": time.time()})
