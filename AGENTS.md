# AGENTS.md — ijentِ back-end / data (bors-backend)

workspace: C:\\Users\\Johnkallnaya\\Desktop\\BorsTerminal_Ultimate_Base (ریشهٔ ریپو، چون market.db/codal.db اینجاست)

## مأموریت
تازه‌سازیِ دادهٔ خامِ **فقط ۵ شاخص FTS** از کدال، با کمترین نرخِ درخواست (ضد ۴۲۹/بن)، و نگه‌داشتنِ جدول‌های `monthly_sales` / `financial_statements` تازه.

## ابزارها (موجود در ریپو — از نو نساز)
- `dev/codal_fts_updater.py` — تازه‌سازِ اختصاصیِ ۵ شاخص. مودها: `--mode monthly|full|local`.
  - چرخشِ IP: `--adb-rotate` (روی ۴۲۹/بلاک: Wi-Fi ویندوز موقتاً خاموش، سه متد adb، پایشِ IP هر ۳s تا ۹۰s، **فقط با دیدنِ IP تازه** موفق می‌شود)، `--adb-long`, و راستی‌آزماییِ مستقلِ `--rotate-test` (بدون درخواست به کدال).
  - `--verify` (چاپ ۵ شاخص)، `--resume` (ادامه از `dev/fts_update_state.json`).
- `dev/fts_refresh_plan.py` — **الگوریتمِ افزایشی**: فقط دِلتا را مشخص می‌کند (نمادِ NEW/NEED_ANNUAL/STALE_MONTHLY/STALE_ANNUAL) + فرمانِ آماده.
- `codal_fetcher.py` — موتورِ HTTP/اسکرپ (rotate_ip_via_adb، fetch_page با backoff ۴۲۹).

## رویهٔ کار (اجباری)
۱) `python dev/fts_refresh_plan.py --out plan.json` → کارنامهٔ دِلتا.
۲) فقط نمادهای `monthly` را با `--mode monthly` و `full`ها را با `--mode full` (و `--adb-rotate`) واکشی کن؛ به‌صورت دسته‌ای/limit‌دار.
۳) روی ۴۲۹/بن: چرخشِ IP، **تأییدِ تغییرِ IP**، سپس ادامه از همان نقطهٔ توقف (`--resume`).
۴) در پایان `--verify` و گزارشِ کوتاه: چند نماد/چند ردیف، وضعیتِ IP، و هر گپ.

## قواعد
- **فقط ۵ شاخص**؛ هیچ اطلاعیهٔ دیگری واکشی نشود.
- بدون دادهٔ ساختگی؛ غایب ⇒ «بدون داده». مرجعِ اعتبار: `docs/FTS_SYSTEM_SPECIFICATION_v2.md` (v2.1).
- شبکه/چرخشِ IP فقط با adbِ گوشیِ متصل؛ اگر گوشی نبود، صریح گزارش بده و توقف کن (بدون تلاشِ پیاپیِ بن‌کننده).
- هیچ فایلِ موقتِ untracked؛ کامیت/مرج نکن (head انجام می‌دهد).
