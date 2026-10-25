#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the pack's gzip is byte-deterministic and round-trips."""
import os
import tempfile

import _harness as H

import r32_io as IO

D = os.path.join(tempfile.gettempdir(), "r32-reference-tests")
os.makedirs(D, exist_ok=True)
rows = [{"schema": "x/1", "i": i, "v": "\u0641\u0648\u0644\u0627\u062f"} for i in range(50)]

a = os.path.join(D, "a.ndjson.gz")
b = os.path.join(D, "b.ndjson.gz")
na = IO.write_ndjson_gz(a, rows)
nb = IO.write_ndjson_gz(b, rows)

H.ck(na == nb == 50, "writer: reports the row count")
H.ck(open(a, "rb").read() == open(b, "rb").read(),
     "gzip is byte-identical across two writes of the same rows (mtime pinned)")
H.ck(list(IO.read_ndjson_gz(a)) == rows, "round-trip: rows come back equal")
H.ck(IO.count_lines(a) == 50, "count_lines matches the written rows")

plain = os.path.join(D, "c.ndjson")
IO.write_ndjson(plain, rows)
H.ck(list(IO.read_ndjson(plain)) == rows, "plain ndjson round-trips")

j = os.path.join(D, "c.json")
IO.write_json(j, {"b": 1, "a": [1, 2]})
H.ck(IO.read_json(j) == {"b": 1, "a": [1, 2]}, "json round-trips")
H.ck(open(j, "rb").read().endswith(b"\n"), "json is written with a trailing newline")

H.report()