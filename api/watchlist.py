"""User watchlist CRUD and the triple-confirmation matrix.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import get_db, get_user_db
from .market import load_fts_config
from fastapi import APIRouter
from fastapi import Query
import fts_engine


router = APIRouter()


@router.get("/api/watchlist")
def get_watchlist():
    """واچ‌لیست کاربر، تازه‌ترین اول."""
    try:
        import watchlist_store
        conn = get_user_db()
        try:
            rows = watchlist_store.list_rows(conn)
        finally:
            conn.close()
        return {"status": "success", "count": len(rows), "data": rows,
                "limit": watchlist_store.MAX_WATCHLIST}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

@router.post("/api/watchlist")
def post_watchlist(payload: dict = None):
    """افزودن/بروزرسانی یک نماد در واچ‌لیست (upsert با کلید نرمال).

    سقفِ «حداکثر سهمِ واچ‌لیست» از پنلِ تنظیمات کدال خوانده میشود (نه فقط
    گاردِ سختِ watchlist_store.MAX_WATCHLIST) — جزوه می‌گوید نهایتاً ۵۰ سهم؛
    اگر کاربر آن را عوض کند، همین‌جا اعمال میشود. نمادِ از قبل موجود همیشه
    آزاد است (وگرنه «ویرایش یادداشت» پشتِ سقف گیر می‌کرد).
    """
    if not payload:
        return {"status": "error", "message": "بدون داده"}
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return {"status": "error", "message": "نماد ارسال نشده"}
    try:
        import watchlist_store
        conn = get_user_db()
        try:
            cap = int(load_fts_config().get("watchlist_max", 50) or 50)
            cap = max(1, min(cap, watchlist_store.MAX_WATCHLIST))
            if (watchlist_store.get(conn, fts_engine.norm_fa(symbol)) is None
                    and watchlist_store.count(conn) >= cap):
                return {"status": "error", "message":
                        "سقف واچ‌لیست (%d سهم) پر است — از پنل تنظیمات کدال "
                        "آن را تغییر دهید" % cap, "limit": cap}
            rec = watchlist_store.add(conn, symbol, name=str(payload.get("name") or ""),
                                      note=str(payload.get("note") or ""))
            conn.commit()
            n = watchlist_store.count(conn)
        finally:
            conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
    if rec is None:
        return {"status": "error", "message": "نماد نامعتبر (تهی پس از نرمال‌سازی)"}
    return {"status": "success", "watch": rec, "count": n, "limit": cap}

@router.delete("/api/watchlist/{symbol}")
def delete_watchlist(symbol: str):
    """حذف با هر نوشتاری (عربی/فارسی) — همان کلیدِ نرمالِ افزودن."""
    try:
        import watchlist_store
        conn = get_user_db()
        try:
            n = watchlist_store.remove(conn, symbol)
            conn.commit()
        finally:
            conn.close()
        return {"status": "success", "deleted": n}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

@router.get("/api/watchlist/matrix")
def get_watchlist_matrix(symbols: str = Query(None)):
    """ماتریس «تایید سه‌گانه» برای واچ‌لیست — read-only و محاسبی.

    `symbols` (اختیاری): فهرست کاما-جدا برای دیدن نتیجهٔ نمادهایی که
    هنوز ذخیره نشده‌اند (مثلاً ردیف‌های مرئی اسکرینر). بدون آن، خودِ جدول.
    خروجی: سه ستون pass|warn|fail|nodata + verdict نهایی (CONFIRMED/PROBABLE/
    WATCH/WEAK/INSUFFICIENT) + conf_reasons (متن هر هشدار) + یادداشت کاربر + asof
    هر ستون. هیچ وضعیتی سهم را از ماتریس حذف نمی‌کند.
    """
    try:
        import watchlist_store
        # «symbols» فقط وقتی رشته است معنا دارد. اگر route مستقیم صدا زده شود
        # (بدون HTTP) مقدار پیش‌فرض خودش شیءِ Query(None) است و truthy هم هست؛
        # بدون این محافظ، آن شیء به فهرست نماد تبدیل می‌شد و ماتریس به‌جای
        # خواندن جدول واچ‌لیست، یک «نماد» بی‌ربط داوری می‌کرد.
        raw = symbols if isinstance(symbols, str) else None
        probe = None
        if raw and raw.strip():
            probe = [s.strip() for s in raw.split(",") if s.strip()]
            probe = probe[:watchlist_store.MAX_WATCHLIST]
        conn = get_user_db()
        try:
            out = watchlist_store.matrix(conn, symbols=probe,
                                         cfg=None, fts_cfg=load_fts_config())
        finally:
            conn.close()
        return out
    except Exception as e:
        return {"status": "error", "message": str(e)[:200], "count": 0, "rows": []}

SELECTION_STATUSES = {"accept", "reject", "monitor", "pending"}
PORTFOLIO_MIN = 5          # حداقل سهمهای سبد
PORTFOLIO_MAX = 7          # حداکثر سهمهای سبد
PORTFOLIO_WEIGHT_CAP_PCT = 20.0   # سقف وزن هر سهم (٪) — بازهٔ راهبردی ۱۰ تا ۲۰

ASSET_KIND_BY_MODE = {"free": "dollar", "mandatory": "rial", "neutral": ""}
