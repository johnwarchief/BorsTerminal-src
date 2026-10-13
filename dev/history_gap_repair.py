# dev/history_gap_repair.py — RC4 (بخشِ C): تشخیصِ تکرارپذیرِ شکافِ پوشش + ترمیمِ idempotent
#
# ریشۀِ شکاف (سنجیدۀِ مرحلۀِ ۲، `_audit/ra365_phase2_coverage.py`): `/api/chart` (CDN، پیمایشِ
# کاملِ CSV) تاریخ‌هایی برمی‌گرداند که درِ `/api/chart-db` (= `price_history`) نیستند؛ ۴٬۳۴۷ روزِ
# مفقود، همۀ writer_gap. علت: increment درِ `test_tsetmc._history_start` فقط از `MAX(date)`ِ خودِ
# نماد به جلو می‌رود، پس هرگز سطری که درِ یک دورۀِ خاموشِ sync از دست رفته را برنمی‌دارد؛ عمقِ
# پیشِ آwitch هم با `backfill=False` گرفته نشده.
#
# ترمیم = همان `fetch_price_history(backfill=True)` که از `CSV_FLOOR` دوباره می‌پیماید و با
# `candle_contract.UPSERT_SQL` (کلیدِ ON CONFLICT(symbol,date) + قیدِ اولویتِ src) می‌نویسد:
# idempotent، بی‌حذف، بی‌بازنویسیِ ردیفِ «منتشرشده» با منبعِ ضعیف‌تر (board). این فایل دو واحدِ
# خالصِ آزمودنی از همان مسیر بیرون می‌کشد:
#   • missing_blocks(expected, actual) → شمارش/بازۀِ شکاف، بدونِ شبکه، کاملاً تکرارپذیر.
#   • repair_from_bars(conn, symbol, bars, dry_run) → پرکردنِ «فقطِ روزهایِ مفقود» با همان UPSERT،
#     داخلِ یکِ تراکنش. هیچ روزی بدونِ barِ مبدأ ساخته نمی‌شود (جعلِ open/last ممنوع). dry_run
#     هیچ نوشتن ندارد.
#
# محدودیتِ قطعیِ این مأموریت: اجرایِ واقعیِ ترمیم رویِ `market.db` عملیاتی مجاز نیست؛ CLI فقط
# --dry-run طرح می‌دهد و نوشتنِ عملیاتی صریحاً بی‌اجرا می‌ماند (پس از تأیید جداگانۀِ مالک).
import os
import sys
import argparse
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import candle_contract  # noqa: E402


def missing_blocks(expected, actual):
    """expected/actual: هر مجموعه/فهرستِ تاریخِ 'YYYY-MM-DD'. → [(start, end, count)] برایِ
    بلوک‌هایِ پیوستۀ «درِ منبع هست، درِ بانک نیست». پیوستگی رویِ *ترتیبِ تاریخ‌هایِ منبع*
    سنجیده می‌شود (نه تقویمِ روزشمار)، پس تعطیلی/جمعه شکافِ جعلی نمی‌سازد.
    """
    exp = sorted(set(expected))
    have = set(actual)
    blocks, cur = [], []
    for d in exp:
        if d in have:
            if cur:
                blocks.append((cur[0], cur[-1], len(cur)))
                cur = []
        else:
            cur.append(d)
    if cur:
        blocks.append((cur[0], cur[-1], len(cur)))
    return blocks


def gap_plan(conn, symbol, expected_dates):
    """فقط‌خواندنی: طرحِ شکافِ یکِ نماد نسبت به setِ تاریخ‌هایِ مبدأ."""
    actual = {r[0] for r in conn.execute(
        "SELECT date FROM price_history WHERE symbol=?", (symbol,))}
    blocks = missing_blocks(expected_dates, actual)
    return {"symbol": symbol, "expected": len(set(expected_dates)), "present": len(actual),
            "missing": sum(b[2] for b in blocks), "blocks": blocks}


