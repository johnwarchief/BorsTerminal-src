"""چپ‌چینِ ردیف‌هایی که کلیدواژه‌هایِ اوراق/کالا از سطلِ سهام بیرون می‌برند."""
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mstat_engine as ME

db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                  "BorsTerminal Ultimate", "market.db")
c = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
c.row_factory = sqlite3.Row
rows, meta = ME.enrich(c)

KW = ("صكوك", "صکوك", "مشاركت", "مشارکت", "سلف", "مرابحه", "آتی", "اتی", "گواحي",
      "گواهی", "اوراق", "اسناد", "اجاره", "استصناع", "مضاربه", "سفت", "ذخیره")
def hit(name, keys=KW):
    n = ME._norm(name)
    return any(ME._word_hit(n, ME._norm(k)) for k in keys)

from collections import defaultdict
grp = defaultdict(lambda: [0, 0.0])
for r in rows:
    nm = ME._norm((r.get("name") or "") + " " + (r.get("symbol") or ""))
    if not hit(nm):
        continue
    k = (r["cls"], r["kind"])
    grp[k][0] += 1
    grp[k][1] += (r["_m"].get("val") or 0) / 1e10
print("نشانه‌دارها per (cls, kind):")
for k in sorted(grp, key=lambda x: -grp[x][1]):
    print("  %-16s n=%-5d val=%10.1f م.ت" % ("%s/%s" % k, grp[k][0], grp[k][1]))

print("\nنمونه‌هایِ سهامی که نشانه می‌گیرند (باید صفر یا بی‌نامربوط باشد):")
n = 0
for r in rows:
    if r["cls"] != "stock":
        continue
    nm = ME._norm((r.get("name") or "") + " " + (r.get("symbol") or ""))
    if hit(nm):
        which = [k for k in KW if ME._word_hit(nm, ME._norm(k))]
        print("  %-10s %-46s %-30s val=%8.1f" % (r.get("symbol"), (r.get("name") or "")[:46],
                                                 ",".join(which)[:30], (r["_m"].get("val") or 0)/1e10))
        n += 1
        if n > 30:
            break
print("جمعِ نمایش‌داده‌شده:", n)
c.close()
