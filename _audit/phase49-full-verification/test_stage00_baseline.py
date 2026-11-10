#!/usr/bin/env python3
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage00_baseline as S  # noqa: E402

DB = "_audit/phase49-finalization/seed/market.db"
PACK = "data/ra365_corrections/ra365-phase49-rebuild-full-v2"


def missing_fixtures():
    """Fixtures are gitignored, so a fresh clone legitimately lacks them."""
    out = []
    for rel, check in ((DB, os.path.isfile), (PACK, os.path.isdir)):
        full = S._abs(rel)
        if not check(full):
            out.append(rel)
    return out


def main():
    absent = missing_fixtures()
    if absent:
        for rel in absent:
            print("SKIP: %s missing (gitignored fixture)" % rel)
        return 0
    rep = S.snapshot(pack=PACK, db=DB)
    assert rep["head"] == S.git_head()
    assert rep["pack"]["counts"]["steps"] == 8280, rep["pack"]
    assert len(rep["pack"]["factors_sha256"]) == 64
    assert len(rep["db"]["sha256"]) == 64
    assert rep["db"]["price_history_rows"] == 511139
    assert rep["db"]["symbols_with_history"] == 6103
    print("BASELINE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
