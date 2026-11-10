#!/usr/bin/env python3
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phase49_manifest as M  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "in.txt")
    open(p, "w", encoding="utf-8").write("x")
    out = os.path.join(tmp, "manifest.json")
    M.write_manifest("stage-test", [p], [], {"rows": 1}, out)
    d = json.load(open(out, encoding="utf-8"))
    assert d["stage"] == "stage-test"
    assert len(d["inputs"][p]) == 64
    assert d["counts"]["rows"] == 1
    raw = open(out, "rb").read()
    assert b"\r" not in raw, "manifest must be LF-only"
    assert raw.rstrip(b"\n").endswith(b"}") and raw.endswith(b"\n"), raw[-8:]
    assert list(d) == sorted(d), list(d)
    print("MANIFEST TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
