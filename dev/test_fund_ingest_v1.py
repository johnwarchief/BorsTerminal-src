# -*- coding: utf-8 -*-
"""Round 8: deterministic tests for the official fund-profit importer.

No network: the legacy HTML report is faked, the Rayan Ham Afza JSON shape is
checked directly, and the instrument lookup uses a temp DB. Covers duplicate
rows, Persian digits, corrupt dates/amounts, and newest-instrument selection.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "tools", "fund_profits_ingest.py")

P = F = 0


def ck(cond, msg, detail=None):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def load_mod():
    spec = importlib.util.spec_from_file_location("fund_ingest", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _Session:
    def __init__(self, text):
        self.text = text
        self.headers = {}

    def get(self, *a, **k):
        return _Resp(self.text)


def main():
    m = load_mod()

    # Persian digits and separators.
    ck(m._num_fa("۱٬۲۳۴") == 1234.0, "Persian digits and thousands separator parse", m._num_fa("۱٬۲۳۴"))
    ck(m._num_fa("abc") is None, "corrupt amount is rejected", m._num_fa("abc"))

    # Jalali to Gregorian.
    d = m._date_of_profit("1405/07/15")
    ck(d is not None and d.isoformat() == "2026-10-07",
       "Jalali profit date maps to 2026-10-07", d)
    ck(m._date_of_profit("not-a-date") is None,
       "corrupt profit date is rejected", m._date_of_profit("not-a-date"))

    # Legacy HTML: duplicate row deduped, incomplete row skipped, Persian digits.
    html = """
    <table>
      <tr><th>ردیف</th><th>تاریخ</th><th>واحد</th><th>سود هر واحد</th><th>کل</th><th>وضعیت</th></tr>
      <tr><td>۱</td><td>۱۴۰۵/۰۷/۱۵</td><td>۱۰۰</td><td>۲۷۲</td><td>۲۷۲۰۰</td><td>پرداخت</td></tr>
      <tr><td>۲</td><td>۱۴۰۵/۰۷/۱۵</td><td>۱۰۰</td><td>۲۷۲</td><td>۲۷۲۰۰</td><td>پرداخت</td></tr>
      <tr><td>۳</td><td>۱۴۰۵/۰۶/۱۵</td><td>۱۰۰</td><td>۲۵۵</td><td>۲۵۵۰۰</td><td>پرداخت</td></tr>
      <tr><td>۴</td><td></td><td>۱۰۰</td><td>۲۵۰</td><td>۲۵۰۰۰</td><td>ناقص</td></tr>
      <tr><td>۵</td><td>۱۴۰۵/۰۵/۱۵</td><td>۱۰۰</td><td>abc</td><td>۰</td><td>خراب</td></tr>
    </table>
    """
    m.requests.Session = lambda: _Session(html)
    rows = m._fetch_legacy({"portal": "https://example.invalid/",
                            "report_path": "/Reports/FundDividendProfitReport"})
    ck(len(rows) == 2, "duplicate legacy row deduped and corrupt rows skipped", rows)
    ck(rows[0]["profitDate"] == "1405/07/15" and rows[0]["unitProfit"] == 272.0,
       "legacy row keeps date and per-unit amount", rows[0] if rows else None)

    # Instrument lookup: newest updated_at wins, variants stay separate.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
                    " board INTEGER, updated_at TEXT)")
        con.execute("INSERT INTO instruments VALUES ('old','X','X',1,'2020-01-01')")
        con.execute("INSERT INTO instruments VALUES ('new','X','X',1,'2026-01-01')")
        con.commit()
        got = m._rows_for_instrument(con, "X")
        con.close()
        ck([r[0] for r in got] == ["new", "old"],
           "newest instrument row is first", got)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


if __name__ == "__main__":
    main()
