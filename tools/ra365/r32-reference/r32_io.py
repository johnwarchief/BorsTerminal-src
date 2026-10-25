#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic readers/writers for the reference pack.

gzip stores an mtime by default, which would make two builds of the same input
produce different bytes.  Every writer here pins mtime=0 so that a pack's
hash is a function of its content alone.
"""
from __future__ import annotations

import gzip
import json
import os

import r32_schema as S


def write_json(path, obj, indent=1):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent, sort_keys=False)
        fh.write("\n")
    return path


def read_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_ndjson_gz(path, rows):
    """Write rows as NDJSON inside a gzip container, deterministically.

    The payload is assembled first and compressed in one call: a streaming
    GzipFile splits the deflate stream at write boundaries, which can differ
    between two runs and make the bytes move even though the payload does not.
    gzip.compress with mtime=0 removes both sources of drift, so a pack's hash
    is a function of its content alone.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    parts = []
    for row in rows:
        parts.append(S.canonical_json(row))
        parts.append("\n")
        n += 1
    payload = "".join(parts).encode("utf-8")
    with open(path, "wb") as raw:
        raw.write(gzip.compress(payload, compresslevel=9, mtime=0))
    return n


def read_ndjson_gz(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_ndjson(path):
    with open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_ndjson(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(S.canonical_json(row))
            fh.write("\n")
            n += 1
    return n


def count_lines(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    n = 0
    with opener(path, "rb") as fh:
        for _ in fh:
            n += 1
    return n


def file_entry(path, schema, rows=None, rel=None):
    return {
        "path": rel or os.path.basename(path),
        "schema": schema,
        "bytes": os.path.getsize(path),
        "rows": count_lines(path) if rows is None else rows,
        "sha256": S.sha256_file(path),
    }