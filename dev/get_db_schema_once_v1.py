"""GETDB-SCHEMA-ONCE v1 — گاردِ بررسیِ یک‌بارهٔ اسکیما (PERF-R5).

پیش از این هر `get_db()` چند CREATE IF NOT EXISTS + PRAGMA table_info + ALTER
را دوباره اجرا می‌کرد: سنجشِ ۱۴۰۵-۰۷-۳۰، ۳۰۰ اتصال ⇒ p50 ۷٫۹ms و ۲٫۱۷s CPU.
حالا کلیدِ «(فایل، PRAGMA schema_version)» یک‌بار بررسی می‌شود.

سه چیز باید ثابت بماند:
  ۱) فراخوانِ دوم همان بانک همان اسکیما را دوباره بررسی نمی‌کند؛
  ۲) جدول‌هایِ ساخت‌شده (selection/mstat/user) واقعاً وجود دارند؛
  ۳) تغییرِ اسکیما از بیرون (ALTER) کلید را عوض می‌کند و بررسی دوباره اجرا
     می‌شود — «یک‌بار» نباید به «هرگز» تبدیل شود.

بانک آزمون کپیِ کوچکی از market.db است؛ بانکِ کاری نوشته نمی‌شود.

usage: python dev/get_db_schema_once_v1.py
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
os.chdir(ROOT)

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "mstat_snapshot_cache_v1", os.path.join(ROOT, "dev", "mstat_snapshot_cache_v1.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_tiny_db


def main():
    if not os.path.exists(os.path.join(ROOT, "market.db")):
        print("SKIP: market.db نیست")
        return 0
    build_tiny_db = load_builder()
    tmp = tempfile.mkdtemp(prefix="bors_getdb_")
    db = os.path.join(tmp, "market.db")
    user = os.path.join(tmp, "user.db")
    try:
        build_tiny_db(db)
        import api._core as C
        C.DB_PATH = db
        C.USER_DB_PATH = user
        C._SCHEMA_READY.clear()

        # شمارشِ خودِ کارِ DDL، نه فراخوانِ دروازه: دروازه هر درخواست صدا
        # زده می‌شود ولی فقط وقتی کلیدِ (فایل، schema_version) تازه باشد DDL
        # را اجرا می‌کند. پس `ensure_market_schema` را می‌شماریم.
        mk_calls = {"n": 0}
        us_calls = {"n": 0}
        orig_mk, orig_sel = C.ensure_market_schema, C.ensure_selection_schema

        def mk(conn):
            mk_calls["n"] += 1
            return orig_mk(conn)

        def sel(conn):
            us_calls["n"] += 1
            return orig_sel(conn)

        C.ensure_market_schema = mk
        C.ensure_selection_schema = sel

        c1 = C.get_db()
        tables = {r[0] for r in c1.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        c1.close()
        ck("اولین get_db اسکیما را می‌سازد", mk_calls["n"] == 1, "calls=%d" % mk_calls["n"])
        ck("جدول‌هایِ selection/mstat ساخته شده‌اند",
           {"selection_decisions", "mstat_snap"} <= tables,
           ",".join(sorted({"selection_decisions", "mstat_snap"} - tables)) or "ok")

        c2 = C.get_db()
        c2.close()
        ck("فراخوانِ دوم همان بانک بررسی را تکرار نمی‌کند", mk_calls["n"] == 1,
           "calls=%d" % mk_calls["n"])

        # تغییرِ اسکیما از بیرون (مثلِ مهاجرتِ ابزارِ دیگر) باید کلید را بشکند.
        side = sqlite3.connect(db)
        side.execute("ALTER TABLE market_watch ADD COLUMN schema_probe_col INTEGER")
        side.commit()
        side.close()
        c3 = C.get_db()
        c3.close()
        ck("ALTERِ بیرونی بررسی را دوباره اجرا می‌کند", mk_calls["n"] == 2,
           "calls=%d" % mk_calls["n"])
        c4 = C.get_db()
        c4.close()
        ck("بعد از بررسیِ دوباره، دوباره یک‌باره می‌شود", mk_calls["n"] == 2,
           "calls=%d" % mk_calls["n"])

        us_calls["n"] = 0
        u1 = C.get_user_db()
        ut = {r[0] for r in u1.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        u1.close()
        u2 = C.get_user_db()
        u2.close()
        ck("user.db جداولش را یک‌بار می‌سازد و بارِ دوم تکرار نمی‌کند",
           us_calls["n"] == 1 and {"user_watchlists", "selection_decisions"} <= ut,
           "calls=%d tables=%s" % (us_calls["n"], sorted(ut)))
    finally:
        for p in (db, user, user + "-wal", user + "-shm", db + "-wal", db + "-shm"):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("GETDB-SCHEMA-ONCE: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
