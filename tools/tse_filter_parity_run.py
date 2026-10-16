# -*- coding: utf-8 -*-
"""یک فرمان برایِ سنجشِ «همان نشست»: هفت فیلتر، مرجعِ سایت در برابرِ اپ.

چرا این ابزار هست: دورِ نهاییِ مأموریتِ ۱۴۰۵-۰۷-۲۰ با سه دستورِ ad-hoc انجام
شد (واکشی باندها، تیکِ بانکِ کپی، سپس `node … --check` و پارالل). آن زنجیره
تکرارپذیر نبود و مالک برایِ سنجشِ درِ ساعتِ بازار به همان یک فرمان نیاز دارد.

هرچه می‌کند عیناً همان چهار گام است، با همان ابزارهایِ موجود:
  ۱) باندهایِ خامِ سایت → `_audit/tse_cache_*.json|txt` (مرجعِ `PrepareFilterCode`)
  ۲) کپیِ `market.db` → تیکِ کاملِ `test_tsetmc.main()` رویِ همان کپی
     (بانکِ واقعیِ برنامه دست نمی‌خورد؛ مسیرها پیش از import عوض می‌شوند)
  ۳) `node tools/tse_saved_filter_eval.mjs --check` — اجرایِ عینِ سایت رویِ باندها
     و خودسنجی با فهرستِ نشستِ مالک
  ۴) `python tools/tse_app_flag_parity.py --db <کپی>` — پرچم‌هایِ مسیرِ
     منتشرشدهٔ `/api/market` در برابرِ همان مرجع

گامِ ۱ و ۲ باید پشتِ سرِ هم بخوانند: سنجشِ «هم‌زمان» با فاصلۀِ چنددقیقه‌ای
سابقه دارد که اختلافِ جعلی ساخت (zd1 بینِ دو واکنش جابه‌جا شد).

اجرا:
  PYTHONIOENCODING=utf-8 python tools/tse_filter_parity_run.py [--no-tick] [--db PATH]
"""
import argparse
import gzip
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = {
    "ClosingPriceAll": "_audit/tse_cache_ClosingPriceAll.txt",
    "InstValue": "_audit/tse_cache_InstValue.txt",
    "mw_rows": "_audit/tse_cache_mw_rows.json",
    "ct": "_audit/tse_cache_ct.json",
}
OLD = "https://old.tsetmc.com/tsev2/data"
CDN = "https://cdn.tsetmc.com/api"
H = {"User-Agent": "Mozilla/5.0",
     "Accept": "application/json, text/plain, */*",
     "Accept-Encoding": "gzip",
     "Referer": "https://old.tsetmc.com/", "Origin": "https://old.tsetmc.com"}


def _raw(url, tries=3, pause=8.0):
    last = None
    for _ in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=240).read()
            return gzip.decompress(r) if r[:2] == b"\x1f\x8b" else r
        except Exception as e:  # noqa: BLE001 — دیدۀبان گاه ۵۰۰ می‌دهد؛ یک بارِ دیگر
            last = f"{type(e).__name__}: {e}"[:90]
            time.sleep(pause)
    raise SystemExit("[snapshot] واکنش نگرفت: %s — %s" % (url, last))


