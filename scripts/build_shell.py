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
    ap = argparse.ArgumentParser(description='Build the Tauri desktop shell')
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
    with open(dest, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    print(f'[OK] {dest} {size / 1e6:.2f} MB sha256={sha[:16]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
