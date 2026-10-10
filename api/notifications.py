"""api/notifications.py — مرکزِ اعلانِ درون‌برنامه (بند ۶ مأموریت).

منبع، همان `codal_notices`ِ خودِ برنامه است که سینکِ کدال پر می‌کند؛ هیچ
سرویسِ بیرونیِ تازه‌ای افزوده نشده و هیچ تیترِ ساختگی سرو نمی‌شود. نوع و
اهمیت از `notifications.py` می‌آید (تک‌تعریف)، و سلامتِ خودِ منبع با
`/api/notifications/sources` خوانده می‌شود تا «چیزی نیست» از «نرسیده»
جدا بماند.

خواندنی است و بی‌کشِ جدا: `codal_notices` خودش درِ `market.db` می‌نشیند و
هر واکشیِ کدال آن را تازه می‌کند. نوشتنِ وضعیتِ «خوانده‌شده» درِ این لایه
نیست — درِ localStorageِ همین دستگاه می‌ماند، پس دو بک‌اند هم‌زمان رویِ
یک بانک با هم نمی‌جنگند (قیدِ تک‌نویسنده).
"""
from ._core import get_db
from fastapi import APIRouter
from fastapi import Query

import notifications as N

router = APIRouter()


@router.get("/api/notifications/sources")
def notifications_sources():
    """سلامتِ منبعِ اطلاعیه‌ها: چند ردیف، تازه‌ترینِ انتشار، آخرینِ واکشی."""
    conn = get_db()
    try:
        return N.sources(conn)
    finally:
        conn.close()


@router.get("/api/notifications/feed")
def notifications_feed(since: str = Query(""), levels: str = Query(""),
                       limit: int = Query(120)):
    """تازه‌ترینِ اطلاعیه‌ها با نوع/اهمیتِ توضیح‌دادنی و بی‌تکرار.

    `levels=high,medium` فیلترِ انتخابیِ خودِ کاربر است؛ `since` تاریخِ
    جلالیِ خودِ کدال. هیچ‌کدام دروازۀ «بیشتر بخوان»ِ بی‌حد نیست: سقفِ
    پاسخ درِ خودِ لایه بسته است.
    """
    conn = get_db()
    try:
        want = [x for x in str(levels or "").split(",") if x.strip()]
        return N.feed(conn, since=str(since or "").strip() or None,
                      levels=want, limit=int(limit or 120))
    finally:
        conn.close()
