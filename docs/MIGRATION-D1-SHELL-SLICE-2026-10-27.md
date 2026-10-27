# D1 — اسلایسِ پوستهٔ Tauri: مشخصاتِ اجراییِ کامل

> **Plan برایِ اجراکننده:** هر تسک با چک‌باکس و گام‌هایِ ۲–۵ دقیقه‌ای است. پیش از هر تسک،
> «قیدهایِ سراسری» را بخوانید. هیچ گامی را بدونِ دیدنِ خروجیِ موردانتظار رد نکنید.
>
> **Goal:** جایگزینیِ پنجرهٔ pywebview با پنجرهٔ Tauri در یک بیلدِ واقعی و قابلِ‌نصب،
> بدونِ تغییرِ بک‌اند/دیتابیس/API/React، با مسیرِ بازگشتِ فوری.
>
> **Architecture:** در D1، لانچرِ پایتونی همچنان میزبانِ فرآیند می‌ماند و
> `BorsTerminal_Shell.exe` (Tauri + WebView2) فقط پنجره را می‌سازد و روی loopback
> بار می‌کند. پوسته هیچ IPC به صفحه نمی‌دهد؛ مرزِ امنیتی همان گاردِ مبدأ محلی است.
> انتقالِ میزبانی به Tauri (sidecar) یک گامِ بعدی و مبتنی بر شواهد است.
>
> **Tech Stack:** Python 3.12 (موجود)، FastAPI/uvicorn (بدونِ تغییر)، Tauri 2.12.5
> (Rust 1.77.2+)، WebView2، React 18 (بدونِ تغییر)، Inno Setup، PyInstaller onedir.
>
> **Spec:** [`docs/MIGRATION-D-SPEC-2026-10-27.md`](MIGRATION-D-SPEC-2026-10-27.md) —
> مرجعِ بالا‌دستی: [`docs/BorsTerminal-Desktop-Migration-Decisions.md`](BorsTerminal-Desktop-Migration-Decisions.md)
> (۵۱۰ خط، بازبینیِ ۲۰۲۶-۱۰-۲۵).

---

## ۰) قیدهایِ سراسری (هر تسک شاملِ این‌هاست)

- **هیچ کوکی/توکن/رمز/اطلاعاتِ احراز هویت** خوانده، چاپ یا کامیت نمی‌شود. تستِ پروفایل
  با یک کلیدِ بی‌خطر (`d1.probe`) انجام می‌شود، نه با `bors_auth_pass`.
- **هیچ دیتابیسِ عملیاتی یا WAL** حذف/بازنویسی/ترمیم نمی‌شود. پذیرش روی نسخهٔ
  Portable با فضایِ دادهٔ مستقل است (§۱۲.۳۱)؛ نسخهٔ نصب‌شده دست‌نخورده می‌ماند.
- **در هر لحظه حداکثر یک حلقهٔ دریافتِ زندهٔ TSETMC** (§۹). آزمونِ آفلاین با
  پروکسیِ مرده و گیتِ IP؛ آزمونِ زنده فقط با هماهنگیِ مالک.
- **گاردِ مبدأ محلی تضعیف نمی‌شود**؛ `Origin: null` عمومی مجاز نمی‌شود (§۲ خط ۲۰).
- **بدونِ IPC به صفحهٔ loopback**؛ قابلیت‌هایِ Tauri برایِ صفحهٔ بیرونی فعال نمی‌شوند.
  پلِ بومی گامِ جداگانهٔ D2 است.
- **بدونِ تغییر در** `app.py`، `api/market.py`، `api/chart.py`، `fts_engine.py`،
  `frontend/src/**`، `requirements.txt` و `numpy==2.0.2`.
- **زبانِ رابط فارسیِ RTL**؛ متنِ تازه فقط دیالوگِ نخستین اجرا، منویِ Tray و صفحهٔ
  stub است. ارقامِ فارسی در رابط با `toFaDigits`؛ در پایتون با `chr(0x06F0+d)`.
- **پایانِ خط:** همهٔ فایل‌هایِ دست‌خورده LF هستند؛ LF را حفظ کنید.
- **کشتنِ فرآیند فقط با PIDی که خودتان بالا آورده‌اید**؛ هیچ `taskkill /IM` عمومی
  در تست‌ها اجرا نمی‌شود (به‌جز دستورِ نصب‌کننده که بخشی از محصول است و فقط در
  بیلدِ نصبی اجرا می‌شود).
- **گزارشِ اعداد قبل از ادعای موفقیت**؛ PASS بصری فقط با حکمِ مالک.

---

## ۱) معماریِ D1

### ۱.۱ درختِ فرآیند

```text
BorsTerminal_Ultimate.exe        (لانچرِ پایتون: preflight، uvicorn در نخ، لاگ)
└── BorsTerminal_Shell.exe       (Tauri 2.12.5: پنجره، Tray، تنظیمِ بستن)
    └── msedgewebview2.exe ...   (فرآیندهایِ WebView2، مثلِ امروز)
```

- سرورِ FastAPI همان‌جا و همان‌طور اجرا می‌شود؛ پنجره فقط
  `http://127.0.0.1:<port>` را بار می‌کند (همان مبدأِ امروز).
- `_webview_storage_dir()` همان مسیرِ پروفایلِ فعلی را به پوسته می‌دهد
  (`%LOCALAPPDATA%\BorsTerminal_Ultimate\webview2`؛ در Portable داخلِ دادهٔ خودش).
  WebView2 داخلِ آن `EBWebView` می‌سازد؛ پس localStorage و نشستِ فعلی حفظ می‌شود.
- سؤالِ «خروج یا Tray» در **نخستین اجرا** توسطِ لانچر پرسیده و در
  `shell_settings.json` ذخیره می‌شود؛ پوسته همان را می‌خواند و منویِ Tray آن را
  تغییر می‌دهد (§۷ خط ۸۴–۸۵).

### ۱.۲ چرا میزبان هنوز پایتون است (نه Tauri-as-host)

- §۱۲.۳۰ می‌خواهد هزینهٔ پوسته از هزینهٔ بک‌اند جدا سنجیده شود؛ این اسلایس
  کمترین تغییر را دارد: فقط `open_native_window` عوض می‌شود.
- preflight، صفحهٔ بوت، دریافتِ `market.db.lzma`، گاردِ GPU/DPI و مسیرِ آپدیت
  دست‌نخورده می‌مانند؛ ریسکِ شکستنِ بیلدِ فریز‌شده حداقل است.
- CI فعلی صریحاً می‌گوید پوستهٔ Tauriِ موجود نمی‌تواند بک‌اند را بالا بیاورد
  (`.github/workflows/release.yml`، jobِ `release-windows`). D1 همین شکاف را
  بدونِ sidecar پر می‌کند.

**معیارِ بررسیِ میزبانیِ Tauri در آینده (D5، نه D1):** اگر اندازه‌گیری نشان داد
چرخهٔ عمرِ دوفرآیندی، آپدیتر یا مصرفِ منابع گلوگاه است، انتقالِ میزبانی با
sidecar و شواهدِ قبل/بعد بررسی می‌شود. اکنون ساخته نمی‌شود.

### ۱.۳ مرزِ امنیتی

| لایه | D1 |
| --- | --- |
| بارگذاریِ صفحه | فقط `http://127.0.0.1:<port>` یا صفحهٔ stubِ محلی |
| گاردِ API | همان `loopback_guard` در `app.py`؛ بدونِ تغییر |
| IPCِ Tauri در صفحه | عمداً وجود ندارد؛ پنجره URLِ بیرونی است و capabilityِ `remote` تنظیم نمی‌شود |
| پروفایل | همان پروفایلِ WebView2 فعلی؛ بدونِ کپی/مهاجرتِ داده |
| آپدیتر | زنجیرهٔ پایتونیِ فعلی تنها آپدیترِ فعال؛ `updater`ِ Tauri در این اسلایس فراخوانی نمی‌شود |

---

## ۲) قراردادِ پوسته

### ۲.۱ آرگومان‌هایِ خطِ فرمان

