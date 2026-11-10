#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage E: upgrade/merge + restart/idempotency product tests on isolated copies."""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, "_audit", "phase49-finalization", "borsd_final.exe")
SEED_DB = os.path.join(ROOT, "_audit", "phase49-finalization", "seed", "market.db")
SEED_GZ = SEED_DB + ".gz"
PACK = os.path.join(ROOT, "_audit", "phase49-finalization", "packs", "rebuild-full-v2")
BASE = os.path.join(ROOT, "_audit", "phase49-finalization", "product-test")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "product-test-report.json")


def api(port, path, token):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path),
                                 headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def wait(port, data_dir, timeout=300):
    tokf = os.path.join(data_dir, "oc", "runtime", "api_token")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(tokf):
            tok = open(tokf, encoding="ascii").read().strip()
            try:
                p = api(port, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
                if p.get("status") == "success":
                    return tok, p
            except Exception:
                pass
        time.sleep(2)
    raise RuntimeError("server not ready")


def start(data_dir, port):
    env = dict(os.environ)
    env["BORS_CORRECTIONS_DIR"] = PACK
    log = open(os.path.join(BASE, "server-%d.log" % port), "ab")
    proc = subprocess.Popen([BIN, "--port", str(port), "--db-dir", data_dir,
                             "--no-shell", "--no-loops", "--server-only"],
                            env=env, stdout=log, stderr=subprocess.STDOUT)
    tok, first = wait(port, data_dir)
    return proc, tok, first


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    up = os.path.join(BASE, "upgrade")
    if os.path.isdir(up):
        shutil.rmtree(up)
    os.makedirs(up)
    shutil.copy2(SEED_DB, os.path.join(up, "market.db"))
    con = sqlite3.connect(os.path.join(up, "market.db"))
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("DELETE FROM price_history WHERE NOT (symbol='فولاد' AND date>='2026-10-20') "
                "AND NOT (symbol='شبندر' AND date>='2026-10-20')")
    for t in ("adjust_events", "adjust_verdict", "price_adjust_events",
              "share_change_events", "instruments", "raw_history_corrections",
              "history_validity", "adjust_pack_state", "seed_manifest"):
        con.execute("DELETE FROM %s" % t)
    con.execute("UPDATE price_history SET close=close+7 WHERE symbol='فولاد' "
                "AND date=(SELECT MAX(date) FROM price_history WHERE symbol='فولاد')")
    mod = con.execute("SELECT date,close FROM price_history WHERE symbol='فولاد' "
                      "ORDER BY date DESC LIMIT 1").fetchone()
    con.execute("INSERT INTO user_watchlists VALUES "
                "('فولاد','فولاد','یادداشت','تست','2026-11-10T00:00:00Z')")
    con.commit()
    before_rows = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    con.close()
    shutil.copy2(SEED_GZ, os.path.join(up, "market.db.gz"))
    rep = {"before_rows": before_rows, "modified_row": mod}
    proc, tok, p1 = start(up, 8171)
    try:
        con = sqlite3.connect(os.path.join(up, "market.db"))
        rows1 = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        ae1 = con.execute("SELECT COUNT(*) FROM adjust_events").fetchone()[0]
        keep = con.execute("SELECT close FROM price_history WHERE symbol='فولاد' AND date=?",
                           (mod[0],)).fetchone()
        watch = con.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0]
        prov = con.execute("SELECT COUNT(*) FROM raw_history_corrections").fetchone()[0]
        val = con.execute("SELECT COUNT(*) FROM history_validity").fetchone()[0]
        dup = con.execute("SELECT COUNT(*) FROM (SELECT symbol,date,COUNT(*) c "
                          "FROM price_history GROUP BY symbol,date HAVING c>1)").fetchone()[0]
        con.close()
        state1 = json.load(open(os.path.join(up, "market_seed.json"), encoding="utf-8"))
        ma = api(8171, "/api/ma/" + urllib.parse.quote("فولاد", safe="") + "?days=5000", tok)
        ma_lens = {k: len(v) for k, v in (ma.get("ma") or {}).items() if isinstance(v, list)}
        rep.update({
            "mode": state1.get("mode"), "state_status": state1.get("status"),
            "rows_after": rows1, "adjust_events": ae1,
            "modified_row_kept": keep is not None and abs(keep[0] - mod[1]) < 1e-9,
            "watchlist_kept": watch == 1, "provenance_rows": prov,
            "validity_rows": val, "duplicate_symbol_dates": dup,
            "chart_count": len(p1.get("candles") or []),
            "chart_first": (p1.get("candles") or [{}])[0].get("time"),
            "chart_last": (p1.get("candles") or [{}])[-1].get("time"),
            "events": len(p1.get("adjustEvents") or []),
            "ma_bars": ma.get("bars"),
            "ma_lens": ma_lens,
            "ma_periods": ma.get("periods"),
        })
    finally:
        stop(proc)
    proc, tok, p2 = start(up, 8171)
    try:
        con = sqlite3.connect(os.path.join(up, "market.db"))
        rows2 = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        con.close()
        state2 = json.load(open(os.path.join(up, "market_seed.json"), encoding="utf-8"))
        rep.update({"rows_after_restart": rows2, "idempotent": rows1 == rows2,
                    "restart_state_reason": state2.get("reason"),
                    "restart_chart_count": len(p2.get("candles") or [])})
    finally:
        stop(proc)
    old = {}
    if os.path.exists(OUT):
        old = json.load(open(OUT, encoding="utf-8"))
    old.setdefault("tests", {})["upgrade_merge_restart"] = rep
    old["schema"] = "phase49-product-test-v1"
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(old, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
