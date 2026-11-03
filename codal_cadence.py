# -*- coding: utf-8 -*-
"""codal_cadence.py — محاسبهٔ خالصِ پنجرهٔ انتشار و فاصلهٔ شبکه.

بدون I/O و بدون import از پروژه؛ `codal_pipeline` دادهٔ ساعت را می‌دهد و این
ماژول فقط تصمیم می‌گیرد «الان داخل پنجره‌ایم؟ چند ثانیه صبر کنیم؟».
"""
from __future__ import annotations

FAST_GAP_S = 600
SLOW_GAP_S = 3 * 3600
MIN_GAP_S = 60
DEFAULT_WINDOWS = ((8.0, 20.0),)


def windows_from_hour_counts(counts, min_samples=200, share=0.25):
    """هیستوگرامِ ۲۴ساعته ⇒ بازه‌های پیوستهٔ انتشار.

    نمونهٔ کم ⇒ پیش‌فرضِ ۸ تا ۲۰ (محافظه‌کارانه، بی‌ادعا). هر ساعتِ فعال =
    سهمی ≥ ۲۵٪ اوج؛ حاشیهٔ نیم‌ساعت چپ و یک‌ساعت‌ونیم راست؛ پنجره‌های نزدیک
    (< ۲ ساعت فاصله) یکی می‌شوند.
    """
    total = sum(int(v or 0) for v in (counts or {}).values())
    if total < int(min_samples):
        return list(DEFAULT_WINDOWS)
    peak = max([int(v or 0) for v in counts.values()] or [0])
    threshold = max(1, int(peak * float(share)))
    active = sorted(h for h in range(24) if int(counts.get(h, 0)) >= threshold)
    if not active:
        return list(DEFAULT_WINDOWS)
    spans = []
    start = prev = active[0]
    for h in active[1:]:
        if h == prev + 1:
            prev = h
            continue
        spans.append((start, prev))
        start = prev = h
    spans.append((start, prev))
    windows = []
    for a, b in spans:
        lo = max(0.0, float(a) - 0.5)
        hi = min(24.0, float(b) + 1.5)
        if windows and lo - windows[-1][1] < 2.0:
            windows[-1] = (windows[-1][0], max(windows[-1][1], hi))
        else:
            windows.append((lo, hi))
    return windows


def inside_window(hour, windows):
    h = float(hour)
    return any(float(lo) <= h < float(hi) for lo, hi in (windows or ()))


def gap_seconds(hour, windows, enabled=True, fast=FAST_GAP_S,
                slow=SLOW_GAP_S, jitter_s=0.0):
    base = fast if (enabled and inside_window(hour, windows)) else slow
    return max(MIN_GAP_S, int(base + float(jitter_s)))


def window_labels(windows):
    def fmt(x):
        h = int(x)
        m = int(round((float(x) - h) * 60))
        if m == 60:
            h, m = h + 1, 0
        return "%02d:%02d" % (h, m)
    return ["%s-%s" % (fmt(a), fmt(b)) for a, b in (windows or ())]