def repair_from_bars(conn, symbol, bars, dry_run=False):
    """ترمیمِ idempotentِ شکاف. `bars` فهرستِ کندل‌هایِ candle_contract است (dict با time/open/.../src).

    قاعدۀِ امن: فقط رویِ روزهایی که *درِ بانک نیستند* نوشتن می‌شود؛ ردیفِ موجود هرگز دست
    نمی‌خورد (بی‌حذف، بی‌بازنویسی). بی‌بارِ مبدأ برایِ یکِ تاریخ، آن تاریخ ساخته نمی‌شود — پس
    open/last مفقود هرگز با close جعل نمی‌شود. dry_run هیچ نوشتن ندارد. برگشت:
      (filled_or_would_fill, skipped_present, skipped_no_source)
    """
    have = {r[0] for r in conn.execute("SELECT date FROM price_history WHERE symbol=?", (symbol,))}
    would_fill = present = no_source = 0
    try:
        conn.execute("BEGIN")
        for b in bars:
            d = b.get("time") or b.get("date")
            if not d:
                no_source += 1
                continue
            if d in have:
                present += 1                       # سطرِ معتبرِ موجود — بی‌دست‌زدن، بی‌duplicate
                continue
            # بی‌barِ معتبرِ مبدأ (بدنه/حجم) کندل ساخته نمی‌شود: candle() خودش None می‌دهد و
            # upsert_row نمی‌تواند چیزی جعل کند.
            if dry_run:
                would_fill += 1
                continue
            conn.execute(candle_contract.UPSERT_SQL, candle_contract.upsert_row(b))
            would_fill += 1
            have.add(d)                            # از میانیِ همین اجرا دوباره‌نویسی نشود
        if not dry_run:
            conn.commit()
        else:
            conn.rollback()                        # dry-run: هیچ اثری رویِ بانک نمی‌ماند
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    return would_fill, present, no_source


def main(argv=None):
    ap = argparse.ArgumentParser(description="طرحِ ترمیمِ شکافِ price_history (پیش‌فرضِ dry-run؛ نوشتن رویِ بانکِ عملیاتی مجاز نیست)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--symbol")
    ap.add_argument("--apply", action="store_true",
                    help="NEVER in this mission; operational backfill needs separate owner authorization")
    a = ap.parse_args(argv)
    if a.apply:
        sys.exit("applyِ عملیاتی درِ این مأموریت قفل است: ترمیمِ واقعیِ market.db پس از تأیید جداگانۀِ مالک.")
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)   # فقط‌خواندنی — نوشتن ناممکن
    try:
        syms = [a.symbol] if a.symbol else [r[0] for r in
                con.execute("SELECT DISTINCT symbol FROM price_history ORDER BY symbol")]
        total = 0
        for s in syms:
            dates = [r[0] for r in con.execute(
                "SELECT date FROM price_history WHERE symbol=? ORDER BY date", (s,))]
            if not dates:
                continue
            # طرحِ عمقِ محلی: فاصلۀِ روزشمارِ میانی که سطر ندارد (تقریبِ بی‌شبکه؛ مرجعِ کامل
            # فقط با backfillِ مجازِ CDN به‌دست می‌آید). این CLI «چقدر احتمالِ شکاف هست» را
            # نشان می‌دهد، نه شمارِ قطعی — شمارِ قطعیِ writer_gap درِ _audit است.
            import datetime as dt
            d0 = dt.date.fromisoformat(dates[0]); d1 = dt.date.fromisoformat(dates[-1])
            span = (d1 - d0).days + 1
            gap = max(0, span - len(dates))
            total += gap
            if gap and (not a.symbol or a.symbol == s):
                print(f"  {s:10s} depth[{dates[0]}..{dates[-1]}] rows={len(dates)} "
                      f"calendar_span={span} interior_gap_upper_bound={gap}")
        print(f"مجموعِ کرانِ بالایِ شکافِ میانی در {len(syms)} نماد: {total} (تقریبِ بی‌شبکه؛ "
              f"شمارِ قطعی از مقایسۀِ CDN↔بانک درِ `_audit/ra365_phase2_coverage.py` می‌آید).")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
