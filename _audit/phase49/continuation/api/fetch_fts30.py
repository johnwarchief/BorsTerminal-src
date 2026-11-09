"""Phase 4.9 — FTS (daily/weekly/monthly) check for the 30 Phase 4.8 symbols.

Read-only GETs against the live Go borsd on the restored Work DB; trims each
response to status/bars/trend D-W-M and writes evidence/api-go-fts-30.json.
The local API token is read from the sandbox runtime and never written out.
"""
import json
import os
import urllib.parse
import urllib.request

CONT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = open(os.path.join(CONT, "api", "sandbox", "oc", "runtime", "api_token"),
             encoding="ascii").read().strip()
BASE = "http://127.0.0.1:8159"


def get(path):
    req = urllib.request.Request(BASE + path,
                                 headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    import csv
    with open(os.path.join(CONT, "symbols30.csv"), encoding="utf-8-sig") as f:
        syms = [r["symbol"] for r in csv.DictReader(f) if r["symbol"]]
    rows = []
    for s in syms:
        try:
            d = get("/api/fts/" + urllib.parse.quote(s, safe=""))
            tr = ((d.get("fts") or {}).get("trend") or {})
            st = (d.get("fts") or {}).get("status") or {}
            rows.append({
                "symbol": s, "status": d.get("status"),
                "bars": d.get("bars"), "basis": d.get("analysis_basis"),
                "d_trend": (tr.get("D") or {}).get("trend"),
                "w_trend": (tr.get("W") or {}).get("trend"),
                "m_trend": (tr.get("M") or {}).get("trend"),
                "w_last": (tr.get("W") or {}).get("last_high_time"),
                "m_last": (tr.get("M") or {}).get("last_high_time"),
                "code": st.get("code"),
                "error": None,
            })
        except Exception as e:
            rows.append({"symbol": s, "status": "error", "error": repr(e)})
        print("[%d/%d] %s %s" % (len(rows), len(syms), s, rows[-1].get("status")),
              flush=True)
    ok = [r for r in rows if r.get("status") == "success"]
    rep = {
        "symbols": len(rows),
        "success": len(ok),
        "with_weekly": sum(1 for r in ok if r.get("w_trend")),
        "with_monthly": sum(1 for r in ok if r.get("m_trend")),
        "failed": [r["symbol"] for r in rows if r.get("status") != "success"],
        "per_symbol": rows,
    }
    out = os.path.join(CONT, "evidence", "api-go-fts-30.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("SUMMARY success=%d/%d weekly=%d monthly=%d -> %s"
          % (rep["success"], rep["symbols"], rep["with_weekly"],
             rep["with_monthly"], out))


if __name__ == "__main__":
    main()
