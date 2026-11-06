# مقایسۀ تاریخچۀ daily_prices بین بانکِ محلی و باس‌لاینِ commit‌شده (فقط خواندن)
import io, os, sqlite3, tempfile, lzma

def probe(path, label):
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    q = lambda s: con.execute(s).fetchone()
    n = q("SELECT COUNT(*) FROM daily_prices")[0]
    lo, hi = q("SELECT MIN(d_even), MAX(d_even) FROM daily_prices")
    nd = q("SELECT COUNT(DISTINCT ins_code) FROM daily_prices")[0]
    print(f"{label:10} ردیف={n:>7}  بازه={lo} … {hi}  نماد={nd}")
    per = con.execute("SELECT substr(d_even,1,6) p, COUNT(*) FROM daily_prices "
                      "GROUP BY p ORDER BY p DESC LIMIT 6").fetchall()
    print("   ", per)
    con.close()

BASE = os.environ.get("BORS_BASE_DB")
probe("market.db", "LOCAL")

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_base_"), "market.db")
with lzma.LZMAFile("market.db.lzma") as z, open(tmp, "wb") as f:
    while True:
        c = z.read(1 << 22)
        if not c:
            break
        f.write(c)
probe(tmp, "BASELINE")
os.remove(tmp)
