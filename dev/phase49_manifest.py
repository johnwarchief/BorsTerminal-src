#!/usr/bin/env python3
"""Stage manifest helper for the Phase 4.9.1 verification ledgers.

Every stage writes ``evidence/<stage>.manifest.json`` recording the exact bytes
it consumed and produced, so a later stage (or the controller) can prove the
pipeline ran on the inputs it claims.

Stdlib only. The serialisation is deterministic: UTF-8 without BOM, sorted
keys, ``indent=1``, LF line endings and one trailing newline, so the same
payload is byte-identical on Windows and on a Linux CI checkout. File hashes
are streamed in 4 MiB chunks (the seed DB is ~270 MB).
"""
import hashlib
import json
import os
import time

CHUNK = 1 << 22


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(stage, inputs, outputs, counts, out_path):
    payload = {
        "stage": stage,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {p: sha256(p) for p in inputs if os.path.isfile(p)},
        "outputs": {p: sha256(p) for p in outputs if os.path.isfile(p)},
        "counts": counts,
    }
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return payload
