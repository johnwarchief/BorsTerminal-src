# -*- coding: utf-8 -*-
"""Measure whether a full-installer update would roll the user's market data back.

ensure_market_db() re-extracts market.db whenever the bundled market.db.lzma
hash differs from market.db.baseline, and carries forward only
MARKET_DB_USER_TABLES. Everything the app synced locally since then is gone.
A far-behind user who then runs the installer is silently downgraded to the
baseline's last trading day.
"""
import hashlib
import lzma
import os
import sqlite3
import tempfile

INSTALLED = r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate"
REPO = r"C:\Users\PCMOD\Desktop\BorsTerminal"


def one(db, sql):
    uri = "file:" + db.replace(os.sep, "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def unpack(lzma_path, tag):
    out = os.path.join(tempfile.gettempdir(), "bors_probe_%s.db" % tag)
    if not (os.path.isfile(out) and os.path.getsize(out) > 1000):
        with lzma.open(lzma_path, "rb") as src, open(out, "wb") as dst:
            dst.write(src.read())
    return out


def main():
    live = os.path.join(INSTALLED, "market.db")
    bundled = os.path.join(INSTALLED, "market.db.lzma")
    repo_lzma = os.path.join(REPO, "market.db.lzma")
    stamp = os.path.join(INSTALLED, "market.db.baseline")

    print("LIVE market.db (the user's own, synced forward)")
    print("   daily_prices   max=%s rows=%s" % one(live, "select max(d_even), count(*) from daily_prices"))
    try:
        print("   price_history  max=%s rows=%s" % one(live, "select max(date), count(*) from price_history"))
    except sqlite3.Error as e:
        print("   price_history  ERR %s" % e)
    try:
        print("   tape_history   max=%s rows=%s" % one(live, "select max(d_even), count(*) from tape_history"))
    except sqlite3.Error as e:
        print("   tape_history   ERR %s" % e)

    print("\nbaseline hash on disk : %s" % open(stamp).read().strip()[:16])
    for tag, path in (("installed .lzma", bundled), ("repo committed .lzma", repo_lzma)):
        if not os.path.isfile(path):
            print("%-22s ABSENT" % tag)
            continue
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        db = unpack(path, tag.split()[0])
        day = one(db, "select max(d_even) from daily_prices")[0]
        rows = one(db, "select count(*) from daily_prices")[0]
        print("%-22s sha=%s last_trading_day=%s daily_rows=%s" % (tag, h[:16], day, rows))

    would_reroll = open(stamp).read().strip() != hashlib.sha256(
        open(repo_lzma, "rb").read()).hexdigest()
    print("\nWould a full v1.0.69 install re-extract (and so roll back) this db? %s"
          % ("YES" if would_reroll else "no"))


if __name__ == "__main__":
    main()
