import re

with open("api/chart.py", "r", encoding="utf-8") as f:
    content = f.read()

new_func = """def _fts_classify_trend(swings, tol=_FTS_EQUAL_TOL, series=None,
                        stale_bars=_FTS_STALE_BARS):
    \"\"\"طبقه‌بندی روند بر پایهٔ ساختار سقف/کف (هستهٔ متدولوژی FTS صفحهٔ ۲).

    دو سقف پیوت و دو کف پیوتِ آخر مقایسه می‌شوند:
        HH + HL → 'up'        (سقف بالاتر و کف بالاتر)
        LH + LL → 'down'      (سقف پایین‌تر و کف پایین‌تر)
    
    در حالت‌های دیگر (مثل یک LH کوچک در روند صعودی)، ساختار کلیدی بررسی می‌شود:
        - اگر کفِ ساختاری قبلی (HL) نشکسته باشد، روند همچنان صعودی می‌ماند.
        - اگر سقفِ ساختاری قبلی (LH) نشکسته باشد، روند همچنان نزولی می‌ماند.
        غیر آن → 'range'
    \"\"\"
    base = {"trend": "na", "hh": None, "hl": None, "basis": "pivots",
            "last_high": None, "prev_high": None, "last_low": None, "prev_low": None,
            "last_high_time": None, "prev_high_time": None,
            "last_low_time": None, "prev_low_time": None,
            "stale_bars": None, "window": None}
            
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    
    piv = None
    if len(highs) >= 2 and len(lows) >= 2:
        # 1. Stateful structure tracking
        struct_trend = "na"
        structural_high = None
        structural_low = None
        last_h = None
        last_l = None
        
        for s in swings:
            p = s["price"]
            k = s["kind"]
            if k == "high":
                if last_h is not None:
                    if p > last_h * (1 + tol):
                        if struct_trend != "up":
                            if structural_high is None or p > structural_high * (1 + tol):
                                if last_l is not None:
                                    struct_trend = "up"
                                    structural_low = last_l
                        else:
                            if last_l is not None and (structural_low is None or last_l > structural_low):
                                structural_low = last_l
                last_h = p
            else:
                if last_l is not None:
                    if p < last_l * (1 - tol):
                        if struct_trend != "down":
                            if structural_low is None or p < structural_low * (1 - tol):
                                if last_h is not None:
                                    struct_trend = "down"
                                    structural_high = last_h 
                        else:
                            if last_h is not None and (structural_high is None or last_h < structural_high):
                                structural_high = last_h
                last_l = p
        
        # 2. Local window comparison
        h2, h1 = highs[-2]["price"], highs[-1]["price"]
        l2, l1 = lows[-2]["price"], lows[-1]["price"]
        hh = h1 > h2 * (1 + tol)
        hl = l1 > l2 * (1 + tol)
        lh = h1 < h2 * (1 - tol)
        ll = l1 < l2 * (1 - tol)
        
        if hh and hl:
            trend = "up"
        elif lh and ll:
            trend = "down"
        else:
            # Fallback to structural trend if local is mixed (e.g. LH + HL)
            if struct_trend in ("up", "down"):
                # Check if current price breaks structural bounds?
                # The state machine already updated struct_trend to the latest state.
                # So if a small LH didn't break structural_low, struct_trend is still "up".
                trend = struct_trend
            else:
                trend = "range"
                
        piv = {"trend": trend, "hh": hh, "hl": hl, "basis": "pivots",
               "last_high": round(h1, 2), "prev_high": round(h2, 2),
               "last_low": round(l1, 2), "prev_low": round(l2, 2),
               "last_high_time": highs[-1].get("time"), "prev_high_time": highs[-2].get("time"),
               "last_low_time": lows[-1].get("time"), "prev_low_time": lows[-2].get("time"),
               "stale_bars": None, "window": None}

    if series is None:
        return piv if piv is not None else base
    n = len(series)
    newest = max((s["idx"] for s in swings), default=-1)
    gap = n - 1 - newest
    if piv is not None and gap <= stale_bars:
        return piv
    win = _fts_recent_window_trend(series)
    if win is None:
        return piv if piv is not None else base
    out = dict(win)
    out["stale_bars"] = gap
    out["last_pivot_time"] = series[newest].get("time") if 0 <= newest < n else None
    out["hh"] = None
    out["hl"] = None
    out["last_high"] = None
    out["prev_high"] = None
    out["last_low"] = None
    out["prev_low"] = None
    if piv is not None:
        out["pivots"] = piv
    return out"""

pattern = re.compile(r"def _fts_classify_trend.*?return out", re.DOTALL)
new_content = pattern.sub(new_func, content)

with open("api/chart.py", "w", encoding="utf-8") as f:
    f.write(new_content)
