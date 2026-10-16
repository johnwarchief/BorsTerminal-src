"""Probe public TSETMC CDN endpoints for per-symbol assembly (مجمع) data.

Evidence-only tool: every HTTP call is recorded with url/status/bytes/sha256 and
a <=400-byte trimmed body sample into _audit/tsetmc_assembly_probe_evidence.json.
Request style copied from tools/tse_live_filter_parity.py (session, headers, _pt).

Run: PYTHONIOENCODING=utf-8 python _audit/tsetmc_assembly_probe.py
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
    "Accept": "application/json",
}

SYMBOLS = [
    ("فولاد", "46348559193224090", "large manufacturer"),
    ("ذوب", "71483646978964608", "large manufacturer"),
    ("وبملت", "778253364357513", "bank"),
    ("وساپا", "37614886280396031", "investment company"),
    ("ثروت", "27812005859539773", "ETF (صندوق قابل معامله)"),
    ("قاروم", "10831074117626896", "zero-volume/suspension-state row"),
    ("شتران", "51617145873056483", "refiner (other)"),
    ("خودرو", "65883838195688438", "auto (other)"),
]

CANDIDATE_KEYS = [
    "navmIC", "statTakeh", "isManager", "memo", "dPS", "prevNext", "farDiv",
    "divCash", "shareHolderMeetingDate", "shareHolderMeetingDecisionDate",
    "maxam", "lMaxam", "cMaxam", "devidDate",
]

EVIDENCE = {"generated": None, "calls": [], "notes": []}


def pt():
    return str(int(time.time() * 1000))


def call(name, url, params=None):
    """One GET; record status/bytes/sha256/<=400B trimmed sample; return (json|None, resp)."""
    full = url
    if params:
        full = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    rec = {"task": name, "url": full, "params": params or {}, "ts": datetime.now().isoformat(timespec="seconds")}
    try:
        r = requests.get(full, headers=HEADERS, timeout=60)
        body = r.content
        rec["status"] = r.status_code
        rec["bytes"] = len(body)
        rec["sha256"] = hashlib.sha256(body).hexdigest()
        rec["sample_body_400b"] = body[:400].decode("utf-8", "replace")
        data = None
        try:
            data = r.json()
        except Exception as e:  # noqa: BLE001
            rec["json_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        EVIDENCE["calls"].append(rec)
        return data, rec
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        EVIDENCE["calls"].append(rec)
        return None, rec


def nonempty(v):
    return v not in (None, "", 0, "0", "0000-00-00 00:00:00", "0000-00-00", "null", "NaN", [])


def walk_keys(obj, prefix=""):
    """Flatten dict/list JSON to dotted key paths (lists sampled at [0])."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}{k}"
            if isinstance(v, dict):
                out.update(walk_keys(v, p + "."))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out[p + ".[0]"] = f"<list len {len(v)}>"
                out.update(walk_keys(v[0], p + ".[0]."))
            else:
                out[p] = v
    return out


