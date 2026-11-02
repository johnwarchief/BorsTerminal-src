#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/intake_indicator.py -- خط لوله پذیرش، ممیزی و تبدیل اندیکاتورهای سفارشی

این اسکریپت فایل‌های موجود در docs/technical-indicators/inbox را اسکن کرده و:
۱. پارامترها، متغیرهای ورودی، دوره‌های هموارسازی و فرمول‌ها را استخراج می‌کند.
۲. ممیزی ضد ری‌پینتینگ و عدم تورش آینده‌نگر (Look-Ahead Bias) را اجرا می‌کند.
۳. متادیتای ساختاریافته برای ثبت در رجیستری و کدهای اورلی TypeScript برای KLineCharts v10 تولید می‌کند.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class IndicatorParam:
    name: str
    param_type: str
    default_value: Any
    description: str = ""


@dataclass
class RepaintingAudit:
    has_repainting_risk: bool
    negative_offsets: List[str] = field(default_factory=list)
    lookahead_flags: List[str] = field(default_factory=list)
    uses_unclosed_current_bar: bool = False
    verdict: str = "SAFE"  # "SAFE" | "REPAINTING_RISK" | "UNCLOSED_BAR_WARNING"
    notes_fa: str = ""


@dataclass
class IndicatorMetadata:
    id: str
    file_name: str
    file_path: str
    extension: str
    indicator_type: str  # "INDICATOR" | "EXPERT_ADVISOR" | "COMPILED_BINARY" | "PINE_SCRIPT"
    source_available: bool
    title: str = ""
    author: str = ""
    version: str = ""
    inputs: List[IndicatorParam] = field(default_factory=list)
    periods_and_smoothing: Dict[str, Any] = field(default_factory=dict)
    repainting_audit: Optional[RepaintingAudit] = None
    suggested_overlay_id: str = ""
    status: str = "PENDING_VERIFICATION"


def inspect_repainting_risk(code_text: str) -> bool:
    """
    سنجش سریع و بولین وجود خطر ری‌پینت و تورش آینده‌نگر (Look-Ahead Bias).
    در صورتی که آفست منفی ایندکس یا پارامتر آینده‌نگر یافت شود True برمی‌گرداند.
    """
    # ۱. جستجوی آفست‌های منفی ایندکس شمع‌ها مانند close[-2] یا series[-1]
    if re.search(r'\[\s*-\s*\d+\s*\]', code_text):
        return True

    # ۲. آفست‌های منفی در توابع پاین‌اسکریپت و MQL (مانند offset = -1)
    if re.search(r'offset\s*=\s*-\s*\d+', code_text, re.IGNORECASE):
        return True

    # ۳. فعال‌سازی صریح lookahead آینده‌نگر در پاین‌اسکریپت
    if re.search(r'lookahead\s*=\s*(?:barmerge\.)?lookahead_on', code_text, re.IGNORECASE):
        return True

    # ۴. شیفت منفی در توابع دسترسی داده MQL (مثلاً iClose(..., -1))
    if re.search(r'i(?:Close|Open|High|Low|Time|Volume|BarShift)\s*\([^)]*,[^\)]*-\s*\d+\s*\)', code_text):
        return True

    return False


def audit_lookahead_and_repainting(code_text: str) -> RepaintingAudit:
    """
    ممیزی جامع و گزارش تفصیلی از عدم ری‌پینتینگ و رعایت محاسبات روی کندل‌های بسته‌شده.
    """
    neg_offsets = re.findall(r'\[\s*-\s*\d+\s*\]', code_text)
    lookahead_flags: List[str] = []

    if re.search(r'offset\s*=\s*-\s*\d+', code_text, re.IGNORECASE):
        lookahead_flags.append("negative_offset_parameter")

    if re.search(r'lookahead\s*=\s*(?:barmerge\.)?lookahead_on', code_text, re.IGNORECASE):
        lookahead_flags.append("barmerge_lookahead_on")

    mql_neg = re.findall(r'i(?:Close|Open|High|Low|Time|Volume|BarShift)\s*\([^)]*,[^\)]*-\s*\d+\s*\)', code_text)
    if mql_neg:
        lookahead_flags.extend(mql_neg)

    has_risk = bool(neg_offsets or lookahead_flags)

    # بررسی استفاده از کندل جاری باز (bar 0) به جای کندل بسته شده (bar 1+)
    unclosed = False
    if re.search(r'\[\s*0\s*\]', code_text) or re.search(r'i(?:Close|Open|High|Low)\s*\([^)]*,\s*0\s*\)', code_text):
        unclosed = True

    if has_risk:
        verdict = "REPAINTING_RISK"
        notes_fa = "خطر ری‌پینتینگ: ارجاع آینده‌نگر یا آفست منفی شناسایی شد."
    elif unclosed:
        verdict = "UNCLOSED_BAR_WARNING"
        notes_fa = "محاسبات شامل کندل باز جاری است؛ سیگنال تا پایان بسته‌شدن کندل قطعی نیست."
    else:
        verdict = "SAFE"
        notes_fa = "محاسبات صرفاً روی کندل‌های قطعی و بسته‌شده انجام می‌شود (بدون ری‌پینت)."

    return RepaintingAudit(
        has_repainting_risk=has_risk,
        negative_offsets=neg_offsets,
        lookahead_flags=lookahead_flags,
        uses_unclosed_current_bar=unclosed,
        verdict=verdict,
        notes_fa=notes_fa,
    )


