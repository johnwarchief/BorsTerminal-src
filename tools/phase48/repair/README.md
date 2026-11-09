# S5 — هارنسِ Repairِ تعاملی (نسخهٔ گیت‌شده)

این پوشه نسخهٔ مسیر‌پارامتری‌شدهٔ هارنسی است که `repair-evidence.json` را ساخت.
نسخهٔ اصلیِ اجراشده و تلاشِ ناموفقِ PowerShell-UIA در
`_audit/phase48closeout/repair/` می‌مانند (gitignored).

## پیش‌نیازها

- باندلِ آزمایشی در `_audit/phase48closeout/installer/bundle/` (پیش‌فرض)
- Inno Setup 6 (`ISCC.exe`)
- مهارتِ Computer Use برای راندنِ جادوگر

مسیرها با `PHASE48_REPAIR_BASE`، `PHASE48_REPAIR_BUNDLE` و `PHASE48_REPAIR_SETUP`
قابلِ تغییرند. `SETUP` به‌طورِ پیش‌فرض از `bors_config.APP_VERSION` ساخته می‌شود.

## اجرا

```bash
python tools/phase48/repair/make_repair_iss.py
"/c/Program Files (x86)/Inno Setup 6/ISCC.exe" \
  _audit/phase48closeout/repair/bors_setup_repairtest.iss
python tools/phase48/repair/manual_repair.py init
python tools/phase48/repair/manual_repair.py start healthy
# drive the wizard with Computer Use -> manual-ui-healthy.json
python tools/phase48/repair/manual_repair.py verify healthy
```

`make_repair_iss.py` روی `installer/bors_setup.iss` تولیدی کار می‌کند و این تغییرها
را می‌دهد: AppId/AppRegIDِ آزمایشی، حذفِ Password/Encryption،
`DefaultDirName` و ریشهٔ حذفِ `LocalAppData` در sandbox، حذفِ
`[Icons]/[Tasks]/[Run]`، و `Exit;` قبل از بدنهٔ `EnsureAppNotRunning` و
`SweepOrphanLeftovers`. خروجیِ آن با شاهدِ ثبت‌شده بایت‌یکسان است
(`sha256=c22dce203d36370fa9f6c5703dad11a7f97b201fd4f5503013c24ab5aa45f020`).

## مرزهای ایمنی

- نصب و Registryِ واقعی هرگز لمس نمی‌شوند؛ AppIdِ آزمایشی:
  `{C3D84F60-2A19-4E7B-8C55-6F9A1B2D3E40}`.
- sandbox: `%LOCALAPPDATA%\BorsTerminal_Phase48RepairTest\app`؛ پورت: `8158`.
- نصب‌کنندهٔ آزمایشی رمز ندارد؛ هیچ دیالوگِ رمزِ نصابِ تولیدی Automation نمی‌شود.
- `manual_repair.py init` فقط Registryِ همان AppId را حذف می‌کند و فقط وقتی
  `InstallLocation` داخلِ sandbox باشد؛ در غیرِ این صورت متوقف می‌شود.
- توکنِ health probe به‌طورِ پیش‌فرض در هر اجرا تصادفی ساخته می‌شود و با
  `PHASE48_REPAIR_TOKEN` قابلِ تنظیم است؛ مقدارِ آن در گیت نیست.