def task1_is_instrument():
    print("== TASK 1: Instrument/IsInstrument (+ real per-instrument endpoints) ==")
    out = {}
    all_keys = set()
    for sym, code, kind in SYMBOLS:
        data, rec = call("t1_IsInstrument", f"{BASE}/Instrument/IsInstrument",
                         {"insCode": code, "_pt": pt()})
        entry = {"status": rec.get("status"), "bytes": rec.get("bytes"), "error": rec.get("error")}
        if data is None:
            print(f"  {sym}: IsInstrument status={rec.get('status')} err={rec.get('error')} -> no JSON")
            # fall through to the site's own instrument endpoint for the key dump
        else:
            top = list(data.keys()) if isinstance(data, dict) else [f"<{type(data).__name__}>"]
            all_keys.update(top)
            entry.update({"top_keys": top,
                          "candidate_values": {k: data[k] for k in CANDIDATE_KEYS if k in data}})
            print(f"  {sym}: IsInstrument status={rec['status']} bytes={rec['bytes']} top_keys={top}")
        time.sleep(1.0)
        # Real endpoint used by the site's instrument page (route list scraped from
        # cdn.tsetmc.com's own JS bundle in a prior session; re-verified live here).
        d2, r2 = call("t1_GetInstrumentInfo", f"{BASE}/Instrument/GetInstrumentInfo",
                      {"instrument": code, "_pt": pt()})
        if isinstance(d2, dict):
            flat = walk_keys(d2)
            entry["GetInstrumentInfo_status"] = r2["status"]
            entry["GetInstrumentInfo_flat_keys"] = sorted(flat.keys())
            entry["GetInstrumentInfo_values"] = {k: v for k, v in flat.items() if any(
                h in k.lower() for h in ("maxam", "meet", "div", "dps", "navm", "statakeh",
                                          "manager", "memo", "council", "board", "hemayat", "saham"))}
            print(f"  {sym}: GetInstrumentInfo status={r2['status']} bytes={r2['bytes']}")
            print(f"     assembly-hint values: {json.dumps(entry['GetInstrumentInfo_values'], ensure_ascii=False)[:500]}")
        else:
            entry["GetInstrumentInfo_status"] = r2.get("status")
            entry["GetInstrumentInfo_error"] = r2.get("error")
            print(f"  {sym}: GetInstrumentInfo status={r2.get('status')} err={r2.get('error')}")
        time.sleep(1.0)
        d3, r3 = call("t1_GetInstrumentState", f"{BASE}/MarketData/GetInstrumentState",
                      {"insCode": code, "_pt": pt()})
        if isinstance(d3, dict):
            entry["GetInstrumentState_status"] = r3["status"]
            entry["GetInstrumentState_values"] = {k: v for k, v in walk_keys(d3).items() if any(
                h in k.lower() for h in ("maxam", "meet", "div", "dps", "navm", "statakeh", "memo"))}
            print(f"  {sym}: GetInstrumentState status={r3['status']} "
                  f"hints={json.dumps(entry['GetInstrumentState_values'], ensure_ascii=False)[:300]}")
        time.sleep(1.0)
        out[sym] = entry
    EVIDENCE["task1"] = {"union_of_top_keys": sorted(all_keys), "per_symbol": out,
                         "candidates_present_in_IsInstrument": sorted(k for k in CANDIDATE_KEYS if k in all_keys),
                         "IsInstrument_note": "IsInstrument status per symbol recorded; see per_symbol"}


def task1b_calendar_msg():
    """Assembly-carrying candidates: instrument calendar + TSETMC msg feed (announcement)."""
    print("== TASK 1b: GetInstrumentCalendar / Msg / ShareChange ==")
    out = {}
    for sym, code, _ in SYMBOLS[:8]:
        entry = {}
        d, r = call("t1b_Calendar", f"{BASE}/ClosingPrice/GetInstrumentCalendar",
                    {"insCode": code, "fromDate": "20250101", "_pt": pt()})
        entry["calendar"] = {"status": r.get("status"), "bytes": r.get("bytes"),
                             "sample": json.dumps(d, ensure_ascii=False)[:350] if d is not None else None}
        print(f"  {sym} calendar: {entry['calendar']['status']} {entry['calendar']['bytes']}b "
              f"{(entry['calendar']['sample'] or '')[:150]}")
        time.sleep(1.0)
        d, r = call("t1b_MsgByInsCode", f"{BASE}/Msg/GetMsgByInsCode",
                    {"insCode": code, "rows": "50", "_pt": pt()})
        blob = json.dumps(d, ensure_ascii=False) if d is not None else ""
        entry["msg"] = {"status": r.get("status"), "bytes": r.get("bytes"),
                        "assembly_hits": blob.count("مجمع"), "sample": blob[:350] or None}
        print(f"  {sym} msg: {entry['msg']['status']} {entry['msg']['bytes']}b 'مجمع'x{entry['msg']['assembly_hits']}")
        time.sleep(1.0)
        d, r = call("t1b_ShareChange", f"{BASE}/Instrument/GetInstrumentShareChange",
                    {"instrument": code, "_pt": pt()})
        entry["shareChange"] = {"status": r.get("status"), "bytes": r.get("bytes"),
                                "sample": json.dumps(d, ensure_ascii=False)[:250] if d is not None else None}
        print(f"  {sym} shareChange: {entry['shareChange']['status']} {entry['shareChange']['bytes']}b")
        time.sleep(1.0)
        out[sym] = entry
    EVIDENCE["task1b"] = out