def read_file_safely(file_path: Path) -> str:
    """خواندن فایل با آزمون ترتیبی انکودینگ‌های رایج."""
    for enc in ("utf-8", "utf-16", "utf-16le", "cp1256", "cp1252", "latin1"):
        try:
            return file_path.read_text(encoding=enc)
        except Exception:
            continue
    return file_path.read_text(encoding="latin1", errors="replace")


def parse_mql_inputs(code: str) -> List[IndicatorParam]:
    """استخراج پارامترهای extern و input از کدهای MQL4/MQL5."""
    params: List[IndicatorParam] = []
    pattern = re.compile(
        r'^\s*(?:extern|input)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*=\s*([^;]+);(?:\s*//\s*(.*))?$',
        re.MULTILINE,
    )
    for match in pattern.finditer(code):
        ptype, pname, pval, pdesc = match.groups()
        val_str = pval.strip()
        val: Any = val_str
        # تبدیل نوع ساده
        if val_str.lower() == "true":
            val = True
        elif val_str.lower() == "false":
            val = False
        else:
            try:
                if "." in val_str:
                    val = float(val_str)
                else:
                    val = int(val_str)
            except ValueError:
                pass
        desc = (pdesc or "").strip()
        params.append(IndicatorParam(name=pname, param_type=ptype, default_value=val, description=desc))
    return params


def parse_pine_inputs(code: str) -> List[IndicatorParam]:
    """استخراج پارامترهای ورودی از کدهای Pine Script."""
    params: List[IndicatorParam] = []
    pattern = re.compile(
        r'([A-Za-z0-9_]+)\s*=\s*input(?:\.([a-z]+))?\s*\(\s*([^,)\n]+)(?:,\s*(?:title\s*=\s*)?["\']([^"\']+)["\'])?[^)]*\)',
        re.MULTILINE,
    )
    for match in pattern.finditer(code):
        pname, ptype_hint, defval, title = match.groups()
        val_str = defval.strip()
        val: Any = val_str
        if val_str.lower() == "true":
            val = True
        elif val_str.lower() == "false":
            val = False
        else:
            try:
                if "." in val_str:
                    val = float(val_str)
                else:
                    val = int(val_str)
            except ValueError:
                pass
        params.append(
            IndicatorParam(
                name=pname,
                param_type=ptype_hint or "auto",
                default_value=val,
                description=(title or "").strip(),
            )
        )
    return params


def detect_indicator_type(code: str, extension: str) -> str:
    """تشخیص نوع ماژول: اندیکاتور، اکسپرت یا اسکریپت."""
    if extension in (".ex4", ".ex5"):
        return "COMPILED_BINARY"

    if re.search(r'\b(OrderSend|OrdersTotal|OrderSelect|PositionOpen|CTrade)\b', code):
        return "EXPERT_ADVISOR"

    if re.search(r'indicator\s*\(|#property\s+indicator_', code):
        return "INDICATOR"

    if extension == ".pine":
        return "PINE_SCRIPT"

    return "INDICATOR"


