"""Foreign-script / corruption scan over source files.

Only Han/Hangul/Kana and Cyrillic are foreign to this repo's Persian-commented
sources, so any hit is a character dropped in by an edit slip. Ranges are built
from code points: writing the literal class here would put CJK into a file that
must stay clean.

Cyrillic is listed because it happened twice on 1405-07-07 while editing Persian
prose — once as a replacement for a Chinese slip, so the CJK-only scan stayed
silent and the Russian word survived into the doc. Greek is NOT flagged: Σ[ih] is
real notation in RELEASE_NOTES/CHART-PARITY docs.
"""
import re
import subprocess
import sys


def rng(lo: int, hi: int) -> re.Pattern[str]:
    return re.compile(f"[{chr(lo)}-{chr(hi)}]")


SCANNERS = {
    "han": rng(0x4E00, 0x9FFF),
    "hangul": rng(0xAC00, 0xD7AF),
    "kana": rng(0x3040, 0x30FF),
    "cyrillic": rng(0x0400, 0x04FF),
}


def touched() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"], capture_output=True, text=True, encoding="utf-8"
    ).stdout
    return [p for p in out.splitlines() if p.endswith((".ts", ".tsx", ".mts", ".py"))]


files = sys.argv[1:] or touched()
total = 0
for path in files:
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"SKIP {path}: {exc}")
        continue
    for name, rx in SCANNERS.items():
        for n, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                total += 1
                print(f"{path}:{n} [{name}]: {line.strip()[:90]}")
print(f"CJK total: {total}")
sys.exit(1 if total else 0)
