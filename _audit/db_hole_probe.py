import os, sqlite3, tempfile, lzma

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_base_"), "market.db")
with lzma.LZMAFile("market.db.lzma") as z, open(tmp, "wb") as f:
    while True:
        c = z.read(1 << 22)
        if not c:
            break
        f.write(c)
B = sqlite3.connect("file:%s?mode=ro" % tmp.replace("\\", "/"), uri=True)
cols = [k[1] for k in B.execute("PRAGMA table_info(daily_prices)").fetchall()]
print("باس‌لاین daily_prices ستون‌ها:", cols)
print("p_last در باس‌لاین:", "p_last" in cols)
n = B.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
print("ردیف:", n)
for d in ("20260922", "20260923", "20260926", "20260927", "20260928", "20260929"):
    print("  ", d, B.execute("SELECT COUNT(*), COUNT(p_closing) FROM daily_prices WHERE substr(d_even,1,8)=?",
                             (d,)).fetchone())
# چه نمادهایی در محلی آن روزها را دارند/ندارند — آیا حفره سراسری است؟
L = sqlite3.connect("file:market.db?mode=ro", uri=True)
for d in ("20260921", "20260922", "20260929"):
    print(" محلی", d, L.execute("SELECT COUNT(*) FROM daily_prices WHERE substr(d_even,1,8)=?", (d,)).fetchone())
    print("   جدول‌های دیگر در همان روز:", L.execute(
        "SELECT COUNT(*) FROM price_history WHERE substr(d_even,1,8)=?", (d,)).fetchone())
print(" price_history محلی: بازه و ردیف")
print("  ", L.execute("SELECT MIN(d_even), MAX(d_even), COUNT(*) FROM price_history").fetchone())
print("  باس‌لاین:", B.execute("SELECT MIN(d_even), MAX(d_even), COUNT(*) FROM price_history").fetchone())
B.close(); L.close(); os.remove(tmp)
