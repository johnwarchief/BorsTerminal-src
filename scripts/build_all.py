#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/build_all.py -- زنجیره بیلد تولیدی Go + Frontend-V2 + Tauri Desktop Shell.

خروجی: dist/BorsTerminal_Ultimate/ (پوشه اجرایی مستقل و بدون پایتون)
شامل:
  - BorsTerminal_Ultimate.exe (بک‌اند سبک و فوق‌سریع Go)
  - BorsTerminal_Shell.exe (پوسته پنجره بومی دسکتاپ Tauri Rust)
  - frontend/ (دارایی‌های کامپایل‌شده React + TypeScript مدرن frontend-v2)
  - market.db (قالبِ اسکیمای جاری برای نصب تازه؛ در ارتقا دست‌نخورده می‌ماند)
  - market.db.gz (seed تاریخی برای ادغام در اولین اجرا؛ از market.db.lzma)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_V2 = os.path.join(ROOT, 'frontend-v2')
BACKEND_GO = os.path.join(ROOT, 'backend-go')
OUT = os.path.join(ROOT, 'dist', 'BorsTerminal_Ultimate')


def default_version():
    try:
        with open(os.path.join(FRONTEND_V2, 'package.json'), encoding='utf-8') as f:
            return str(json.load(f).get('version') or '0.0.0')
    except (OSError, ValueError):
        return '0.0.0'


def run(cmd, cwd, label):
    print(f'\n=== {label} ===')
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=cwd, shell=(os.name == 'nt'))
    if rc != 0:
        print(f'[ERR] {label} failed with exit {rc}')
        sys.exit(rc)
    print(f'[OK] {label} done in {time.time() - t0:.1f}s')


