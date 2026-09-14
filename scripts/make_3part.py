# -*- coding: utf-8 -*-
"""make_3part.py — split the EXE zip into 3 parts (for file size limits).
Usage: python make_3part.py   (after make_exe_release.py produced releases/BorsTerminal_Ultimate_v<ver>_exe.zip)
Output: releases/v<ver>/exe_3part/...part1..3 + merge_parts.bat (ASCII only)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
RELEASES = os.path.join(ROOT, "releases")

def cur_version():
    try:
        with open(os.path.join(RELEASES, ".version"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

def split_file(src, part_dir, n=3):
    size = os.path.getsize(src)
    chunk = size // n
    sizes = [chunk] * (n - 1) + [size - chunk * (n - 1)]
    with open(src, "rb") as f:
        for i, sz in enumerate(sizes, 1):
            with open(os.path.join(part_dir, f"BorsTerminal_Ultimate_v{ver}_exe.zip.part{i}"), "wb") as o:
                left = sz
                while left > 0:
                    d = f.read(min(8 << 20, left))
                    if not d:
                        break
                    o.write(d)
                    left -= len(d)
    return all(os.path.exists(os.path.join(part_dir, f"BorsTerminal_Ultimate_v{ver}_exe.zip.part{i}")) for i in range(1, n + 1))

def make_merge_bat(part_dir, ver):
    lines = [
        "@echo off",
        "rem Merge the three parts back into the full ZIP (put this bat next to all three parts)",
        "setlocal",
    ]
    for i in range(1, 4):
        lines.append(f"set SRC{i}=BorsTerminal_Ultimate_v{ver}_exe.zip.part{i}")
    lines.append(f"set DST=BorsTerminal_Ultimate_v{ver}_exe.zip")
    lines.append("if not exist \"%SRC1%\" (echo [ERR] part1 not found next to this bat. & goto :end)")
    lines.append("if not exist \"%SRC2%\" (echo [ERR] part2 not found next to this bat. & goto :end)")
    lines.append("if not exist \"%SRC3%\" (echo [ERR] part3 not found next to this bat. & goto :end)")
    lines.append("echo Merging %SRC1% + %SRC2% + %SRC3% -> %DST% ...")
    lines.append("copy /b \"%SRC1%\"+\"%SRC2%\"+\"%SRC3%\" \"%DST%\" >nul")
    lines.append("for %%A in (\"%DST%\") do set SIZE=%%~zA")
    lines.append("if not \"%SIZE%\"==\"\" (echo [OK] %DST% created - %SIZE% bytes.) else (echo [ERR] merge failed.)")
    lines.append(":end")
    lines.append("pause")
    bat_path = os.path.join(part_dir, "merge_parts.bat")
    with open(bat_path, "w", encoding="ascii", errors="ignore") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return bat_path

if __name__ == "__main__":
    ver = cur_version()
    exe_zip = os.path.join(RELEASES, f"BorsTerminal_Ultimate_v{ver}_exe.zip")
    outdir = os.path.join(RELEASES, "v" + ver)
    part_dir = os.path.join(outdir, "exe_3part")
    os.makedirs(part_dir, exist_ok=True)
    if not os.path.exists(exe_zip):
        print(f"[ERR] {exe_zip} missing — run make_exe_release.py first")
        raise SystemExit(1)
    for f in os.listdir(part_dir):
        os.remove(os.path.join(part_dir, f))
    ok = split_file(exe_zip, part_dir)
    if not ok:
        print("[ERR] split failed")
        raise SystemExit(1)
    bat = make_merge_bat(part_dir, ver)
    name = os.path.basename(exe_zip)
    print(f"  + exe_3part/  ({round(os.path.getsize(os.path.join(part_dir, name + '.part1'))/1048576,1)}+...+3 MB)")
    print(f"  + exe_3part/merge_parts.bat")
    print(f"  => {part_dir}")
