# Modular Patch/Update System (v10)

> **راهنمای updater با ریسک قدیمی‌بودن:** این سند به مسیرها و فرض‌های نسخهٔ پیشین اشاره می‌کند. قبل از هر patch واقعی، قرارداد جاری نسخه را در AGENTS.md و bors_config.py، و فرمان‌های به‌روز را در scripts/ و workflow انتشار بررسی کنید. ادعای منبع نسخه در متن زیر را بدون تطبیق اجرا نکنید.

The EXE install can be updated **without re-downloading the database**.
Two pieces live in the repo:

| Piece | Role |
|---|---|
| `scripts/make_patch.py` | Zips the freshly built `dist/BorsTerminal_Ultimate` bundle into `dist/BorsTerminal_Update.zip` (flat overlay patch). |
| `scripts/apply_update.bat` | The end-user updater, embedded at the zip root. |

## Build a patch (developer)

```
python scripts/build_exe.py      # produce dist/BorsTerminal_Ultimate (onedir)
python scripts/make_patch.py     # produce dist/BorsTerminal_Update.zip
```

`make_patch.py` adds `Version.txt` (app version from `static/index.html`,
git short commit, build time) and `apply_update.bat` into the zip root.
Zip entries are flat (`_internal/...`, `BorsTerminal_Ultimate.exe`) and use
forward slashes, so both `tar -xf` and PowerShell `Expand-Archive` can apply them.

## Apply an update (end user)

1. Put `BorsTerminal_Update.zip` and `apply_update.bat` **inside the current
   install folder** (the folder that already contains `BorsTerminal_Ultimate.exe`
   and `_internal\`).
2. Double-click `apply_update.bat`.
3. It stops the running app (graceful `taskkill`, up to 8s wait, then forced),
   extracts the zip **in place**, stamps `Version.txt`, and relaunches the app.
4. First-time installs must still use the full release ZIP
   (`releases/BorsTerminal_Ultimate_v*_exe.zip`) — the patch assumes the
   configs of an existing install.

## What the patch never touches (hard rule)

`market.db`, `market.db.lzma`, `adb_config.json`, `codal_control.json`,
`codal_state.json`, `sync*.json`, `logs/`, caches (`__pycache__`, `*.pyc`)
are **excluded** from the patch zip, so applying an update can never clobber
the user's database, tethering config, control file or logs.
`apply_update.bat` also never deletes anything (`rd /s /q` is forbidden);
a failed extraction aborts with the old files intact.

Set `BORS_UPDATE_NORELAUNCH=1` to skip the automatic relaunch (used by tests).

## Full-release database image (`market.db.lzma`)

The full installer ships `market.db.lzma`, decompressed to `market.db`
on first run. `make_exe_release.py` refreshes that image **only when the
database schema changes** (a fingerprint of `sqlite_master` DDL +
`user_version` is kept in the git-ignored `releases/market_db_schema.sha`).
Routine data syncs therefore never rebuild the base image, and patches
carry code only - never the user's database or configs.

## Guard

`dev/patch_check_v10.py` locks these contracts and runs as part of
`python dev/run_all_tests.py`. When `dist/BorsTerminal_Update.zip` exists on
the machine, its structure is validated too.

---
خلاصهٔ فارسی: `make_patch.py` پچ میسازد (بدون دیتابیس و تنظیمات کاربر)،
`apply_update.bat` آن را روی نصب فعلی اعمال میکند: توقف برنامه، extract درجا،
نوشتن Version.txt و اجرای دوباره. نصب اولیه همچنان با zip کامل ریلیز انجام شود.
