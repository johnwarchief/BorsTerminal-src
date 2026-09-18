# راهنمای جامع استقرار و بیلد دسکتاپ با Tauri v2 و سیستم به‌روزرسانی خودکار (In-App Updater)
# BorsTerminal Ultimate — Tauri v2 Desktop & Auto-Updater Guide

این سند راهنمای رسمی توسعه، بیلد نصبی سبک ویندوز (.exe)، مدیریت کلیدهای امضای دیجیتال و پایپ‌لاین انتشار خودکار GitHub Actions برای ترمینال بورس التیمیت است.

---

## ۱. معماری سیستم و ساختار فایل‌ها

فریم‌ورک **Tauri v2** جایگزینی فوق‌سبک و با امنیت بالا برای فریم‌ورک‌های سنگین (نظیر Electron) است. به جای پکیج کردن مرورگر کرومیوم کامل (که بیش از ۱۵۰ مگابایت حجم و رم بالایی مصرف می‌کند)، Tauri از هسته نیتیو Rust و موتور استاندارد **Microsoft Edge WebView2** ویندوز استفاده می‌کند که منجر به خروجی نصبی حدود **۱۰ تا ۱۵ مگابایت** و مصرف رم کمتر از ۱۰۰ مگابایت می‌شود.

### ساختار شاخه‌ها:
```
BorsTerminal_Ultimate_Base/
├── .github/
│   └── workflows/
│       ├── release.yml               # پایپ‌لاین خودکار بیلد، ساین و انتشار ریلیز گیت‌هاب
│       └── guards.yml                # تست‌های سلامت و گارد‌های کیفیت ریپو
├── frontend/
│   ├── src/
│   │   ├── features/
│   │   │   └── updater/
│   │   │       ├── useAppUpdater.ts        # هوک مدیریت دانلود و اعتبارسنجی پکیج‌ها
│   │   │       ├── UpdateManagerModal.tsx  # مودال مدرن سایبرپانک مدیریت به‌روزرسانی
│   │   │       └── index.ts
│   │   ├── shared/
│   │   │   └── stores/
│   │   │       └── authStore.ts            # احراز هویت با قفل ضد بروت‌فورس
│   │   └── widgets/
│   │       ├── LoginScreen.tsx             # فرم لاگین امن بدون اطلاعات پیش‌فرض
│   │       └── UpdateManagerModal.tsx
│   ├── src-tauri/
│   │   ├── src/
│   │   │   ├── main.rs                     # نقطه ورود اپلیکیشن نیتیو
│   │   │   └── lib.rs                      # رجیستر پلاگین‌های updater و process
│   │   ├── capabilities/
│   │   │   └── default.json                # مجوزهای دسترسی امنیتی Tauri v2
│   │   ├── Cargo.toml                      # وابستگی‌های کریت‌های Rust
│   │   └── tauri.conf.json                 # پیکربندی پنجره، آیکون‌ها و اندپوینت‌های آپدیتر
│   └── package.json                        # وابستگی‌های npm کلاینت Tauri v2
└── TAURI_GUIDE.md                          # این سند راهنما
```

---

## ۲. پیش‌نیازهای توسعه و بیلد محلی

برای توسعه یا بیلد محلی در سیستم‌عامل ویندوز، موارد زیر مورد نیاز است:

