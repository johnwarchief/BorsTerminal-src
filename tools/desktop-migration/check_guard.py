#!/usr/bin/env python3
"""Loopback-guard contract check for the backend and the prototype proxy.

Verifies that the production rule is unchanged: loopback Host/Origin (or no
Origin) may read; external Host, external Origin, `Origin: null` and
tauri.localhost are rejected. The prototype proxy rewrites Host upstream, so it
must enforce the same rule itself.

usage:
  python tools/desktop-migration/check_guard.py \
      --out artifacts/desktop-migration/security-guard.json
"""
from __future__ import annotations

import argparse
import http.client
import json
import time


def request(port: int, host: str | None, origin: str | None) -> int:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Accept": "application/json"}
    if host:
        headers["Host"] = host
    if origin:
        headers["Origin"] = origin
    try:
        conn.request("GET", "/api/update/version", headers=headers)
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-port", type=int, default=8102)
    ap.add_argument("--proxy-port", type=int, default=8105)
    ap.add_argument("--out", default="artifacts/desktop-migration/security-guard.json")
    args = ap.parse_args()

    cases = [
        ("no origin, loopback host", "127.0.0.1:{p}", None, 200),
        ("localhost host, loopback origin", "localhost:{p}", "http://localhost:{p}", 200),
        ("external origin", "127.0.0.1:{p}", "http://evil.example", 403),
        ("null origin", "127.0.0.1:{p}", "null", 403),
        ("tauri.localhost origin", "127.0.0.1:{p}", "http://tauri.localhost", 403),
        ("external host", "evil.example", None, 403),
    ]
    out = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "targets": [],
        "note": (
            "The first proxy version rewrote Host upstream without checking it, so "
            "external-Host requests returned 200. serve_prototype.py now enforces "
            "the same loopback Host/Origin contract before proxying; this run is "
            "the post-fix evidence. The production backend was never changed."
        ),
    }
    for name, port_attr in (("backend", args.backend_port), ("prototype proxy", args.proxy_port)):
        rows = []
        for label, host, origin, expected in cases:
            h = host.format(p=port_attr) if host else None
            o = origin.format(p=port_attr) if origin else None
            status = request(port_attr, h, o)
            rows.append({"case": label, "host": h, "origin": o, "status": status,
                         "expected": expected, "ok": status == expected})
        out["targets"].append({"name": name, "port": port_attr, "cases": rows,
                               "ok": all(r["ok"] for r in rows)})
    out["ok"] = all(t["ok"] for t in out["targets"])
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
