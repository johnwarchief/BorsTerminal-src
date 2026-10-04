import os, sqlite3, tempfile, lzma

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_base_"), "market.db")
with lzma.LZMAFile("market.db.lzma") as z, open(tmp, "wb") as f:
    while True:
        c = z.read(1 << 22)
        if not c:
            break
        f.write(c)
B = sqlite3.connect("file:%s?mode=ro" % tmp.replace("\\", "/"), uri=True)
L = sqlite3.connect("file:market.db?mode=ro", uri=True)

for db, lbl in ((L, "LOCAL"), (B, "BASE")):
    cols = [k[1] for k in db.execute("PRAGMA table_info(price_history)").fetchall()]
    print(lbl, "price_history ستون‌ها:", cols)
    n = db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    print("   ردیف:", n)
    dcol = "date" if "date" in cols else ("d_even" if "d_even" in cols else cols[1])
    lo, hi = db.execute(f"SELECT MIN({dcol}), MAX({dcol}) FROM price_history").fetchone()
    print(f"   بازهٔ {dcol}:", lo, "…", hi)
    for d in ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-26", "2026-09-27", "2026-09-28", "2026-09-29"):
        q = db.execute(f"SELECT COUNT(*) FROM price_history WHERE {dcol}=?", (d,)).fetchone()[0]
        print("     ", d, q)
B.close(); L.close(); os.remove(tmp)