| آرگومان | اجباری | معنا |
| --- | --- | --- |
| `--url <url>` | خیر | URLِ loopbackِ برنامه یا صفحهٔ بوت؛ نبودش یعنی صفحهٔ stubِ محلی |
| `--profile <dir>` | خیر | پوشهٔ دادهٔ WebView2 (`data_directory`) |
| `--settings <file>` | خیر | مسیرِ `shell_settings.json`؛ نبودش یعنی رفتارِ بستن = خروج |
| `--ready <file>` | خیر | پس از ساخته‌شدنِ پنجره نوشته می‌شود (JSON) |
| `--parent-pid <pid>` | خیر | نگهبانِ مرگِ والد؛ با مرگِ پایتون، پوسته خارج می‌شود |

### ۲.۲ متغیرهایِ محیط

| متغیر | مقدار | اثر |
| --- | --- | --- |
| `BORS_SHELL` | `tauri` (پیش‌فرض)، `pywebview`، `0`، `off` | انتخابِ پنجره؛ `pywebview` مسیرِ قدیم را اجباری می‌کند |
| `BORS_SHELL_ASK_CLOSE` | `1` (پیش‌فرض)، `0` | `0` دیالوگِ نخستین اجرا را نمی‌پرسد و `exit` می‌نویسد |
| `BORS_WEBVIEW_PROFILE` | مسیر | بازنویسیِ پروفایل برایِ تستِ ایزوله/مهاجرت |
| `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` | `--remote-debugging-port=9334` | فقط اندازه‌گیری/عیب‌یابی؛ در تولید تنظیم نمی‌شود |

### ۲.۳ فایل‌هایِ وضعیت

`shell_settings.json` در `bors_config.WORK_DIR`:

```json
{
  "version": 1,
  "close_action": "tray"
}
```

`close_action` فقط `tray` یا `exit` است؛ هر مقدارِ دیگر/فایلِ خراب ⇒ `exit` (امن).

`shell_ready.json` (فقط برایِ handshake لانچر):

```json
{"pid": 12345, "url": "http://127.0.0.1:8001/"}
```

### ۲.۴ کدهایِ خروج و fallback

| وضعیت | رفتار |
| --- | --- |
| پوسته پیدا نشد | لاگ `[shell] shell exe not found` و رفتن به pywebview |
| پوسته پیش از `ready` مرد | لاگ با کدِ خروج و fallback به pywebview |
| `ready` در ۲۰ ثانیه نیامد | `terminate` همان PIDِ فرزند، لاگ، fallback |
| پنجره باز شد و بسته شد | لانچر خارج می‌شود (`[exit]` در لاگ) |
| پنجره به Tray رفت | لانچر منتظر می‌ماند؛ با «خروج» از Tray خارج می‌شود |
| پایتون مرد/کرش کرد | نگهبانِ والد در پوسته، پوسته را می‌بندد |

---

## ۳) نقشهٔ فایل‌ها

### ۳.۱ فایل‌هایِ تازه

| فایل | مسئولیت |
| --- | --- |
| `frontend/src-tauri/shell-dist/index.html` | صفحهٔ stubِ محلی برایِ اجرایِ بدونِ `--url` (بی‌اسکریپت) |
| `frontend/src-tauri/src/lib.rs` | کلِ پوسته: args، پنجره، Tray، تنظیمِ بستن، نگهبانِ والد (بازنویسی) |
| `bors_shell.py` | تنظیماتِ پوسته، مسیرِ EXE، خواندن/نوشتن/پرسشِ `close_action` (قابلِ تست) |
| `scripts/build_shell.py` | `cargo build --release --locked` و کپیِ EXE به `dist/` |
| `dev/shell_launcher_v103.py` | گاردِ منبع/توزیع + تستِ واحدِ `bors_shell` |
| `docs/MIGRATION-D1-SHELL-SLICE-2026-10-27.md` | همین سند |

### ۳.۲ فایل‌هایِ تغییرکرده

| فایل | تغییر |
| --- | --- |
| `frontend/src-tauri/Cargo.toml` | پینِ Tauri، فیچرِ `tray-icon`، نامِ باینری، `windows-sys`، نسخهٔ 1.0.88 |
| `frontend/src-tauri/tauri.conf.json` | `frontendDist` = stub، پنجرهٔ پیش‌فرض حذف، CSP غیرِ null |
| `bors_entry.py` | تلاشِ پوسته قبل از pywebview + `_open_shell_window` |
| `api/update.py` | انتظار برایِ مرگِ پوسته در batchِ نصب |
| `installer/bors_setup.iss` | `ShellExe` و kill در `EnsureAppNotRunning` |
| `scripts/build_all.py` | ساختِ پوسته پس از PyInstaller |
| `release.ps1` | فراخوانیِ `build_shell.py` و نظارت بر فایل‌هایِ پوسته |
| `.github/workflows/release.yml` | Rust toolchain/cache در jobِ `release-inno` |
| `dev/run_all_tests.py` | ثبتِ گاردِ تازه |
| `dev/version_anchor_guard.py` | لنگرِ هفتم: `Cargo.toml` |
| `AGENTS.md` | به‌روزرسانیِ فهرستِ لنگرها (شش → هفت) |
| `frontend/src-tauri/Cargo.lock` | تازه، commit می‌شود |

### ۳.۳ دست‌نخورده

`app.py`، `api/*` (به‌جز `update.py`)، `tauri`هایِ دیگر، `frontend/src/**`،
`fts_terminal.spec`، `requirements.txt`، `market.db`/`user.db`، `installer/out/**`.

---

## ۴) تسک‌ها

### Task 0 — پیش‌پروازِ محیط (بدونِ کد)

**Files:** هیچ.

- [ ] **Step 1: نسخهٔ Rust و Tauri را ثبت کن**

```bash
cargo --version
rustc --version
```

انتظار: `cargo 1.8x` و `rustc 1.8x` (حداقل 1.77.2).

- [ ] **Step 2: WebView2 را ثبت کن**

```bash
reg query "HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv
```

انتظار: نسخه‌ای مانند `155.0.4283.62`. اگر نبود، D1 متوقف می‌شود؛ نصبِ
Evergreen bootstrapper یک کارِ انتشار است، نه اسلایس.

- [ ] **Step 3: پروفایلِ فعلی را ببین (بدونِ خواندنِ مقدارِ رمز)**

```bash
ls "$LOCALAPPDATA/BorsTerminal_Ultimate/webview2/EBWebView/Default/Local Storage"
```

انتظار: پوشهٔ `leveldb`. این ثابت می‌کند مسیرِ پروفایلِ pywebview همان مسیرِ
WebView2 است که پوسته باید بگیرد.

- [ ] **Step 4: وضعیتِ پورتِ نصب‌شده را ببین (نکش)**

```bash
curl -s -m 2 http://127.0.0.1:8001/api/update/version || echo "8001 free"
```

اگر پاسخ داد، برنامهٔ نصب‌شده در حالِ اجراست: برایِ تست از پورتِ Portable
(`8101`) استفاده کن و هیچ فرآیندی را نکش.

- [ ] **Step 5: ثبت در گزارش**

این چهار عدد/وضعیت در گزارشِ D1 می‌آید: نسخهٔ Rust، نسخهٔ WebView2، وجودِ
`Local Storage`، و وضعیتِ 8001.

---

### Task 1 — پیکربندیِ crate و صفحهٔ stub

**Files:**
- Modify: `frontend/src-tauri/Cargo.toml`
- Modify: `frontend/src-tauri/tauri.conf.json`
- Create: `frontend/src-tauri/shell-dist/index.html`
- Create: `frontend/src-tauri/Cargo.lock` (با cargo)

**Interfaces:**
- Produces: باینریِ `BorsTerminal_Shell.exe` با args و رفتارِ Task 2.

- [ ] **Step 1: تستِ ناموفقِ پیکربندی بنویس**

```bash
cd frontend/src-tauri
cargo metadata --no-deps --format-version 1 | grep -q '"name":"BorsTerminal_Shell"' \
  && echo "BIN OK" || echo "BIN MISSING"
```

