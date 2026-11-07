# _audit/_ghost_negative_control.py -- کنترلِ منفیِ آزمونِ ردیفِ شبح
# چرا: «آزمونِ تازه باید خطایِ واقعی را ببیند» — پس همان سناریو با نویسندۀِ پیشین
# (upsert-only، از `git show a149bdc:api/chart.py`) اجرا می‌شود. اگر آن هم سبز شد،
# آزمونِ `dev/test_adjustment_phasea.py` چیزی را ثابت نمی‌کند.
import io, os, sqlite3, subprocess, sys, tempfile, textwrap
_keep = sys.stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
import api.chart as CH

old_src = subprocess.run(["git", "show", "a149bdc:api/chart.py"], capture_output=True,
                         text=True, encoding="utf-8").stdout
i = old_src.index("def _store_adjust_events")
j = old_src.index("\n\n\ndef ", i)
ns = {"sqlite3": sqlite3, "DB_PATH": None, "_ADJ_TABLE_DDL": CH._ADJ_TABLE_DDL,
      "_ADJ_VERDICT_DDL": CH._ADJ_VERDICT_DDL, "_ADJ_KNOWN_SOURCES": CH._ADJ_KNOWN_SOURCES}
exec(old_src[i:j], ns)
old_store = ns["_store_adjust_events"]

db = os.path.join(tempfile.mkdtemp(prefix="ghost_old_"), "g.db")
ns["DB_PATH"] = db
CH.DB_PATH = db
ev_all = [{"date": "2024-01-05", "ratio": 0.90}, {"date": "2024-06-02", "ratio": 0.80},
          {"date": "2024-09-01", "ratio": 0.95}]
S = "شبحِ_آزمون"


def dates(store):
    c = sqlite3.connect(db)
    try:
        return [r[0] for r in c.execute("SELECT date FROM adjust_events WHERE symbol=? "
                                        "ORDER BY date", (S,))]
    finally:
        c.close()


old_store(S, ev_all, "base-price-discontinuity")
old_store(S, [ev_all[0], ev_all[2]], "base-price-discontinuity")
left = dates(CH._stored_adjust_events(S))
print(f"  نویسندۀِ پیشین پس از کشفِ دوم: {left}  → ردیفِ شبح مانده: "
      f"{'بله (آزمونِ تازه خطا را می‌بیند)' if '2024-06-02' in left else 'نه'}")
fac_old = CH._factors_from_events(["2024-01-01"], CH._stored_adjust_events(S))
print(f"  فاکتورِ پیشین {fac_old[0]:.4f}  |  درست (بی‌شبح) 0.8550  |  خطا "
      f"{abs(fac_old[0]-0.855)/0.855*100:.2f}٪")
c = sqlite3.connect(db); c.execute("DELETE FROM adjust_events WHERE symbol=?", (S,)); c.commit(); c.close()
CH._store_adjust_events(S, ev_all, "base-price-discontinuity")
CH._store_adjust_events(S, [ev_all[0], ev_all[2]], "base-price-discontinuity")
print(f"  نویسندۀِ فعلی پس از کشفِ دوم: {dates(CH._stored_adjust_events(S))}")
