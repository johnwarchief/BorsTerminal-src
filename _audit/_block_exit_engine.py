# ============================================================================
# taxonomyِ واحدِ سیگنال (دورِ J): هر پرچمِ موتور یک نقش دارد، نه بیشتر.
#   entry    → تریگرِ ورود، فقط رویِ کندلِ آخر
#   context  → موقعیت/ساختار؛ نه رأیِ ورود، نه امتیاز
#   warning  → هشدار (پایش/کاهش پوزیشن)؛ خروجِ تأییدشده نیست
#   exit     → خروجِ تأییدشده (یا حدِ ضرر)
# رابط و امتیازِ سیگنال همین جدول را می‌خوانند؛ هیچ‌کدام برایِ پرچمی نقشِ
# دیگری اختراع نمی‌کند (فیbo مثلاً context است، پس امتیازِ ورود نمی‌گیرد).
_FTS_ROLES = {
    "jet": "entry", "choch_bullish": "entry", "point_hunt": "entry",
    "double_bottom": "entry", "range_break": "entry", "hourglass": "entry",
    "fib_zone": "context", "trend": "context", "support_resistance": "context",
    "third_peak": "warning", "rsi_divergence": "warning",
    "rsi_rollover": "warning", "ma14_pending": "warning",
    "hard_stop": "exit", "ma14_exit": "exit", "choch_bearish": "exit",
    "channel_break": "exit", "double_top": "exit", "hs_break": "exit",
}

# برچسبِ فارسیِ تریگرها (متنِ رابط از همین جدول، نه از رشتهٔ ثابتِ کامپوننت)
_FTS_TRIGGER_LABELS = {
    "jet": "جت",
    "point_hunt": "شکار نقطه",
    "choch_bullish": "تغییرِ ساختارِ صعودی",
    "double_bottom": "کفِ دوقلو",
    "range_break": "شکستِ باکسِ رنج",
    "hourglass": "ساعتِ شنی",
}

# اولویتِ وضعیتِ عمومی (رأیِ مالک، دورِ J): از جدی‌ترین به کم‌اهمیت‌ترین
FTS_STATUS_PRIORITY = ("hard_stop", "confirmed_exit", "weekly_veto", "entry_trigger",
                       "warning", "context_only", "no_signal", "insufficient")

FTS_STATUS_TEXT = {
    "hard_stop": "حدِ ضررِ سخت خورده شد — خروج",
    "confirmed_exit": "خروجِ تأییدشده (موتورِ چهارلایه)",
    "weekly_veto": "وتوی تایم هفتگی — فرصت ورود نمی‌دهد",
    "entry_trigger": "تریگرِ فعال رویِ کندلِ امروز",
    "warning": "هشدار (پایش/کاهش پوزیشن) — خروجِ تأییدشده نیست",
    "context_only": "فقطِ موقعیت (کمربندِ فیبو یا ساختار) — سیگنالِ ورود نیست",
    "no_signal": "هیچِ سیگنالِ فعالی نیست",
    "insufficient": "داده برایِ داوری کافی نیست — سنجیده نشد",
}


def _fts_roles_table():
    """کپیِ جدولِ نقش‌ها — لایۀ نمایش این را می‌خواند تا نقش را دوباره نسازد."""
    return dict(_FTS_ROLES)