def snapshot():
    """چهار باندِ همان لحظه → فایل‌هایِ کشِ مرجع."""
    import json
    pt = "&".join("paperTypes[%d]=%d" % (i, i + 1) for i in range(9))
    mw = json.loads(_raw(CDN + "/ClosingPrice/GetMarketWatch?market=0&%s&showTraded=false"
                               "&withBestLimits=true&hEven=0" % pt).decode("utf-8", "replace"))
    ct = json.loads(_raw(CDN + "/ClientType/GetClientTypeAll").decode("utf-8", "replace"))
    rows = mw.get("marketwatch") or []
    if not rows:
        raise SystemExit("[snapshot] marketwatch خالی برگشت — سنجش در این لحظه بی‌مفهوم است")
    io.open(CACHE["ClosingPriceAll"], "w", encoding="utf-8", newline="").write(
        _raw(OLD + "/ClosingPriceAll.aspx").decode("utf-8", "replace"))
    io.open(CACHE["InstValue"], "w", encoding="utf-8", newline="").write(
        _raw(OLD + "/InstValue.aspx?t=a").decode("utf-8", "replace"))
    json.dump(rows, io.open(CACHE["mw_rows"], "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(ct.get("clientTypeAllDto") or [], io.open(CACHE["ct"], "w", encoding="utf-8"),
              ensure_ascii=False)
    print("[snapshot] %s | ردیفِ دیدۀبان=%s  حجمِ [ih]=%s  [is]=%s"
          % (time.strftime("%Y-%m-%d %H:%M:%S"), f"{len(rows):,}",
             f"{os.path.getsize(CACHE['ClosingPriceAll']):,}",
             f"{os.path.getsize(CACHE['InstValue']):,}"))
    return rows


def tick_copy(db):
    """کپیِ بانکِ برنامه را کامل نو می‌کند؛ خودِ `market.db` فقط خوانده می‌شود."""
    src = os.path.join(ROOT, "market.db")
    if not os.path.exists(src):
        raise SystemExit("[tick] بانکِ برنامه نیست (%s) — کپی ساختنی نیست" % src)
    shutil.copy(src, db)
    print("[tick] کپی ساخته شد:", db)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    code = (
        "import sys; sys.path.insert(0,%r)\n"
        "import bors_config as B\n"
        "B.DB_PATH=%r; B.STATUS_PATH=%r; B.MARKET_STATUS_PATH=%r\n"
        "import test_tsetmc as T\n"
        "T.DB_PATH=B.DB_PATH; T.STATUS_PATH=B.STATUS_PATH; T.MARKET_STATUS_PATH=B.MARKET_STATUS_PATH\n"
        "T.main()\n"
        % (ROOT, db, "_audit/parity_run_status.json", "_audit/parity_run_mstatus.json"))
    log = "_audit/tse_parity_tick.log"
    with io.open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.call([sys.executable, "-c", code], cwd=ROOT, env=env,
                             stdout=fh, stderr=subprocess.STDOUT)
    keep = [l.strip() for l in io.open(log, encoding="utf-8", errors="replace")
            if "tape-slots" in l or "inst-value" in l or "Symbols fetched" in l]
    print("[tick] rc=%d | %s" % (rc, " | ".join(keep) or "هیچ خطِ کلیدی در لاگ"))
    if rc != 0:
        raise SystemExit("[tick] تیکِ کپی شکست — لاگ: " + log)
    conn = sqlite3.connect(db)
    try:
        for t in ("tape_ih_slot", "tse_inst_stat"):
            n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            print("[tick] %s = %s ردیف" % (t, f"{n:,}"))
    finally:
        conn.close()


def run(cmd):
    print("[run] " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("   ", line)
    if p.returncode != 0:
        print("[run] rc=%d" % p.returncode)
    return p.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="_audit/market_copy_parity.db")
    ap.add_argument("--no-tick", action="store_true",
                    help="بانکِ کپی را دوباره نو نکن (وقتی همین الان نو شده)")
    a = ap.parse_args()
    t0 = time.time()
    snapshot()
    if not a.no_tick:
        tick_copy(a.db)
    print("\n──── گامِ ۳: اجرایِ عینِ سایت رویِ باندها ────")
    run(["node", os.path.join("tools", "tse_saved_filter_eval.mjs"), "--check"])
    print("\n──── گامِ ۴: پرچم‌هایِ /api/market در برابرِ همان مرجع ────")
    run([sys.executable, os.path.join("tools", "tse_app_flag_parity.py"),
         "--db", a.db, "--ref", "_audit/tse_saved_filter_eval.json"])
    print("\n[done] %.0f ثانیه | مرجع: _audit/tse_saved_filter_eval.json | "
          "پارالل: _audit/tse_app_flag_parity.json" % (time.time() - t0))


if __name__ == "__main__":
    main()
