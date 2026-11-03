"""MSTAT-CACHE-DURABILITY v1 — گاردِ کشِ ۵دقیقه‌ایِ بیرونِ نشست (PERF-R6).

بازِ دوبارهٔ «وضعیت بازار» پس از ۵۰ثانیه بیکاری ۷٫۰s طول می‌کشید، چون TTLِ
۴۵ثانیه‌ای همهٔ ۲۰ پنل را دوباره می‌ساخت، هرچند داده عوض نشده بود. حالا:
  • بیرونِ نشست TTL=۳۰۰s، درِ نشست همان ۴۵s؛
  • کلیدِ کش همان چهار نشانهٔ داده (revision/static_rev/session_day/mstat_snap)
    است.

دو چیز باید ثابت بماند:
  ۱) TTL واقعاً نشست‌محور است (۴۵ درِ ساعتِ بازار، ۳۰۰ بیرون)؛
  ۲) تغییرِ نشانهٔ داده کلید را عوض می‌کند — TTLِ بلندتر هرگز دادهٔ کهنه را
     با کلیدِ ثابت نگه نمی‌دارد.

بانک آزمون کپیِ کوچکی از market.db است؛ بانکِ کاری نوشته نمی‌شود.

usage: python dev/mstat_cache_durability_v1.py
"""
import datetime
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
os.chdir(ROOT)

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def main():
    if not os.path.exists(os.path.join(ROOT, "market.db")):
        print("SKIP: market.db نیست")
        return 0
    spec = importlib.util.spec_from_file_location(
        "mstat_snapshot_cache_v1", os.path.join(ROOT, "dev", "mstat_snapshot_cache_v1.py"))
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    tmp = tempfile.mkdtemp(prefix="bors_mstat_ttl_")
    db = os.path.join(tmp, "market.db")
    try:
        builder.build_tiny_db(db)
        import mstat_engine as E
        import api._core as C
        import api.market_status as MS
        C.DB_PATH = db
        C.USER_DB_PATH = os.path.join(tmp, "user.db")
        C._SCHEMA_READY.clear()
        MS.DB_PATH = db
        MS._MSTAT_CACHE.clear()

        orig_session = E.in_trading_session
        E.in_trading_session = lambda hm, now=None: 90000 <= int(hm) < 130000
        try:
            ck("درِ نشست ⇒ TTL ۴۵s", MS._mstat_ttl(datetime.datetime(2026, 10, 22, 10, 0)) == 45.0)
            ck("بیرونِ نشست ⇒ TTL ۳۰۰s", MS._mstat_ttl(datetime.datetime(2026, 10, 22, 16, 0)) == 300.0)
        finally:
            E.in_trading_session = orig_session

        before = MS._mstat_state()
        orig_rev = MS._MS.revision
        MS._MS.revision = lambda: int(orig_rev()) + 7
        try:
            after = MS._mstat_state()
        finally:
            MS._MS.revision = orig_rev
        ck("تغییرِ revision کلید را عوض می‌کند", before != after,
           "%s -> %s" % (str(before)[:70], str(after)[:70]))
        ck("کلیدِ حالت همان چهار نشانهٔ داده را دارد", len(after) == 4,
           "state=%s" % (after,))
    finally:
        for p in (db, db + "-wal", db + "-shm"):
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
    print("MSTAT-CACHE-DURABILITY: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
