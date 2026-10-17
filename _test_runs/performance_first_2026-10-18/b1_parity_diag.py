# -*- coding: utf-8 -*-
# B1: علتِ timeoutِ fts_engine_paths_parity_v1076 — زمانِ bulk_scan و scan_symbol رویِ یک DB (فقط‌خواندنی، کپیِ موقت).
import cProfile
import io
import json
import os
import pstats
import shutil
import sqlite3
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(WT)
sys.path.insert(0, WT)
import bors_config  # noqa: E402
import fts_engine as F  # noqa: E402

src, tag, n_sym = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25
tmp = os.path.join(tempfile.gettempdir(), "bors_parity_diag_%s.db" % tag)
shutil.copyfile(src, tmp)
conn = sqlite3.connect("file:%s?mode=ro" % tmp.replace("\\", "/"), uri=True)
conn.row_factory = sqlite3.Row
cfg = json.load(open(bors_config.FTS_CONFIG_PATH, encoding="utf-8"))
res = {"tag": tag, "src": src, "bytes": os.path.getsize(src)}
t0 = time.perf_counter()
bulk = {r["symbol_norm"]: r for r in F.bulk_scan(conn, cfg=cfg)}
res["bulk_scan_s"] = round(time.perf_counter() - t0, 2)
res["bulk_rows"] = len(bulk)
total = F.mstat_engine.market_total_rials(conn)[0]
times = []
prof = cProfile.Profile()
for i, (key, br) in enumerate(bulk.items()):
    if i >= n_sym:
        break
    t1 = time.perf_counter()
    prof.enable()
    F.scan_symbol(conn, br["symbol"], br["mcap"], total, br["sector_name"] or "", cfg=cfg)
    prof.disable()
    times.append(round(time.perf_counter() - t1, 3))
conn.close()
res["scan_symbol_n"] = len(times)
res["scan_symbol_s"] = times
res["scan_symbol_mean_s"] = round(sum(times) / len(times), 3) if times else None
res["projected_full_s"] = round(res["bulk_scan_s"] + (res["scan_symbol_mean_s"] or 0) * len(bulk), 1)
buf = io.StringIO()
pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(25)
res["profile_top"] = buf.getvalue().splitlines()[:70]
os.remove(tmp)
with open(os.path.join(HERE, "b1-parity-diag-%s.json" % tag), "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "profile_top"}, ensure_ascii=False))