def main():
    ap = argparse.ArgumentParser(description='BorsTerminal Production Build (Go + V2 + Tauri)')
    ap.add_argument('--skip-npm', action='store_true', help='skip frontend-v2 npm build')
    ap.add_argument('--skip-go', action='store_true', help='skip Go backend build')
    ap.add_argument('--skip-shell', action='store_true', help='skip Tauri shell build')
    ap.add_argument('--version', default=default_version(),
                    help='application version stamped into the exe and Version.txt')
    args = ap.parse_args()
    version = args.version.strip().lstrip('v')

    # Clean old build output (removes any legacy Python _internal from prior builds)
    if os.path.isdir(OUT):
        print(f'[clean] removing prior output directory: {OUT}')
        # If _internal exists, remove it specifically to purge python files
        legacy_internal = os.path.join(OUT, '_internal')
        if os.path.isdir(legacy_internal):
            shutil.rmtree(legacy_internal, ignore_errors=True)
        try:
            shutil.rmtree(OUT)
        except Exception as e:
            print(f'[warn] rmtree {OUT} failed: {e}; removing files individually')
            for root_dir, dirs, files in os.walk(OUT, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root_dir, f))
                    except Exception:
                        pass
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root_dir, d))
                    except Exception:
                        pass

    os.makedirs(OUT, exist_ok=True)

    # 1. Build Frontend-V2
    if not args.skip_npm:
        npm_cmd = 'npm.cmd' if os.name == 'nt' else 'npm'
        run(f'{npm_cmd} run build', FRONTEND_V2, 'frontend-v2: npm run build')

    # 2. Build Go Backend (BorsTerminal_Ultimate.exe)
    if not args.skip_go:
        exe_out = os.path.join(OUT, 'BorsTerminal_Ultimate.exe')
        # ldflags: /healthz, the updater's current version and Version.txt must
        # all agree; the updater refuses to run without a known version.
        go_build = ['go', 'build',
                    '-ldflags', f'-X borsterminal/backend/internal/httpapi.version={version}',
                    '-o', exe_out, './cmd/borsd']
        run(go_build, BACKEND_GO, f'backend-go: BorsTerminal_Ultimate.exe (v{version})')

    # Version.txt is the on-disk source of truth for the in-app updater.
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                                         text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = 'unknown'
    with open(os.path.join(OUT, 'Version.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'app_version={version}\nsource=build_all\ngit_commit={commit}\n'
                f'built_at_utc={time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}\n')
    print(f'[version] Version.txt -> {version} ({commit})')

    # 3. Build Tauri Desktop Shell (BorsTerminal_Shell.exe)
    if not args.skip_shell:
        run([sys.executable, os.path.join(ROOT, 'scripts', 'build_shell.py'), '--dist', OUT],
            ROOT, 'shell: Tauri desktop window')

    # 4. Copy Frontend-V2 assets to bundle
    frontend_dist = os.path.join(FRONTEND_V2, 'dist')
    bundle_frontend = os.path.join(OUT, 'frontend')
    if os.path.isdir(frontend_dist):
        print(f'\n[frontend] copying {frontend_dist} -> {bundle_frontend}')
        if os.path.isdir(bundle_frontend):
            shutil.rmtree(bundle_frontend)
        shutil.copytree(frontend_dist, bundle_frontend)

    # 5. Copy static assets and helper scripts
    apply_bat = os.path.join(ROOT, 'scripts', 'apply_update.bat')
    if os.path.isfile(apply_bat):
        shutil.copy2(apply_bat, os.path.join(OUT, 'apply_update.bat'))

    market_db = os.path.join(ROOT, 'market.db')
    if os.path.isfile(market_db):
        dest_db = os.path.join(OUT, 'market.db')
        if not os.path.isfile(dest_db) or os.path.getsize(dest_db) != os.path.getsize(market_db):
            print(f'[db] copying market.db -> {dest_db}')
            shutil.copy2(market_db, dest_db)

    # seedِ تاریخی: XZ برای آرشیو می‌ماند، اما نسخهٔ gzip کنارِ آن ساخته می‌شود
    # تا borsd در اولین اجرا آن را با stdlib در چند ثانیه باز کند (خواندنِ
    # XZِ خالص‌Go برای ۲۸۰ مگابایت حدودِ سه دقیقه است). اگر .lzma نبود،
    # بسته مثلِ قبل با market.dbِ قالب بالا می‌آید و seed در دسترس نیست.
    seed_lzma = os.path.join(ROOT, 'market.db.lzma')
    if os.path.isfile(seed_lzma):
        fast_seed = os.path.join(OUT, 'market.db.gz')
        run(f'"{sys.executable}" "{os.path.join(ROOT, "scripts", "make_fast_seed.py")}" '
            f'"{seed_lzma}" "{fast_seed}"', ROOT, 'seed: market.db.gz')

    corrections_dir = os.path.join(ROOT, 'data', 'ra365_corrections')
    if os.path.isdir(corrections_dir):
        dest_corrections = os.path.join(OUT, 'data', 'ra365_corrections')
        print(f'[corrections] copying {corrections_dir} -> {dest_corrections}')
        if os.path.isdir(dest_corrections):
            shutil.rmtree(dest_corrections)
        shutil.copytree(corrections_dir, dest_corrections)

    # پکِ تقویمِ مرجعِ هفتگی/ماهانه: بدونِ آن borsd به هفته/ماهِ میلادی برمی‌گردد
    # و W/M با پایتون/گلدن ناهمخوان می‌شود (chart/wmcalendar.go).
    calendar_dir = os.path.join(ROOT, 'data', 'ra365_calendar', 'ra365-r32d')
    if os.path.isdir(calendar_dir):
        dest_calendar = os.path.join(OUT, 'data', 'ra365_calendar', 'ra365-r32d')
        print(f'[calendar] copying {calendar_dir} -> {dest_calendar}')
        if os.path.isdir(dest_calendar):
            shutil.rmtree(dest_calendar)
        shutil.copytree(calendar_dir, dest_calendar)

    # 6. Verify Production Bundle Contract (ZERO Python)
    print('\n=== Verifying Production Bundle Contract ===')
    main_exe = os.path.join(OUT, 'BorsTerminal_Ultimate.exe')
    shell_exe = os.path.join(OUT, 'BorsTerminal_Shell.exe')
    html = os.path.join(bundle_frontend, 'index.html')

    if not os.path.isfile(main_exe):
        print(f'[FAIL] main executable missing: {main_exe}')
        sys.exit(1)
    if not os.path.isfile(shell_exe):
        print(f'[FAIL] shell executable missing: {shell_exe}')
        sys.exit(1)
    if not os.path.isfile(html):
        print(f'[FAIL] frontend index.html missing: {html}')
        sys.exit(1)

    py_artifacts = []
    total_bytes = 0
    for dirpath, _dirs, files in os.walk(OUT):
        for f in files:
            fp = os.path.join(dirpath, f)
            total_bytes += os.path.getsize(fp)
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.py', '.pyc', '.pyd') or f.lower().startswith('python') or f == '_internal':
                py_artifacts.append(fp)

    if py_artifacts:
        print(f'[FAIL] Python artifacts found in production bundle: {py_artifacts}')
        sys.exit(1)

    print(f'[OK] BorsTerminal_Ultimate.exe ({os.path.getsize(main_exe)/1e6:.1f} MB)')
    print(f'[OK] BorsTerminal_Shell.exe ({os.path.getsize(shell_exe)/1e6:.1f} MB)')
    print(f'[OK] Frontend-V2 SPA bundle ({sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(bundle_frontend) for f in fs)/1e6:.2f} MB)')
    print(f'[OK] ZERO Python artifacts verified in bundle')
    print(f'\n=== DONE ===\noutput: {OUT}\ntotal size: {total_bytes / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    main()