انتظار فعلی: `BIN MISSING`.

- [ ] **Step 2: `Cargo.toml` را کامل کن**

```toml
[package]
name = "bors-terminal"
version = "1.0.88"
description = "Bors Terminal Ultimate Desktop Shell"
authors = ["BorsTerminal"]
license = "MIT"
repository = ""
edition = "2021"
rust-version = "1.77.2"

[lib]
name = "bors_terminal_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[[bin]]
name = "BorsTerminal_Shell"
path = "src/main.rs"

[build-dependencies]
tauri-build = { version = "=2.6.3" }

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
log = "0.4"
tauri = { version = "=2.12.5", features = ["tray-icon"] }
tauri-plugin-log = "2"
tauri-plugin-updater = "2"
tauri-plugin-process = "2"

[target.'cfg(windows)'.dependencies]
windows-sys = { version = "=0.61.2", features = [
  "Win32_Foundation",
  "Win32_System_Threading",
] }
```

`Cargo.lock` نسخهٔ دقیقِ همهٔ وابستگی‌ها را pin می‌کند و commit می‌شود.

- [ ] **Step 3: `tauri.conf.json` را کامل کن**

```json
{
  "$schema": "../node_modules/@tauri-apps/cli/config.schema.json",
  "productName": "Bors Terminal Ultimate",
  "version": "1.0.88",
  "identifier": "com.borsterminal.app",
  "build": {
    "frontendDist": "shell-dist"
  },
  "app": {
    "windows": [],
    "security": {
      "csp": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi"],
    "createUpdaterArtifacts": true,
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  },
  "plugins": {
    "updater": {
      "endpoints": [
        "https://github.com/johnwarchief/BorsTerminal/releases/latest/download/latest.json"
      ],
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3NgpSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="
    }
  }
}
```

نکته: CSP فقط به محتوایِ محلی (stub) اعمال می‌شود؛ صفحهٔ loopback CSPِ خودش را
از سرورِ برنامه می‌گیرد (امروز هیچ CSP ندارد؛ سخت‌سازیِ آن کارِ D5 است).
`updater` دست‌نخورده ماند تا مسیرِ دستیِ Tauri حذف نشود، اما در D1 هیچ‌جا
فراخوانی نمی‌شود.

- [ ] **Step 4: صفحهٔ stub را بساز**

`frontend/src-tauri/shell-dist/index.html`:

```html
<!doctype html>
<html lang="fa" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <title>BorsTerminal Shell</title>
    <style>
      html, body { height: 100%; margin: 0; background: #0b0f17; color: #e6edf7;
        font: 14px/1.9 Tahoma, "Segoe UI", sans-serif; }
      .wrap { height: 100%; display: grid; place-items: center; padding: 24px; }
      .card { max-width: 520px; padding: 24px; border: 1px solid #1f2a3a;
        border-radius: 14px; background: #111827; }
      p { margin: 0; color: #8ea3bd; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <p>این پنجره فقط از داخل BorsTerminal اجرا می‌شود. برنامه را از میان‌بر
          خودش باز کنید.</p>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 5: قفل و کامپایل را بررسی کن**

```bash
cd frontend/src-tauri
cargo generate-lockfile
cargo check --locked
```

انتظار: `Finished` بدونِ خطا. اگر `tray-icon` یا APIیِ دیگری خطا داد، آن را
با نسخهٔ 2.12.5 هم‌تراز کن؛ نسخه را بالا/پایین نبر.

- [ ] **Step 6: Commit**

```bash
git add frontend/src-tauri/Cargo.toml frontend/src-tauri/Cargo.lock \
  frontend/src-tauri/tauri.conf.json frontend/src-tauri/shell-dist/index.html
git commit -m "feat(shell): Tauri window crate pinned to 2.12.5 with tray + stub page"
```

---

### Task 2 — پیاده‌سازیِ پوستهٔ Tauri

**Files:**
- Modify: `frontend/src-tauri/src/lib.rs` (بازنویسی)
- Test: همان فایل، `#[cfg(test)]`

**Interfaces:**
- Consumes: args در §۲.۱.
- Produces: EXEی که پنجره می‌سازد، `ready` می‌نویسد، Tray می‌دهد، رویِ
  `CloseRequested` تصمیم می‌گیرد و با مرگِ والد خارج می‌شود.

