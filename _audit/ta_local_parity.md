# پوششِ لوکال در برابرِ فیدِ تریدرزآرنا — نشستِ ۱۴۰۵-۰۷-۰۷

تولید: `PYTHONIOENCODING=utf-8 python tools/ta_local_parity.py --ta archive` (پروکسی حذف شده؛ منبع، بایگانیِ `_audit/ta/` است).
ساختارِ دو طرف مقایسه می‌شود، نه ریالِ آن‌ها؛ تبدیلِ واحد در `docs/TA-PARITY-1405-07-04.md` است.

| پنلِ تریدرزآرنا | منبع | او | اندپوینتِ ما | ما | داوری |
|---|---|---|---|---|---|
| `overview` | بایگانیِ `_audit/ta/market0.json` | 29 فیلد/سری | `/api/mstat/summary` | 9 سطرِ خلاصه + health | پوشش داده شد |
| `timeline` | بایگانیِ `_audit/ta/market_chart_totals0.json` | 26 فیلد/سری | `/api/mstat/timeline?mode=cum` | 99 نقطه، روز 20260928 | پوشش داده شد |
| `industries` | بایگانیِ `_audit/ta/data_industries-csv.fz` | 61 سطر | `/api/mstat/industries` | 46 صنعت | شکاف: 15 گروه (عمدتاً دسته‌هایِ صندوق) درِ برنامه نیست |
| `mainwatch` | بایگانیِ `_audit/ta/data_mainwatch_symbols.fz` | 20 سطر | `/api/mstat/mainwatch` | 120 نماد (کل 1440) | پوشش داده شد |
| `histo` | بایگانیِ `_audit/ta/market_histo-status.json` | 5 افق × سطل | `/api/mstat/histogram` | 12+7 سطل، افق: closing_vs_yesterday | شکاف: افق‌هایِ ۵/۱۰/۲۰/۶۰ روزه درِ برنامه نیست |

UNCOVERED=2