def _fts_status_block(candles, out):
    """وضعیتِ عمومیِ canonical از همان اعدادی که موتور منتشر کرده.

    یک‌جا حساب می‌شود تا رابط (کارتِ وضعیت، بج‌ها، سیگنالِ مستر) متنِ ثابتِ خودش
    را جایِ رأیِ موتور نگذارد: پیش از این کارتِ وضعیت هر حالتی را با «در انتظار
    شکست خط آبی» توضیح می‌داد، حتی وقتی موتور خروج یا جتِ فعال گفته بود.
    اولویت: حدِ ضرر ← خروجِ تأییدشده ← وتوی هفتگی ← تریگرِ امروز ← هشدار ←
    فقطِ موقعیت ← بی‌سیگنال ← بی‌داده.
    `trigger` فقط وقتی هست که یک ستاپِ «entry» رویِ **کندلِ آخر** فعال باشد، و
    تاریخش همان کندلِ تریگرِ موتور است (برایِ شکارِ نقطه: `trigger_date`، نه
    لنگرِ کفِ کانال). وتوی هفتگی بر تریگر غالب است: «پرواز» با وتو هم‌زمان
    منتشر نمی‌شود.
    خروجی: {'code','text','trigger','exits','warnings','unknown','vetoed',
            'priority','roles'}
    """
    last_date = str(candles[-1]["time"])[:10] if candles else None
    ex = out.get("exit_engine") or {}
    l1 = ex.get("l1") or {}
    l2 = ex.get("l2") or {}
    l3 = ex.get("l3") or {}
    l4 = ex.get("l4") or {}
    jet = out.get("jet") or {}
    choch = out.get("choch") or {}
    ph = out.get("point_hunt") or {}
    dbl = out.get("double_bottom") or {}
    box = out.get("range_box") or {}
    hg = out.get("hourglass") or {}
    fib = out.get("fib") or {}

    # --- تریگرِ فعلی (نقش entry) ---
    trig_candidates = [
        ("jet", jet.get("active"), jet.get("resistance"), last_date),
        ("point_hunt", ph.get("active"), ph.get("floor_price"), ph.get("trigger_date")),
        ("choch_bullish", choch.get("bullish"), choch.get("level"), last_date),
        ("double_bottom", dbl.get("active"), dbl.get("neckline"), last_date),
        ("range_break", box.get("active"), box.get("top"), last_date),
        ("hourglass", hg.get("active"), hg.get("ma52"), last_date),
    ]
    trig = None
    for kind, flag, price, date in trig_candidates:
        if flag is True and price is not None and date:
            trig = {"kind": kind, "price": price, "date": date,
                    "label": _FTS_TRIGGER_LABELS.get(kind, kind), "role": "entry"}
            break

    exit_flags = [("hard_stop", l1.get("stop_hit")),
                  ("choch_bearish", l2.get("choch_break")),
                  ("channel_break", l2.get("channel_break")),
                  ("double_top", l3.get("double_top")),
                  ("hs_break", l3.get("hs_break")),
                  ("ma14_exit", l1.get("ma14_exit"))]
    warn_flags = [("third_peak", l3.get("third_peak")),
                  ("rsi_divergence", l4.get("rsi_divergence")),
                  ("rsi_rollover", l4.get("rsi_rollover")),
                  ("ma14_pending", l1.get("ma14_exit_pending"))]
    all_flags = trig_candidates + exit_flags + warn_flags
    exits = [k for k, v in exit_flags if v is True]
    warnings = [k for k, v in warn_flags if v is True]
    unknown = [k for k, v in all_flags if v is None]
    measured = any(v is not None for _k, v in all_flags)
    vetoed = ((out.get("trend") or {}).get("matrix") or {}).get("decision") == "REJECT"
    in_fib = bool((fib.get("zone_33_40") or {}).get("in_zone")
                  or (fib.get("zone_618_70") or {}).get("in_zone"))

    if "hard_stop" in exits:
        code = "hard_stop"
    elif any(e != "hard_stop" for e in exits):
        code = "confirmed_exit"
    elif vetoed:
        code = "weekly_veto"
    elif trig is not None:
        code = "entry_trigger"
    elif warnings:
        code = "warning"
    elif in_fib:
        code = "context_only"
    elif not measured:
        code = "insufficient"
    else:
        code = "no_signal"

    text = FTS_STATUS_TEXT[code]
    if code == "entry_trigger":
        text = "%s: %s" % (text, trig["label"])
    if code == "weekly_veto" and jet.get("active") is True:
        text = "%s (جتِ امروز هم فعال است، ولی وتو بر ورود غالب است)" % text
    return {"code": code, "text": text, "trigger": trig,
            "exits": exits, "warnings": warnings, "unknown": unknown,
            "vetoed": bool(vetoed), "context_only": bool(in_fib and trig is None
                                                         and not exits and not warnings),
            "priority": list(FTS_STATUS_PRIORITY), "roles": dict(_FTS_ROLES)}


def _fts_exit_engine(candles, entry_hint=None):
    """FTS four-layer exit/stop engine - master assembler.

    Layers (each independently tri-state flagged, layer dict exposed verbatim):
      L1 hard stop + MA14 trailing body-exit  -> _fts_exit_layer1
      L2 structural breaks (CHoCH, channel)   -> _fts_exit_layer2
      L3 reversal patterns (3rd peak, DT, HS) -> _fts_exit_layer3
      L4 momentum (RSI divergence, rollover)  -> _fts_exit_layer4
    Verdict precedence (highest severity first):
      'stop'    - hard stop hit; position must be closed
      'exit'    - confirmed structural/pattern/trailing exit (L1 ma14, L2, L3)
      'caution' - soft warnings only (MA14 pending, divergence, rollover,
                  third peak) - reduce / monitor, do not add
      'hold'    - سنجیده شد و خروجی نیست
      'unknown' - هیچ لایه‌ای نتوانست بسنجد؛ «بی‌داده»، نه «خروجی ندارد»
    `signals` فقط پرچم‌های True را می‌شمارد و `unmeasured` آن‌هایی را که None
    ماندند؛ تفکیکِ این دو برایِ رابط لازم است (قاعدۀ null ≠ false).
    Input candles are DAILY OHLCV dicts (same shape as get_chart_db output).
    Output: {'verdict', 'signals', 'unmeasured', 'l1', 'l2', 'l3', 'l4'}.
    """
    l1 = _fts_exit_layer1(candles, entry_hint=entry_hint)
    swings_d = _fts_swings(candles, k=_FTS_SWING_K)
    l2 = _fts_exit_layer2(candles, swings_d)
    l3 = _fts_exit_layer3(candles, swings_d)
    l4 = _fts_exit_layer4(candles)
    flags = [("stop_hard", l1["stop_hit"]), ("ma14_trail", l1["ma14_exit"]),
             ("ma14_watch", l1["ma14_exit_pending"]),
             ("choch_break", l2["choch_break"]), ("channel_break", l2["channel_break"]),
             ("third_peak", l3["third_peak"]), ("double_top", l3["double_top"]),
             ("hs_break", l3["hs_break"]),
             ("rsi_divergence", l4["rsi_divergence"]),
             ("rsi_rollover", l4["rsi_rollover"])]
    signals = [k for k, v in flags if v is True]
    unmeasured = [k for k, v in flags if v is None]
    tr = lambda k: next((v for kk, v in flags if kk == k), None)
    if tr("stop_hard") is True:
        verdict = "stop"
    elif tr("ma14_trail") is True or tr("choch_break") is True \
            or tr("channel_break") is True or tr("double_top") is True \
            or tr("hs_break") is True:
        verdict = "exit"
    elif tr("ma14_watch") is True or tr("rsi_divergence") is True \
            or tr("rsi_rollover") is True or tr("third_peak") is True:
        verdict = "caution"
    elif any(v is False for _k, v in flags):
        verdict = "hold"
    else:
        verdict = "unknown"
    return {"verdict": verdict, "signals": signals, "unmeasured": unmeasured,
            "l1": l1, "l2": l2, "l3": l3, "l4": l4}
