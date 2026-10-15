# RC 1.0.90 — سندِ تحویل به سیستمِ اول

**وضعیت:** آماده برای انتشار. **هیچ release یا tagی ساخته نشد.** هیچ assetی در مخزن عمومی منتشر نشد.

| قلم | مقدار |
| --- | --- |
| شاخه | `release/rc-1.0.90-2026-10-16` |
| worktree | `C:\Users\PCMOD\Desktop\_bors-rc` |
| پایه | `github/mission/windows-stable-release-2026-10-15` @ `c183d0db` (= `main` + ۱۲) |
| نسخه | `1.0.90` — هر شش لنگر یکسان (`dev/version_anchor_guard.py`: ۶/۰) |
| مخزن سورس | `johnwarchief/BorsTerminal-src` — **خصوصی می‌ماند** |

---

## ۱) چرا این پایه

از ۳۳ شاخۀ روی GitHub، ۱۷ تا جلوتر از `main`اند. فقط یک شاخه `behind=0` دارد:
`mission/windows-stable-release-2026-10-15`. بقیه یا روی `main`ِ ۱۰۲ کامیتِ پیشین
شعبه زده‌اند یا کارِ منتشرشده‌اند. پایه‌گذاری روی آن، تنها راهی بود که تاریخچه‌یِ
هیچ عاملی را بازنویسی نکند.

خانوادۀ سیستم دوم یک زنجیره است، نه چهار شاخۀ مستقل (اندازه‌گیریِ `merge-base
--is-ancestor`):

```
mission/fts-indicator-engineering (51)  ⊆  fix/system-2-reproducible-fixtures (56)
        ⊆  handoff/system-2/inventory (61)        mission/ui-audit-system-2 (66) ← نوک
```

`ui-audit-system-2` نسبت به نوکِ زنجیره ۱۶/۱ است — یعنی تقریباً همه‌چیز را دارد.

## ۲) آنچه ادغام شد (شش کامیت، با حلِ تعارض)

| کامیت | از | تعارض و تصمیم |
| --- | --- | --- |
| `5ec81527` نگهبانِ توکنِ رنگ + رفعِ `accent-amber` | سیستم دوم/گریویتی | دو فایلِ قیف: ساختارِ پایه (عنوان/testid) ماند، اصلاحِ توکن اعمال شد |
| `a8ba5ec0` رفعِ بی‌رنگیِ حالتِ `unknown` در پنل اجرا | **یافتِ جدید در همین ادغام** | — (گاردِ منتقل‌شده همان‌جا قرمز شد) |
| `60768efe` آدیتِ ریسپانسیو سیستمِ اول | من | `TechnicalPage`: پایه از `calc(--pinned-h)` به `h-full` رفته بود ⇒ سمتِ پایه؛ تیترِ بلوکِ تایم‌لاین حفظ شد |
| `185a80a4` فیدهایِ Binder1 (`mstat_panels.py`) | سیستم دوم | `/api/mstat/board`: شش پنل به **همان `_panel` کش‌خورده** وصل شدند، نه درون‌خطیِ بی‌کش |
| `6860903` فیدِ دسته‌ای + گاردِ قرارداد پنل | سیستم دوم | تمیز |
| `d1368015` بازسازیِ تب در هشت بخش | سیستم دوم | چیدمانِ صفحه: سمتِ تازه under-setِ قبض است؛ تیترِ متنِ پایه برگردانده شد |

**یک کامیت رد شد:** `0d0b76fe` (کلیدِ کشِ تب بر حالتِ بانک) — پایه همین را
کامل‌تر در `7196c61a` (SWR + تک‌پروازگی + یک سطح کش) دارد.

**قفلِ شکست‌پذیر:** `mstat_panels` ماژولِ ریشه است و `api/market_status` سطح‌بال
importش می‌کند ⇒ هم `('mstat_panels.py', '.')` در `datas` و هم `'mstat_panels'` در
`hiddenimports` در `fts_terminal.spec` اضافه شد. بدون آن EXE روی اولین
`/api/mstat/treemap` می‌مرد — و این درِ بیلدِ واقعی آزموده شد (بندِ ۴).

## ۳) گیت‌ها (نتیجۀ واقعی، نه مورد انتظار)

| گیت | نتیجه |
| --- | --- |
| `npx tsc -b` | صفر خطا |
| `npx vitest run --maxWorkers=2` | **۱۷۲ فایل / ۱۷۷ تست پاس · ۵ skip · صفر fail** (پیش از ادغام ۱۷۰۱ ⇒ +۴۶) |
| `dev/run_all_tests.py` | **ALL SUITES PASSED** — ۱۰۵ سوئیت شمارش‌شده، ۲۹ silent (فقط exit code) |
| `dev/mstat_local_v975.py` | ۱۸۷ چک / ۰ |
| `dev/version_anchor_guard.py` | ۶ / ۰ |
| `dev/persian_glyph_guard.py` | ۴ / ۴ |
| `scripts/build_all.py` | موفق — `dist/BorsTerminal_Ultimate`، ۱۲۰٫۹ مگابایت |

## ۴) آزمونِ بستهٔ فریزشده (نه بیلد، نه dev)

اجرا با پرتِ اختصاصی و حالتِ جداسازی‌شده تا دادهٔ کاربر دست‌نخورده بماند:

```
BORS_PORT=8123 BORS_PORTABLE=1 BORS_NO_FETCH_LOOPS=1 BORS_CODAL_AUTO=0 ./BorsTerminal_Ultimate.exe
```