- [ ] **Step 1: تست‌هایِ واحد را اول بنویس (در انتهایِ lib.rs)**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn args_parse_all() {
        let a = Args::from_iter(
            [
                "--url", "http://127.0.0.1:8001/",
                "--profile", "C:\\p",
                "--settings", "C:\\s.json",
                "--ready", "C:\\r.json",
                "--parent-pid", "123",
            ]
            .iter()
            .map(|s| s.to_string()),
        );
        assert_eq!(a.url.as_deref(), Some("http://127.0.0.1:8001/"));
        assert_eq!(a.parent_pid, Some(123));
        assert!(a.profile.is_some());
        assert!(a.settings.is_some());
    }

    #[test]
    fn settings_default_to_exit_when_missing() {
        let st = ShellState::from_settings(&Some(PathBuf::from("Z:\\no\\such.json")));
        assert!(!st.close_to_tray.load(Ordering::Relaxed));
    }

    #[test]
    fn settings_roundtrip_tray_and_exit() {
        let dir = std::env::temp_dir().join(format!("bors_shell_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let p = dir.join("shell_settings.json");
        let st = ShellState { close_to_tray: AtomicBool::new(false), settings_path: Some(p.clone()) };
        st.write(true);
        assert!(ShellState::from_settings(&Some(p.clone())).close_to_tray.load(Ordering::Relaxed));
        st.write(false);
        assert!(!ShellState::from_settings(&Some(p.clone())).close_to_tray.load(Ordering::Relaxed));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
```

- [ ] **Step 2: تست را رد کن**

```bash
cd frontend/src-tauri
cargo test --locked
```

انتظار: خطایِ کامپایل (`Args`/`ShellState` وجود ندارند).

- [ ] **Step 3: `lib.rs` را کامل کن**

```rust
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::menu::{CheckMenuItemBuilder, MenuBuilder, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct ShellSettings {
    version: u32,
    close_action: String,
}

struct ShellState {
    close_to_tray: AtomicBool,
    settings_path: Option<PathBuf>,
}

impl ShellState {
    fn from_settings(path: &Option<PathBuf>) -> Self {
        let mut close_to_tray = false;
        if let Some(p) = path {
            if let Ok(txt) = std::fs::read_to_string(p) {
                if let Ok(s) = serde_json::from_str::<ShellSettings>(&txt) {
                    close_to_tray = s.close_action == "tray";
                }
            }
        }
        Self {
            close_to_tray: AtomicBool::new(close_to_tray),
            settings_path: path.clone(),
        }
    }

    fn write(&self, close_to_tray: bool) {
        let Some(p) = &self.settings_path else { return };
        let s = ShellSettings {
            version: 1,
            close_action: if close_to_tray { "tray".into() } else { "exit".into() },
        };
        if let Ok(txt) = serde_json::to_string_pretty(&s) {
            let _ = std::fs::write(p, txt);
        }
    }
}

#[derive(Default)]
struct Args {
    url: Option<String>,
    profile: Option<PathBuf>,
    settings: Option<PathBuf>,
    ready: Option<PathBuf>,
    parent_pid: Option<u32>,
}

impl Args {
    fn from_iter<I: Iterator<Item = String>>(iter: I) -> Self {
        let mut a = Args::default();
        let mut it = iter;
        while let Some(k) = it.next() {
            let Some(v) = it.next() else { break };
            match k.as_str() {
                "--url" => a.url = Some(v),
                "--profile" => a.profile = Some(PathBuf::from(v)),
                "--settings" => a.settings = Some(PathBuf::from(v)),
                "--ready" => a.ready = Some(PathBuf::from(v)),
                "--parent-pid" => a.parent_pid = v.parse().ok(),
                _ => {}
            }
        }
        a
    }

    fn parse() -> Self {
        Self::from_iter(std::env::args().skip(1))
    }
}

fn write_ready(path: &Option<PathBuf>, url: Option<&str>) {
    let Some(p) = path else { return };
    let url_json = serde_json::to_string(&url.unwrap_or(""))
        .unwrap_or_else(|_| "\"\"".into());
    let body = format!("{{\"pid\":{},\"url\":{}}}", std::process::id(), url_json);
    let _ = std::fs::write(p, body);
}

#[cfg(windows)]
fn watch_parent(pid: u32, app: tauri::AppHandle) {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::Threading::{OpenProcess, WaitForSingleObject, INFINITE};
    const SYNCHRONIZE: u32 = 0x0010_0000;

    std::thread::spawn(move || unsafe {
        let h = OpenProcess(SYNCHRONIZE, 0, pid);
        if h.is_null() {
            return;
        }
        WaitForSingleObject(h, INFINITE);
        CloseHandle(h);
        app.exit(0);
    });
}

#[cfg(not(windows))]
fn watch_parent(_pid: u32, _app: tauri::AppHandle) {}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let args = Args::parse();
            let state = ShellState::from_settings(&args.settings);
            let close_to_tray = state.close_to_tray.load(Ordering::Relaxed);
            app.manage(state);

            let builder = match args.url.as_deref() {
                Some(u) => {
                    let url: tauri::Url = u.parse()?;
                    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                }
                None => {
                    WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                }
            };
            let mut builder = builder
                .title("بورس‌ترمینال — BorsTerminal")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1024.0, 640.0)
                .maximized(true)
                .visible(false);
            if let Some(p) = &args.profile {
                builder = builder.data_directory(p.clone());
            }
            let win = builder.build()?;

            let app_handle = app.handle().clone();
            let win_for_close = win.clone();
            win.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    let state = app_handle.state::<ShellState>();
                    if state.close_to_tray.load(Ordering::Relaxed) {
                        api.prevent_close();
                        let _ = win_for_close.hide();
                    }
                }
            });

            let show_item = MenuItemBuilder::with_id("show", "نمایشِ پنجره").build(app)?;
            let close_item = CheckMenuItemBuilder::with_id(
                "close_tray",
                "بستنِ پنجره → System Tray",
            )
            .checked(close_to_tray)
            .build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "خروج").build(app)?;
            let menu = MenuBuilder::new(app)
                .items(&[&show_item, &close_item, &quit_item])
                .build()?;

            let mut tray_builder = TrayIconBuilder::with_id("main")
                .tooltip("بورس‌ترمینال")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "close_tray" => {
                        let state = app.state::<ShellState>();
                        let new_value = !state.close_to_tray.load(Ordering::Relaxed);
                        state.close_to_tray.store(new_value, Ordering::Relaxed);
                        state.write(new_value);
                        let _ = close_item.set_checked(new_value);
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                });
            if let Some(icon) = app.handle().default_window_icon() {
                tray_builder = tray_builder.icon(icon.clone());
            }
            let tray = tray_builder.build(app)?;
            app.manage(tray);

            win.show()?;
            write_ready(&args.ready, args.url.as_deref());
            if let Some(pid) = args.parent_pid {
                watch_parent(pid, app.handle().clone());
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

`src/main.rs` تغییر نمی‌کند:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  bors_terminal_lib::run();
}
```

- [ ] **Step 4: تست‌ها را سبز کن**

```bash
cd frontend/src-tauri
cargo test --locked
```

انتظار: ۳ تستِ PASS.

- [ ] **Step 5: بیلدِ release**

```bash
cargo build --release --locked
ls -la target/release/BorsTerminal_Shell.exe
```

انتظار: EXE بینِ ۶ تا ۱۵ مگابایت.

- [ ] **Step 6: دودِ دستی با یک URLِ محلی**

```bash
cd frontend/src-tauri
./target/release/BorsTerminal_Shell.exe \
  --url http://127.0.0.1:8001/ \
  --settings "$TEMP/shell_settings.json" \
  --ready "$TEMP/shell_ready.json" \
  --parent-pid $$
cat "$TEMP/shell_ready.json"
```

انتظار: پنجره باز می‌شود (اگر برنامهٔ نصب‌شده در حالِ اجراست) و `ready` نوشته
می‌شود. اگر 8001 آزاد است، به‌جای URLِ صفحهٔ بوت/خطا، فقط بازشدنِ پنجره و
نوشتنِ `ready` مهم است. سپس پنجره را ببند؛ با `close_action=exit` فرآیند تمام
می‌شود. `shell_settings.json` را حذف کن.

- [ ] **Step 7: Commit**

```bash
git add frontend/src-tauri/src/lib.rs
git commit -m "feat(shell): tauri window, tray close policy, ready handshake, parent watchdog"
```

---

### Task 3 — اتصالِ لانچرِ پایتون

**Files:**
- Create: `bors_shell.py`
- Modify: `bors_entry.py` (نزدیکِ `_webview_storage_dir`/`open_native_window`)
- Test: `dev/shell_launcher_v103.py` (Task 6)

**Interfaces:**
- Consumes: `BorsTerminal_Shell.exe` و args در §۲.۱.
- Produces: `open_native_window(url)` که اول پوسته را امتحان می‌کند و در شکست
  به pywebview برمی‌گردد.

- [ ] **Step 1: `bors_shell.py` را بساز**

```python
# -*- coding: utf-8 -*-
"""ابزارهایِ پوستهٔ Tauri (D1) — بدونِ وابستگی به لانچر، تا قابلِ تست باشد."""
import json
import os

SHELL_EXE = 'BorsTerminal_Shell.exe'
SHELL_READY_TIMEOUT = 20.0
_VALID_ACTIONS = ('tray', 'exit')


def shell_exe_path(*roots):
    """نخستین مسیری که Shell EXE در آن هست؛ None یعنی نصب/بیلد نشده."""
    for root in roots:
        if not root:
            continue
        p = os.path.join(root, SHELL_EXE)
        if os.path.isfile(p):
            return p
    return None


def settings_path(root):
    return os.path.join(root, 'shell_settings.json')


def read_close_action(path):
    """'tray' یا 'exit'؛ فایلِ خراب/مقدارِ ناشناخته ⇒ 'exit'."""
    try:
        with open(path, encoding='utf-8') as f:
            value = json.load(f).get('close_action')
        return value if value in _VALID_ACTIONS else 'exit'
    except Exception:
        return 'exit'


def write_close_action(path, action):
    action = action if action in _VALID_ACTIONS else 'exit'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'version': 1, 'close_action': action},
                      f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f'[shell] cannot write settings ({e})')
        return False


def ask_close_action(path, ask=True):
    """نخستین اجرا: خروج یا Tray. انتخاب در فایل می‌ماند؛ تا تغییرِ Tray."""
    if os.path.isfile(path):
        return read_close_action(path)
    if not ask:
        write_close_action(path, 'exit')
        return 'exit'
    action = 'exit'
    try:
        import ctypes
        mb_yesno, mb_icon, mb_front = 0x4, 0x20, 0x10000
        msg = (
            'بستنِ پنجره چه معنایی داشته باشد؟\n\n'
            'بله: انتقال به System Tray — دریافتِ بازار و وضعیتِ اتصال ادامه می‌یابد.\n'
            'خیر: خروجِ کامل.\n\n'
            'این انتخاب بعداً از منویِ Tray قابلِ تغییر است.'
        )
        result = ctypes.windll.user32.MessageBoxW(
            0, msg, 'BorsTerminal — رفتارِ بستنِ پنجره',
            mb_yesno | mb_icon | mb_front)
        action = 'tray' if result == 6 else 'exit'   # IDYES = 6
    except Exception as e:
        print(f'[shell] close dialog failed ({e}) -> exit')
    write_close_action(path, action)
    return action
