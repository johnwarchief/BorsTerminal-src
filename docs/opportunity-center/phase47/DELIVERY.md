# تحویلِ دسکتاپ (Build / Installer / Update) — فاز ۴٫۷

این سند **معماریِ واقعیِ موجود** را ثبت می‌کند و بعد می‌گوید کدام بخش با شاهدِ
محلی تأیید شد و کدام اندازه‌گیری نشد. هیچ موردی PASS فرضی ندارد.

## ۱. معماریِ استخراج‌شده (نه فرض‌شده)

| لایه | واقعیتِ درخت | شاهد |
| --- | --- | --- |
| پوستهٔ دسکتاپ | Tauri v2 (Rust) | `frontend/src-tauri/tauri.conf.json`، `scripts/build_shell.py` |
| رابط | React + TS (`frontend-v2`) | `frontend-v2/package.json`، `npm run build` → `frontend-v2/dist` |
| بک‌اند | **Go** (`cmd/borsd`) — باینریِ مستقل، بدونِ Python | `scripts/build_all.py` گامِ ۲؛ `cmd/bundlecheck` |
| مسیرِ Python | هنوز در درخت است (`app.py`, `test_tsetmc.py`) و **تنها نویسندهٔ ingestion**؛ در بستهٔ نهایی نیست | `build_all.py` قراردادِ «ZERO Python» را assert می‌کند |
| نصاب | Inno Setup، per-user، رمزنگاری‌شده | `installer/bors_setup.iss` |
| امضا | Minisign (کلیدِ عمومی در `.tauri/updater.key.pub` و `api/update.UPDATE_PUBKEY`) | `bors_minisign.py`, `api/update.py` |
| به‌روزرسانی | `latest.json` → امضا → نصبِ سایلنتِ Inno؛ پچِ دلتا با `apply_update.bat` | `api/update.py` (`/api/update/check`, `_verify_file`, `_spawn_install`) |
| دادهٔ بازار | نسل‌هایِ امضاشده (Stage 4) + `market.db.lzma` کنارِ EXE | `internal/snapshot`, `internal/pointerfile`, `sync/download.go` |

نسخه: **1.0.95** در ۱۱ لنگرِ محصول یکسان (`dev/version_anchor_guard.py`: 11 checks, 0 failed).

> تناقضِ ثبت‌شده: متنِ مأموریت معماریِ «Tauri v2 + Go» را مفروض گرفته بود. این
> درخت با آن یکی است، ولی یک جزء مهم را باید صریح گفت: **ingestion هنوز Pythonی
> است**. یعنی «بدونِ Python» فقط دربارهٔ بستهٔ اجراییِ کلاینت درست است، نه دربارهٔ
> تولیدِ داده. این را به‌عنوانِ بدهیِ معماری ثبت می‌کنم، نه PASS.

## ۲. زنجیرهٔ Build

`scripts/build_all.py`:
1. `frontend-v2: npm run build` → `frontend-v2/dist`
2. `backend-go: go build -o dist/BorsTerminal_Ultimate/BorsTerminal_Ultimate.exe ./cmd/borsd`
3. `scripts/build_shell.py` → `BorsTerminal_Shell.exe` (Tauri)
4. کپیِ دارایی‌هایِ فرانت به `frontend/`
5. `apply_update.bat` (اعمال‌کنندهٔ پچِ دلتا)
6. `market.db` در صورتِ وجود
7. `data/ra365_corrections` (بستهٔ تصحیح)
8. `data/ra365_calendar/ra365-r32d` (پکِ تقویم — بدونِ آن W/M میلادی می‌شود)
9. قراردادِ بسته: نبودِ هر `.py/.pyc/.pyd`، `Python*.exe/.dll` و رشتهٔ
   `uvicorn/fastapi/pyinstaller/libpython`

### شاهدِ محلی (این ماشین، همین درخت)

