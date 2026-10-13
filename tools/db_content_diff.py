# -*- coding: utf-8 -*-
"""tools/db_content_diff.py — مقایسۀ **محتوایی** دو بانک، جدول‌به‌جدول.

چرا (بندِ ۱۳ معیارهای بستنِ پرونده): «دیتابیس عملیاتی دست‌نخورده است» با
`COUNT(*)` ثابت نمی‌شود — همۀ گیت‌ها هم همین را با موقیتِ فایل می‌سنجند و
mtime درِ `market.db` هر چند دقیقه عوض می‌شود (همگام‌سازیِ بازار). این ابزار
به‌جای هشِ فایل، **مجموعۀ رافیف‌ها** را می‌سنجد: برایِ هر جدول مشترک،
`sha1` رویِ `repr()`ِ ردیف‌ها درِ ترتیبِ rowid + شمارِ ردیف. دو حالتِ خروجی:

  * «identical» ⇒ محتوا یکی است (هرچند ترتیبِ فیزیکیِ صفحات فرق کند).
  * «DIFF» ⇒ باید دید کدامِ جدول و کدامِ ستون فرق کرده؛ برایِ همین `--rows`
    تعدادِ ردیفِ نمونه می‌دهد تا ریشه معلوم شود.

فقط‌خواندنی: هر دو اتصال با `mode=ro` باز می‌شوند.

    usage: PYTHONIOENCODING=utf-8 python tools/db_content_diff.py A.db B.db [--rows 3]
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3


def ro(path):
    return sqlite3.connect("file:" + path.replace(chr(92), "/") + "?mode=ro", uri=True)


def tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def digest(conn, t):
    h = hashlib.sha1()
    n = 0
    for row in conn.execute('SELECT * FROM "%s" ORDER BY rowid' % t):
        h.update(repr(row).encode("utf-8", "replace"))
        n += 1
    return n, h.hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--rows", type=int, default=0,
                    help="برایِ جدول‌هایِ DIFF، چندی صفوره نماد چاپ شود")
    a = ap.parse_args()
    ca, cb = ro(a.a), ro(a.b)
    ta, tb = tables(ca), tables(cb)
    diff = []
    for t in sorted(ta & tb):
        x, y = digest(ca, t), digest(cb, t)
        if x != y:
            diff.append((t, x, y))
    print("A=%s  B=%s" % (a.a, a.b))
    print("tables compared: %d | identical: %d | differing: %d"
          % (len(ta & tb), len(ta & tb) - len(diff), len(diff)))
    for t, x, y in diff:
        print("  DIFF %-24s A(rows=%s,%s) B(rows=%s,%s)" % (t, x[0], x[1], y[0], y[1]))
        if a.rows:
            ka = {tuple(r) for r in ca.execute('SELECT * FROM "%s"' % t)}
            kb = {tuple(r) for r in cb.execute('SELECT * FROM "%s"' % t)}
            for r in list(ka - kb)[:a.rows]:
                print("     only-in-A:", str(r)[:120])
            for r in list(kb - ka)[:a.rows]:
                print("     only-in-B:", str(r)[:120])
    print("only-in-A:", sorted(ta - tb))
    print("only-in-B:", sorted(tb - ta))
    return 1 if diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
