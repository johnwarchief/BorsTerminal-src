#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اندازه‌گیریِ کفِ دلتای onedir —证据ِ go/no-go برایِ Phase C (Velopack).

سوال: آیا خروجیِ onedir واقعاً دیف‌های کوچک می‌دهد؟ onefile یک CArchiveِ
فشردهٔ واحد است، پس diffِ دو بیلدِ روی همان سورس تقریباً هیچ پس‌اندازی
ندارد — به همین دلیل «دلتای» فعلی (22,873,624 B) از خودِ exe (22,767,994 B)
هم بزرگتر است. onedir هر DLL/PYD را جدا نگه می‌دارد، پس باینری‌های
تغییرنکرده باید دقیقاً یکسان بمانند.

روش: دو بیلدِ متوالی از همان spec را با sha256 مقایسه می‌کنیم. هر فایلی که
hash یکسان دارد «ثابت» است و فقط فایل‌های متفاوت در دلتای نسخهٔ بعدی
سفر می‌کنند.

استفاده:
    python dev/onedir_delta_floor.py A B     # A,B دو پوشهٔ onedir
"""
import hashlib
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def hashes(d):
    out = {}
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, d).replace("\\", "/")
            try:
                out[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
            except Exception:
                pass
    return out


def main(a_dir, b_dir):
    a, b = hashes(a_dir), hashes(b_dir)
    same = [k for k in a if k in b and a[k] == b[k]]
    changed = [k for k in a if k in b and a[k] != b[k]]
    only_a = [k for k in a if k not in b]
    only_b = [k for k in b if k not in a]

    def sz(d, keys):
        return sum(os.path.getsize(os.path.join(d, k)) for k in keys
                   if os.path.exists(os.path.join(d, k)))

    tot = len(a)
    print("== onedir delta floor ==")
    print("  build A files: %d" % len(a))
    print("  build B files: %d" % len(b))
    print("  identical:     %d (%.1f%%)" % (len(same), 100.0 * len(same) / tot))
    print("  changed:       %d  (%s MB)" % (
        len(changed), round(sz(b_dir, changed) / 1048576.0, 2)))
    print("  only in A:     %d" % len(only_a))
    print("  only in B:     %d  (%s MB)" % (
        len(only_b), round(sz(b_dir, only_b) / 1048576.0, 2)))
    delta_bytes = sz(b_dir, changed) + sz(b_dir, only_b)
    print("  ────────────────────────────────────────")
    print("  DELTA FLOOR:   %s MB over a %s MB package (%.1f%%)"
          % (round(delta_bytes / 1048576.0, 2),
             round(sz(b_dir, list(b)) / 1048576.0, 1),
             100.0 * delta_bytes / max(1, sz(b_dir, list(b)))))
    print("")
    print("  interpretation:")
    if delta_bytes < 5 * 1048576:
        print("    GO — deltas are small; Velopack will ship real savings.")
    else:
        print("    CAUTION — delta is not small; re-scope Phase C.")
    if changed:
        print("    changed files (top 10 by size):")
        for k in sorted(changed, key=lambda k: -os.path.getsize(
                os.path.join(b_dir, k)))[:10]:
            print("      %8.1f KB  %s" % (
                os.path.getsize(os.path.join(b_dir, k)) / 1024.0, k))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
