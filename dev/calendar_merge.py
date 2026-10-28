# -*- coding: utf-8 -*-
"""dev/calendar_merge.py — ادغامِ افزایشیِ کشِ تقویم (Task 7).

قرارداد:
    merge_calendar(old: dict, new: dict) -> dict

  * رویدادها بر پایهٔ ``(نماد، دسته، تاریخ، عنوان)`` یکتا می‌شوند؛ ردیفِ
    قدیمی حفظ می‌شود و ردیفِ تکراریِ تازه کنار گذاشته می‌شود.
  * ``meta.fetchedAt`` از payloadِ تازه می‌آید، ``meta.count`` دوباره
    شمرده می‌شود، و ``meta.industries``/``meta.jmonths`` افزایشی‌اند تا
    رویدادهایِ قدیمی صنعت/ماهِ خود را از دست ندهند.
  * ورودیِ خالی/ناقص هرگز exception نمی‌دهد: خروجی همیشه یک dict با
    کلیدهایِ ``meta``/``events`` (و ``token``) است.

«دسته» در کشِ خام ستونِ مستقلی ندارد؛ نزدیک‌ترین نشانگرِ پایدار
``event_type_id`` است (دستهٔ نمایشیِ فرانت از عنوان+tid ساخته می‌شود).
اگر مصرف‌کننده‌ای کلیدِ ``cat`` را روی ردیف گذاشته باشد، همان اولویت دارد.
"""
from datetime import datetime, timezone


def _events(payload):
    if not isinstance(payload, dict):
        return []
    events = payload.get("events")
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def _meta(payload):
    if not isinstance(payload, dict):
        return {}
    meta = payload.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def _cat(ev):
    """نشانگرِ دسته: ``cat`` صریح، وگرنه ``event_type_id`` خام."""
    if ev.get("cat") not in (None, ""):
        return str(ev.get("cat")).strip()
    tid = ev.get("event_type_id")
    return "" if tid is None else str(tid).strip()


def _title(ev):
    return str(ev.get("event_title") or ev.get("description") or "").strip()


def _date(ev):
    # فقط بخشِ تاریخ؛ تغییرِ جزئیِ ساعت نباید ردیفِ یک رویداد را دوتا کند.
    raw = str(ev.get("date_time") or ev.get("date") or "").strip()
    return raw[:10] if len(raw) >= 10 else raw


def event_key(ev):
    """کلیدِ یکتاییِ یک رویداد — برایِ تست و مصرفِ بیرونی."""
    return (str(ev.get("asset_symbol_trade") or "").strip(),
            _cat(ev), _date(ev), _title(ev))


def _merge_meta(old_meta, new_meta):
    meta = dict(old_meta)
    meta.update(new_meta)
    industries = dict(old_meta.get("industries") or {})
    industries.update(new_meta.get("industries") or {})
    if industries:
        meta["industries"] = industries
    jmonths = []
    for source in (old_meta.get("jmonths"), new_meta.get("jmonths")):
        if not isinstance(source, list):
            continue
        for item in source:
            if item not in jmonths:
                jmonths.append(item)
    if jmonths:
        meta["jmonths"] = jmonths
    return meta


def merge_calendar(old, new):
    """کشِ قدیمی + payloadِ تازه → payloadِ ادغام‌شده (بدونِ نوشتنِ فایل)."""
    old_meta, new_meta = _meta(old), _meta(new)
    merged, seen = [], set()
    for ev in _events(old) + _events(new):
        key = event_key(ev)
        if key in seen:
            continue
        seen.add(key)
        merged.append(ev)
    merged.sort(key=lambda e: str(e.get("date_time") or e.get("date") or ""))

    meta = _merge_meta(old_meta, new_meta)
    meta["fetchedAt"] = (str(new_meta.get("fetchedAt") or "").strip()
                         or old_meta.get("fetchedAt")
                         or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    meta["count"] = len(merged)

    token = old.get("token") if isinstance(old, dict) else None
    if token is None and isinstance(new, dict):
        token = new.get("token")
    return {"meta": meta, "token": token, "events": merged}