| قلم | نتیجه |
| --- | --- |
| `GOOS=windows GOARCH=amd64 go build ./cmd/borsd` | موفق — `BorsTerminal_Ultimate.exe` = 21,723,136 بایت |
| بستهٔ مونتاژشده (exe + frontend/dist + data) | ساخته شد |
| `go run ./cmd/bundlecheck -path <bundle>` | `bundle contract OK: no python/uvicorn/fastapi artifacts` (exit 0) |
| پکِ تقویم | `data/ra365_calendar/ra365-r32d` = ۲ فایل (`manifest.json`, `wm_calendar_bars.ndjson.gz`) |
| بستهٔ تصحیح | `data/ra365_corrections` = ۲ پک (`ra365-r32b-v2`, `ra365-live40-v1`) |
| `frontend-v2/dist/index.html` | موجود |

بازتولیدِ کاملِ Tauri (Rust + WebView2) در این دور اجرا نشد؛ فقط باینریِ Go و بستهٔ
دارایی‌ها ساخته شد. بنابراین «Build کاملِ قابلِ تکرار» وضعیتِ **PARTIAL** دارد:
زنجیره مستند و مراحلِ Go/فرانت/بسته سبزند، ولی `build_shell.py` اجرا نشده است.

## ۳. نصاب (Inno Setup)

طراحیِ موجود (خوانده‌شده، نه اجراشده):

- `PrivilegesRequired=lowest` + `PrivilegesRequiredOverridesAllowed="dialog commandline"`
  ⇒ نصبِ per-user بدونِ UAC، و آپدیتِ درون‌برنامه‌ای می‌تواند واقعاً سایلنت باشد.
- `Password={#SetupPassword}` + `Encryption=yes` (رمز از فایلِ gitignored).
- `[InstallDelete]` فقط `_internal` را پاک می‌کند (باقی‌ماندهٔ مسیرِ Python قدیمی).
- `[UninstallDelete]` محصولِ اجرا (`market.db*`, `codal.db*`, `logs`, `backups`) را
  پاک می‌کند ولی **`user.db` را نه** — در `[Code]` صریح نوشته شده:
  «user.db هیچ‌جا حذف نمی‌شود: نوشتهٔ خودِ کاربر است» (خط ۲۳۹).
- `EnsureAppNotRunning()` پیش از نصب اجرا می‌شود (مدیریتِ برنامهٔ در حالِ اجرا).

| سناریو | وضعیت | علت |
| --- | --- | --- |
| نصبِ تمیز | **NOT_MEASURED** | نیازمندِ اجرایِ واقعیِ نصاب رویِ سیستم؛ در این مأموریت نصب انجام نشد |
| ارتقا رویِ نسخهٔ قبلی | **NOT_MEASURED** | همان دلیل + باید حفظِ `user.db`/`oc_client.db` رویِ نصبِ واقعی دیده شود |
| Repair | **NOT_MEASURED** | Inno خودش repair ندارد؛ باید با نصبِ مجدد سنجیده شود |
| Uninstall | **NOT_MEASURED** (طراحی: `user.db` حفظ، دادهٔ بازار پاک) | نیازمندِ نصبِ واقعی |

اجرایِ این چهار مورد بدونِ اجازهٔ صریحِ صاحبِ پروژه انجام نشد، چون رویِ همین ماشین
نصبِ موجود را دست‌کاری می‌کند. چک‌لیستِ آماده برای اجرا در §۶ آمده است.

## ۴. به‌روزرسانی و بازیابی

مسیرِ واقعی (کد خوانده شد):

```
/api/update/check → latest.json (GitHub releases)
  → انتخابِ نسخه/پچ (semver + patches)
  → دانلود در worker با پیشرفت (/api/update/status)
  → _verify_file: تأییدِ امضای minisign با UPDATE_PUBKEY   ← تنها ریشهٔ اعتماد
  → _spawn_install: اجرای Inno با فلگ‌هایِ سایلنت (/VERYSILENT یا /SILENT)
  → apply_update.bat برایِ پچِ دلتا (خودش را در %TEMP% کپی می‌کند)
```

