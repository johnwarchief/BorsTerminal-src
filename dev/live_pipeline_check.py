import json, urllib.request, collections
B = "http://127.0.0.1:8012"
s = json.loads(urllib.request.urlopen(B + "/api/screener", timeout=300).read().decode("utf-8"))
rows = s.get("data") or []
print("total symbols:", len(rows))
exc = [r for r in rows if r.get("excluded")]
print("excluded:", len(exc), "| eligible:", len(rows) - len(exc))
# reasons breakdown
reasons = collections.Counter()
for r in rows:
    rs = (r.get("exclusion_reasons") or "").strip()
    if rs:
        for part in [p.strip() for p in rs.split("·") if p.strip()]:
            reasons[part] += 1
print("\ntop exclusion reasons:")
for k, v in reasons.most_common(10):
    print("  %4d  %s" % (v, k))
# score distribution
sc = collections.Counter(r.get("score") for r in rows)
print("\nscore distribution:", dict(sorted(sc.items(), key=lambda x: (x[0] is None, x[0]))))
wl = [r for r in rows if r.get("watchlist")]
print("\nwatchlist size:", len(wl))
print("top 10 watchlist:")
for r in sorted(wl, key=lambda x: -(x.get("score") or 0))[:10]:
    print("  ", r.get("symbol"), "| score:", r.get("score"), "| gap:", r.get("eps_data_gap"),
          "| rev_growth:", r.get("rev_growth"))
