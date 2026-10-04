# ترمیمِ حفرۀ پنج‌روزۀ market.db: بازگردانیِ daily_prices از باس‌لاین + کندل از خودِ تابلو
# (مسیرِ خودِ برنامه: test_tsetmc.sync_price_history_from_daily)
import argparse, os, sqlite3, sys, tempfile, lzma

DAYS = ("20260922", "20260923", "20260926", "20260927", "20260928")

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
args = ap.parse_args()

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_base_"), "market.db")
with lzma.LZMAFile("market.db.lzma") as z, open(tmp, "wb") as f:
    while True:
        c = z.read(1 << 22)
        if not c:
            break
        f.write(c)

conn = sqlite3.connect("market.db", timeout=60)
conn.execute("PRAGMA busy_timeout=60000")
conn.execute("ATTACH DATABASE ? AS base", (tmp.replace("\\", "/"),))
main_cols = [r[1] for r in conn.execute("PRAGMA main.table_info(daily_prices)")]
base_cols = [r[1] for r in conn.execute("PRAGMA base.table_info(daily_prices)")]
common = [c for c in main_cols if c in base_cols]
print("ستون‌های مشترک:", len(common), "| فقط محلی:", sorted(set(main_cols) - set(base_cols)))

before_dp = conn.execute("SELECT COUNT(*) FROM main.daily_prices").fetchone()[0]
before_ph = conn.execute("SELECT COUNT(*) FROM main.price_history").fetchone()[0]
print("پیش از ترمیم: daily_prices", before_dp, "| price_history", before_ph)

if not args.apply:
    print("DRY-RUN")
    conn.close(); os.remove(tmp); sys.exit(0)

if not os.path.exists("market.db.holefix-backup"):
    dst = sqlite3.connect("market.db.holefix-backup")
    conn.backup(dst)
    dst.close()
    print("بکاپ گرفته شد: market.db.holefix-backup", f"{os.path.getsize('market.db.holefix-backup'):,}")

ins = "INSERT OR IGNORE INTO main.daily_prices (%s) SELECT %s FROM base.daily_prices WHERE substr(d_even,1,8)=?"
n = 0
for d in DAYS:
    r = conn.execute(ins % (",".join(common), ",".join(common)), (d,)).rowcount
    n += r
    print("  daily_prices", d, "+", r)
conn.commit()
print("درجِ تابلو:", n, "ردیف")

sys.path.insert(0, ".")
import test_tsetmc  # noqa: E402
print("جبرانِ کندل از تابلو (مسیرِ خودِ برنامه):")
res = test_tsetmc.sync_price_history_from_daily(conn, full=True)
print("  نتیجه:", res)
conn.close()
os.remove(tmp)

V = sqlite3.connect("file:market.db?mode=ro", uri=True)
print("از اتصالِ تازه:")
print("  daily_prices:", V.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0],
      "| price_history:", V.execute("SELECT COUNT(*) FROM price_history").fetchone()[0])
for d in DAYS:
    dp = V.execute("SELECT COUNT(*) FROM daily_prices WHERE substr(d_even,1,8)=?", (d,)).fetchone()[0]
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    ph = V.execute("SELECT COUNT(*) FROM price_history WHERE date=?", (iso,)).fetchone()[0]
    srcs = V.execute("SELECT COALESCE(src,'-'), COUNT(*) FROM price_history WHERE date=? GROUP BY 1",
                     (iso,)).fetchall()
    print(f"   {iso}: تابلو={dp} کندل={ph} مالکیت={srcs}")
print("  بازهٔ کندل:", V.execute("SELECT MIN(date), MAX(date) FROM price_history").fetchone())
print("  نشستنِ بی‌کندل در ۲۴ نشستِ آخر تابلو:", V.execute(
    "SELECT d.d_even, COUNT(DISTINCT d.ins_code) FROM daily_prices d "
    "WHERE d.q_tot_tran > 0 AND d.p_closing > 0 AND NOT EXISTS (SELECT 1 FROM price_history p "
    "  WHERE p.date = substr(d.d_even,1,4)||'-'||substr(d.d_even,5,2)||'-'||substr(d.d_even,7,2)) "
    "GROUP BY d.d_even ORDER BY d.d_even DESC LIMIT 8").fetchall())
V.close()
