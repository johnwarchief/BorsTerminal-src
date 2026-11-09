"""Phase 4.9 — field-level diff: Go borsd /api/chart-db vs Python /api/chart-db.

Both sides read byte-identical DB copies and the same correction pack
(ra365-r32b-v2, authoritative). Reports candle-level OHLCV/closing diffs,
factor-series diffs, adjustEvents/adjustRejected diffs and adjustCapability
deltas to evidence/api-python-vs-go-parity.json.
"""
import json
import os

CONT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(CONT, "evidence")

PAIRS = {
    "فولاد": (os.path.join(EV, "api-go-foulad-fresh.json"),
             os.path.join(EV, "api-python-authoritative", "فولاد.json")),
    "وسکاب": (os.path.join(EV, "api-go-voskab-fresh.json"),
             os.path.join(EV, "api-python-authoritative", "وسکاب.json")),
}

CANDLE_FIELDS = ["open", "high", "low", "close", "closing", "volume",
                 "high_raw", "low_raw"]


def by_date(rows):
    out = {}
    for r in rows or []:
        d = str(r.get("date") or r.get("time") or "")[:10]
        if d:
            out[d] = r
    return out


def num_eq(a, b, tol=1e-9):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    except (TypeError, ValueError):
        return a == b


def event_sig(ev):
    return (str(ev.get("date"))[:10], ev.get("ratio"), ev.get("source"),
            ev.get("kind"), ev.get("correction_version"))


def rejected_sig(ev):
    return (str(ev.get("date"))[:10], ev.get("ratio"), ev.get("factor_status"),
            ev.get("correction_version"))


def diff_symbol(sym, go_path, py_path):
    go = json.load(open(go_path, encoding="utf-8"))
    py = json.load(open(py_path, encoding="utf-8"))
    rep = {"symbol": sym}

    gc, pc = by_date(go.get("candles")), by_date(py.get("candles"))
    rep["go_candles"] = len(gc)
    rep["py_candles"] = len(pc)
    rep["dates_only_go"] = sorted(set(gc) - set(pc))[:10]
    rep["dates_only_py"] = sorted(set(pc) - set(gc))[:10]
    field_diffs = {}
    max_abs = {}
    for f in CANDLE_FIELDS:
        n = 0
        mx = 0.0
        examples = []
        for d in sorted(set(gc) & set(pc)):
            a, b = gc[d].get(f), pc[d].get(f)
            if not num_eq(a, b):
                n += 1
                try:
                    mx = max(mx, abs(float(a) - float(b)))
                except (TypeError, ValueError):
                    pass
                if len(examples) < 5:
                    examples.append({"date": d, "go": a, "py": b})
        if n:
            field_diffs[f] = {"count": n, "max_abs": mx, "examples": examples}
            max_abs[f] = mx
    rep["candle_field_diffs"] = field_diffs

    gf, pf = by_date(go.get("factors")), by_date(py.get("factors"))
    fd = 0
    fmx = 0.0
    fex = []
    for d in sorted(set(gf) & set(pf)):
        a, b = gf[d].get("factor"), pf[d].get("factor")
        if not num_eq(a, b, 1e-12):
            fd += 1
            try:
                fmx = max(fmx, abs(float(a) - float(b)))
            except (TypeError, ValueError):
                pass
            if len(fex) < 5:
                fex.append({"date": d, "go": a, "py": b})
    rep["factor_days_go"] = len(gf)
    rep["factor_days_py"] = len(pf)
    rep["factor_diffs"] = fd
    rep["factor_max_abs"] = fmx
    rep["factor_examples"] = fex

    ge = [event_sig(e) for e in go.get("adjustEvents") or []]
    pe = [event_sig(e) for e in py.get("adjustEvents") or []]
    rep["events_go"] = len(ge)
    rep["events_py"] = len(pe)
    rep["events_equal"] = ge == pe
    if ge != pe:
        rep["events_only_go"] = [list(x) for x in ge if x not in pe]
        rep["events_only_py"] = [list(x) for x in pe if x not in ge]

    gr = sorted([rejected_sig(e) for e in go.get("adjustRejected") or []],
                key=lambda x: (x[0], str(x[1]), str(x[2])))
    pr = sorted([rejected_sig(e) for e in py.get("adjustRejected") or []],
                key=lambda x: (x[0], str(x[1]), str(x[2])))
    rep["rejected_go"] = len(gr)
    rep["rejected_py"] = len(pr)
    rep["rejected_equal"] = gr == pr
    if gr != pr:
        rep["rejected_only_go"] = [list(x) for x in gr if x not in pr][:10]
        rep["rejected_only_py"] = [list(x) for x in pr if x not in gr][:10]

    gcap = (go.get("adjustCapability") or {}).get("corrections") or {}
    pcap = (py.get("adjustCapability") or {}).get("corrections") or {}
    cap_delta = {k: {"go": gcap.get(k), "py": pcap.get(k)}
                 for k in sorted(set(gcap) | set(pcap))
                 if gcap.get(k) != pcap.get(k)}
    rep["cap_delta"] = cap_delta

    rep["last_go"] = go.get("candles", [{}])[-1] if go.get("candles") else None
    rep["last_py"] = py.get("candles", [{}])[-1] if py.get("candles") else None
    return rep


report = {s: diff_symbol(s, gp, pp) for s, (gp, pp) in PAIRS.items()}
out = os.path.join(EV, "api-python-vs-go-parity.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