```

- [ ] **Step 2: تستِ واحدِ پایتون را بنویس (در گاردِ Task 6، اینجا اجرا کن)**

```python
# dev/shell_launcher_v103.py (بخشِ اول؛ فایلِ کامل در Task 6)
import bors_shell
assert bors_shell.read_close_action('nope.json') == 'exit'
assert bors_shell.ask_close_action('tmp.json', ask=False) == 'exit'
```

- [ ] **Step 3: `bors_entry.py` را وصل کن**

پس از `_webview_storage_dir` و پیش از `open_native_window`:

```python
# ── پوستهٔ Tauri (D1) ─────────────────────────────────────────────────────
# میزبان هنوز همین لانچر است؛ پوسته فقط پنجره می‌سازد. شکستِ پوسته باید بی‌صدا
# به pywebview برنگردد: دلیل در لاگ می‌ماند و انتخاب با BORS_SHELL قابلِ بازگشت است.
def _open_shell_window(url):
    exe = bors_shell.shell_exe_path(WORK, _data_root())
    if not exe:
        print('[shell] shell exe not found -> pywebview')
        _note('shell exe missing')
        return False
    try:
        import bors_config
        data_dir = bors_config.WORK_DIR
    except Exception:
        data_dir = WORK
    settings = bors_shell.settings_path(data_dir)
    action = bors_shell.ask_close_action(
        settings, ask=os.environ.get('BORS_SHELL_ASK_CLOSE', '1') != '0')
    profile = _webview_storage_dir()
    ready = os.path.join(data_dir, 'shell_ready.json')
    try:
        if os.path.isfile(ready):
            os.remove(ready)
    except OSError:
        pass
    args = [exe, '--url', url, '--settings', settings,
            '--ready', ready, '--parent-pid', str(os.getpid())]
    if profile:
        args += ['--profile', profile]
    _note(f'shell launch close={action} url={url}')
    try:
        proc = subprocess.Popen(args, cwd=WORK)
    except Exception as e:
        print(f'[shell] launch failed ({e}) -> pywebview')
        _note(f'shell launch failed: {e}')
        return False
    deadline = time.time() + bors_shell.SHELL_READY_TIMEOUT
    while time.time() < deadline:
        if os.path.isfile(ready):
            _note(f'shell ready pid={proc.pid}')
            try:
                code = proc.wait()
            except KeyboardInterrupt:
                code = -1
            _note(f'shell closed code={code}')
            return True
        if proc.poll() is not None:
            print(f'[shell] died before ready (code={proc.returncode}) -> pywebview')
            _note(f'shell died before ready code={proc.returncode}')
            return False
        time.sleep(0.2)
    print(f'[shell] not ready in {bors_shell.SHELL_READY_TIMEOUT:.0f}s -> pywebview')
    _note('shell ready timeout')
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        pass
    return False
```

در بالایِ `bors_entry.py`، کنارِ importها:

```python
import bors_shell
```

در `open_native_window`، بلافاصله پس از گاردِ `BORS_NATIVE_WINDOW` و پیش از
`import webview`:

```python
    if os.environ.get('BORS_SHELL', 'tauri').strip().lower() not in ('0', 'off', 'pywebview'):
        if _open_shell_window(url):
            return True
        # ادامه: مسیرِ pywebview به‌عنوانِ fallback
```

مسیرِ pywebview و `webview.start(**kwargs)` دست‌نخورده می‌ماند.

- [ ] **Step 4: تستِ دستی با URLِ ساختگی (بدونِ بک‌اند)**

```bash
python - <<'PY'
import bors_shell, os, tempfile
d = tempfile.mkdtemp(prefix='d1_')
p = os.path.join(d, 'shell_settings.json')
assert bors_shell.read_close_action(p) == 'exit'
assert bors_shell.ask_close_action(p, ask=False) == 'exit'
assert bors_shell.read_close_action(p) == 'exit'
print('bors_shell OK', d)
PY
```

انتظار: `bors_shell OK`.

- [ ] **Step 5: بررسیِ منبع**

```bash
python - <<'PY'
src = open('bors_entry.py', encoding='utf-8').read()
assert 'bors_shell' in src and '_open_shell_window' in src
assert src.index('_open_shell_window(url)') < src.index('import webview')
assert 'webview.start(**kwargs)' in src
print('launcher wiring OK')
PY
```

- [ ] **Step 6: Commit**

```bash
git add bors_shell.py bors_entry.py
git commit -m "feat(shell): launcher prefers tauri window with pywebview fallback"
```

---

### Task 4 — قفل‌هایِ آپدیتر و نصب‌کننده

**Files:**
- Modify: `api/update.py` (`_spawn_install` و ثابت‌ها)
- Modify: `installer/bors_setup.iss`
- Test: `dev/shell_launcher_v103.py` (Task 6)

**Interfaces:**
- Consumes: `BorsTerminal_Shell.exe` کنارِ `BorsTerminal_Ultimate.exe`.
- Produces: نصبِ سایلنت بدونِ فایلِ قفل‌شده؛ حذفِ نصب بدونِ پنجرهٔ زنده.

- [ ] **Step 1: تستِ ردشدنی برای batch بنویس**

در گارد (Task 6) این را اضافه کن:

```python
import api.update as upd
lines = upd._install_batch_lines(1234, r"C:\app\BorsTerminal_Ultimate.exe",
                                 r"C:\tmp\setup.exe", ["/VERYSILENT"])
text = "\n".join(lines)
assert 'BorsTerminal_Shell.exe' in text
assert ':waitshell' in text
```

انتظار فعلی: `AttributeError: _install_batch_lines`.

- [ ] **Step 2: `api/update.py` را بازآرایی کن**

نزدیکِ `APP_EXE`:

```python
SHELL_EXE = "BorsTerminal_Shell.exe"
```

`_spawn_install` را به دو بخش تقسیم کن:

```python
def _install_batch_lines(pid, app_exe, installer, flags):
    """خطوطِ batchِ نصب: منتظرِ مرگِ پایتون و پوسته، سپس setup و اجرای دوباره."""
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        ":wait",
        'tasklist /fi "PID eq %d" 2>nul | find "%d" >nul' % (pid, pid),
        "if errorlevel 1 goto waitshell",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":waitshell",
        "set /a SHELL_TRIES=0",
        ":waitshell_loop",
        'tasklist /fi "IMAGENAME eq %s" 2>nul | find /I "%s" >nul'
        % (SHELL_EXE, SHELL_EXE),
        "if errorlevel 1 goto run",
        "set /a SHELL_TRIES+=1",
        "if %SHELL_TRIES% GEQ 15 goto run",
        "ping -n 2 127.0.0.1 >nul",
        "goto waitshell_loop",
        ":run",
        'start /WAIT "" "%s" %s' % (installer, " ".join(flags)),
    ]
    if app_exe:
        lines += [
            'if not exist "%s" goto end' % app_exe,
            'start "" "%s"' % app_exe,
        ]
    lines += [":end", 'del "%~f0"']
    return lines


def _spawn_install(installer, flags):
    pid = os.getpid()
    bat_path = os.path.join(CACHE_DIR, "bors_install.cmd")
    lines = _install_batch_lines(pid, _app_exe_path(), installer, flags)
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")
    creationflags = 0x00000008 | 0x08000000
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=creationflags, close_fds=True)
    threading.Thread(target=_delayed_exit, args=(2.0,), daemon=True).start()
```

کامنتِ توضیحیِ قبلیِ `_spawn_install` را حفظ کن و یک جمله اضافه کن: «پوستهٔ Tauri
هم باید بمیرد؛ وگرنه Inno فایلِ قفل‌شده را نمی‌تواند جایگزین کند.»

- [ ] **Step 3: نصب‌کننده را هم‌تراز کن**

نزدیکِ `#define AppExe`:

```pascal
#define ShellExe "BorsTerminal_Shell.exe"
```

در `EnsureAppNotRunning`، پس از killِ `AppExe`:

```pascal
  Exec(ExpandConstant('{cmd}'), '/C "taskkill /F /IM {#ShellExe} >NUL 2>NUL"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
```

- [ ] **Step 4: تست‌ها را اجرا کن**