| سنج | نتیجه |
| --- | --- |
| آمادگی | HTTP 200 روی `/api/mstat/summary` پس از ~۳۰ ثانیه |
| `mstat_panels` در EXE | `_internal/mstat_panels.py` موجود **و** هر هفت اندپوینتِ تازه `status=ok` |
| `/api/mstat/board` | ۱۸ کلید، شامل هر شش پنلِ تازه: `treemap` ۲۲۰ سطر · `tops` ۴ پنل · `indexcards` ۳ کارت |
| صداقتِ بی‌داده | `gold.no_source` = ۸ سنجه با دلیل؛ `access_limits` = «ارزشِ ذاتی»؛ `symbols_count` = ۱۹ نمادِ واقعی |
| خاموش‌کردن | فقط PIDی که خودمان بالا آورده بودیم کشته شد (۲۱۰۲۰، فرزندِ ۳۱۴۴۸) |

## ۵) اندروید (جدا از RC دسکتاپ، دست‌نخورده در این ادغام)

`android-1.1.0` به‌عنوان **prerelease** در مخزن عمومی منتشر شد و راستی‌آزمایی شد:

- لینکِ عمومی `.../android-1.1.0/bors-terminal-android-1.1.0.apk` → HTTP 200
- `build-apk :: success` · `upgrade-matrix-on-device :: success`
- گواهیِ امضا = `1a4da33d…4b58` = `vars.ANDROID_RELEASE_CERT_SHA256` (کلیدِ رسمی، نه debug)
- آپدیتر ویندوز دست‌نخورده: `releases/latest` = `v1.0.89`، نه‌پیش‌انتشار، ۱۳ asset

**یک مورد باز:** `webview-on-emulator :: failure` — دو FAIL:
`webview-360x800-a11y` (هیچ واژۀ دیدنیِ برنامه در uiautomator نبود) و `anr`
(`ANR in com.borsterminal.mobile/.MainActivity`)، همراه با خطاهای گرافیکِ امولاتور
(`Failed to bind to texture: invalid color buffer`). `crash [PASS]` بود. پس رابط
نصب و بالا آمد ولی تأییدِ DOM در WebView **همچنان `NOT_VERIFIED`** است — با شاهد،
نه با سکوت.

## ۶) آنچه در این ادغام **نیامد** و چرا

| مورد | دلیل |
| --- | --- |
| `mission/fts-indicator-engineering` به‌صورت mergeِ کامل | ۱۶ تعارض از جمله `fts_terminal.spec`؛ ادغامِ کور ممنوع. فقط پنج کامیتِ خودکفا برداشته شد |
| فازهایِ تکنیکال/تعدیل (`6ae7ea95`، `22e45e06`، `0dc103a3`، `415c82b3`) | مالکیتِ موتورِ تعدیل و parity نمودار به ایجنتِ دیگری واگذار شده؛ واردکردنشان بدونِ آن ممیزی یعنی تغییرِ قواعد FTS بی‌شاهد |
| `arena/fts-mobile-uiux-20261007` | محصولِ اندروید است، جدا منتشر می‌شود؛ قلمروِ این RC دسکتاپ است |
| `handoff/system-1/*`، `roadmap-main`، `docs/*` | سند/دستی، بدون کدِ محصول |

## ۷) چک‌لیستِ سیستمِ اول برای انتشار

1. `git log --oneline github/main..release/rc-1.0.90-2026-10-16` را ببیند (شش کامیت).
2. تصمیمِ نهاییِ merge به `main` — در این مأموریت انجام **نشد**.
3. `python dev/data_age_release_guard.py` روی `market.db.lzma`ی روزِ انتشار.
4. `scripts/publish_github_release.py` — بخشِ `## v1.0.90` در `docs/RELEASE_NOTES.md`
   عیناً به‌عنوان متنِ ریلیز و `notes`ِ `latest.json` می‌رود؛ آن بند حالا شامل
   هشت‌بخشیِ وضعیت بازار، بی‌منبع‌بودنِ هشت سنجه، برآوردِ «اثر بر شاخص» و دو
   رنگِ رفع‌شده است.
5. بیلدِ نهایی روی تگ، آزمونِ delta، و امضای artifacts.

## ۸) موارد بازِ دانسته (نه پنهان‌شده)

- WebView DOM روی دستگاه: `NOT_VERIFIED` (بندِ ۵).
- بیست‌و‌نه سوئیتِ `run_all_tests` فقط exit code می‌دهند؛ سبز بودنشان «سکوت» است نه «شمارشِ صفر خطا» — خودِ هارنس همین را اعلام می‌کند.
- «اثر بر شاخص» ۲۵٪ پسماند دارد و در رابط به‌عنوان برآورد نشان داده می‌شود، نه عددِ رسمی.
- هشت سنجهٔ طلا/مسکن/تورم تا یافتنِ منبعِ مجاز خالی می‌مانند.
- سندِ `docs/research/RAHAVARD-13-PAGES-MARKET-STATUS-RECONSTRUCTION.md` (در
  `mission/4-axes-2026-10-10`) دو ادعایش با این ادغام تصحیح شد: «treemap نیست»
  (نسبت به `main` درست، نسبت به آن شاخه غلط) و «فرمولِ اثر بر شاخص را نمی‌سازم»
  (ساخته شده، با پسماندِ اعلام‌شده).
