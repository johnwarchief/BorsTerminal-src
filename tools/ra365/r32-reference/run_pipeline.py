#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command that rebuilds the whole Round 32A reference pack.

It runs the R32 tools in order over the evidence that survived in git, writes
the pack, and verifies it against its own manifest.  Pass the same
`--generated-at` twice and the two packs are byte-identical.

  capture export (optional, from capture_rahavard.mjs)
        |
        v
  import_reference.py  -> bars.ndjson.gz + coverage.json
        |
        +--> infer_factor_segments.py  -> factor_segments.ndjson.gz
        |
        +--> build_mismatch_ledger.py   -> mismatch_map.ndjson.gz
        |
        v
  pack.py -> manifest.json      verify_pack.py -> OK

Usage
  python run_pipeline.py --pack D:/BorsTerminal-tmp/ra365_round32/reference-pack
  python run_pipeline.py --pack <dir> --capture <rahavard-export.json>
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

sys.path.insert(0, HERE)
import r32_schema as S  # noqa: E402

CANDLE_LEDGER = os.path.join(ROOT, "_audit", "RA365-CANDLE-DIVERGE-2026-10-12.csv")
PARITY_LEDGER = os.path.join(ROOT, "_audit", "RA365-PARITY-DIVERGE-2026-10-12.csv")
STEPS_LEDGER = os.path.join(ROOT, "artifacts", "ra365", "r30", "attribution", "steps.csv")
FAMILIES = os.path.join(ROOT, "artifacts", "ra365", "r30", "attribution", "families.csv")
DECLARED = os.path.join(ROOT, "artifacts", "ra365", "r26", "reference-coverage.json")


def run(args, **kw):
    print("$ " + " ".join(os.path.basename(a) if a.endswith(".py") else a for a in args))
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    subprocess.run([sys.executable] + args, check=True, env=env, **kw)


def tool(name):
    return os.path.join(HERE, name)


def export_artifacts(pack, dest, inputs):
    """Copy the shareable subset into git: contract, stats, hashes - no raw bars.

    The reference OHLC itself is the owner's subscription and never leaves the
    local pack; what is published here is the schema, the manifest, the
    aggregate coverage, the summaries and the hashes.
    """
    import glob
    import json
    os.makedirs(dest, exist_ok=True)
    share = ["manifest.json", "coverage.json", "factor-segments-summary.json",
             "mismatch-summary.json", "mismatch-disposition.json"]
    for name in share:
        src = os.path.join(pack, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dest, name))
    # a handful of inferred segments: derived factors, not raw price series
    segments = []
    if os.path.exists(os.path.join(pack, "factor_segments.ndjson.gz")):
        import sys as _sys
        _sys.path.insert(0, HERE)
        import r32_io as IO
        for i, rec in enumerate(IO.read_ndjson_gz(os.path.join(pack, "factor_segments.ndjson.gz"))):
            if i >= 8:
                break
            segments.append(rec)
    with open(os.path.join(dest, "factor-segments-sample.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump({"note": "derived factors only; the raw series stays in the local pack",
                   "records": segments}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    lines = []
    for path in list(inputs) + sorted(glob.glob(os.path.join(pack, "*"))):
        if os.path.isfile(path) and not path.endswith(".ndjson.gz"):
            lines.append("%s  %s" % (S.sha256_file(path), os.path.basename(path)))
    for name in ("bars.ndjson.gz", "factor_segments.ndjson.gz",
                 "factor_segments_frozen.ndjson.gz", "mismatch_map.ndjson.gz"):
        path = os.path.join(pack, name)
        if os.path.exists(path):
            lines.append("%s  %s" % (S.sha256_file(path), name))
    with open(os.path.join(dest, "evidence-sha256.txt"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("artifacts exported to %s (%d files)" % (dest, len(share) + 2))


def main():
    ap = argparse.ArgumentParser(description="Rebuild the R32A reference pack.")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--artifacts", default=None,
                    help="directory in git to receive the shareable subset")
    ap.add_argument("--capture", default=None,
                    help="a Rahavard export from capture_rahavard.mjs to import as well")
    ap.add_argument("--generated-at", default=None)
    a = ap.parse_args()

    pack = os.path.abspath(a.pack)
    tmp = os.path.join(pack, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    pairs_candle = os.path.join(tmp, "pairs_candle.ndjson.gz")
    pairs_parity = os.path.join(tmp, "pairs_parity.ndjson.gz")
    stamp = ["--generated-at", a.generated_at] if a.generated_at else []

    # 1) bars + coverage: reference adjusted beside product raw, session by session
    run([tool("import_reference.py"), "--in", CANDLE_LEDGER, "--kind", "candle-diverge",
         "--out", pack, "--also-pairs", pairs_candle,
         "--declared-coverage", DECLARED] + stamp)

    # 2) the four named parity arms, dumped as pairs for the ledger
    run([tool("import_reference.py"), "--in", PARITY_LEDGER, "--kind", "parity-diverge",
         "--out", os.path.join(tmp, "parity"),
         "--also-pairs", pairs_parity] + stamp)

    # 3) the frozen factor-chain boundaries, kept under their own name
    run([tool("import_reference.py"), "--in", STEPS_LEDGER, "--kind", "steps",
         "--out", os.path.join(tmp, "steps")] + stamp)
    shutil.copyfile(os.path.join(tmp, "steps", "factor_segments.ndjson.gz"),
                    os.path.join(pack, "factor_segments_frozen.ndjson.gz"))

    # 4) a real capture, when one is available
    if a.capture:
        run([tool("import_reference.py"), "--in", a.capture, "--kind", "rahavard-json",
             "--out", os.path.join(tmp, "capture")] + stamp)
        shutil.copyfile(os.path.join(tmp, "capture", "bars.ndjson.gz"),
                        os.path.join(pack, "bars_capture.ndjson.gz"))

    # 5) infer the effective factors from the raw-vs-adjusted pairs
    run([tool("infer_factor_segments.py"), "--pairs", pairs_candle, "--out", pack] + stamp)

    # 6) every unmatched paired date, keyed
    run([tool("build_mismatch_ledger.py"), "--mode", "ledger",
         "--pairs", pairs_parity, "--prefiltered", "--out", pack] + stamp)

    # 7) reconcile the frozen 413,365 against the R30 families
    run([tool("build_mismatch_ledger.py"), "--mode", "disposition",
         "--families", FAMILIES, "--out", pack] + stamp)

    # 8) manifest + verification
    run([tool("pack.py"), "--dir", pack, "--require", "bars.ndjson.gz,coverage.json"] + stamp)
    run([tool("verify_pack.py"), "--dir", pack])

    if a.artifacts:
        export_artifacts(pack, os.path.abspath(a.artifacts),
                         [CANDLE_LEDGER, PARITY_LEDGER, STEPS_LEDGER, FAMILIES, DECLARED])

    print("\npack ready at %s" % pack)
    return 0


if __name__ == "__main__":
    sys.exit(main())