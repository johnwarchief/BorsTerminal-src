#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import symbol_identity as SI  # noqa: E402


def main():
    assert SI.key("كگل") == SI.key("کگل")
    assert SI.key("شبندر ") == SI.key("شبندر")
    assert SI.key("آب\u200cس") == SI.key("آبس")
    assert SI.key("\u064a") == SI.key("\u06cc")
    assert SI.key("\u0649") == SI.key("\u06cc")
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE instruments(
        ins_code TEXT, l_val18 TEXT, l_val30 TEXT, paper_type INTEGER,
        isin TEXT, updated_at TEXT)""")
    con.execute("INSERT INTO instruments VALUES('1','كگل','الف',1,NULL,'2026-01-01')")
    con.execute("INSERT INTO instruments VALUES('2','کگل','ب',1,'I','2025-01-01')")
    con.execute("INSERT INTO instruments VALUES('3','فولاد','ج',8,NULL,'2026-02-01')")
    con.commit()
    m = SI.load_instruments(con)
    assert m[SI.key("کگل")]["ins_code"] == "2", m
    assert m[SI.key("فولاد")]["ins_code"] == "3"
    con.close()
    os.unlink(path)
    import importlib.util
    p = os.path.join(HERE, "..", "tools", "phase45", "select_symbols.py")
    spec = importlib.util.spec_from_file_location("select_symbols", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for s in ("كگل", "کگل", "شبندر ", "آب\u200cس"):
        assert mod.key(s) == SI.key(s), s
    print("SYMBOL IDENTITY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
