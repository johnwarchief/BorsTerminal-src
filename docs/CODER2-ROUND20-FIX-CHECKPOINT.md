# Coder2 — Round 20 Raw Field Fix Checkpoint

**تاریخ:** 2026-10-23  
**شاخه:** `mission/ra365-round20-real-fixes-2026-10-23`  
**HEAD:** `376d03de0228`  
**مبنا:** `1cf886ea`  
**Commitها:** `376d03de`  
**Gate:** `VERIFIED`

## وضعیت

- Raw literal قبل/بعد روی ۱٬۱۹۱٬۸۰۵ ردیف: **۸۷٫۳۴۲۱٪ → ۹۹٫۸۱۰۴٪**؛ high_raw ۹۱٫۴۵۶۷٪ → ۹۹٫۹۳۲۰٪.
- residual: ۲٬۲۶۰ ردیف / ۳٬۶۳۴ فیلد؛ همه سمت type0 vs CSV؛ ۲۶۶ parser-skip (۲۰۲۳-۰۳-۲۷) جدا.
- Type7 ۲۹نمادی: ۲۲٫۸۱٪ در تلورانس، میانه ۰٫۲۱۶۲٪، p90 ۱٫۴۳۶۰٪، p99 ۷٫۰۴۷۵٪؛ بدون تغییر production.
- Weekly volume: جمع ۳٬۹۷۰/۳٬۹۹۵؛ first-day ۷۳ — قانون روز اول اعمال نشد.
- Monthly: `NOT_MEASURED` (مرجع M ندارد).
- Local DB raw: `BLOCKED_LOCALDB_RAW_SCHEMA`.
- دیتابیس محافظت‌شده: `7b933b05d03b…` / `8fb85f381317…` بدون تغییر.

## بازتولید

```bash
python dev/test_round18_raw_parity_v1.py
python tools/ra365_round20_raw_replay.py
python _audit/ra365_ledger_ab.py
python _audit/r20_v10_per_symbol.py
python tools/ra365_round20_type7_evidence.py
```

## بعدی

- ML local DB raw schema/backfill (با تأیید جداگانه؛ اکنون عملیاتی دست‌نخورده).
- marks کامل/CODAL S برای type7؛ بدون آن ۱۰۰٪ ادعا نمی‌شود.
