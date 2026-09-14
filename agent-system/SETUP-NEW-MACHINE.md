# راه‌اندازی روی ماشین جدید (هر AI-agent environment: Nimbalyst، Hermes، Claude Code، ...)

## ۰. پیش‌نیازها
- Git + Python 3.11/3.12 (+ `pip install -r requirements.txt` **در venv**)
- Node.js 20+
- پوشهٔ پروژه (از بکاپ base code یا `git clone`)

## ۱. سرور مرکزی (یک‌بار)
```powershell
# از ریشهٔ پروژه
python bootstrap_first_run.py        # چک پیش‌نیاز
python start_dashboard.py --port 8012
# تأیید: curl http://127.0.0.1:8012/api/market باید JSON رد کند
```
> ایجنت‌ها سرور باز نمی‌کنند — همه به همین ۸۰۱۲ می‌چسبند.

## ۲. فرانت‌اند (یک‌بار قبل از اولین بیلد)
```powershell
cd frontend; npm ci
```

## ۳. ورک‌تری‌های ایجنت‌ها
```powershell
cd <repo root>
.\agent-system\setup-worktrees.ps1
# = ساخت ۴ شاخه + ۴ ورک‌تری کنار ریشه: ../<repo>_worktrees/{silky-arch,serene-mountain,neat-plateau,mellow-brook}
```
هر ورک‌تری یک‌بار `cd <worktree>\frontend && npm ci` لازم دارد.

## ۴. سشن‌های ایجنت‌ها
در محیط agent خودتان (Nimbalyst/Hermes/…) ۴ سشن بسازید؛ هر سشن را روی **پوشهٔ ورک‌تری خودش** قفل کنید و **System Prompt داخل `agents/<name>.md`** را به‌عنوان اولین پیام بدهید.

| ایجنت | ورک‌تری | فایل |
|---|---|---|
| Tape | silky-arch | agents/tape.md |
| Fundamental | serene-mountain | agents/fundamental.md |
| Technical | neat-plateau | agents/technical.md |
| Master & Portfolio | mellow-brook | agents/master-portfolio.md |

## ۵. ارکستراتور
یک سشن پنجم (= «ایجنت هد») با `PLAYBOOK-ORCHESTRATOR.md` بسازید.
مأموریت‌ها را با فرمت `dispatch to agent/<x>` به هد بدهید؛ او:
۱) مأموریت را به ایجنت مربوطه می‌فرستد ۲) کامیت را چک/نudge می‌کند ۳) merge + تست + build می‌گیرد.

## ۶. دیتابیس
market.db / codal.db در **ریشهٔ چک‌اوت اصلی** باشند (ایجنت‌ها نمی‌خواندنشان مستقیم؛ فقط سرور).
بروزرسانی دیتا: سرور خودش sync thread دارد (market sync) یا کلیدهای داشبورد.

## دام‌های شناخته‌شده (همه‌جا صادق‌اند)
- **node_modules خالی در ورک‌تری** → اولین اجرای vitest ایجنت را بی‌کار می‌گذارد؛ `npm ci` اول.
- **پایپ زندهٔ npx در PowerShell قفل می‌کند** → همیشه `cmd /c "... > file 2>&1"` و بعد خواندن فایل.
- **free model providerها zombie می‌سازند** (running کاذب بدون ابزار) → pattern: ۲۰ دقیقه بی‌فعالیت = interrupt + پرامپت ۵خطی مکانیکی؛ اگر باز تکرار شد، مدل سشن را عوض کنید.
- **AppShell دست‌نخورده می‌ماند** — حتی اگر مأموریت بگوید «پوسته را عوض کن»؛ فقط ایجنت هد.
- **pasted mission text** ممکن است با برچسب `tests/unit/` بیاید — ساختار واقعی تست `frontend/src/__tests__/*.spec.ts` است؛ هد قبل از dispatch اصلاح مسیر می‌کند.
