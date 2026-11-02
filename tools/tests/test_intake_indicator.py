#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/tests/test_intake_indicator.py -- آزمون‌های خط لوله پذیرش و ممیزی اندیکاتورها
"""

import sys
from pathlib import Path

import pytest

# افزودن ریشه پروژه به مسیر جهت ایمپورت مستقیم tools
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.intake_indicator import (
    audit_lookahead_and_repainting,
    generate_kline_overlay,
    inspect_repainting_risk,
    parse_source_indicator,
    scan_inbox_directory,
)


def test_detect_lookahead_offset():
    """آزمون تشخیص آفست‌های منفی آینده‌نگر (Look-Ahead Bias) و کدهای ایمن."""
    risky_code = "val = close[-2] + open[-1]"
    assert inspect_repainting_risk(risky_code) is True

    safe_code = "val = close[1] + high[1]"
    assert inspect_repainting_risk(safe_code) is False

    # آزمون تنظیمات پاین‌اسکریپت با آفست منفی
    pine_risky = 'plot(sma, offset = -3, title = "Forward MA")'
    assert inspect_repainting_risk(pine_risky) is True

    # آزمون تنظیمات بافر MQL با شیفت منفی
    mql_risky = "double future_close = iClose(_Symbol, PERIOD_CURRENT, -1);"
    assert inspect_repainting_risk(mql_risky) is True


def test_audit_lookahead_details():
    """آزمون گزارش تفصیلی ممیزی و هشدارهای کندل جاری باز."""
    risky_code = "val = close[-2] + open[-1]"
    audit_risky = audit_lookahead_and_repainting(risky_code)
    assert audit_risky.has_repainting_risk is True
    assert audit_risky.verdict == "REPAINTING_RISK"
    assert len(audit_risky.negative_offsets) >= 1

    closed_safe_code = "double c1 = GetClose(1); double h1 = GetHigh(1);"
    audit_safe = audit_lookahead_and_repainting(closed_safe_code)
    assert audit_safe.has_repainting_risk is False
    assert audit_safe.verdict == "SAFE"


def test_scan_inbox_directory():
    """آزمون اسکن پوشه docs/technical-indicators/inbox و شناسایی اقلام."""
    inbox_path = ROOT_DIR / "docs" / "technical-indicators" / "inbox"
    results = scan_inbox_directory(inbox_path)

    assert len(results) > 0, "پوشه inbox نباید خالی باشد"

    # بررسی حضور اندیکاتورهای چهارگانه در متادیتا
    found_brt = False
    found_supertrend = False
    found_fiborsi8 = False
    found_rsima = False

    for item in results:
        fname = item.file_name.lower()
        if "breakout retest pro" in fname and item.extension == ".mq4":
            found_brt = True
            assert item.source_available is True
            assert item.indicator_type in ("INDICATOR", "EXPERT_ADVISOR")
        elif "supertrend" in fname and item.extension == ".ex4":
            found_supertrend = True
            assert item.source_available is False
            assert item.indicator_type == "COMPILED_BINARY"
        elif "fiborsi8" in fname and item.extension == ".ex5":
            found_fiborsi8 = True
            assert item.source_available is False
            assert item.indicator_type == "COMPILED_BINARY"
        elif "rsi ma - smooth" in fname and item.extension == ".ex4":
            found_rsima = True
            assert item.source_available is False
            assert item.indicator_type == "COMPILED_BINARY"

    assert found_brt, "Breakout Retest Pro EA .mq4 یافت نشد"
    assert found_supertrend, "SuperTrend(wHA) .ex4 یافت نشد"
    assert found_fiborsi8, "FiboRSI8_SingleShot .ex5 یافت نشد"
    assert found_rsima, "rsi ma - smooth .ex4 یافت نشد"


def test_metadata_extraction():
    """آزمون استخراج پارامترهای ورودی و تنظیمات هموارسازی از سورس MQL."""
    inbox_path = ROOT_DIR / "docs" / "technical-indicators" / "inbox"
    mq4_file = inbox_path / "Breakout Retest Pro EA Source Code @IndicatorsforTV.mq4"

    meta = parse_source_indicator(mq4_file)
    assert meta.source_available is True
    assert meta.extension == ".mq4"

    # بررسی پارامترهای استخراج‌شده
    params_dict = {p.name: p.default_value for p in meta.inputs}
    assert "Buy_SwingLength" in params_dict
    assert params_dict["Buy_SwingLength"] == 10
    assert "Buy_ImpulseMult" in params_dict
    assert params_dict["Buy_ImpulseMult"] == 1.5
    assert "Buy_BreakConfirm" in params_dict
    assert params_dict["Buy_BreakConfirm"] == 2
    assert "TrendSMA" in params_dict
    assert params_dict["TrendSMA"] == 50

    # بررسی ممیزی ری‌پینتینگ: کد بر پایه کندل‌های بسته است
    assert meta.repainting_audit is not None
    assert meta.repainting_audit.has_repainting_risk is False


def test_generate_kline_overlay():
    """آزمون تولید کد قالب ثبت اورلی KLineCharts v10."""
    code = generate_kline_overlay("SuperTrendHeikinAshi", {"atrPeriod": 10, "multiplier": 3.0})
    assert "registerSuperTrendHeikinAshiOverlay" in code
    assert "SuperTrendHeikinAshi" in code
    assert "registerOverlay" in code
    assert "klinecharts" in code