def task2_market_watch():
    print("== TASK 2: ClosingPrice/GetMarketWatch ==")
    data, rec = call("t2_marketwatch", f"{BASE}/ClosingPrice/GetMarketWatch",
                     {"market": "0", "showTraded": "false", "withBestLimits": "true", "_pt": pt()})
    if not isinstance(data, dict):
        EVIDENCE["task2"] = {"error": f"not dict, status={rec.get('status')}", "sample": rec.get("sample_body_400b")}
        print("  unexpected shape:", rec.get("status"), rec.get("error"))
        return
    rows = None
    for k, v in data.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            rows = v
            EVIDENCE["task2"] = {"wrapper_key": k, "rows": len(rows)}
            break
    if rows is None:
        EVIDENCE["task2"] = {"error": "no list-of-dicts", "top_keys": list(data.keys())}
        print("  no rows; top keys:", list(data.keys()))
        return
    all_keys = sorted({k for r in rows for k in r.keys()})
    freq = {}
    for key in all_keys:
        n = sum(1 for r in rows if nonempty(r.get(key)))
        freq[key] = n
    assembly_related = {k: v for k, v in freq.items() if any(
        h in k.lower() for h in ("maxam", "meet", "div", "dps", "navm", "statakeh", "manager", "memo"))}
    EVIDENCE["task2"]["row_keys"] = all_keys
    EVIDENCE["task2"]["nonempty_freq"] = freq
    EVIDENCE["task2"]["assembly_candidates"] = assembly_related
    EVIDENCE["task2"]["sample_row"] = rows[0]
    print(f"  rows={len(rows)} wrapper={data.keys()}")
    print("  row keys:", all_keys)
    print("  assembly-candidate nonempty counts:", json.dumps(assembly_related, ensure_ascii=False))
    # how do our 8 symbols appear?
    code_set = {c for _, c, _ in SYMBOLS}
    for r in rows:
        if r.get("insCode") in code_set:
            EVIDENCE["task2"].setdefault("our_symbols", {})[r.get("lva") or r.get("insCode")] = {
                k: r.get(k) for k in r.keys() if any(
                    h in k.lower() for h in ("maxam", "meet", "div", "dps", "navm", "statakeh", "memo"))}
    print("  our-symbol candidate fields:", json.dumps(EVIDENCE["task2"].get("our_symbols"), ensure_ascii=False)[:800])


