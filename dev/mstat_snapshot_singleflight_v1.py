"""MSTAT-SNAP-SINGLEFLIGHT v1 — گاردِ تک‌پروازگیِ ساختِ اسنپ‌شات.

سنجشِ ۱۴۰۵-۰۷-۳۰ (مرورگر واقعی، کشِ سرد): تبِ «وضعیت بازار» ۱۹ درخواستِ
هم‌زمان می‌فرستد و هر درخواست پیش از پر شدنِ `_SNAP_CACHE` اسنپ‌شاتِ خودش را
می‌ساخت. `_build_snapshot` حدود ۶۵۰ms کوئریِ تکراری رویِ daily_prices و
client_type دارد؛ نتیجه ۱۰٫۸ ثانیه تا آمادگیِ تب بود.

این گارد همان رقابت را بازتولید می‌کند: هشت اتصالِ تازه (مثلِ هشت درخواستِ
HTTP) هم‌زمان `load_snapshot` را صدا می‌زنند. سازندۀ اصلی با یک تأخیرِ عمدی
(فقط در همین آزمون) طولانی می‌شود تا مسابقه قطعی باشد. انتظار:
  • `_build_snapshot` فقط **یک** بار اجرا شود؛
  • هر هشت فراخوان همان داده را بگیرند؛
  • پس از گرم شدن، هیچ ساختِ تازه‌ای رخ ندهد.

بانک آزمون کپیِ کوچکی از market.db است (۳۰۰ نماد)؛ بانکِ کاری هرگز
نوشته نمی‌شود و هیچ تغییری در داده یا کلیدِ کش سنجیده نمی‌شود.

usage: python dev/mstat_snapshot_singleflight_v1.py
"""
import os
import sqlite3
import sys
import tempfile
import threading
import time

REPO = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(REPO)
sys.path.insert(0, REPO)
os.chdir(REPO)

SRC_DB = os.path.join(REPO, "market.db")
TABLES = ("market_watch", "instruments", "client_type", "client_type_value",
          "daily_prices", "price_history", "mstat_snap")
N = 8

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def build_tiny_db(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/"), uri=True, timeout=30)
    con.execute("ATTACH DATABASE ? AS ro",
                ("file:" + SRC_DB.replace("\\", "/") + "?mode=ro",))
    codes = [r[0] for r in con.execute("SELECT ins_code FROM ro.market_watch LIMIT 300")]
    if not codes:
        raise SystemExit("market.db در دسترس نیست — گارد بدونِ بانک نمی‌دود")
    qmarks = ",".join("?" * len(codes))
    for t in TABLES:
        try:
            cols = [r[1] for r in con.execute("PRAGMA ro.table_info(%s)" % t)]
        except sqlite3.Error:
            continue
        if not cols:
            continue
        pick = "ins_code" if "ins_code" in cols else ("symbol" if "symbol" in cols else None)
        where = "WHERE %s IN (%s)" % (pick, qmarks) if pick else ""
        con.execute("CREATE TABLE %s (%s)" % (t, ", ".join('"%s"' % c for c in cols)))
        con.execute("INSERT INTO %s SELECT %s FROM ro.%s %s" %
                    (t, ", ".join('"%s"' % c for c in cols), t, where), codes if where else [])
    con.commit()
    con.close()


def new_conn(path):
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def main():
    if not os.path.exists(SRC_DB):
        print("SKIP: market.db پیدا نشد")
        return 0
    tmp = tempfile.mkdtemp(prefix="bors_snap_singleflight_")
    path = os.path.join(tmp, "market.db")
    try:
        build_tiny_db(path)
        import mstat_engine as E

        orig_build = E._build_snapshot
        calls = {"n": 0}
        calls_lock = threading.Lock()

        def slow_build(conn, sig, key):
            with calls_lock:
                calls["n"] += 1
            time.sleep(0.35)          # مسابقه را قطعی می‌کند؛ فقط در آزمون
            return orig_build(conn, sig, key)

        E._build_snapshot = slow_build
        barrier = threading.Barrier(N)
        results = [None] * N
        errors = []

        def worker(i):
            try:
                conn = new_conn(path)
                try:
                    barrier.wait(timeout=10)
                    results[i] = E.load_snapshot(conn)
                finally:
                    conn.close()
            except Exception as e:                       # noqa: BLE001
                errors.append("%s: %s" % (type(e).__name__, e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        ck("هیچ فراخوانی خطا نداد", not errors, "; ".join(errors)[:220])
        ck("هم‌زمانیِ سرد فقط یک ساخت انجام داد", calls["n"] == 1,
           "builds=%d (پیش از اصلاح تا %d)" % (calls["n"], N))
        ns = [len(r["rows"]) for r in results if r]
        ck("همهٔ فراخوان‌ها دادهٔ یکسان گرفتند", len(ns) == N and len(set(ns)) == 1,
           "n=%s" % (sorted(set(ns)) if ns else []))

        before = calls["n"]
        conn = new_conn(path)
        try:
            E.load_snapshot(conn)
        finally:
            conn.close()
        ck("پس از گرم شدن، ساختِ تازه‌ای رخ نمی‌دهد", calls["n"] == before,
           "builds=%d" % (calls["n"] - before))
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("MSTAT-SNAP-SINGLEFLIGHT: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