def parse_source_indicator(file_path: Path) -> IndicatorMetadata:
    """تجزیه فایل سورس منبع اندیکاتور یا اکسپرت."""
    code = read_file_safely(file_path)
    ext = file_path.suffix.lower()

    ind_type = detect_indicator_type(code, ext)
    audit = audit_lookahead_and_repainting(code)

    # استخراج ورودی‌ها
    inputs: List[IndicatorParam] = []
    if ext in (".mq4", ".mq5"):
        inputs = parse_mql_inputs(code)
    else:
        inputs = parse_pine_inputs(code)

    # استخراج عنوان و فراداده‌ها
    title_match = re.search(r'#property\s+copyright\s+["\']([^"\']+)["\']', code)
    author = title_match.group(1) if title_match else ""

    ver_match = re.search(r'#property\s+version\s+["\']([^"\']+)["\']', code)
    version = ver_match.group(1) if ver_match else ""

    pine_title = re.search(r'indicator\s*\(\s*(?:title\s*=\s*)?["\']([^"\']+)["\']', code)
    title = pine_title.group(1) if pine_title else file_path.stem

    # استخراج متغیرهای مربوط به دوره و هموارسازی
    periods: Dict[str, Any] = {}
    for p in inputs:
        low = p.name.lower()
        if any(k in low for k in ("period", "length", "atr", "ema", "sma", "rsi", "swing", "smooth", "mult")):
            periods[p.name] = p.default_value

    clean_id = re.sub(r'[^a-zA-Z0-9_]', '', file_path.stem)
    return IndicatorMetadata(
        id=clean_id,
        file_name=file_path.name,
        file_path=str(file_path),
        extension=ext,
        indicator_type=ind_type,
        source_available=True,
        title=title,
        author=author,
        version=version,
        inputs=inputs,
        periods_and_smoothing=periods,
        repainting_audit=audit,
        suggested_overlay_id=clean_id,
        status="AUDITED_SAFE" if audit.verdict == "SAFE" else "AUDITED_FLAGGED",
    )


def handle_compiled_binary(file_path: Path) -> IndicatorMetadata:
    """ثبت فایل کامپایل‌شده فاقد سورس جهت بازپیاده‌سازی مرجع."""
    clean_id = re.sub(r'[^a-zA-Z0-9_]', '', file_path.stem)
    known_defaults: Dict[str, Any] = {}

    lower = file_path.name.lower()
    if "supertrend" in lower:
        clean_id = "SuperTrendHeikinAshi"
        known_defaults = {"atrPeriod": 10, "multiplier": 3.0}
    elif "fiborsi8" in lower:
        clean_id = "FiboRSI8"
        known_defaults = {"rsiPeriod": 8, "oversold": 23.6, "overbought": 78.6}
    elif "rsi ma" in lower or "divergence" in lower:
        clean_id = "RsiMaSmooth"
        known_defaults = {"rsiPeriod": 14, "smoothingPeriod": 9, "divergenceLookback": 20}
    elif "breakout retest" in lower:
        clean_id = "BreakoutRetestPro"
        known_defaults = {"swingLength": 10, "impulseMult": 1.5, "retestAtr": 0.5}

    return IndicatorMetadata(
        id=clean_id,
        file_name=file_path.name,
        file_path=str(file_path),
        extension=file_path.suffix.lower(),
        indicator_type="COMPILED_BINARY",
        source_available=False,
        title=file_path.stem,
        inputs=[IndicatorParam(k, "number", v, "پارامتر پیش‌فرض مرجع") for k, v in known_defaults.items()],
        periods_and_smoothing=known_defaults,
        repainting_audit=RepaintingAudit(
            has_repainting_risk=False,
            verdict="SAFE",
            notes_fa="فایل اجرایی کامپایل‌شده؛ منطق در فرانت‌اند با فرمول استاندارد بدون ری‌پینت بازپیاده‌سازی می‌شود.",
        ),
        suggested_overlay_id=clean_id,
        status="REQUIRES_REFERENCE_REVERSE_ENGINEERING",
    )


def scan_inbox_directory(inbox_dir: str | Path = "docs/technical-indicators/inbox") -> List[IndicatorMetadata]:
    """اسکن کامل پوشه ورودی اندیکاتورها و استخراج تمام اقلام."""
    p = Path(inbox_dir)
    if not p.exists() or not p.is_dir():
        return []

    results: List[IndicatorMetadata] = []
    # فیلتر پسوندهای مدنظر
    valid_extensions = {".mq4", ".mq5", ".ex4", ".ex5", ".pine", ".txt"}

    for item in sorted(p.iterdir()):
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        if ext not in valid_extensions:
            continue

        if ext in (".ex4", ".ex5"):
            results.append(handle_compiled_binary(item))
        else:
            # بررسی فایل متنی / سورس
            meta = parse_source_indicator(item)
            results.append(meta)

    return results


