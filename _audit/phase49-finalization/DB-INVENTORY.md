# Phase 4.9 finalization — DB-wide inventory

- DB: `_audit/phase49-finalization/db/restored-work.db` (restored isolated copy of the Phase 4.8 work DB)
- Price rows: **511139**; trading dates: **4056** (2010-01-02 .. 2026-11-09)
- Symbols with history: **6103**; in `instruments`: **5941**
- Instruments without history: **1306**; history not in instruments: **1468**

## Coverage

| metric | value |
| --- | ---: |
| Product events (stored) | 12829 |
| Product events pre-2020 | 4954 |
| Symbols with product events | 1087 |
| Pack replace steps | 6631 |
| Pack steps pre-2020 | 76 |
| Symbols with pack steps | 827 |
| Symbols with official ledger rows | 674 |

| history depth | symbols |
| --- | ---: |
| 10y+ | 25 |
| 5-10y | 2 |
| 1-5y | 822 |
| <1y | 5254 |

| freshness vs last DB session | symbols |
| --- | ---: |
| last_session | 29 |
| 1-5 sessions | 1 |
| 6-21 sessions | 2293 |
| >21 sessions | 3780 |

## Quality flags

| flag | symbols |
| --- | ---: |
| no_adjustment_evidence | 6328 |
| calendar_gaps | 4542 |
| open_eq_prev_close | 3548 |
| no_price_history | 1343 |
| has_product_events | 1087 |
| has_pack_steps | 827 |
| single_candle | 685 |
| has_official_ledger | 674 |
| has_pre2020_events | 557 |
| zero_fields | 44 |
| pack_pre2020 | 12 |

## The Phase 4.9 30

| symbol | rows | first | last | events | pre-2020 | pack | pack pre-2020 | ledger |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| شبندر | 2908 | 2012-06-24 | 2026-11-09 | 20 | 8 | 8 | 0 | yes |
| شپنا | 3339 | 2010-02-16 | 2026-11-09 | 27 | 12 | 14 | 0 | yes |
| فملي | 3741 | 2010-01-02 | 2026-11-09 | 32 | 16 | 13 | 0 | yes |
| فولاد | 3689 | 2010-01-02 | 2026-11-09 | 31 | 16 | 12 | 0 | yes |
| وبملت | 3525 | 2010-01-02 | 2026-11-09 | 26 | 10 | 11 | 0 | yes |
| وتجارت | 3485 | 2010-01-02 | 2026-11-09 | 21 | 10 | 9 | 0 | yes |
| شتران | 2802 | 2012-10-10 | 2026-11-09 | 20 | 6 | 13 | 0 | yes |
| شستا | 1378 | 2020-04-15 | 2026-11-09 | 10 | 0 | 8 | 0 | yes |
| شپديس | 3388 | 2011-04-18 | 2026-11-09 | 18 | 9 | 8 | 0 | yes |
| فارس | 2979 | 2013-04-16 | 2026-11-09 | 23 | 8 | 12 | 0 | yes |
| فزر | 1029 | 2022-02-09 | 2026-11-09 | 7 | 0 | 6 | 0 | yes |
| شصفها | 2500 | 2010-01-02 | 2026-11-09 | 6 | 2 | 1 | 0 | no |
| ولقمان | 1001 | 2021-03-15 | 2026-11-09 | 8 | 0 | 8 | 0 | no |
| وملت | 3358 | 2010-10-02 | 2026-11-09 | 3 | 0 | 3 | 0 | no |
| پشاهن | 940 | 2010-01-11 | 2026-11-09 | 11 | 3 | 7 | 0 | no |
| فنوال | 3357 | 2010-01-05 | 2026-11-09 | 20 | 8 | 11 | 0 | yes |
| كچاد | 3668 | 2010-01-02 | 2026-11-09 | 47 | 20 | 14 | 0 | yes |
| كگل | 3589 | 2010-01-02 | 2026-11-09 | 58 | 25 | 17 | 0 | yes |
| ولانا | 1893 | 2013-11-30 | 2026-11-09 | 16 | 4 | 9 | 0 | no |
| ومعادن | 3580 | 2010-01-02 | 2026-11-09 | 49 | 27 | 13 | 0 | yes |
| حآفرين | 1123 | 2021-09-13 | 2026-11-09 | 7 | 0 | 6 | 0 | yes |
| هانيكو | 157 | 2025-12-13 | 2026-11-09 | 2 | 0 | 2 | 0 | yes |
| چكاوه | 3305 | 2010-01-04 | 2026-11-02 | 17 | 9 | 4 | 0 | yes |
| سبهان | 3433 | 2010-01-06 | 2026-11-09 | 21 | 12 | 8 | 0 | yes |
| سخاش | 3200 | 2010-01-16 | 2026-11-09 | 24 | 12 | 9 | 0 | yes |
| سرود | 3797 | 2010-01-02 | 2026-11-09 | 25 | 15 | 8 | 0 | yes |
| خودرو | 3572 | 2010-01-02 | 2026-11-09 | 14 | 11 | 2 | 0 | yes |
| دالبر | 3621 | 2010-01-02 | 2026-11-09 | 42 | 19 | 14 | 0 | yes |
| دعبيد | 3310 | 2010-01-02 | 2026-11-09 | 31 | 17 | 12 | 0 | yes |
| مبين | 2641 | 2015-04-28 | 2026-11-09 | 16 | 6 | 9 | 0 | yes |

**This is not Full Database Coverage.** Raw OHLC exists for 6103 symbols; adjustment evidence exists for 1087 (product) / 827 (pack) symbols; independent reference validation exists only where measured elsewhere.
