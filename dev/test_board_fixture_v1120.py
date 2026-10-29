#!/usr/bin/env python
"""گاردِ B1: فیکسچرِ تابلو، اوراکلِ طلایی و متنِ SQL باید تازه و بازتولیدپذیر باشند.

چهار سنجش، همه بی‌شبکه و فقط رویِ فایلِ موقت:
  ۱) ساختِ فیکسچر دو بار در دو پوشهٔ موقت ⇒ همان sha256.
  ۲) خروجیِ تازهٔ استخراج‌کننده ⇒ بایت‌به‌بایت همان sql_text.goِ کامیت‌شده.
  ۳) اجرایِ دوبارهٔ اوراکل رویِ همان فیکسچر ⇒ هر پنج JSON پس از پارس برابرِ کامیت.
  ۴) خودِ فیکسچر: دقیقاً 30 ردیفِ market_watch و دقیقاً یک نمادِ instruments
     که در market_watch نیست.

گارد هرگز market.dbِ عملیاتیِ ریشه را باز نمی‌کند؛ فقط فیکسچرِ کامیت‌شده را
read-only می‌خواند و بقیهٔ کارها در TemporaryDirectory است.
"""
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "tools", "parity")
FIX = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "fixture")
GOLD = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "golden")
SQL_GO = os.path.join(ROOT, "backend-go", "internal", "store", "sql_text.go")
GOLDEN_FILES = ("market.json", "market_all.json", "delta_negative.json",
                "delta_mirror.json", "sync_state.json")
ENV_KEYS = ("BORS_DATA_DIR", "BORS_NO_FETCH_LOOPS", "BORS_CODAL_OFFLINE")

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + (" — " + detail if detail else ""))


def load(name, filename):
    path = os.path.join(PARITY, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    # ۱) بازتولیدپذیریِ فیکسچر — دو ساختِ مستقل، همان بایت‌ها.
    try:
        mf = load("board_fixture_gen", "make_board_fixture.py")
        with tempfile.TemporaryDirectory(prefix="b1-fixture-") as tmp:
            digests = []
            for leaf in ("a", "b"):
                mf.OUT = os.path.join(tmp, leaf)
                with redirect_stdout(io.StringIO()):
                    mf.main()
                digests.append(sha256_file(os.path.join(mf.OUT, "market.db")))
        check("fixture build is deterministic (two builds, same sha256)",
              digests[0] == digests[1],
              "%s != %s" % (digests[0][:12], digests[1][:12]))
    except Exception as e:                                        # noqa: BLE001
        check("fixture build is deterministic (two builds, same sha256)", False, repr(e))

    # ۲) متنِ SQL — خروجیِ تازۀ استخراج‌کننده باید همان فایلِ کامیت باشد.
    try:
        ex = load("board_sql_extract", "extract_board_sql.py")
        with tempfile.TemporaryDirectory(prefix="b1-sql-") as tmp:
            ex.OUT = os.path.join(tmp, "sql_text.go")
            with redirect_stdout(io.StringIO()):
                ex.main()
            fresh = open(ex.OUT, "rb").read()
        current = open(SQL_GO, "rb").read()
        check("sql_text.go is the extractor's byte-exact output", fresh == current,
              "%d vs %d bytes" % (len(fresh), len(current)))
    except Exception as e:                                        # noqa: BLE001
        check("sql_text.go is the extractor's byte-exact output", False, repr(e))

    # ۳) طلایی‌ها — اجرایِ تازۀ اوراکل، مقایسه پس از پارس (ترتیبِ کلید مهم نیست).
    saved = {k: os.environ.get(k) for k in ENV_KEYS}
    try:
        gg = load("board_golden_gen", "gen_board_golden.py")
        with tempfile.TemporaryDirectory(prefix="b1-golden-") as tmp:
            gg.OUT = tmp
            with redirect_stdout(io.StringIO()):
                gg.main()
            bad = ""
            for name in GOLDEN_FILES:
                if read_json(os.path.join(GOLD, name)) != read_json(os.path.join(tmp, name)):
                    bad = name
                    break
        check("goldens equal a fresh oracle run (parsed JSON)", not bad,
              ("%s differs" % bad) if bad else "")
    except Exception as e:                                        # noqa: BLE001
        check("goldens equal a fresh oracle run (parsed JSON)", False, repr(e))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ۴) شکلِ خودِ فیکسچر (read-only؛ هیچ نوشتنی به فایلِ کامیت‌شده نیست).
    try:
        uri = Path(os.path.join(FIX, "market.db")).as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        try:
            n_rows = con.execute("SELECT COUNT(*) FROM market_watch").fetchone()[0]
            n_absent = con.execute(
                "SELECT COUNT(*) FROM instruments i WHERE NOT EXISTS"
                " (SELECT 1 FROM market_watch m WHERE m.ins_code = i.ins_code)"
            ).fetchone()[0]
        finally:
            con.close()
        check("fixture has exactly 30 market_watch rows", n_rows == 30,
              "count=%d" % n_rows)
        check("fixture has exactly one instruments row absent from market_watch",
              n_absent == 1, "count=%d" % n_absent)
    except Exception as e:                                        # noqa: BLE001
        check("fixture has exactly 30 market_watch rows", False, repr(e))
        check("fixture has exactly one instruments row absent from market_watch", False, repr(e))

    print("board_fixture_v1120: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
