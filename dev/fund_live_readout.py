"""Read the app's own fundamental numbers for a set of symbols (live API, no shell encoding traps)."""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8001"
SYMS = sys.argv[1:] or []

if not SYMS:
    # take a spread from the screener: highest and lowest scoring, plus a fund
    with urllib.request.urlopen(BASE + "/api/fundamental/screen?limit=400", timeout=90) as r:
        rows = json.load(r).get("rows") or json.load(r).get("data") or []
    print("screen rows:", len(rows))
    sys.exit(0)


def g(d, *path, default=None):
    for p in path:
        if isinstance(d, dict):
            d = d.get(p)
        else:
            return default
    return d if d is not None else default


for s in SYMS:
    url = BASE + "/api/fundamental/" + urllib.parse.quote(s)
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            d = json.load(r)
    except Exception as e:
        print("%-8s ERROR %s" % (s, e))
        continue
    ind = d.get("indicators") or {}
    i1, i2, i3, i4 = (ind.get("1") or {}), (ind.get("2") or {}), (ind.get("3") or {}), (ind.get("4") or {})
    print("=" * 78)
    print("symbol        :", d.get("symbol"), "|", d.get("name"))
    print("score         :", d.get("score"), "of", g(d, "methodology", "max_score", default="?"))
    print("passes        :", json.dumps(d.get("passes"), ensure_ascii=False))
    print("I1 revenue    :", g(i1, "monetary", "revenue_bt"), "bt | period", g(i1, "monetary", "period"))
    print("I1 basis      :", g(i1, "monetary", "revenue_basis"))
    print("I2 eps        :", json.dumps({k: v for k, v in i2.items() if not isinstance(v, (dict, list))}, ensure_ascii=False)[:300])
    print("I3 margin     :", g(i3, "margin_pct"), "% | gp", g(i3, "gross_profit_bt"), "| rev", g(i3, "revenue_bt"))
    print("I3 basis      :", g(i3, "basis"))
    print("I4 sales/mcap :", json.dumps({k: v for k, v in i4.items() if not isinstance(v, (dict, list))}, ensure_ascii=False)[:300])
