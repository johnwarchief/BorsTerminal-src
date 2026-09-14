"""scripts/build_all.py -- زنجیره بیلد فاز 7: فرانت + بسته دسکتاپ.

اجرا (از ریشه ریپو):
    python scripts/build_all.py            # فرانت + PyInstaller (onedir)
    python scripts/build_all.py --skip-npm # فقط PyInstaller (فرانت از قبل ساخته)

خروجی: dist/BorsTerminal_Ultimate/ (پوشه اجرایی مستقل)
سپس دستی کنارش بگذار: market.db.lzma (اولین اجرا خودش extract می‌کند)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, 'frontend')
SPEC = os.path.join(ROOT, 'fts_terminal.spec')
OUT = os.path.join(ROOT, 'dist', 'BorsTerminal_Ultimate')


def run(cmd, cwd, label):
    print(f'\n=== {label} ===')
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=cwd, shell=(os.name == 'nt'))
    if rc != 0:
        print(f'[ERR] {label} failed with exit {rc}')
        sys.exit(rc)
    print(f'[OK] {label} done in {time.time() - t0:.0f}s')


def main():
    ap = argparse.ArgumentParser(description='FTS Terminal full build (phase 7)')
    ap.add_argument('--skip-npm', action='store_true', help='skip frontend build')
    args = ap.parse_args()

    if not args.skip_npm:
        run('npm run build', FRONTEND, 'frontend: npm run build')

    run('python -m PyInstaller --noconfirm --clean "{}"'.format(SPEC), ROOT,
        'pyinstaller: fts_terminal.spec')

    if not os.path.isdir(OUT):
        print('[ERR] expected output missing:', OUT)
        sys.exit(1)

    # market.db.lzma کنار exe -- داده اجرایی (نه داخل باینری)
    src = os.path.join(ROOT, 'market.db.lzma')
    if os.path.exists(src):
        dst = os.path.join(OUT, 'market.db.lzma')
        shutil.copy2(src, dst)
        print(f'[OK] data: market.db.lzma -> {dst}')

    total = 0
    for dirpath, _dirs, files in os.walk(OUT):
        for f in files:
            total += os.path.getsize(os.path.join(dirpath, f))
    print(f'\n=== DONE ===\noutput: {OUT}\nsize: {total / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    main()
