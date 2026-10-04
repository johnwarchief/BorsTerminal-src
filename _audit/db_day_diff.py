import os, sqlite3, tempfile, lzma

def conn(p):
    return sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_base_"), "market.db")
with lzma.LZMAFile("market.db.lzma") as z, open(tmp, "wb") as f:
    while True:
        c = z.read(1 << 22)
        if not c:
            break
        f.write(c)

L, B = conn("market.db"), conn(tmp)
days = sorted({r[0] for r in L.execute("SELECT DISTINCT d_even FROM daily_prices")} |
              {r[0] for r in B.execute("SELECT DISTINCT d_even FROM daily_prices")})
print("روز | محلی | باس‌لاین | فرق")
for d in days:
    a = L.execute("SELECT COUNT(*) FROM daily_prices WHERE d_even=?", (d,)).fetchone()[0]
    b = B.execute("SELECT COUNT(*) FROM daily_prices WHERE d_even=?", (d,)).fetchone()[0]
    flag = "" if a == b else ("  <<<" if abs(a - b) > 50 else "  <-")
    print(f"{d} | {a:>5} | {b:>5} | {a-b:>6}{flag}")

D0 = "20260922"
print("\nنماد در روز", D0, "(محلی):", L.execute(
    "SELECT COUNT(DISTINCT ins_code) FROM daily_prices WHERE substr(d_even,1,8)=?", (D0,)).fetchone()[0])
print("نماد در روز", D0, "(باس‌لاین):", B.execute(
    "SELECT COUNT(DISTINCT ins_code) FROM daily_prices WHERE substr(d_even,1,8)=?", (D0,)).fetchone()[0])
for lbl, c in (("LOCAL", L), ("BASE", B)):
    cols = [k[1] for k in c.execute("PRAGMA table_info(daily_prices)").fetchall()]
    probe = [x for x in ("last", "value", "close", "open") if x in cols]
    sel = ", ".join("COUNT(%s)" % x for x in probe)
    n = c.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
    print(lbl, "ردیف =", n, "| ستون‌ها:", cols)
    print("   پرشدگی", dict(zip(probe, c.execute("SELECT " + sel + " FROM daily_prices").fetchone())))
L.close(); B.close(); os.remove(tmp)