برایِ دادهٔ بازار (مسیرِ Go، `sync/download.go`):
manifest + manifest.sig → `snapshot.VerifyAsset` → دانلودِ هر دارایی + `.sig` →
`sha256` در برابرِ manifest → `Applier.ApplySnapshotSet` به نسلِ تازه →
`active_generation.json` → `reloadHook`.

| قلم | وضعیت | شاهد |
| --- | --- | --- |
| تأییدِ امضا وجود دارد و تنها ریشهٔ اعتماد است | PASS (کد) | `_verify_file` → `verify_minisign`؛ `DownloadAndApplySnapshot` → `VerifyAsset` |
| بررسیِ sha256 دارایی‌ها | PASS (کد) | `hashFileSHA256` در برابرِ `meta.SHA256` |
| staging و جلوگیری از نصبِ ناقص | PASS (کد) | `os.MkdirTemp(staging)` + `defer os.RemoveAll` |
| نصبِ اتمیکِ داده | PASS (کد + تست‌هایِ Go) | `internal/snapshot`, `internal/pointerfile`, `internal/generation` |
| قطعِ اینترنت هنگامِ دانلود | **NOT_MEASURED** | نیازمندِ اجرایِ واقعی |
| فایلِ خراب / امضایِ نامعتبر | **NOT_MEASURED** (کد مسیرِ خطا دارد) | `DownloadAndApplySnapshot` خطا را با وضعیت ثبت می‌کند |
| بسته‌شدنِ برنامه هنگامِ Update | **NOT_MEASURED** | — |
| Rollback به نسخهٔ قبلی | **NOT_MEASURED** | مکانیزمِ نسل/فایلِ اشاره‌گر موجود است؛ اجرایِ واقعی نشد |
| Update متوالی | **NOT_MEASURED** | — |

## ۵. CI

`guards.yml` سه جابِ تازه گرفت (کلِ فایل با YAML پارس شد؛ ۹ جاب):

| جاب | چه می‌کند |
| --- | --- |
| `go-windows` | ماتریسِ `windows-2022` + `windows-latest`: `go vet`, ساختِ EXE، `go test ./...` رویِ ویندوز |
| `delivery-contract` | build فرانت + Go، مونتاژِ بسته با پکِ تقویم/تصحیح، `bundlecheck`، مانیفستِ `sha256` و آپلودِ artifact |
| `data-integrity` | `test_phase47_ingestion_v1`, `candle_contract_v1071`, repair/gap رویِ DB موقت |

وضعیتِ اجرا در GitHub Actions: **NOT_RUN** — در این نشست push/CI اجرا نشد. صحتِ
*منطقِ* جابِ `delivery-contract` به‌صورتِ محلی بازتولید شد (همان دستورها: ساختِ EXE،
مونتاژ، `bundlecheck` = exit 0)، ولی «سبز شدنِ جاب در runner» ادعا نمی‌شود.

## ۶. چک‌لیستِ اجرایِ واقعی (نیازمندِ اجازهٔ صاحبِ پروژه)

1. `python scripts/build_all.py` رویِ ویندوز تمیز (شاملِ `build_shell.py`).
2. `go run ./cmd/bundlecheck -path dist/BorsTerminal_Ultimate` → باید exit 0.
3. نصبِ تمیز با `/CURRENTUSER /DIR=<temp>` و ثبتِ فایل‌هایِ ساخته‌شده.
4. اجرا → بررسیِ `market.db` در مسیرِ داده، ساختِ `user.db`، و لاگ.
5. نصبِ نسخهٔ بعدی رویِ همان مسیر → مقایسهٔ `sha256`ِ `user.db` پیش/پس (باید یکی باشد).
6. Uninstall → تأییدِ باقی‌ماندنِ `user.db` و حذفِ `market.db`.
7. Update با اینترنتِ قطع، فایلِ خراب، و امضایِ نامعتبر → باید fail بسته و نسخهٔ
   فعلی سالم بماند.

هر یک از این هفت مورد تا اجرا نشدن، `NOT_MEASURED` می‌ماند.