def generate_kline_overlay(indicator_name: str, params: Optional[Dict[str, Any]] = None) -> str:
    """تولید کد قالب اورلی تایپ‌اسکریپت برای KLineCharts v10."""
    p_dict = params or {}
    params_comment = json.dumps(p_dict, indent=2, ensure_ascii=False)
    return f"""// Generated by tools/intake_indicator.py for KLineCharts v10
import {{ registerOverlay }} from 'klinecharts';
import type {{ OverlayTemplate, OverlayFigure, OverlayCreateFiguresCallbackParams }} from 'klinecharts';

/*
Default Parameters:
{params_comment}
*/

export function register{indicator_name}Overlay(): void {{
  const template: OverlayTemplate = {{
    name: '{indicator_name}',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {{
      const {{ chart, bounding, xAxis, yAxis }} = params;
      const dataList = chart.getDataList();
      if (!dataList || dataList.length === 0) return [];

      const figures: OverlayFigure[] = [];
      // Closed candles only calculation (No-Repainting)
      return figures;
    }},
  }};

  try {{
    registerOverlay(template);
  }} catch {{
    // Idempotent registration guard
  }}
}}
"""


def generate_intake_report(metadata_list: List[IndicatorMetadata]) -> str:
    """تولید گزارش ممیزی پذیرش اندیکاتورها به زبان فارسی."""
    lines: List[str] = [
        "# کارنامه ممیزی و پذیرش اندیکاتورهای سفارشی (Indicator Intake Audit)",
        "",
        f"تعداد کل اقلام پردازش‌شده: {len(metadata_list)}",
        "",
        "| شناسه | فایل | نوع | سورس؟ | ری‌پینت؟ | داوری | اورلی پیشنهادی |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in metadata_list:
        rep = "خطر" if m.repainting_audit and m.repainting_audit.has_repainting_risk else "پاک"
        src = "بله" if m.source_available else "خیر (باینری)"
        verd = m.repainting_audit.verdict if m.repainting_audit else "UNKNOWN"
        lines.append(
            f"| `{m.id}` | `{m.file_name}` | `{m.indicator_type}` | {src} | {rep} | `{verd}` | `{m.suggested_overlay_id}` |"
        )

    lines.append("")
    lines.append("## جزئیات پارامترها و تنظیمات استخراج‌شده:")
    lines.append("")
    for m in metadata_list:
        lines.append(f"### {m.id} ({m.file_name})")
        lines.append(f"- **نوع:** {m.indicator_type}")
        lines.append(f"- **وضعیت:** {m.status}")
        if m.repainting_audit:
            lines.append(f"- **یادداشت ممیزی:** {m.repainting_audit.notes_fa}")
        if m.inputs:
            lines.append("- **پارامترهای ورودی:**")
            for inp in m.inputs[:12]:
                desc = f" ({inp.description})" if inp.description else ""
                lines.append(f"  - `{inp.name}`: `{inp.default_value}` [{inp.param_type}]{desc}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="ابزار ممیزی و پذیرش اندیکاتورهای ورودی")
    parser.add_argument(
        "--scan",
        default="docs/technical-indicators/inbox",
        help="مسیر پوشه صندوق ورودی اندیکاتورها",
    )
    parser.add_argument("--out", default=None, help="مسیر خروجی گزارش JSON یا Markdown")
    parser.add_argument("--generate-ts", default=None, help="نام اندیکاتور برای تولید کد تایپ‌اسکریپت")

    args = parser.parse_args()

    if args.generate_ts:
        ts_code = generate_kline_overlay(args.generate_ts)
        print(ts_code)
        return

    items = scan_inbox_directory(args.scan)
    report_md = generate_intake_report(items)

    if args.out:
        out_p = Path(args.out)
        if out_p.suffix == ".json":
            serializable = [asdict(item) for item in items]
            out_p.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out_p.write_text(report_md, encoding="utf-8")
        print(f"گزارش در {args.out} ذخیره شد.")
    else:
        print(report_md)


if __name__ == "__main__":
    main()