1. **Node.js**: نسخه 20 یا بالاتر (تست‌شده با v20.x و v22.x).
2. **Rust & Cargo**:
   - نصب از طریق وبسایت رسمی: [https://rustup.rs](https://rustup.rs)
   - کامند نصب ابزار MSVC:
     ```powershell
     rustup default stable-x86_64-pc-windows-msvc
     ```
3. **ابزارهای ساخت C++ در Visual Studio**:
   - در هنگام نصب Visual Studio Build Tools، تیک گزینه **Desktop development with C++** را فعال کنید.
4. **WebView2**:
   - به طور پیش‌فرض روی ویندوز ۱۰ و ۱۱ نصب است.

---

## ۳. دستورات اجرا و توسعه (Local Development)

### اجرای فرانت‌اند در مرورگر (حالت وب):
```powershell
cd frontend
npm run dev
```

### اجرای فرانت‌اند درون پنجره نیتیو دسکتاپ Tauri با Hot-Reload:
```powershell
cd frontend
npx tauri dev
```
> در حالت `tauri dev`، پنجره ویندوزی با ابعاد استاندارد `1440x900`، مینیمم `1024x700` و استایل‌های سایبرپانک اجرا شده و هر تغییری در کدهای React مستقیماً در پنجره منعکس می‌شود.

---

## ۴. تولید فایل نصبی سبک (.exe / .msi)

برای ساخت فایل‌های نصبی نهایی و بهینه‌سازی‌شده برای توزیع به کاربران:

```powershell
cd frontend
npx tauri build
```

پس از پایان کامپایل، پکیج‌ها در مسیر زیر قرار می‌گیرند:
- **نصاب استاندارد سبک (NSIS - فایل Setup.exe تک‌کلیک):**
  `frontend/src-tauri/target/release/bundle/nsis/Bors Terminal Ultimate_1.0.0_x64-setup.exe`
- **نصاب سازمانی ویندوز (MSI Package):**
  `frontend/src-tauri/target/release/bundle/msi/Bors Terminal Ultimate_1.0.0_x64_en-US.msi`

---

## ۵. امنیت و امضای دیجیتال به‌روزرسانی‌ها (Minisign Keypair)

برای جلوگیری از هرگونه تزریق کد مخرب یا دستکاری بسته در مسیر شبکه، تمامی آپدیت‌های دریافتی باید امضای دیجیتال متناظر با کلید عمومی ثبت‌شده در `tauri.conf.json` را داشته باشند.

### کلید عمومی ثبت‌شده در پروژه:
```
dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEYyOTAxNTI2NDU1ODAxNEIKUldSTEFWaEZKaFdROGgyTUMvaEtyaWRBWHgvUTJKT0J3aUJCMzVVcGpMMXJONDFCSUVib040c24K
```

### روش تولید کلید جدید در صورت نیاز به چرخش (Key Rotation):
```powershell
cd frontend
npx tauri signer generate -w .tauri_updater_key
```
این دستور دو فایل ایجاد می‌کند:
1. `.tauri_updater_key` (کلید خصوصی برای ساین - **محرمانه**)
2. `.tauri_updater_key.pub` (کلید عمومی - قرارگیری در `tauri.conf.json` فیلد `plugins.updater.pubkey`)

---

## ۶. تنظیم پایپ‌لاین CI/CD در GitHub Actions

فایل ورک‌فلو `.github/workflows/release.yml` برای کامپایل ابری و انتشار خودکار طراحی شده است.

### تنظیم Secretهای مخزن گیت‌هاب:
به صفحه ریپازیتوری در گیت‌هاب بروید:
`Settings` ➔ `Secrets and variables` ➔ `Actions` ➔ `New repository secret`

دو سکرت زیر را اضافه کنید:
1. `TAURI_SIGNING_PRIVATE_KEY`:
   محتوای کامل فایل کلید خصوصی تولید‌شده (شامل خط untrusted comment و کلید).
2. `TAURI_SIGNING_KEY_PASSWORD`:
   در صورت تنظیم پسورد روی کلید، رمز آن را وارد کنید (اگر بدون پسورد تولید شده، خالی بگذارید).

### انتشار یک نسخه جدید (Release Trigger):
هر زمان که مایل به انتشار نسخه جدید بودید، فقط کافیست تگ نسخه جدید را Push کنید:
```bash
git tag v1.0.1
git push origin v1.0.1
```

ورک‌فلو به صورت خودکار مراحل زیر را طی می‌کند:
1. روی سرور `windows-latest` گیت‌هاب اجرا می‌شود.
2. ابزارهای Node و Rust را کانفیگ می‌کند.
3. بیلد کامل پروداکشن را انجام می‌دهد.
4. فایل‌های `.exe` و `.msi` را به همراه امضای دیجیتال تولید می‌کند.
5. فایل مانیفست `latest.json` را به عنوان متادیتای آپدیتر خودکار ایجاد می‌کند.
6. تمامی فایل‌ها را در صفحه **GitHub Releases** بارگذاری و منتشر می‌نماید.

---

## ۷. ساختار مانیفست آپدیتر (`latest.json`)

پلاگین آپدیتر ترمینال اندپوینت زیر را بررسی می‌کند:
```json
{
  "version": "1.0.1",
  "notes": "بهبود کارایی و عملکرد، اضافه شدن قابلیت‌های جدید فیلتر نخبگان FTS",
  "pub_date": "2026-09-18T20:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "<امضای دیجیتال تولیدشده توسط tauri-action>",
      "url": "https://github.com/Johnkallnaya/BorsTerminal/releases/download/v1.0.1/Bors.Terminal.Ultimate_1.0.1_x64-setup.nsis.zip"
    }
  }
}
```

---

## ۸. قابلیت‌های درون‌برنامه‌ای (In-App Features)

1. **بررسی خودکار و دستی**: با کلیک روی دکمه «🚀 آپدیت» در هدر برنامه (Topbar)، پنجره وضعیت باز شده و بلافاصله استعلام انجام می‌شود.
2. **نوار پیشرفت نئونی (Progress Bar)**: درصد پیشرفت دانلود پکیج با جلوه بصری بلادرنگ نمایش داده می‌شود.
3. **ری‌استارت ایمن با `relaunch`**: پس از پایان دانلود، با کلیک روی دکمه نهایی، برنامه به شکل تمیز بسته شده و با نسخه جدید راه‌اندازی می‌شود.
4. **حالت آفلاین (Fallback)**: در شرایطی که اتصال اینترنت به گیت‌هاب با کندی یا اختلال مواجه باشد، کاربر می‌تواند فایل فشرده ریلیز را مستقیماً از حافظه دستگاه انتخاب و بارگذاری کند.
5. **سیستم امنیت ورود**: ورود با اطلاعات پیش‌فرض یا دکمه‌های دمو حذف شده و سیستم حفاظت ضد بروت‌فورس در صورت ۵ تلاش ناموفق مکرر، ورود را به مدت ۳۰ ثانیه قفل می‌کند.
