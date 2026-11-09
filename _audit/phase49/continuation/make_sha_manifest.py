"""Phase 4.9 — SHA-256 manifest for artifacts, packs, test DBs and evidence.

Writes docs/opportunity-center/phase49/ARTIFACTS-SHA256.txt (committed) with
one line per artifact: <sha256>  <size>  <category>  <path>. Large DB copies
and evidence are local-only (gitignored) but their hashes are recorded here.
"""
import hashlib
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
OUT = os.path.join(ROOT, "docs", "opportunity-center", "phase49",
                   "ARTIFACTS-SHA256.txt")
CONT = "_audit/phase49/continuation"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add(lst, cat, rel):
    p = os.path.join(ROOT, rel)
    if os.path.isfile(p):
        lst.append((cat, rel.replace("\\", "/"), os.path.getsize(p), sha256(p)))


def walk(lst, cat, rel_dir, exts=None):
    base = os.path.join(ROOT, rel_dir)
    for dirpath, _, files in os.walk(base):
        for fn in sorted(files):
            if exts and not fn.endswith(tuple(exts)):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            lst.append((cat, rel.replace("\\", "/"), os.path.getsize(p), sha256(p)))


def main():
    rows = []
    # Committed code + docs + tests
    for rel in [
        "adjustment_corrections.py", "api/chart.py", "dev/run_all_tests.py",
        "dev/test_phase49_correction_parity_v1.py",
        "backend-go/internal/chart/canonical.go",
        "backend-go/internal/chart/corrections.go",
        "backend-go/internal/chart/handlers.go",
        "backend-go/internal/chart/phase49_parity_test.go",
    ]:
        add(rows, "committed-code", rel)
    for rel in [
        "docs/opportunity-center/phase49/STAGE0-AUDIT.md",
        "docs/opportunity-center/phase49/CHAIN-ANALYSIS.md",
        "docs/opportunity-center/phase49/EVENT-MAPPING-30.csv",
        "docs/opportunity-center/phase49/RAW-PARITY.md",
        "docs/opportunity-center/phase49/ADJUSTED-PARITY.md",
        # FINAL-REPORT.md is intentionally excluded: it is edited after this
        # manifest is generated (CI status), so hashing it here would go stale.
    ]:
        add(rows, "committed-doc", rel)
    walk(rows, "committed-fixture", "backend-go/internal/chart/testdata/phase49")
    # Mission scripts (committed)
    import glob
    for p in sorted(glob.glob(os.path.join(ROOT, CONT, "*.py"))
                    + glob.glob(os.path.join(ROOT, CONT, "api", "*.py"))):
        add(rows, "mission-script", os.path.relpath(p, ROOT))
    add(rows, "mission-script", CONT + "/symbols30.csv")
    # Phase 4.8 archives (committed)
    walk(rows, "phase48-archive", "data/phase48/db", exts=(".lzma",))
    # Test DB copies and packs (local)
    walk(rows, "local-testdb", os.path.join(CONT, "db"), exts=(".db",))
    add(rows, "local-testdb", CONT + "/api/python/market.db")
    add(rows, "local-testdb", CONT + "/api/sandbox/market.db")
    walk(rows, "local-pack", os.path.join(CONT, "packs"))
    # Evidence (local)
    walk(rows, "local-evidence", os.path.join(CONT, "evidence"))

    lines = [
        "# Phase 4.9 artifact SHA-256 manifest (generated 2026-11-10)",
        "# format: sha256  size_bytes  category  path",
        "# committed-* files are in git; local-* files are gitignored test copies/evidence.",
        "",
    ]
    for cat, rel, size, h in sorted(rows, key=lambda x: (x[0], x[1])):
        lines.append("%s  %d  %s  %s" % (h, size, cat, rel))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", OUT, "entries", len(rows))


if __name__ == "__main__":
    main()