def task3_candidates():
    print("== TASK 3: candidate endpoints ==")
    sym, code, _ = SYMBOLS[0]  # فولاد
    targets = [
        ("t3_InstrumentInfo", f"{BASE}/Instrument/InstrumentInfo", {"instrument": code}),
        ("t3_InstrumentInfoFull", f"{BASE}/Instrument/InstrumentInfoFull", {"instrument": code}),
        ("t3_Dash_GetInstrumentInfo", f"{BASE}/Dashboard/GetInstrumentInfo", {"instrument": code}),
        ("t3_Dash_DivDatesByInsCode", f"{BASE}/Dashboard/GetDividendDatesByInsCode", {"insCode": code}),
        ("t3_Dash_DivDatesBySymbol", f"{BASE}/Dashboard/GetDividendDatesBySymbol", {"symbol": sym}),
        ("t3_News_ByInstrument", f"{BASE}/News/GetNewsByInstrument", {"instrument": code, "rows": "20"}),
        ("t3_Karbasta_ByInstrument", f"{BASE}/Karbasta/GetByInstrument", {"instrument": code}),
        ("t3_Meeting_GetMeetings", f"{BASE}/Meeting/GetMeetings", None),
        ("t3_Council_GetDecisions", f"{BASE}/Council/GetDecisions", None),
        ("t3_Announcement_ByInstrument", f"{BASE}/Announcement/GetByInstrument", {"instrument": code}),
    ]
    results = []
    for name, url, params in targets:
        p = dict(params or {})
        p["_pt"] = pt()
        data, rec = call(name, url, p)
        shape = None
        assembly = False
        if isinstance(data, dict):
            shape = {"type": "dict", "top_keys": list(data.keys())[:40]}
            blob = json.dumps(data, ensure_ascii=False).lower()
            assembly = any(h in blob for h in ("maxam", "meeting", "مجمع"))
        elif isinstance(data, list):
            shape = {"type": "list", "len": len(data)}
            blob = json.dumps(data, ensure_ascii=False).lower()
            assembly = any(h in blob for h in ("maxam", "meeting", "مجمع"))
        entry = {"endpoint": url.replace(BASE + "/", ""), "status": rec.get("status"),
                 "bytes": rec.get("bytes"), "error": rec.get("error"),
                 "shape": shape, "has_assembly_content": assembly}
        results.append(entry)
        print(f"  {entry['endpoint']}: status={entry['status']} bytes={entry['bytes']} "
              f"err={entry.get('error')} assembly_content={assembly}")
        if isinstance(data, dict):
            entry["sample_json_top"] = {k: (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__} len {len(v)}>")
                                        for k, v in list(data.items())[:15]}
        time.sleep(1.2)
    EVIDENCE["task3"] = {"instrument_used": sym, "results": results}


def task5_rate(endpoint_key):
    print("== TASK 5: rate behaviour (10 rapid GETs, no sleep) ==")
    sym, code, _ = SYMBOLS[0]
    timings = []
    for i in range(10):
        t0 = time.perf_counter()
        if endpoint_key == "IsInstrument":
            url = f"{BASE}/Instrument/IsInstrument?insCode={code}&_pt={pt()}"
        elif endpoint_key == "GetInstrumentInfo":
            url = f"{BASE}/Instrument/GetInstrumentInfo?instrument={code}&_pt={pt()}"
        else:
            url = f"{BASE}/ClosingPrice/GetMarketWatch?market=0&showTraded=false&withBestLimits=true&_pt={pt()}"
        r = None
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            ms = round((time.perf_counter() - t0) * 1000)
            item = {"call": i + 1, "status": r.status_code, "ms": ms, "bytes": len(r.content)}
        except Exception as e:  # noqa: BLE001
            ms = round((time.perf_counter() - t0) * 1000)
            item = {"call": i + 1, "status": None, "ms": ms, "error": f"{type(e).__name__}: {str(e)[:150]}"}
        timings.append(item)
        print(f"  call {item['call']}: status={item['status']} ms={item['ms']} bytes={item.get('bytes')}")
    EVIDENCE["task5"] = {"endpoint": endpoint_key, "sequential_no_sleep": True, "timings": timings}
    return timings


def main():
    EVIDENCE["generated"] = datetime.now().isoformat(timespec="seconds")
    EVIDENCE["base"] = BASE
    EVIDENCE["symbols"] = [{"symbol": s, "ins_code": c, "role": k} for s, c, k in SYMBOLS]
    task1_is_instrument()
    task1b_calendar_msg()
    task2_market_watch()
    task3_candidates()
    # best working per-instrument endpoint (one that returned 200 with a JSON object)
    gi = [e.get("GetInstrumentInfo_status") for e in EVIDENCE["task1"]["per_symbol"].values()]
    best = "GetInstrumentInfo" if 200 in gi else "GetMarketWatch"
    timings = task5_rate(best)
    codes = [t["status"] for t in timings]
    EVIDENCE["task5"]["first_block_call"] = next((t["call"] for t in timings if t["status"] in (403, 429)), None)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tsetmc_assembly_probe_evidence.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(EVIDENCE, fh, ensure_ascii=False, indent=1)
    print("wrote", out)
    print("statuses:", codes)


if __name__ == "__main__":
    main()
