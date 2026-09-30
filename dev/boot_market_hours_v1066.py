"""dev/boot_market_hours_v1066.py — بوتِ کامل درِ ساعتِ بازار، بی‌شبکه.

چرا این گارد هست: موجِ سبک‌سازیِ ۱٫۰٫۶۶ سه چیز را در مسیرِ استارت دست زد
(پروبِ PowerShellِ `_market_sync_alive`، نخِ دوّمِ `_sync_market_on_start` در
`__main__`، و فراخوانِ مستقیم به‌جایِ نخ در هوکِ startup). هیچ‌کدام مسیرِ داده
را لمس نمی‌کنند، ولی «لمس نمی‌کنند» یک ادعاست نه یک سنجه. این اسکریپت همان
ادعا را روی خودِ برنامه می‌سنجد: کلِ اپ را با ساعتِ جعلیِ «وسطِ نشست» بوت
می‌کند و می‌بیند آیا هر شش نخِ استارت همان کاری را می‌کنند که باید.

چه چیزی سنجیده می‌شود (همه در یک بوتِ واقعی، نه ماک):
  • دقیقاً **یک** سینکِ کاملِ بازار راه می‌افتد (نه صفر، نه دو تا).
  • حلقهٔ تیکِ ۵ ثانیه‌ای می‌دود و واقعاً در بانک می‌نویسد (h_even جلو می‌رود).
  • حلقهٔ تازه‌سازیِ ۹۰ ثانیه‌ایِ تابلو درِ پنجرهٔ نشست فعال است.
  • کشِ `/api/market` تازه می‌شود: ETag عوض می‌شود و `meta.h_even` جلو می‌رود
    — یعنی «دادهٔ کهنه» رخ نمی‌دهد.
  • تصویرِ کندل درِ بوت (`sync_price_history_from_daily` +
    `normalize_price_history_geometry`) اجرا می‌شود و `price_history` را
    عقب نمی‌برد.
  • اسنپ‌شاتِ نبضِ بازار نقطه می‌سازد.

بی‌شبکه: `polite_get` با یک فیدِ ساختگی که از خودِ `market_watch` بانک ساخته
می‌شود جایگزین می‌گردد و در هر تیک اعداد را تکان می‌دهد؛ پس هیچ درخواستی به
TSETMC نمی‌رود و در عین حال داده واقعاً عوض می‌شود.

بی‌بانک (CI): اگر `market.db` نباشد SKIP می‌دهد و rc=0 برمی‌گرداند.

عمداً در `dev/run_all_tests.py` نیست: رویِ `market.db`ِ واقعیِ کاربر می‌نویسد
(پشتیبان می‌گیرد و با atexit برمی‌گرداند، ولی نوشتن روی دادهٔ مالک نباید کارِ
یک گاردِ روتین باشد). ابزارِ A/B است، دستی اجرا می‌شود:

    # پنجرهٔ پیش‌فرض ۲۶ ثانیه
    python dev/boot_market_hours_v1066.py --json /tmp/new.json
    # پنجرهٔ بلند تا دورِ ۹۰ ثانیه‌ایِ تازه‌سازیِ تابلو هم دیده شود
    BOOT_PROBE_SECONDS=105 python dev/boot_market_hours_v1066.py --json /tmp/new.json
    # همین را در یک worktree رویِ کامیتِ پایه بدوان و دو JSON را diff کن
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# قفل لازم است: هر دو شمارنده از چند نخ هم‌زمان بالا می‌روند و `d[k] += 1`
# در CPython اتمیک نیست (LOAD/ADD/STORE با امکانِ سوییچ وسطش). بی‌قفل، این
# هارنس گاهی «۱ فراخوان» گزارش می‌داد در حالی که واقعاً ۲ تا بود — یعنی
# خودِ ابزارِ سنجش نویز می‌ساخت، نه برنامه.
import threading as _thr
_CNT_LOCK = _thr.Lock()

FAILS = []
REPORT = {}


def ck(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (("  | " + str(detail)) if detail else ""))
    if not cond:
        FAILS.append(label)


def skip(msg):
    print("  SKIP " + msg)
    print("\nSKIPPED (rc=0)")
    sys.exit(0)


# ── ۱) ساعتِ جعلی: کلِ فرآیند باید فکر کند وسطِ نشست است ──────────────────
# با TZ و نه با وصلهٔ datetime: وصله فقط ماژولی را می‌گیرد که می‌شناسیم، ولی
# app.py داخلِ بستارهایِ تودرتویش `import datetime as _dt` می‌کند. تغییرِ
# منطقهٔ زمانی همهٔ آن‌ها را با هم و بدونِ یک خط وصله جابه‌جا می‌کند.
# POSIX TZ: «XXX3:35» یعنی UTC−۳:۳۵ (علامت وارونه است).
def _force_session_clock():
    import datetime as dt
    if not hasattr(time, "tzset"):
        return None                      # ویندوز: tzset ندارد
    utc = dt.datetime.now(dt.timezone.utc)
    if utc.weekday() in (3, 4):          # پنجشنبه/جمعه → هر ساعتی بسته است
        return None
    # می‌خواهیم ساعتِ محلی ۱۰:۳۰ شود، بی‌آنکه تاریخ (و در نتیجه weekday) بپرد.
    target_min = 10 * 60 + 30
    utc_min = utc.hour * 60 + utc.minute
    off = utc_min - target_min           # دقیقه‌هایی که باید عقب برویم
    if not (0 < off < 23 * 60):
        return None
    os.environ["TZ"] = "XXX%d:%02d" % (off // 60, off % 60)
    time.tzset()
    return dt.datetime.now()


now_local = _force_session_clock()
if now_local is None:
    skip("ساعتِ سیستم به پنجرهٔ نشست نگاشته نمی‌شود (ویندوز یا آخرِ هفتهٔ UTC)")

print("  clock  ساعتِ محلیِ جعلی: %s (weekday=%d)" % (now_local.strftime("%Y-%m-%d %H:%M:%S"),
                                                      now_local.weekday()))

import mstat_engine  # noqa: E402

in_sess = mstat_engine.in_trading_session(
    now_local.hour * 10000 + now_local.minute * 100 + now_local.second, now_local)
ck("ساعتِ جعلی واقعاً «درونِ نشست» شمرده می‌شود", in_sess)
if not in_sess:
    skip("نگاشتِ ساعت نگرفت")

# ── ۲) بانکِ یکبارمصرف ───────────────────────────────────────────────────
from bors_config import DB_PATH  # noqa: E402

if not os.path.exists(DB_PATH):
    skip("market.db نیست (CI بی‌بانک)")

BACKUP = DB_PATH + ".boot_probe_backup"
shutil.copy2(DB_PATH, BACKUP)


def _restore():
    """market.db را به حالتِ پیش از پروب برمی‌گرداند. idempotent."""
    if not os.path.exists(BACKUP):
        return
    for suf in ("", "-wal", "-shm"):
        q = DB_PATH + suf
        if os.path.exists(q):
            try:
                os.remove(q)
            except OSError:
                pass
    shutil.move(BACKUP, DB_PATH)


# با atexit هم بسته می‌شود: این اسکریپت رویِ بانکِ واقعیِ کاربر می‌نویسد،
# پس حتی کرش یا Ctrl-C هم نباید بانک را دست‌کاری‌شده رها کند.
import atexit  # noqa: E402
atexit.register(_restore)


FEED_INS = []


def snap():
    c = sqlite3.connect(DB_PATH, timeout=60)
    try:
        q = lambda s: (c.execute(s).fetchone() or [None])[0]  # noqa: E731
        return {
            "market_watch_rows": q("SELECT COUNT(*) FROM market_watch"),
            "market_watch_max_h_even": q("SELECT MAX(h_even) FROM market_watch"),
            # MAX رویِ کلِ جدول کافی نیست: فیدِ جعلی فقط ۹۰۰ نماد دارد و ۴۵۲۷
            # ردیفِ دیگر h_evenِ قبلیِ خودشان را نگه می‌دارند، پس MAX تکان
            # نمی‌خورد حتی وقتی تیک درست نوشته. سنجه باید رویِ همان نمادهایی
            # باشد که فید لمسشان می‌کند.
            "feed_max_h_even": (q("SELECT MAX(h_even) FROM market_watch WHERE ins_code IN (%s)"
                                  % ",".join("'%s'" % i for i in FEED_INS)) if FEED_INS else None),
            "market_watch_max_d_even": q("SELECT MAX(d_even) FROM market_watch"),
            "daily_prices_rows": q("SELECT COUNT(*) FROM daily_prices"),
            "price_history_rows": q("SELECT COUNT(*) FROM price_history"),
            "price_history_max_date": str(q("SELECT MAX(date) FROM price_history")),
            "price_history_symbols": q("SELECT COUNT(DISTINCT symbol) FROM price_history"),
            "mstat_snap_rows": q("SELECT COUNT(*) FROM mstat_snap"),
        }
    finally:
        c.close()


# ── ۳) شبکهٔ جعلی: فیدِ تابلو از خودِ بانک ساخته می‌شود ────────────────────
import test_tsetmc as T  # noqa: E402

_conn = sqlite3.connect(DB_PATH, timeout=60)
_rows = _conn.execute(
    "SELECT ins_code, d_even, h_even, p_closing, price_min, price_max, price_yesterday,"
    "       price_first, q_tot_tran, q_tot_cap, z_tot_tran, price_change, eps, pe,"
    "       total_shares, sector_code FROM market_watch LIMIT 900").fetchall()
_conn.close()
if not _rows:
    _restore()
    skip("market_watch خالی است")

_BASE_FEED = [{
    "insCode": r[0], "dEven": r[1], "hEven": int(r[2] or 100000),
    "pcl": r[3], "pmn": r[4], "pmx": r[5], "py": r[6], "pf": r[7],
    "pMin": r[4], "pMax": r[5], "qtj": r[8], "qtc": r[9], "ztt": r[10],
    "pc": r[11], "eps": r[12], "pe": r[13], "ztd": r[14], "csv": r[15],
    "lva": "X", "lvc": "X", "bv": 0,
} for r in _rows]
FEED_INS[:] = [str(r["insCode"]) for r in _BASE_FEED]

TICKS = {"n": 0, "rows": 0}
FEED_CALLS = {"marketwatch": 0, "other": 0}


def fake_polite_get(s, url, key=None, timeout=90):
    """هیچ بایتی به شبکه نمی‌رود. فقط تابلو داده برمی‌گرداند؛ بقیه خالی."""
    if key == "marketwatch" and "market=0" in url:
        FEED_CALLS["marketwatch"] += 1
        bump = FEED_CALLS["marketwatch"]
        out = []
        for i, r in enumerate(_BASE_FEED):
            d = dict(r)
            # هر تیک اعداد را تکان می‌دهد تا نوشتن واقعاً رخ دهد و امضایِ
            # _tick_observe عوض شود (وگرنه تیک به حالتِ «گوش‌دادن» می‌رود).
            d["hEven"] = 103000 + bump
            d["qtj"] = (d["qtj"] or 0) + bump * 100 + i
            d["pcl"] = (d["pcl"] or 0) + (bump % 3)
            out.append(d)
        return out
    FEED_CALLS["other"] += 1
    return [] if key else None


T.polite_get = fake_polite_get
T.make_session = lambda *a, **k: type("S", (), {"_polite": None, "get": None})()
T._tick_session = lambda *a, **k: type("S", (), {"_polite": None, "get": None})()

_real_tick = T.tick_live


def counting_tick(conn=None):
    n = _real_tick(conn)
    with _CNT_LOCK:
        TICKS["n"] += 1
        TICKS["rows"] += int(n or 0)
    return n


T.tick_live = counting_tick

# ── ۴) شمارندهٔ سینکِ کامل ────────────────────────────────────────────────
import api._sync_market as SM  # noqa: E402

# دو شمارنده، چون دو چیزِ متفاوت‌اند و قاطی‌کردنشان خطایِ خواندنِ لاگ می‌سازد:
#   calls  = چند بار _run_market_sync صدا زده شد. درِ نشست این عددِ ۲ **درست**
#            است: یکی هوکِ استارت، یکی اولین دورِ _board_refresh_loop که چون
#            پنجرهٔ بازار باز است بلافاصله می‌دود.
#   runs   = چند بار واقعاً سینق شد، یعنی چند بار قفل گرفته شد و main() دوید.
#            این باید ۱ باشد؛ دومی باید پشتِ قفل «skip» بخورد.
SYNCS = {"calls": 0, "runs": 0}
_real_run = SM._run_market_sync
_real_main = T.main


def counting_main(*a, **k):
    with _CNT_LOCK:
        SYNCS["runs"] += 1
    return _real_main(*a, **k)


T.main = counting_main


def counting_run():
    with _CNT_LOCK:
        SYNCS["calls"] += 1
    return _real_run()


SM._run_market_sync = counting_run

# ── ۵) بوتِ واقعی ─────────────────────────────────────────────────────────
BEFORE = snap()
print("  before %s" % json.dumps(BEFORE, ensure_ascii=False))

from fastapi.testclient import TestClient  # noqa: E402
import app as appmod  # noqa: E402

OBSERVE_S = float(os.environ.get("BOOT_PROBE_SECONDS", "26"))
etags, metas = [], []
t_boot = time.perf_counter()
try:
    with TestClient(appmod.app, base_url="http://127.0.0.1:8001") as client:
        boot_s = time.perf_counter() - t_boot
        deadline = time.time() + OBSERVE_S
        while time.time() < deadline:
            r = client.get("/api/market")
            if r.status_code == 200:
                et = r.headers.get("etag")
                if et and (not etags or etags[-1] != et):
                    etags.append(et)
                    try:
                        metas.append(r.json().get("meta"))
                    except Exception:
                        pass
            time.sleep(2.0)
    AFTER = snap()
finally:
    pass

print("  after  %s" % json.dumps(AFTER, ensure_ascii=False))

# ── ۶) داوری ──────────────────────────────────────────────────────────────
print()
ck("بوت مسدود نمی‌شود (هوکِ startup زیرِ ۵ ثانیه)", boot_s < 5.0, "%.2fs" % boot_s)
# نامتغیرِ اصلی: یک سینق درِ بوت، به‌اضافهٔ یکی به‌ازایِ هر دورِ کاملِ
# ۹۰ ثانیه‌ایِ `_board_refresh_loop` که داخلِ پنجرهٔ پایش افتاده. بیشتر از
# این یعنی قفلِ تک‌نفره نشتی دارد؛ کمتر یعنی تابلو درِ نشست تازه نمی‌شود.
_expect_runs = 1 + int(OBSERVE_S // 90)
ck("سینق‌ها دقیقاً به تعدادِ انتظار اجرا شدند (۱ بوت + هر ۹۰ ثانیه یکی)",
   SYNCS["runs"] == _expect_runs,
   "runs=%d (انتظار %d) از %d فراخوان، پنجره %ds"
   % (SYNCS["runs"], _expect_runs, SYNCS["calls"], OBSERVE_S))
# «چند فراخوان» را نمی‌سنجیم چون تا ۱٫۰٫۶۵ مسابقه‌ای بود: هوکِ استارت نخ
# می‌ساخت و `_board_refresh_loop` هم درِ نشست بلافاصله می‌دوید، و هرکدام که
# زودتر می‌رسید قفل را می‌گرفت؛ سنجشِ ۳×۳ همین‌جا هر دو ترتیب را دید
# (۲/۲/۱ فراخوان). نتیجه هر دو حالت یکی بود، ولی مسیر تصادفی بود. از
# ۱٫۰٫۶۶ هوک مستقیم صدا می‌زند و همیشه اول است. فقط ثبتش می‌کنیم.
ck("سینق از مسیرِ استارت شروع شد (نه از حلقهٔ ۹۰ ثانیه‌ای)",
   SYNCS["calls"] >= 1, "calls=%d" % SYNCS["calls"])
# ریتم: پنجره/۵، با ۲ ثانیه اغماض برایِ بالاآمدنِ نخ.
_expect_ticks = max(3, int((OBSERVE_S - 2) // 5))
ck("حلقهٔ تیکِ ۵ ثانیه‌ای با همان ریتم دوید",
   TICKS["n"] >= _expect_ticks, "ticks=%d (انتظار ≥%d در %ds)" % (TICKS["n"], _expect_ticks, OBSERVE_S))
ck("تیک واقعاً در بانک نوشت", TICKS["rows"] > 0, "rows=%d" % TICKS["rows"])
ck("هیچ درخواستی به TSETMC نرفت (فیدِ جعلی)", FEED_CALLS["marketwatch"] > 0)
ck("h_evenِ نمادهایِ فید جلو رفت ⇒ دادهٔ تابلو کهنه نماند",
   (AFTER["feed_max_h_even"] or 0) != (BEFORE["feed_max_h_even"] or 0),
   "%s → %s" % (BEFORE["feed_max_h_even"], AFTER["feed_max_h_even"]))
ck("ETag کشِ /api/market عوض شد ⇒ فرانت دادهٔ تازه می‌گیرد",
   len(etags) >= 2, "%d etag یکتا" % len(etags))
ck("روزِ نشست عقب نرفت", (AFTER["market_watch_max_d_even"] or 0) >= (BEFORE["market_watch_max_d_even"] or 0),
   "%s → %s" % (BEFORE["market_watch_max_d_even"], AFTER["market_watch_max_d_even"]))
ck("کندل‌ها عقب نرفتند (price_history rows)",
   (AFTER["price_history_rows"] or 0) >= (BEFORE["price_history_rows"] or 0),
   "%s → %s" % (BEFORE["price_history_rows"], AFTER["price_history_rows"]))
ck("آخرین تاریخِ کندل عقب نرفت",
   str(AFTER["price_history_max_date"]) >= str(BEFORE["price_history_max_date"]),
   "%s → %s" % (BEFORE["price_history_max_date"], AFTER["price_history_max_date"]))
ck("تعدادِ نمادهایِ دارایِ کندل کم نشد",
   (AFTER["price_history_symbols"] or 0) >= (BEFORE["price_history_symbols"] or 0),
   "%s → %s" % (BEFORE["price_history_symbols"], AFTER["price_history_symbols"]))
ck("اسنپ‌شاتِ نبض نقطه ساخت",
   (AFTER["mstat_snap_rows"] or 0) >= (BEFORE["mstat_snap_rows"] or 0),
   "%s → %s" % (BEFORE["mstat_snap_rows"], AFTER["mstat_snap_rows"]))

REPORT.update({
    "boot_seconds_under_5": boot_s < 5.0,
    "full_sync_runs": SYNCS["runs"],
    "full_sync_calls_at_least_2": SYNCS["calls"] >= 2,
    "ticks": TICKS["n"] >= 3,
    "tick_wrote_rows": TICKS["rows"] > 0,
    "unique_etags_at_least_2": len(etags) >= 2,
    "before": BEFORE,
    "after": AFTER,
    "h_even_advanced": (AFTER["feed_max_h_even"] or 0) != (BEFORE["feed_max_h_even"] or 0),
    "meta_last": metas[-1] if metas else None,
    "fails": FAILS,
})

_restore()

ap = argparse.ArgumentParser()
ap.add_argument("--json")
args, _ = ap.parse_known_args()
if args.json:
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("  wrote %s" % args.json)

print("\n%d pass / %d fail" % (12 - len(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
