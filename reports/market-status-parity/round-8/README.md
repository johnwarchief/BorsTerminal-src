# Round 8 — گیت‌ها و محدودیتِ محیط

| فایل | اجرا | نتیجه |
|---|---|---|
| `backend-gate-no-db.txt` | `python dev/run_all_tests.py` بدونِ `market.db` عملیاتی | ۱۲۶ سوئیت شمارش شد، ۱۹ FAIL، ۲ SKIP، `GATE_RC=1`؛ ریشهٔ بیشترِ FAILها جدول‌های غایبِ `market.db` و نبودِ `node` بود |
| `isolated-db/candle_integrity_roundj.txt` | با کپیِ ایزولهٔ `.q3-live-run/market.db` | rc=0؛ پاریتیِ زندهٔ HTTP اجرا نشد (بدون `--api`) |
| `isolated-db/incremental_sync_resilience.txt` | همان کپی | ۳۱ بررسی، ۰ خطا |
| `isolated-db/codal_publish_date_v1089.txt` | همان کپی | ۲۴/۲۴ |
| `isolated-db/proc_probe_cache_v1105.txt` | جداگانه | ۱۳/۱۳ |
| `isolated-db/qa_routes_guard.txt` | جداگانه | ۴/۴ |
| `isolated-db/sarkhati_protocol_v1119.txt` | جداگانه | ۴۷/۴۷ |
| `isolated-db/p0_gates_v1118.txt` | جداگانه | ۳۳/۳۳ |
| `isolated-db/tsetmc_p0_v1076.txt` | جداگانه | ۱۶۴/۱۶۵؛ تنها شکست: سقفِ زمانِ مرحلهٔ شبکه (`aborted=None`)، timingِ محیط |
| `vitest-partial.txt` | `vitest run` کامل | ناتمام: ۱۱۴ از ۱۹۸ فایلِ spec دیده شد، ۰ شکست در همان بخش؛ **سبزِ کامل ادعا نمی‌شود** |

تست‌های هدفمندِ تب بازار: ۳۷/۳۷. `tsc -b` و `npm run build` سبز.
`market.db` عملیاتی در این worktree وجود ندارد؛ کپیِ ایزوله پس از اجرا حذف می‌شود.
