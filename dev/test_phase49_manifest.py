#!/usr/bin/env python3
import hashlib, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phase49_manifest as M  # noqa: E402


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path, data):
    """Binary write: text mode would turn LF into CRLF on Windows."""
    with open(path, "wb") as fh:
        fh.write(data.encode("utf-8"))


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

    # (a) empty input/output lists -> documented empty maps, still a valid file
    empty_out = os.path.join(tmp, "stage-empty.manifest.json")
    e = M.write_manifest("stage-empty", [], [], {}, empty_out)
    assert e["inputs"] == {} and e["outputs"] == {}, e
    ed = json.load(open(empty_out, encoding="utf-8"))
    assert ed["inputs"] == {} and ed["outputs"] == {} and ed["counts"] == {}, ed

    # (b) files nested in directories hash to the same digest as hashlib
    nested = os.path.join(tmp, "a", "b", "c")
    os.makedirs(nested)
    deep = os.path.join(nested, "deep.txt")
    side = os.path.join(tmp, "a", "side.txt")
    open(deep, "wb").write(b"deep\n")
    open(side, "wb").write(b"side\n")
    nested_out = os.path.join(tmp, "stage-nested.manifest.json")
    n = M.write_manifest("stage-nested", [deep, side], [], {}, nested_out)
    assert n["inputs"][deep] == _sha("deep\n"), n["inputs"]
    assert n["inputs"][side] == _sha("side\n"), n["inputs"]

    # (c) output files are hashed too, with the same digest as hashlib
    produced = os.path.join(tmp, "produced.json")
    open(produced, "wb").write(b'{"ok": true}\n')
    out_out = os.path.join(tmp, "stage-out.manifest.json")
    o = M.write_manifest("stage-out", [], [produced], {"written": 1}, out_out)
    assert o["outputs"] == {produced: _sha('{"ok": true}\n')}, o["outputs"]
    assert json.load(open(out_out, encoding="utf-8"))["outputs"] == o["outputs"]
    assert M.sha256(produced) == _sha('{"ok": true}\n')

    # (d) a missing path is silently omitted (documented "skip" rule), never
    # recorded with a bogus hash and never raised as an error.
    gone = os.path.join(tmp, "does-not-exist.txt")
    miss_out = os.path.join(tmp, "stage-missing.manifest.json")
    m = M.write_manifest("stage-missing", [p, gone], [gone], {}, miss_out)
    assert p in m["inputs"] and gone not in m["inputs"], m["inputs"]
    assert m["outputs"] == {}, m["outputs"]

    print("MANIFEST TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
