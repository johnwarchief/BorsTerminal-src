# MIGRATION.md — انتقال پروژه BorsTerminal Ultimate به سیستم جدید

> خلاصه: کد، سند، تست و اسکریپت‌های بسته‌بندی **داخل مخزن** هستند. چیزی که باید دستی منتقل/بازسازی شود: **دیتابیس‌ها، `.env`، تعریف ایجنت‌های OpenClaw، ورکتری‌ها و فایل‌های `AGENTS.md` هر ورکتری، و دو فلگ کانفیگ.**

---

## ۰) پیش‌نیازها روی سیستم جدید
- Windows 10/11 x64
- Python 3.x (`pip install -r requirements.txt`)
- Node.js + npm (در `frontend`: `npm install`، سپس `npm run build`)
- (برای ساخت نصب‌کننده) Inno Setup 6 — مسیرش را در `release.ps1` تنظیم کن (`$PY`, `$NPM`, `$ISCC`)

## ۱) کپی خود پروژه
پوشهٔ پروژه را **همراه `.git`** کپی کن (تا همهٔ برنچ‌ها بیایند):
```
BorsTerminal_Ultimate_Base\        ← ریپو (master + ۴ برنچ agent/*)
```
برنچ‌ها: `master` · `agent/tape` · `agent/fundamental` · `agent/technical` · `agent/master-portfolio`

## ۲) فایل‌های محرمانه/ماشین‌محور (در gitignore ⇒ دستی)
| فایل | چرا لازم است |
|---|---|
| `market.db` (≈۱۰۰MB) | دیتای اصلی بورس |
| `codal.db` | دیتای کدال |
| `.env` | کلیدها/تنظیمات |
| `xray_config.json` / `v2ray*` | (اختیاری) روتیتور |
| `adb_config.json` | (اختیاری) سینک موبایل |

> جایگزین سبک: `release.ps1` یک `market.db.lzma` (~۱۳MB) می‌سازد؛ همان را ببر و اپ در اجرای اول بازش می‌کند.

## ۳) بازسازی ورکتری‌های ایجنت‌ها
اسکریپت آماده:
```powershell
.\setup-agents.ps1 -RepoRoot "D:\Proj\BorsTerminal_Ultimate_Base" -WorktreeRoot "D:\Proj\_worktrees"
```
این کار: ۴ ورکتری از برنچ‌ها می‌سازد + `AGENTS.md` هر ایجنت را می‌نویسد + junctionِ `node_modules` را وصل می‌کند.
(برنچ‌ها داخل `.git` هستند، پس ورکتری‌ها همه‌جا قابل بازسازی‌اند.)

## ۴) بازسازی ایجنت‌ها در اپ AutoClaw
تعریف ایجنت‌ها در `%APPDATA%\autoclaw\settings.json` است (خارج از ریپو). دو راه:
- **الف)** همان فایل settings را از سیستم قبلی کپی کن و بعد مسیرهای `workspace` چهار ایجنت را به مسیرهای جدید ویرایش کن.
- **ب)** در خود اپ، ۴ ایجنت بساز با این نگاشت:
  | id | workspace |
  |---|---|
  | `bors-tape` | `<WorktreeRoot>\silky-arch` |
  | `bors-fundamental` | `<WorktreeRoot>\serene-mountain` |
  | `bors-technical` | `<WorktreeRoot>\neat-plateau` |
  | `bors-master-portfolio` | `<WorktreeRoot>\mellow-brook` |

## ۵) فلگ‌های کانفیگ (لازم برای کارکرد «هد»)
در کانفیگ gateway (که اپ از settings می‌سازد) این دو مقدار را ست کن:
```
tools.sessions.visibility = all
tools.agentToAgent.enabled  = true
```
(بدون اینها، ایجنت‌ها نمی‌توانند به ایجنت‌هد پیام بدهند.)

## ۶) اجرا و تأیید
```powershell
# اجرای سرور (توسعه)
python -m uvicorn app:app --host 127.0.0.1 --port 8001
# یا کاربر نهایی:
python start_dashboard.py
```
تأیید سلامت:
```powershell
python dev\fts_formula_tests_v2.py          # ۷۲ تست فرمول
python dev\live_pipeline_check.py           # واچ‌لیست زنده + دلایل رد
cd frontend; npm run test -- --run --no-file-parallelism   # تست‌های فرانت
```

## ۷) ساخت نسخه‌ها
```powershell
.\release.ps1 setup      # نصب‌کننده (installer\out\*.exe)
.\release.ps1 portable   # نسخهٔ قابل‌حمل
.\release.ps1 base       # بیس‌کد خام (zip)
.\release.ps1 all        # هر سه
```

## ۸) چه چیزی داخل مخزن آماده است (نیازی به کار ندارد)
- کل کد بک‌اند/فرانت، `requirements.txt`، `package.json`/lock
- `public/vendor` چارت (۸ فایل) و `frontend/public`
- `docs/FTS_SYSTEM_SPECIFICATION_v2.md` (v2.1)، `REPO_MAP.md`، `agent-system/PLAYBOOK-ORCHESTRATOR.md`
- `release.ps1` + `installer/bors_setup.iss` + `installer/Farsi.isl` + `bors_setup.spec` + `assets/bors.ico`
- تست‌ها: `dev/fts_formula_tests_v2.py`، `dev/live_pipeline_check.py`، کل تست‌های vitest
- همهٔ برنچ‌های ایجنت‌ها

## ۹) نکات ظریف
- `fts_thresholds.json` **داخل مخزن** است ⇒ تنظیمات غربالگری همراهش می‌آید.
- `frontend/dist` و `node_modules` داخل مخزن نیستند ⇒ روی سیستم جدید build/install لازم است.
- اگر از `release.ps1` استفاده می‌کنی، اول سه متغیر مسیر بالای فایل را با سیستم جدید هم‌راست کن.
