"""Phase 4.9 finalization — SHA-256 manifest of final artifacts.

Writes docs/opportunity-center/phase49/ARTIFACTS-SHA256-finalization.txt with
one line per artifact: <sha256>  <size>  <category>  <path>

Categories:
  committed  tracked in this branch (hash of the git blob, i.e. the bytes a
             fresh clone gets — LF-normalised where .gitattributes says so)
  local      local-only evidence / DB / binary (gitignored; hash of the file)
  reference  owner-authenticated Rahavard capture (not redistributed)
"""
import hashlib
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
BASE = "_audit/phase49-finalization"
OUT = os.path.join(ROOT, "docs", "opportunity-center", "phase49",
                   "ARTIFACTS-SHA256-finalization.txt")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def add_committed(rows, rel):
    p = rel.replace("\\", "/")
    try:
        data = subprocess.run(["git", "cat-file", "blob", ":" + p], cwd=ROOT,
                              capture_output=True, check=True).stdout
    except Exception:                                             # noqa: BLE001
        return add_local(rows, "committed", rel)
    rows.append(("committed", p, len(data), sha256_bytes(data)))


def add_local(rows, cat, rel):
    p = os.path.join(ROOT, rel)
    if os.path.isfile(p):
        rows.append((cat, rel.replace("\\", "/"), os.path.getsize(p),
                     sha256_file(p)))


def main():
    rows = []
    for rel in (
        "data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl",
        "data/ra365_corrections/ra365-phase49-rebuild-full-v2/raw_ohlc.jsonl",
        "data/ra365_corrections/ra365-phase49-rebuild-full-v2/manifest.json",
        "adjustment_corrections.py",
        "backend-go/internal/chart/corrections.go",
        "backend-go/internal/seed/seed.go",
        "dev/test_chart_fixture_b3.py",
        "dev/test_mstat_fixture_v1121.py",
        ".github/workflows/guards.yml",
        "docs/opportunity-center/phase49/FINALIZATION-REPORT.md",
        BASE + "/EVENT-MAPPING-FULL.csv",
        BASE + "/VALIDITY-30.csv",
        BASE + "/VALIDITY-7.csv",
        BASE + "/DB-INVENTORY.md",
        BASE + "/OPEN-AUDIT-SUMMARY.json",
        BASE + "/OPEN-CORRECTIONS-BY-SYMBOL.csv",
        BASE + "/open-apply-report.json",
        BASE + "/seed-build-report.json",
        BASE + "/product-test-report.json",
        BASE + "/engine-parity-30-final.json",
        BASE + "/stageA-restore-report.json",
        BASE + "/evidence/product-clean-evidence.json",
        BASE + "/evidence/db-inventory.json",
        BASE + "/evidence/canonical-summary.json",
        BASE + "/evidence/reference-parity-30-final.json",
        BASE + "/evidence/reference-parity-7-final.json",
        BASE + "/reference-parity-30-final.csv",
        BASE + "/reference-parity-7-final.csv",
        BASE + "/reference-step-decisions-all.csv",
        BASE + "/rahavard/symbols30.json",
        BASE + "/rahavard/symbols7.json",
        BASE + "/rahavard/normalized30/summary.json",
        BASE + "/rahavard/normalized7/summary.json",
    ):
        add_committed(rows, rel)
    for rel in (
        BASE + "/seed/market.db",
        BASE + "/seed/market.db.lzma",
        BASE + "/seed/market.db.gz",
        BASE + "/borsd_final.exe",
        BASE + "/product-test/clean-evidence.json",
        BASE + "/evidence/open-audit-30.json",
        BASE + "/open-corrections-30.csv",
    ):
        add_local(rows, "local", rel)
    for rel in (
        BASE + "/rahavard/capture-30.json",
        BASE + "/rahavard/capture-7.json",
        BASE + "/rahavard/normalized30/bars.ndjson.gz",
        BASE + "/rahavard/normalized7/bars.ndjson.gz",
    ):
        add_local(rows, "reference", rel)
    seen, lines = set(), []
    for cat, rel, size, digest in rows:
        if rel in seen:
            continue
        seen.add(rel)
        lines.append("%s  %d  %s  %s" % (digest, size, cat, rel))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Phase 4.9 finalization artifact SHA-256 manifest\n")
        f.write("# format: sha256  size_bytes  category  path\n")
        f.write("\n".join(lines) + "\n")
    print("wrote %s artifacts=%d" % (OUT, len(lines)))


if __name__ == "__main__":
    main()
