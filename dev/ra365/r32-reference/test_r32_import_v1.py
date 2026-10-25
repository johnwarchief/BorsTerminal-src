#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the importer end to end, and the pack manifest + verifier.

Runs the real CLI in a subprocess so the test covers argument handling and file
layout, not only the library functions.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import _harness as H

import r32_schema as S

WORK = os.path.join(tempfile.gettempdir(), "r32-reference-tests", "import")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK, exist_ok=True)

CANDLE_HEADER = ["date", "our_c", "our_h", "our_l", "our_last", "our_o", "our_src", "our_v",
                 "ref_c", "ref_c_equals_our_last", "ref_h", "ref_l", "ref_o", "ref_v", "symbol"]
csv1 = H.tmp_csv("r32_import_candle.csv", CANDLE_HEADER, [
    ["2024-01-05", 5780, 5810, 5650, "", 5680, "", 100, 2845.7, "no",
     2855.5, 2776.8, 2791.6, 100, "\u0641\u0648\u0644\u0627\u062f"],
    ["2024-01-06", 5850, 5920, 5780, "", 5870, "", 120, 2899.7, "yes",
     2909.5, 2840.7, 2885.0, 120, "\u0641\u0648\u0644\u0627\u062f"],
])
declared = os.path.join(WORK, "declared.json")
with open(declared, "w", encoding="utf-8") as fh:
    json.dump({"reference": "test", "coverage": [
        {"type": "type0", "res": "D", "series": 2599, "assets": 2595, "bars": 10}]}, fh)

env = dict(os.environ, PYTHONIOENCODING="utf-8")
out = os.path.join(WORK, "pack")
cmd = [sys.executable, os.path.join(H.TOOLS, "import_reference.py"),
       "--in", csv1, "--kind", "candle-diverge", "--out", out,
       "--also-pairs", os.path.join(WORK, "pairs.ndjson.gz"),
       "--declared-coverage", declared, "--generated-at", "2026-10-25T00:00:00Z"]
res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=H.TOOLS)
H.ck(res.returncode == 0, "import: the CLI exits 0", res.stderr[-400:])
H.ck(os.path.exists(os.path.join(out, "bars.ndjson.gz")), "import: bars were written")
H.ck(os.path.exists(os.path.join(out, "coverage.json")), "import: coverage was written")
H.ck(os.path.exists(os.path.join(out, "import-manifest.json")), "import: the manifest was written")
H.ck(os.path.exists(os.path.join(WORK, "pairs.ndjson.gz")), "import: the pairs dump was written")

cov = json.load(open(os.path.join(out, "coverage.json"), encoding="utf-8"))
H.ck(cov["totals"]["bars"] == 4 and cov["totals"]["series"] == 2,
     "import: two series of two bars each", cov["totals"])
H.ck(cov["totals"]["schema_violations"] == 0, "import: no record violated the contract")
H.ck(len(cov["series"]) == 2, "import: coverage lists both series")
H.ck(all(s["status"] == "OK" for s in cov["series"]), "import: non-empty series are OK")
H.ck(cov["shortfall"]["declared_assets"] == 2595 and cov["shortfall"]["present_assets"] == 1,
     "import: the shortfall is measured against the declared universe", cov["shortfall"])
H.ck(cov["shortfall"]["assets_missing"] == 2594, "import: the missing asset count is explicit")

# every written bar satisfies the contract
import gzip
for line in gzip.open(os.path.join(out, "bars.ndjson.gz"), "rt", encoding="utf-8"):
    rec = json.loads(line)
    H.ck(S.validate(rec, S.SCHEMA_BAR) == [], "import: a written bar validates (%s %s)"
         % (rec["adjust"], rec["date"]))

# re-importing the same input yields the same bytes
out2 = os.path.join(WORK, "pack2")
subprocess.run([sys.executable, os.path.join(H.TOOLS, "import_reference.py"),
                "--in", csv1, "--kind", "candle-diverge", "--out", out2,
                "--generated-at", "2026-10-25T00:00:00Z"],
               capture_output=True, text=True, env=env, cwd=H.TOOLS, check=True)
H.ck(open(os.path.join(out, "bars.ndjson.gz"), "rb").read()
     == open(os.path.join(out2, "bars.ndjson.gz"), "rb").read(),
     "import: the same input produces byte-identical bars")

# --- pack + verify -------------------------------------------------------
subprocess.run([sys.executable, os.path.join(H.TOOLS, "pack.py"), "--dir", out,
                "--require", "bars.ndjson.gz,coverage.json",
                "--generated-at", "2026-10-25T00:00:00Z"],
               capture_output=True, text=True, env=env, cwd=H.TOOLS, check=True)
man = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
H.ck(man["schema"] == S.SCHEMA_MANIFEST, "pack: the manifest carries its schema")
H.ck(len(man["pack_id"]) == 64, "pack: pack_id is a sha256")
H.ck(all(f["sha256"] for f in man["files"]), "pack: every file has a hash")
H.ck(any(u["path"] == "factor_segments.ndjson.gz" for u in man["unavailable"]),
     "pack: a member the run did not produce is listed unavailable, not omitted")

v = subprocess.run([sys.executable, os.path.join(H.TOOLS, "verify_pack.py"), "--dir", out],
                   capture_output=True, text=True, env=env, cwd=H.TOOLS)
H.ck(v.returncode == 0, "verify: a healthy pack verifies", v.stdout[-400:])

# a tampered file must be caught
with open(os.path.join(out, "coverage.json"), "a", encoding="utf-8") as fh:
    fh.write(" ")
v2 = subprocess.run([sys.executable, os.path.join(H.TOOLS, "verify_pack.py"), "--dir", out],
                    capture_output=True, text=True, env=env, cwd=H.TOOLS)
H.ck(v2.returncode == 1, "verify: a moved hash is caught")
H.ck("hash moved" in v2.stdout, "verify: the failure names the moved hash", v2.stdout[-200:])

H.report()