```bash
python - <<'PY'
import api.update as upd
lines = upd._install_batch_lines(1234, r"C:\app\BorsTerminal_Ultimate.exe",
                                 r"C:\tmp\setup.exe", ["/VERYSILENT"])
text = "\n".join(lines)
assert 'BorsTerminal_Shell.exe' in text and ':waitshell' in text
assert ':run' in text and 'start /WAIT' in text
print('install batch OK')
PY
```

انتظار: `install batch OK`.

- [ ] **Step 5: Commit**

```bash
git add api/update.py installer/bors_setup.iss
git commit -m "fix(shell): updater waits for tauri shell; installer kills both exes"
```

---

### Task 5 — زنجیرهٔ بیلد و انتشار

**Files:**
- Create: `scripts/build_shell.py`
- Modify: `scripts/build_all.py`
- Modify: `release.ps1`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `frontend/src-tauri/Cargo.toml` و `Cargo.lock`.
- Produces: `dist/BorsTerminal_Ultimate/BorsTerminal_Shell.exe` در هر بیلد.

- [ ] **Step 1: تستِ ناموفق**

```bash
python -c "import os; print(os.path.isfile('dist/BorsTerminal_Ultimate/BorsTerminal_Shell.exe'))"
```

انتظار: `False`.

- [ ] **Step 2: `scripts/build_shell.py` را بساز**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ساختِ پنجرهٔ Tauri و کپیِ آن کنارِ باندلِ پایتون (D1).

