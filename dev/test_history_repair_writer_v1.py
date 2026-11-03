#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic proof of the Round-5 price_history writer.

No network and no operational DB: a temp DB + a fake CSV response reproduce the
`_schedule_history_repair -> test_tsetmc.fetch_price_history -> UPSERT_SQL`
path that inserted `src='published'` rows. With BORS_NO_FETCH_LOOPS=1 the same
call must not spawn a thread or write anything.
"""
import os
import sqlite3
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402
import test_tsetmc as T  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % detail) if detail else ""))


CSV = ("DTYYYYMMDD,DTYYYYMMDD,FIRST,HIGH,LOW,CLOSE,VALUE,VOL,OPEN,X,BASE,LAST\n"
       "20261020,20261020,100,105,95,102,1000000,50000,100,0,100,102\n")


class Resp:
    status_code = 200
    text = CSV

    def raise_for_status(self):
        return None


class Sess:
    _polite = {"cooldown_level": 0}

    def get(self, *a, **kw):
        return Resp()


work = tempfile.mkdtemp(prefix="bors_hist_writer_")
db = os.path.join(work, "market.db")
con = sqlite3.connect(db)
con.execute("CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT, l_val30 TEXT, updated_at TEXT)")
con.execute("INSERT INTO instruments VALUES('1','X','X','2026-10-20')")
con.execute("CREATE TABLE price_history(symbol TEXT, date TEXT, open REAL, high REAL,"
            " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
            " PRIMARY KEY(symbol,date))")
con.execute("INSERT INTO price_history VALUES('X','2026-10-19',100,100,100,100,1000,100,1000,'board')")
con.commit()
con.close()

saved = (T.DB_PATH, T.make_session, T._rate_wait, C._HISTORY_REPAIR_AT.copy())
saved_env = os.environ.get("BORS_NO_FETCH_LOOPS")
try:
    T.DB_PATH = db
    T.make_session = lambda *a, **k: Sess()
    T._rate_wait = lambda s: None
    C._HISTORY_REPAIR_AT.clear()

    os.environ.pop("BORS_NO_FETCH_LOOPS", None)
    scheduled = C._schedule_history_repair("X", "2026-10-19", "2026-10-20")
    deadline = time.time() + 10
    row = None
    while time.time() < deadline:
        time.sleep(0.05)
        con = sqlite3.connect(db)
        row = con.execute("SELECT symbol,date,open,high,low,close,volume,last,value,src"
                          " FROM price_history WHERE symbol='X' AND date='2026-10-20'").fetchone()
        con.close()
        if row:
            break
    ck(scheduled is True, "repair is scheduled when the gate is open")
    ck(row is not None, "history repair writes a row")
    ck(bool(row) and row[9] == "published", "the written row is src=published", row)
    ck(bool(row) and row[5] == 102.0 and row[2] == 100.0,
       "CSV maps FIRST->open and CLOSE->close", row)

    # Closed gate: no thread, no write.
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    C._HISTORY_REPAIR_AT.clear()
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    scheduled2 = C._schedule_history_repair("X", "2026-10-19", "2026-10-20")
    time.sleep(0.3)
    after = sqlite3.connect(db).execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    threads = [t.name for t in __import__("threading").enumerate()
               if "hist-repair" in t.name.lower()]
    ck(scheduled2 is False, "BORS_NO_FETCH_LOOPS=1 refuses to schedule")
    ck(before == after and not threads, "closed gate writes nothing and spawns no thread",
       (before, after, threads))
finally:
    T.DB_PATH, T.make_session, T._rate_wait = saved[0], saved[1], saved[2]
    C._HISTORY_REPAIR_AT.clear()
    C._HISTORY_REPAIR_AT.update(saved[3])
    if saved_env is None:
        os.environ.pop("BORS_NO_FETCH_LOOPS", None)
    else:
        os.environ["BORS_NO_FETCH_LOOPS"] = saved_env
    try:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    except Exception:
        pass

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
