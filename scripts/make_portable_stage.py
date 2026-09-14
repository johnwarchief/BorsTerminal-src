#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_portable_stage.py — stage پرتابل (onedir) + wheels آفلاین.

خروجی: portable/stage/ (BorsTerminal.bat + BorsTerminal_Ultimate/ + wheels/)
سپس با ISCC BorsTerminal_Setup.iss → setup.exe آفلاین.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
STAGE = os.path.join(ROOT, "portable", "stage")
DIST = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")

def main():
    if not os.path.isdir(DIST):
        print("[ERR] dist/BorsTerminal_Ultimate missing — run build_exe.py first")
        sys.exit(1)
    # stage پاک/ساخت
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    # onedir کل را کپی
    dst_app = os.path.join(STAGE, "BorsTerminal_Ultimate")
    shutil.copytree(DIST, dst_app)
    # لانچر
    shutil.copy2(os.path.join(ROOT, "portable", "BorsTerminal.bat"), STAGE)
    # wheels آفلاین (از requirements نصبشده در venv_build)
    wheels = os.path.join(STAGE, "wheels")
    os.makedirs(wheels, exist_ok=True)
    pip = os.path.join(ROOT, "venv_build", "Scripts", "python.exe")
    reqs = ["numpy==2.0.2", "pandas==2.2.3", "fastapi", "uvicorn", "requests", "httpx",
            "python-docx", "openpyxl", "reportlab", "lxml", "Pillow", "websockets",
            "click", "cryptography"]
    for pkg in reqs:
        subprocess.run([pip, "-m", "pip", "download", pkg, "-d", wheels,
                        "--disable-pip-version-check", "-q"], check=False)
    n = len(os.listdir(wheels))
    size = sum(os.path.getsize(os.path.join(wheels, f)) for f in os.listdir(wheels)) / 1e6
    print(f"[OK] stage ready: {STAGE}")
    print(f"     wheels: {n} files ({size:.0f} MB) — offline install possible")
    print("next: ISCC portable/BorsTerminal_Setup.iss")

if __name__ == "__main__":
    main()