پیش‌نیاز: cargo روی PATH. خروجی: dist/BorsTerminal_Ultimate/BorsTerminal_Shell.exe
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAURI = os.path.join(ROOT, 'frontend', 'src-tauri')
EXE = os.path.join(TAURI, 'target', 'release', 'BorsTerminal_Shell.exe')
OUT = os.path.join(ROOT, 'dist', 'BorsTerminal_Ultimate')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', default=OUT)
    args = ap.parse_args()
    if not shutil.which('cargo'):
        print('[ERR] cargo not on PATH; install Rust or use --skip-shell')
        return 1
    print('[shell] cargo build --release --locked')
    rc = subprocess.call(['cargo', 'build', '--release', '--locked'], cwd=TAURI)
    if rc != 0 or not os.path.isfile(EXE):
        print('[ERR] shell build failed')
        return 1
    os.makedirs(args.dist, exist_ok=True)
    dest = os.path.join(args.dist, os.path.basename(EXE))
    shutil.copy2(EXE, dest)
    size = os.path.getsize(dest)
    sha = hashlib.sha256(open(dest, 'rb').read()).hexdigest()
    print(f'[OK] {dest} {size / 1e6:.2f} MB sha256={sha[:16]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 3: `scripts/build_all.py` را وصل کن**

```python
    ap.add_argument('--skip-shell', action='store_true',
                    help='skip the Tauri window build')
```

پس از بلاکِ PyInstaller و پیش از بررسیِ `OUT`:

```python
    if not args.skip_shell:
        run([sys.executable, os.path.join('scripts', 'build_shell.py')], ROOT,
            'shell: Tauri window')
```

- [ ] **Step 4: `release.ps1` را وصل کن**

در `Build-Exe`، پس از `Test-DistBundle`:

```powershell
    & $PY scripts\build_shell.py
    if ($LASTEXITCODE -ne 0) { Write-Error '[shell] build failed. ABORT.'; exit 1 }
    if (-not (Test-Path "$Bundle\BorsTerminal_Shell.exe")) {
        Write-Error '[shell] BorsTerminal_Shell.exe missing from bundle. ABORT.'; exit 1
    }
```

`$watch` را گسترش بده:

```powershell
               'frontend/src-tauri/Cargo.toml',
               'frontend/src-tauri/Cargo.lock',
               'frontend/src-tauri/tauri.conf.json',
               'frontend/src-tauri/src/lib.rs',
               'frontend/src-tauri/src/main.rs',
               'frontend/src-tauri/shell-dist/index.html',
               'scripts/build_shell.py',
```

- [ ] **Step 5: CI را هم‌تراز کن**

در jobِ `release-inno`، پیش از `Build Python Backend`:

```yaml
      - name: Install Rust Stable Toolchain
        uses: dtolnay/rust-toolchain@stable

      - name: Rust Cache
        uses: swatinem/rust-cache@v2
        with:
          workspaces: 'frontend/src-tauri'
```

`python scripts/build_all.py` خودش پوسته را می‌سازد. jobِ دستیِ
`release-windows` را تغییر نده؛ محصول نیست و D1 آن را منتشر نمی‌کند.

- [ ] **Step 6: بیلد را اجرا کن**

```bash
python scripts/build_all.py --skip-npm
```

انتظار: پیامِ `[shell] build ...` و `[OK] ... BorsTerminal_Shell.exe`؛ سپس
`dist/BorsTerminal_Ultimate/BorsTerminal_Shell.exe` موجود است.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_shell.py scripts/build_all.py release.ps1 .github/workflows/release.yml
git commit -m "build(shell): compile tauri window into the onedir bundle and release-inno CI"
```

---

### Task 6 — گاردها و لنگرها

**Files:**
- Create: `dev/shell_launcher_v103.py`
- Modify: `dev/run_all_tests.py`
- Modify: `dev/version_anchor_guard.py`
- Modify: `AGENTS.md`

- [ ] **Step 1: گارد را بساز**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/shell_launcher_v103.py — قراردادِ پوستهٔ Tauri در منبع و باندل.

چرا: پنجرهٔ تازه سه راهِ شکستِ بی‌صدا دارد: فراموش‌شدنِ fallback به pywebview،
از‌دست‌رفتنِ پروفایلِ تنظیمات، و جاافتادنِ EXE در باندل/نصب. این گارد هر سه را
می‌سنجد. `--dist` وجود و اندازهٔ EXE را هم چک می‌کند.
"""
import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import bors_shell  # noqa: E402

FAILS = []


def ck(label, cond):
    print(('  ok   ' if cond else '  FAIL ') + label)
    if not cond:
        FAILS.append(label)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', default='')
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix='bors_shell_guard_') as d:
        p = os.path.join(d, 'shell_settings.json')
        ck('missing settings -> exit', bors_shell.read_close_action(p) == 'exit')
        ck('ask disabled writes exit',
           bors_shell.ask_close_action(p, ask=False) == 'exit')
        ck('exit persisted', bors_shell.read_close_action(p) == 'exit')
        ck('tray write/read',
           bors_shell.write_close_action(p, 'tray')
           and bors_shell.read_close_action(p) == 'tray')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('{broken')
        ck('broken settings -> exit', bors_shell.read_close_action(p) == 'exit')
        ck('exe missing -> None', bors_shell.shell_exe_path(d) is None)
        fake = os.path.join(d, bors_shell.SHELL_EXE)
        open(fake, 'wb').close()
        ck('exe found', bors_shell.shell_exe_path(d) == fake)
        ck('ready timeout bounded', 0 < bors_shell.SHELL_READY_TIMEOUT <= 30)

    src = read('bors_entry.py')
    ck('launcher uses bors_shell', 'import bors_shell' in src and '_open_shell_window' in src)
    ck('shell tried before pywebview',
       src.index('_open_shell_window(url)') < src.index('import webview'))
    ck('pywebview fallback intact', 'webview.start(**kwargs)' in src)
    ck('shell switch env', "BORS_SHELL" in src)

    conf = json.loads(read('frontend/src-tauri/tauri.conf.json'))
    ck('no default window', conf.get('app', {}).get('windows') == [])
    ck('stub frontendDist',
       conf.get('build', {}).get('frontendDist') == 'shell-dist')
    ck('csp is not null', conf.get('app', {}).get('security', {}).get('csp') is not None)

    cargo = read('frontend/src-tauri/Cargo.toml')
    ck('tauri pinned 2.12.5', 'version = "=2.12.5"' in cargo)
    ck('tray feature enabled', 'features = ["tray-icon"]' in cargo)
    ck('shell binary name', 'name = "BorsTerminal_Shell"' in cargo)

    iss = read('installer/bors_setup.iss')
    ck('installer knows shell', '{#ShellExe}' in iss and 'BorsTerminal_Shell.exe' in iss)
    upd = read('api/update.py')
    ck('updater waits for shell', 'SHELL_EXE' in upd and ':waitshell' in upd)

    if args.dist:
        exe = os.path.join(args.dist, bors_shell.SHELL_EXE)
        exists = os.path.isfile(exe)
        ck('shell in bundle', exists)
        if exists:
            mb = os.path.getsize(exe) / 1e6
            ck(f'shell size sane ({mb:.2f} MB)', 5 <= mb <= 25)
        ck('python exe in bundle',
           os.path.isfile(os.path.join(args.dist, 'BorsTerminal_Ultimate.exe')))

    print(f'\n{len(FAILS)} failed')
    print('SHELL LAUNCHER GUARD ' + ('OK' if not FAILS else 'FAILED'))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: اجرا کن**

```bash
python dev/shell_launcher_v103.py --dist dist/BorsTerminal_Ultimate
```

انتظار: `SHELL LAUNCHER GUARD OK`.

- [ ] **Step 3: در `run_all_tests.py` ثبت کن**

نزدیکِ گاردهایِ دیگر:

```python
    ('dev/shell_launcher_v103.py', 'Tauri shell contract: launcher fallback + bundle'),
```

- [ ] **Step 4: لنگرِ هفتمِ نسخه**

در `dev/version_anchor_guard.py` پس از بلاکِ `tauri.conf.json`:

```python
    cargo = read(os.path.join("frontend", "src-tauri", "Cargo.toml"))
    m = re.search(r'^version\s*=\s*"([^"]+)"', cargo, re.M)
    find("src-tauri/Cargo.toml", m.group(1) if m else None)
```

و در docstring/پیام: «شش جا» → «هفت جا».

- [ ] **Step 5: `AGENTS.md` را هم‌تراز کن**

در بخشِ «نام‌گذاریِ بیلد و ریلیز»: «شش لنگرِ نسخه» → «هفت لنگرِ نسخه» و
`frontend/src-tauri/Cargo.toml` را به فهرست اضافه کن.

- [ ] **Step 6: گاردها را اجرا کن**

```bash
python dev/shell_launcher_v103.py --dist dist/BorsTerminal_Ultimate
python dev/version_anchor_guard.py
python dev/test_compat_guard_v1012.py
python dev/loopback_guard_v1029.py
python dev/onedir_contract_v11.py --dist dist
python dev/persian_glyph_guard.py
```

انتظار: همه OK. اگر `test_compat_guard_v1012` از تغییرِ `bors_entry.py` قرمز شد،
پیمانِ آن را با حفظِ `_webview_storage_dir` و `webview.start(**kwargs)` نگه دار؛
حذفِ مسیرِ pywebview در D1 مجاز نیست.

- [ ] **Step 7: Commit**

```bash
git add dev/shell_launcher_v103.py dev/run_all_tests.py dev/version_anchor_guard.py AGENTS.md
git commit -m "test(shell): guard launcher fallback, profile settings and bundle contract"
```

---

### Task 7 — پذیرشِ زندهٔ §۱۲.۲۸ و اندازه‌گیری

**Files:** هیچ (فقط اجرا و گزارش).

- [ ] **Step 1: بیلدِ Portableِ مستقل بساز**

```bash
python scripts/build_all.py --skip-npm
python - <<'PY'
import shutil, os, tempfile
src = os.path.join('dist', 'BorsTerminal_Ultimate')
dst = os.path.join(tempfile.gettempdir(), 'bors_d1_slice')
if os.path.isdir(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)
open(os.path.join(dst, 'bors_portable.flag'), 'w', encoding='ascii').write('1')
print(dst)
PY
```

`bors_portable.flag` یعنی دادهٔ مستقل (`<dst>/data`) و پورت `8101`؛ نصبِ عملیاتی
دست‌نخورده می‌ماند (§۱۲.۳۱).

- [ ] **Step 2: دادهٔ آزمون را از نسخهٔ A به نسخهٔ D1 کپی کن**

از نسخهٔ Portable سنجشِ A (یا یک کپیِ آفلاینِ همان `market.db`)، فقط
`market.db` را در `<dst>/data/market.db` بگذار. **از `market.db` عملیاتیِ در حالِ
نوشتن کپی نکن**؛ اگر برنامهٔ نصب‌شده باز است، از کپیِ A استفاده کن.

- [ ] **Step 3: گیتِ آفلاین را روشن کن**

```bash
export HTTP_PROXY=127.0.0.1:9 HTTPS_PROXY=127.0.0.1:9 ALL_PROXY=127.0.0.1:9
export NO_PROXY=127.0.0.1,localhost
export BORS_NO_FETCH_LOOPS=1
export BORS_SHELL_ASK_CLOSE=0
export BORS_SHELL=tauri
```

گیتِ IPِ TSETMC/Codal را از `tools/migration/perf_baseline.py` (همان
`TSETMC_IPS`/`BLOCK`ِ سنجشِ A) بگیر؛ `BORS_NO_FETCH_LOOPS` تنها کافی نیست.

- [ ] **Step 4: اجرا و مسیرِ انتها‌به‌انتهایِ §۱۲.۲۸**

```bash
"$(cygpath "$TEMP")/bors_d1_slice/BorsTerminal_Ultimate.exe"
```

به‌ترتیب بررسی کن و هر مورد را در جدولِ گزارش ثبت کن:

| # | بررسی | شاهد |
| --- | --- | --- |
| ۱ | نصب/شروعِ مستقل | پورت 8101، مسیرِ دادهٔ `<dst>/data`، نصبِ عملیاتی دست‌نخورده |
| ۲ | دادهٔ واقعی در محیطِ کنترل‌شده | `GET /api/market` 200 و حجمِ ~۷٫۴ مگابایت از DBِ کپی |
| ۳ | تابلو | `fe_probe` روی `/market`؛ حداقل ۱۰ ردیفِ `tape-row` |
| ۴ | نمودار و کندلِ تعدیل‌شده | `/technical`، `chart-area` و canvas؛ همان مسیرِ A |
| ۵ | حداقلِ تکنیکال | تایم‌فریم/نشانگرِ ضروریِ همان صفحه |
| ۶ | نسخه/تازگیِ ورودی | `/api/update/version` و نشانگرِ تازگیِ UI |
| ۷ | بستن/بازکردن | `[shell] window ready` و `[exit]`؛ پورت پس از بستن آزاد |
| ۸ | قطع/وصلِ شبکه | گیتِ آفلاین، سپس رفعِ گیت و بازیابیِ داده؛ بدونِ معرفیِ دادهٔ کهنه به‌عنوانِ زنده |
| ۹ | مالکیتِ poller/DB | یک حلقه؛ هیچ processِ اضافیِ بک‌اند |

- [ ] **Step 5: اندازه‌گیریِ CDP (همان روشِ C)**

```bash
export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=9334"
# اجرای دوبارهٔ برنامه، سپس:
BORS_CDP=http://127.0.0.1:9334 \
BORS_UI_BASE=http://127.0.0.1:8101 \
BORS_VIEWPORT=1366x768 BORS_RUNS=2 \
node tools/migration/fe_probe.js --out D1_ui_1366.json
```

ثبت کن: cold/warm، اولین `GET /`، اولین `/api/*`، زمانِ تب‌ها (بازار/تکنیکال/
بنیادی/وضعیت/استراتژی)، TBT/long task، canvas، heap. سپس RSSِ کلِ درخت
(پایتون + `BorsTerminal_Shell.exe` + `msedgewebview2*`) بعد از idle؛ حجمِ
باندل. مقایسه با A و C در جدولِ گزارش.

- [ ] **Step 6: تستِ نگهبانِ والد**

پنجره را باز نگه دار و فقط PIDِ پایتونی که خودت بالا آورده‌ای را بکش:

```bash
python - <<'PY'
import os, signal, subprocess, sys
# PID را از لاگ/پورت 8101 بگیر؛ هرگز taskkill /IM اجرا نکن.
print('kill the exact python PID you started')
PY
```

انتظار: `BorsTerminal_Shell.exe` حداکثر تا ~۲ ثانیه بسته می‌شود؛ هیچ پنجرهٔ
مرده نمی‌ماند. این را در گزارش با زمان ثبت کن.

- [ ] **Step 7: تستِ Tray (دستی)**

`shell_settings.json` را به `tray` تغییر بده، برنامه را باز کن، پنجره را ببند:
پنجره ناپدید می‌شود ولی پایتون و پورت زنده می‌مانند. از منویِ Tray «نمایشِ
پنجره» و سپس «خروج» را بزن. اگر اجرایِ تعاملی ممکن نیست، این مورد را
`UNVERIFIED` ثبت کن؛ خودت PASS اعلام نکن.

- [ ] **Step 8: تستِ fallback**

```bash
export BORS_SHELL=pywebview
```

انتظار: پنجرهٔ pywebview باز می‌شود (مسیرِ قدیم سالم). سپس
`BORS_SHELL=tauri` و پوسته را موقتاً تغییرِ نام بده: لاگِ `shell exe not found`
و fallback. پوسته را برگردان.

- [ ] **Step 9: گزارش**

گزارش با جدولِ RTL: اعداد، مقایسه با A/C، مواردِ `UNVERIFIED`، و هر اختلاف.
هیچ PASS بصری خوداعلام نکن.

---

### Task 8 — جمع‌بندی، Commit و Push

- [ ] **Step 1: `python dev/run_all_tests.py`** (سرورهایِ dev بسته باشند)
- [ ] **Step 2: `npx tsc -b` و `npx vitest run`** در `frontend/` (بدونِ تغییرِ فرانت، برایِ اطمینان)
- [ ] **Step 3: گزارشِ خروجی را قبل از commit بنویس و اعداد را ذکر کن**
- [ ] **Step 4: Commitِ نهاییِ اسناد/گزارش**

```bash
git add docs/MIGRATION-D1-SHELL-SLICE-2026-10-27.md docs/MIGRATION-D-SPEC-2026-10-27.md
git commit -m "docs(migration): D1 shell-slice plan and measured acceptance"
```

- [ ] **Step 5: Push فقط شاخهٔ مأموریت**

```bash
git push github mission/4-axes-2026-10-10
git ls-remote github refs/heads/mission/4-axes-2026-10-10
```

---

## ۵) معیارهایِ پذیرشِ D1 (§۱۲.۲۸)

| معیار | شاهدِ الزامی | وضعیتِ D1 |
| --- | --- | --- |
| نصب/شروعِ مستقل | Portable با دادهٔ جدا؛ نصبِ عملیاتی دست‌نخورده | باید |
| دریافتِ دادهٔ واقعی در محیطِ کنترل‌شده | `/api/market` از DBِ کپی + گیتِ IP | باید |
| نمایشِ تابلو | `tape-row` ≥ ۱۰ | باید |
| نمودارِ واقعی و کندلِ تعدیل‌شده | `chart-area` + canvas + مسیرِ تعدیل | باید |
| حداقلِ تکنیکال | تایم‌فریم/نشانگرِ ضروری | باید |
| نسخه/تازگیِ ورودی | `/api/update/version` + نشانگرِ تازگی | باید |
| بستن/بازکردن | `[shell] window ready`/`[exit]` + آزادشدنِ پورت | باید |
| قطع/وصلِ شبکه | گیتِ آفلاین → رفع → بازیابی | باید |
| مالکیتِ poller/DB | یک حلقه، بدونِ orphan | باید |
| Tray/close طبقِ §۷ | hide/show/quit + فایلِ تنظیمات | باید؛ دستی |
| fallback | `BORS_SHELL=pywebview` سالم | باید |
| گاردها | `run_all_tests.py` سبز | باید |
| اعداد | cold/warm/RSS/تب‌ها ثبت‌شده | باید |

---

## ۶) شکست‌ها و رفتارِ امن

| رخداد | رفتار | شاهد |
| --- | --- | --- |
| WebView2 نیست | پوسته بالا نمی‌آید؛ لانچر fallback می‌کند | `[shell] died before ready` |
| `ready` نمی‌آید | terminateِ همان PID و fallback | `[shell] not ready in 20s` |
| پوسته کرش می‌کند | لاگِ کدِ خروج؛ fallback | `[shell] died before ready code=...` |
| پایتون می‌میرد | نگهبانِ والد پوسته را می‌بندد | پنجرهٔ مرده نمی‌ماند |
| پروفایل قفل است | Tauri/WebView2 خطا می‌دهد؛ fallback | لاگ |
| آپدیت هنگامِ Tray | نصب باید پوسته را هم ببندد | batch `:waitshell` |
| فایلِ تنظیمات خراب | `exit` (امن) | گارد |

---

## ۷) Rollback

1. **در زمانِ اجرا:** `BORS_SHELL=pywebview` (یا `BORS_SHELL=0`)؛ هیچ داده‌ای
   مهاجرت نمی‌کند.
2. **بدونِ env:** `BorsTerminal_Shell.exe` را تغییرِ نام بده؛ لانچر خودش
   fallback می‌کند.
3. **بیلد:** `python scripts/build_all.py --skip-shell` برایِ بیلدِ بدونِ پوسته.
4. **کد:** revertِ همان commitهایِ D1؛ پروفایل و `market.db`/`user.db` دست‌نخورده‌اند.

---

## ۸) ریسک‌ها

| ریسک | کاهش |
| --- | --- |
| دو فرآیند و orphan | نگهبانِ والد + تستِ kill + batch `:waitshell` |
| پروفایلِ جدا و از‌دست‌رفتنِ تنظیمات | `data_directory` = همان مسیر؛ تستِ `d1.probe` |
| Tauri 2.12.5 API متفاوت | `cargo check` قبل از هر تغییر؛ پینِ دقیق + Cargo.lock |
| حجمِ باندل | stub به‌جای distِ کامل؛ سقفِ ۵۲۰ مگ در D-spec |
| Tray با دو پنجره | D1 یک Tray برایِ هر فرآیند؛ مستند؛ D5 اگر لازم شد |
| آپدیت در حالتِ Tray | D1 فقط مکانیک؛ UIِ تأییدِ آپدیت در D3/D5 |
| jobِ دستیِ Tauri | محصول نیست؛ D1 منتشرش نمی‌کند؛ D5 تعیین تکلیف |

---

## ۹) خارج از محدودهٔ D1

- IPC/پلِ بومی (D2، §۲ خط ۲۰).
- بازطراحیِ UI، نمونهٔ بازار/تکنیکال (D3، §۱۲.۳۸.۴).
- تغییرِ موتورِ نمودار/FTS یا منطقِ سفارش (§۶، §۸).
- Tauri-as-host با sidecar (با شواهد، بعد از D1).
- امضایِ دیجیتال/نصب‌کنندهٔ توزیعیِ کامل (D5، §۱۲.۹).

---

## ۱۰) چک‌لیستِ پایانی

- [ ] `cargo test --locked` سبز
- [ ] `cargo build --release --locked` و وجودِ EXE
- [ ] `python dev/shell_launcher_v103.py --dist dist/BorsTerminal_Ultimate` سبز
- [ ] `python dev/version_anchor_guard.py` سبز (هفت لنگر)
- [ ] `python dev/test_compat_guard_v1012.py` سبز (fallback حفظ شده)
- [ ] `python dev/loopback_guard_v1029.py` سبز
- [ ] `python dev/onedir_contract_v11.py --dist dist` سبز
- [ ] `python dev/persian_glyph_guard.py` سبز
- [ ] `python dev/run_all_tests.py` سبز
- [ ] پذیرشِ §۱۲.۲۸ با اعداد ثبت شده
- [ ] fallback و نگهبانِ والد آزموده
- [ ] گزارش بدونِ PASS خوداعلام؛ Push فقط شاخهٔ مأموریت
