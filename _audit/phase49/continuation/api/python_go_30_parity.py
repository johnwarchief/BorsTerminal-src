"""Phase 4.9 — 30-symbol Python vs Go chain parity per correction mode.

For each symbol in the Go evidence directory (fetched from live borsd), run the
same Python /api/chart-db function with BORS_DB pointing at the isolated DB copy
and BORS_CORRECTIONS_DIR at the given pack, then compare:

  count, factors (per date), adjustEvents, adjustRejected (incl. dedupe
  evidence), and the corrections capability block.

Usage:
  python_go_30_parity.py --pack <dir> --evidence api-overlay-dedup --label overlay
"""
import argparse
import gzip
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", ".."))
CONT = os.path.join(ROOT, "_audit", "phase49", "continuation")
EVID = os.path.join(CONT, "evidence")


def event_sig(ev):
    return (str(ev.get("date"))[:10], ev.get("ratio"), ev.get("source"))


def rejected_sig(ev):
    dedupe = ev.get("dedupe") or {}
    return (str(ev.get("date"))[:10], ev.get("ratio"), ev.get("factor_status"),
            ev.get("correction_version"),
            (str(dedupe.get("pack_date"))[:10], dedupe.get("delta_days"))
            if dedupe else None)


def factors_map(rows):
    out = {}
    for r in rows or []:
        d = str(r.get("time") or r.get("date") or "")[:10]
        if d:
            out[d] = r.get("factor")
    return out


def compare(ap, gp):
    rep = {"symbol": ap.get("symbol") or gp.get("symbol")}
    gc, pc = gp.get("count"), ap.get("count")
    rep["count_go"], rep["count_py"] = gc, len(ap.get("candles") or [])
    rep["count_equal"] = gc == rep["count_py"]

    gf, pf = factors_map(gp.get("factors")), factors_map(ap.get("factors"))
    rep["factor_days_go"], rep["factor_days_py"] = len(gf), len(pf)
    rep["dates_only_go"] = sorted(set(gf) - set(pf))[:5]
    rep["dates_only_py"] = sorted(set(pf) - set(gf))[:5]
    fd, fmx, fex = 0, 0.0, []
    for d in set(gf) & set(pf):
        a, b = gf[d], pf[d]
        if a is None or b is None or abs(float(a) - float(b)) > 1e-12:
            fd += 1
            try:
                fmx = max(fmx, abs(float(a) - float(b)))
            except (TypeError, ValueError):
                pass
            if len(fex) < 3:
                fex.append({"date": d, "go": a, "py": b})
    rep["factor_diffs"], rep["factor_max_abs"], rep["factor_examples"] = fd, fmx, fex

    ge = [event_sig(e) for e in gp.get("adjustEvents") or []]
    pe = [event_sig(e) for e in ap.get("adjustEvents") or []]
    rep["events_go"], rep["events_py"], rep["events_equal"] = len(ge), len(pe), ge == pe
    if ge != pe:
        rep["events_only_go"] = [list(x) for x in ge if x not in pe]
        rep["events_only_py"] = [list(x) for x in pe if x not in ge]

    gr = sorted([rejected_sig(e) for e in gp.get("adjustRejected") or []],
                key=lambda x: (x[0], str(x[1]), str(x[2])))
    pr = sorted([rejected_sig(e) for e in ap.get("adjustRejected") or []],
                key=lambda x: (x[0], str(x[1]), str(x[2])))
    rep["rejected_go"], rep["rejected_py"], rep["rejected_equal"] = len(gr), len(pr), gr == pr
    if gr != pr:
        rep["rejected_only_go"] = [list(x) for x in gr if x not in pr][:5]
        rep["rejected_only_py"] = [list(x) for x in pr if x not in gr][:5]

    gcap = (gp.get("adjustCapability") or {}).get("corrections") or {}
    pcap = (ap.get("adjustCapability") or {}).get("corrections") or {}
    keys = ("mode", "covered", "replace_steps", "suppress_steps", "raw_fields",
            "version", "as_of")
    rep["cap_delta"] = {k: {"go": gcap.get(k), "py": pcap.get(k)}
                        for k in keys if gcap.get(k) != pcap.get(k)}
    rep["ok"] = (rep["count_equal"] and fd == 0 and not rep["dates_only_go"]
                 and not rep["dates_only_py"] and rep["events_equal"]
                 and rep["rejected_equal"] and not rep["cap_delta"])
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--symbols", default="")
    args = ap.parse_args()

    os.environ["BORS_DB"] = os.path.join(CONT, "api", "python", "market.db")
    os.environ["BORS_CORRECTIONS_DIR"] = args.pack
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    sys.path.insert(0, ROOT)
    import api.chart as C  # noqa: E402

    syms = [s for s in args.symbols.split(",") if s]
    if not syms:
        idx = json.load(open(os.path.join(EVID, args.evidence, "_index.json"),
                             encoding="utf-8"))
        syms = [r["symbol"] for r in idx]

    out = []
    for i, sym in enumerate(syms, 1):
        gp = json.load(gzip.open(os.path.join(EVID, args.evidence, sym + ".json.gz"),
                                 "rt", encoding="utf-8"))
        try:
            api_res = C.get_chart_db_visible(sym)
            rep = compare(api_res, gp)
        except Exception as e:
            rep = {"symbol": sym, "ok": False, "error": repr(e)}
        rep["symbol"] = sym
        out.append(rep)
        print("[%d/%d] %s ok=%s factors=%d/%d events=%d/%d rejected=%d/%d cap_delta=%s"
              % (i, len(syms), sym, rep.get("ok"),
                 rep.get("factor_days_py", -1), rep.get("factor_days_go", -1),
                 rep.get("events_py", -1), rep.get("events_go", -1),
                 rep.get("rejected_py", -1), rep.get("rejected_go", -1),
                 rep.get("cap_delta")), flush=True)

    summary = {
        "label": args.label,
        "pack": os.path.relpath(args.pack, ROOT).replace("\\", "/"),
        "evidence": "evidence/" + args.evidence,
        "symbols": len(out),
        "ok": sum(1 for r in out if r.get("ok")),
        "failed": [r["symbol"] for r in out if not r.get("ok")],
        "per_symbol": out,
    }
    fn = os.path.join(EVID, "api-python-go-30-parity-%s.json" % args.label)
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("SUMMARY %s: %d/%d ok -> %s" % (args.label, summary["ok"], summary["symbols"], fn))


if __name__ == "__main__":
    main()
