#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the RA365 v3 correction pack from hash-verified inputs.

Inputs are deliberately outside Git:
  * reference: D:/BorsTerminal-tmp/ra365_round32b_v3/reference/ref_bars_v2.jsonl
    (SHA-256 4b1ecb4c...; raw file is not committed)
  * product: the frozen R29 payload shards (2,594 JSON files), recorded in
    PRODUCT-INPUTS.json; not committed.

The command runs the Round 32B audit in pack-only mode (same full-overlay step
matching) and then the pack builder, both with a fixed created_at so the output
is byte-stable.  It writes build-hashes.json; pass that file back with
--expect-hashes to prove a second run is identical.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = "D:/BorsTerminal-tmp/ra365_round32b_v3"
DEFAULT_REF = D + "/reference/ref_bars_v2.jsonl"
DEFAULT_REF_SHA = "4b1ecb4c1effc4d5770c42521d96a2540a9c9f7b471d7cc710cd034712a8c17c"
DEFAULT_PRODUCT = ",".join("D:/BorsTerminal-tmp/r29_bench/full_shard%d" % i
                           for i in range(6))
DEFAULT_COHORT = "D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl"
DEFAULT_MANIFEST = D + "/inputs/PRODUCT-INPUTS.json"
DEFAULT_CREATED = "2026-10-25T20:00:00+00:00"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_reference(path, expected):
    got = sha256(path)
    if got != expected:
        raise SystemExit("REFERENCE_SHA_MISMATCH %s != %s" % (got, expected))
    return {"path": path, "sha256": got, "size": os.path.getsize(path)}


def verify_inputs(manifest_path, product_roots, cohort, verify_files=True):
    meta = json.load(open(manifest_path, encoding="utf-8"))
    payload_manifest = meta.get("manifest") or ""
    if not payload_manifest or not os.path.exists(payload_manifest):
        raise SystemExit("PAYLOAD_MANIFEST_MISSING")
    msha = sha256(payload_manifest)
    if meta.get("manifest_sha256") and msha != meta["manifest_sha256"]:
        raise SystemExit("PRODUCT_MANIFEST_SHA_MISMATCH")
    co = meta.get("cohort") or {}
    if cohort != co.get("path"):
        raise SystemExit("COHORT_PATH_MISMATCH %s != %s" % (cohort, co.get("path")))
    csha = sha256(cohort)
    if co.get("sha256") and csha != co["sha256"]:
        raise SystemExit("COHORT_SHA_MISMATCH")
    if co.get("size") and os.path.getsize(cohort) != co["size"]:
        raise SystemExit("COHORT_SIZE_MISMATCH")
    roots = {os.path.basename(x.rstrip("/\\")): x for x in product_roots}
    listed = 0
    if verify_files:
        with open(meta["manifest"], encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 2:
                    continue
                h, rel = parts[0], parts[1]
                shard, name = rel.split("/", 1)
                p = os.path.join(roots[shard], name)
                if not os.path.exists(p):
                    raise SystemExit("PRODUCT_FILE_MISSING %s" % p)
                if sha256(p) != h:
                    raise SystemExit("PRODUCT_FILE_SHA_MISMATCH %s" % p)
                listed += 1
    return {"manifest": payload_manifest, "metadata": manifest_path,
            "manifest_sha256": msha,
            "cohort": cohort, "cohort_sha256": csha,
            "product_files_verified": listed,
            "product_roots": product_roots}


def collect_hashes(out, manifest):
    names = {"manifest.json"}
    for key in ("factors", "raw_ohlc", "basis_summary"):
        if manifest.get("files", {}).get(key):
            names.add(manifest["files"][key])
    for name in (manifest.get("files", {}).get("basis_split") or {}).values():
        names.add(name)
    hashes = {}
    for name in sorted(names):
        p = os.path.join(out, name)
        hashes[name] = sha256(p)
    return hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default=DEFAULT_REF)
    ap.add_argument("--expected-ref-sha", default=DEFAULT_REF_SHA)
    ap.add_argument("--product", default=DEFAULT_PRODUCT)
    ap.add_argument("--cohort", default=DEFAULT_COHORT)
    ap.add_argument("--product-manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit-out", default="")
    ap.add_argument("--version", default="ra365-r32b-v3")
    ap.add_argument("--created-at", default=DEFAULT_CREATED)
    ap.add_argument("--expect-hashes", default="")
    ap.add_argument("--skip-product-file-verify", action="store_true")
    a = ap.parse_args()
    product_roots = [x for x in a.product.split(",") if x]
    audit_out = a.audit_out or (a.out + "/audit")
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(audit_out, exist_ok=True)

    ref = verify_reference(a.reference, a.expected_ref_sha)
    inputs = verify_inputs(a.product_manifest, product_roots, a.cohort,
                           verify_files=not a.skip_product_file_verify)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    audit_cmd = [sys.executable, os.path.join(ROOT, "tools", "ra365_round32b_audit.py"),
                 "--ref", a.reference, "--product", a.product, "--cohort", a.cohort,
                 "--out", audit_out, "--full-overlay", "--pack-only",
                 "--correction-version", a.version, "--created-at", a.created_at]
    subprocess.run(audit_cmd, cwd=ROOT, env=env, check=True)
    pack_cmd = [sys.executable, os.path.join(ROOT, "tools", "ra365_round32b_pack.py"),
                "--audit-dir", audit_out, "--out", a.out, "--version", a.version,
                "--mode", "authoritative", "--created-at", a.created_at]
    subprocess.run(pack_cmd, cwd=ROOT, env=env, check=True)
    manifest_path = os.path.join(a.out, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    if manifest.get("reference_sha256") != a.expected_ref_sha:
        raise SystemExit("PACK_REFERENCE_SHA_MISMATCH")
    hashes = collect_hashes(a.out, manifest)
    build = {
        "version": a.version,
        "created_at": a.created_at,
        "reference": ref,
        "inputs": inputs,
        "out": a.out,
        "counts": manifest.get("counts", {}),
        "file_sha256": hashes,
        "reproduce_command": ("python tools/ra365_round32b_reproduce_v3.py --out <out> "
                              "--expect-hashes <this-json>"),
    }
    build_path = os.path.join(a.out, "build-hashes.json")
    json.dump(build, open(build_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.expect_hashes:
        expected = json.load(open(a.expect_hashes, encoding="utf-8"))
        exp = expected.get("file_sha256") or expected.get("hashes") or {}
        diffs = {k: (exp.get(k), hashes.get(k)) for k in set(exp) | set(hashes)
                 if exp.get(k) != hashes.get(k)}
        if diffs:
            print(json.dumps({"reproducible": False, "diff": diffs}, ensure_ascii=False, indent=1))
            return 1
        print(json.dumps({"reproducible": True, "version": a.version,
                          "files": len(hashes), "sha256": hashes,
                          "counts": manifest.get("counts", {})}, ensure_ascii=False, indent=1))
        return 0
    print(json.dumps(build, ensure_ascii=False, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
