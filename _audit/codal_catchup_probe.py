# -*- coding: utf-8 -*-
"""_audit/codal_catchup_probe.py — اجرایِ واقعیِ صفِ جبران، رویِ **کپیِ** بانک.

سنجشِ هدفِ ۱: آیا «اطلاعیه هست ولی ردیفِ مشتق نیست» واقعاً با یکِ اجرای increment
پر می‌شود؟ بانکِ کاری (`market.db`) دست نمی‌خورد — کپی گرفته می‌شود و همان مسیرِ
تولید (`codal_fetcher._deep_extract` + `pending_notices`) رویِ کپی اجرا می‌شود.

`POLITE=True` عمدی است: بدونِ چرخشِ IP/ADB (همان کاری که درِ ماشینِ مالک با
`--no-tether`/`--polite` انجام می‌شود) تا شبکهٔ او دست‌نخورده بماند.

اجرا:  python _audit/codal_catchup_probe.py 3
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF          # noqa: E402

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def counts(con):
    return {t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            for t in ("codal_notices", "financial_statements", "monthly_sales")}


def main():
    src = os.path.join(ROOT, "market.db")
    work = tempfile.mkdtemp(prefix="codal_probe_")
    db = os.path.join(work, "copy.db")
    x = sqlite3.connect(src, timeout=60)
    y = sqlite3.connect(db)
    with y:
        x.backup(y)
    x.close()
    y.close()
    print("کپی ساخته شد:", db)

    CF.DB_PATH = db                       # هر چه مسیرِ بانک می‌خواند، کپی باشد
    CF.set_polite(True)                   # بی‌ADB، بی‌چرخشِ IP
    con = sqlite3.connect(db, timeout=60, isolation_level=None)
    CF.create_schema(con)
    CF.migrate_schema(con)
    before = counts(con)
    print("پیش از اجرا:", before)

    pend = CF.pending_notices(con, limit=LIMIT)
    print("صفِ جبران (تازۀ‌ترین %d):" % LIMIT,
          [(r[0], r[1], (r[3] or "")[:26]) for r in pend])
    processed, fs_done, ms_done = CF.derived_state(con)
    touched = sorted({r[1] for r in pend})
    n_fs, n_ms = CF._deep_extract(pend, processed, con, store_notices=False)
    after = counts(con)
    print("نتیجه: %d FS + %d ماهانه درج شد" % (n_fs, n_ms))
    print("پس از اجرا:", after)
    led = con.execute("SELECT tracing_no, kind, ok FROM codal_extracted ORDER BY tracing_no").fetchall()
    print("دفترِ استخراج:", led)
    for tno, _k in [(p[0], 0) for p in pend]:
        row = con.execute("SELECT symbol, period_end, revenue FROM financial_statements"
                          " WHERE tracing_no=?", (tno,)).fetchone()
        row2 = con.execute("SELECT symbol, period_end, monthly_revenue FROM monthly_sales"
                           " WHERE tracing_no=?", (tno,)).fetchone()
        print("   ", tno, "→", row or row2)
    # نشاندادِ هیچِ خرابیِ جانبی: فقط نمادهایِ لمس‌شده ممکن است dedupe بخورند
    print("نمادهایِ لمس‌شده:", touched)
    for s in touched:
        r = con.execute("SELECT (SELECT COUNT(*) FROM financial_statements WHERE symbol=?),"
                        " (SELECT COUNT(*) FROM monthly_sales WHERE symbol=?)", (s, s)).fetchone()
        print("   ", s, "صورت‌ها:", r[0], "ماهیانه:", r[1])
    con.close()
    shutil.rmtree(work, ignore_errors=True)
    print("کپی پاک شد؛", src, "دست‌نخورده")


if __name__ == "__main__":
    main()
