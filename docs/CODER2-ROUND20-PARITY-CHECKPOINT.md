# Coder2 — Round 20 Parity Checkpoint

**تاریخ:** 2026-10-23  
**شاخه:** `mission/ra365-round20-raw-performance-adjusted-2026-10-23`  
**HEAD:** `b3d1686153c0`  
**مبنا:** `a36f4b0b`  
**Commit ابزار/تست/شواهد:** `c1f0cb78` + `b3d16861`  
**Gate:** `VERIFIED`

## وضعیت

- Raw منجمد: ۹۹٫۸۹۰۷٪ فیلد / ۹۹٫۸۲۲۱٪ ردیف؛ ۲٬۱۱۵ mismatch تعیین‌تکلیف؛ UNCLASSIFIED صفر.
- Raw live نمونه: ۷۰ از ۱۰۱ فیلد بد بسته شد؛ ۰ regression در همین نمونه؛ full live `NOT_MEASURED`.
- Adjusted: factor ۶۹٫۰۲۴۳٪، ±۱٪ ۸۸٫۰۸۲۳٪، OHLC ۶۸٫۳۰۴۵٪؛ runner با candle-closing بازتولید شد.
- DPS/اندوخته: PROVEN در marks sample؛ آورده/مطالبات: `UNVERIFIED` (S).
- Volume adjusted: ۱۰۰٫۰۰٪ برابر با خام در ۱٬۲۳۳٬۲۱۳ ردیف روزانه.
- هیچ تغییر production یا دیتابیس محافظت‌شده؛ Track B دست‌نخورده.

## Blocked

- `BLOCKED_REFERENCE_MARKS`: marks کامل بدون نشست مجاز/export.
- `BLOCKED_REFERENCE_EVENT_INPUT`: S پذیره و event-set مرجع.
- `BLOCKED_SOURCE_REFERENCE`: type0 در برابر TSETMC.
- `BLOCKED_REFERENCE_GEOMETRY`: flat/H-L نامعتبر type0.
- `NOT_MEASURED`: live full (کل Universe)، weekly aggregation، full marks.

## بازتولید

```bash
python tools/ra365_round16_parity.py --db D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db \
  --out artifacts/ra365/r20/adjusted-baseline-candle --candle-closing
python tools/ra365_round20_marks_oracle.py
python tools/ra365_round20_live_raw_recheck.py --limit-symbols 50
python tools/ra365_round20_reference_invariants.py
python dev/test_ra365_round20_formula_oracle_v1.py
```

## بعدی

marks کامل + S پذیره + live full با rate limit؛ بدون این شواهد ۱۰۰٪ ادعا نمی‌شود.
