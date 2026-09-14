# -*- coding: utf-8 -*-
"""make_dist.py — بسته‌بندی نهایی ریلیز در پوشه‌های جدا (قاطی نشدن).

ساختار خروجی:
  releases/v3.2.3/
    BorsTerminal_Ultimate_v3.2.3.zip          (کد کامل — بدون EXE)
    BorsTerminal_Ultimate_v3.2.3_exe.zip      (تک‌فایل EXE)
    exe_2part/
      BorsTerminal_Ultimate_v3.2.3_exe.zip.part1
      BorsTerminal_Ultimate_v3.2.3_exe.zip.part2
      merge_parts.bat
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
RELEASES = os.path.join(ROOT, "releases")

def cur_version():
    """نسخه از releases/.version — بدون +1 (نسخهٔ ساخته‌شده)."""
    try:
        with open(os.path.join(RELEASES, ".version"), encoding="utf-8") as f:
            v = f.read().strip()
        # .version = آخرین نسخهٔ ساخته‌شده؛ فایل‌های این ریلیز با همین نام هستند
        return v
    except Exception:
        return "0.0.0"

def split_file(src, part1, part2):
    size = os.path.getsize(src)
    half = (size + 1) // 2
    with open(src, "rb") as f, open(part1, "wb") as o1, open(part2, "wb") as o2:
        left = half
        while True:
            chunk = f.read(8 << 20)
            if not chunk:
                break
            if left > 0:
                take = min(len(chunk), left)
                o1.write(chunk[:take])
                left -= take
                rest = chunk[take:]
            else:
                rest = chunk
            if rest:
                o2.write(rest)
    return os.path.getsize(part1) + os.path.getsize(part2) == size

MERGE_BAT = r"""@echo off
rem Merge the two parts back into the full ZIP (put this bat next to both parts)
setlocal
set SRC1=__PART1__
set SRC2=__PART2__
set DST=__DST__
if not exist "%SRC1%" (
  echo [ERR] part1 not found next to this bat.
  goto :end
)
if not exist "%SRC2%" (
  echo [ERR] part2 not found next to this bat.
  goto :end
)
echo Merging %SRC1% + %SRC2% -^> %DST% ...
copy /b "%SRC1%"+"%SRC2%" "%DST%" >nul
for %%A in ("%DST%") do set SIZE=%%~zA
if not "%SIZE%"=="" (
  echo [OK] %DST% created - %SIZE% bytes.
) else (
  echo [ERR] merge failed.
)
:end
pause
"""

def main():
    ver = cur_version()
    outdir = os.path.join(RELEASES, "v" + ver)
    os.makedirs(outdir, exist_ok=True)
    code_zip = os.path.join(RELEASES, f"BorsTerminal_Ultimate_v{ver}.zip")
    exe_zip = os.path.join(RELEASES, f"BorsTerminal_Ultimate_v{ver}_exe.zip")
    part_dir = os.path.join(outdir, "exe_2part")
    os.makedirs(part_dir, exist_ok=True)

    # 1) کد
    if os.path.exists(code_zip):
        shutil.copy2(code_zip, os.path.join(outdir, os.path.basename(code_zip)))
        print(f"  + {os.path.basename(code_zip)}  ({round(os.path.getsize(code_zip)/1048576,1)} MB)")
    else:
        print(f"  [WARN] {code_zip} missing — run make_release_3.py first")

    # 2) EXE تک‌فایل
    if os.path.exists(exe_zip):
        shutil.copy2(exe_zip, os.path.join(outdir, os.path.basename(exe_zip)))
        print(f"  + {os.path.basename(exe_zip)}  ({round(os.path.getsize(exe_zip)/1048576,1)} MB)")
    else:
        print(f"  [WARN] {exe_zip} missing — run make_exe_release.py first")

    # 3) دو پارت
    p1 = os.path.join(part_dir, f"BorsTerminal_Ultimate_v{ver}_exe.zip.part1")
    p2 = os.path.join(part_dir, f"BorsTerminal_Ultimate_v{ver}_exe.zip.part2")
    if os.path.exists(exe_zip):
        for p in (p1, p2):
            if os.path.exists(p):
                os.remove(p)
        ok = split_file(exe_zip, p1, p2)
        if ok:
            print(f"  + exe_2part/  ({round(os.path.getsize(p1)/1048576,1)}+{round(os.path.getsize(p2)/1048576,1)} MB)")
        else:
            print("  [ERR] split failed")
        bat = os.path.join(part_dir, "merge_parts.bat")
        with open(bat, "w", encoding="ascii", errors="ignore") as f:
            f.write(MERGE_BAT
                    .replace("__PART1__", os.path.basename(p1))
                    .replace("__PART2__", os.path.basename(p2))
                    .replace("__DST__", f"BorsTerminal_Ultimate_v{ver}_exe.zip"))
        print("  + exe_2part/merge_parts.bat")

    print(f"\n  => {outdir}")

if __name__ == "__main__":
    main()
