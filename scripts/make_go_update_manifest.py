#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the signed Go update channel manifest (latest-go.json).

The Go updater (backend-go/internal/update) trusts only the embedded minisign
public key; this manifest merely advertises a version and an artifact. It is a
different file from the legacy latest.json on purpose: that channel installs
the Python-era installer and must not be consumed as channel="go".

Usage:
  python scripts/make_go_update_manifest.py \
      --version 1.0.96 \
      --installer installer/out/BorsTerminal_Ultimate_Setup_v1.0.96.exe \
      --signature installer/out/BorsTerminal_Ultimate_Setup_v1.0.96.exe.sig \
      --out dist/latest-go.json \
      --url https://github.com/johnwarchief/BorsTerminal/releases/download/v1.0.96/Setup.exe
"""
import argparse
import base64
import hashlib
import json
import os
import sys
from email.utils import formatdate

DEFAULT_REPO = "johnwarchief/BorsTerminal"


def signature_b64(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read().strip()
    if not raw:
        raise SystemExit("signature file is empty")
    if raw.startswith("untrusted comment:"):
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")
    decoded = base64.b64decode(raw, validate=True)
    if not decoded.startswith(b"untrusted comment:"):
        raise SystemExit("signature is neither raw minisign text nor its base64 form")
    return raw


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(version, installer, signature, url, notes="", repo=DEFAULT_REPO):
    version = version.strip().lstrip("v")
    name = os.path.basename(installer)
    if not url:
        url = f"https://github.com/{repo}/releases/download/v{version}/{name}"
    return {
        "channel": "go",
        "version": version,
        "notes": notes,
        "pub_date": formatdate(localtime=True, usegmt=True),
        "platforms": {
            "windows-x86_64": {
                "url": url,
                "signature": signature_b64(signature),
                "size": os.path.getsize(installer),
                "sha256": sha256_file(installer),
            }
        },
    }


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        installer = os.path.join(tmp, "Setup_v9.9.9.exe")
        sig = os.path.join(tmp, "Setup_v9.9.9.exe.sig")
        with open(installer, "wb") as f:
            f.write(b"installer-bytes")
        raw = "untrusted comment: x\nRUAAAA\n"
        with open(sig, "w", encoding="utf-8") as f:
            f.write(base64.b64encode(raw.encode()).decode())
        m = build_manifest("v9.9.9", installer, sig, "")
        assert m["channel"] == "go" and m["version"] == "9.9.9", m
        asset = m["platforms"]["windows-x86_64"]
        assert base64.b64decode(asset["signature"]).startswith(b"untrusted comment:")
        assert asset["size"] == len(b"installer-bytes") and len(asset["sha256"]) == 64
        assert asset["url"].endswith("/v9.9.9/Setup_v9.9.9.exe"), asset["url"]
    print("GO UPDATE MANIFEST SELF-TEST OK")


def main():
    ap = argparse.ArgumentParser(description="Build latest-go.json for the Go update channel")
    ap.add_argument("--version")
    ap.add_argument("--installer")
    ap.add_argument("--signature")
    ap.add_argument("--out")
    ap.add_argument("--url", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-file", default="")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    missing = [n for n in ("version", "installer", "signature", "out") if not getattr(args, n)]
    if missing:
        raise SystemExit("missing required arguments: " + ", ".join(missing))
    notes = args.notes
    if args.notes_file:
        with open(args.notes_file, encoding="utf-8") as f:
            notes = f.read()
    manifest = build_manifest(args.version, args.installer, args.signature, args.url, notes, args.repo)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    asset = manifest["platforms"]["windows-x86_64"]
    print(f"wrote {args.out}: version={manifest['version']} size={asset['size']} sha256={asset['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
