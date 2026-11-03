"""Stage-five proof for the frozen desktop package (mission 2026-10-18).

Three questions, answered with evidence rather than with "the code exists":

  1. PROVENANCE — is the SPA inside this bundle the one built from this tree, and
     does it carry the new connection UI? (sha256 of the content-hashed entry
     chunk + a testid grep inside the shipped JS)
  2. PACKAGING — is `execution_settings` really frozen in? (the module list that
     PyInstaller wrote, plus the live `/api/execution/status`, which imports it)
  3. SAFE MODE — what do the four connection endpoints answer on the *package*
     itself, in the order the owner asked for: status, settings, session, restart.

Nothing here sends anything to a broker: every request goes to 127.0.0.1. The
token posted is a probe string, and the script checks it never comes back.

usage:  python tools/frozen_build_check_1018.py <port> <bundle_dir>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8111"
BUNDLE = sys.argv[2] if len(sys.argv) > 2 else r"dist\BorsTerminal_Ultimate"
SPA_DIST = os.path.join(BUNDLE, "_internal", "frontend", "dist")
SRC_DIST = os.path.join("frontend", "dist")
PROBE_TOKEN = "BORS-FROZEN-PROBE-NOT-A-REAL-SESSION"
NEW_UI_IDS = ["sarkhati-token-input", "sarkhati-token-save", "sarkhati-token-clear",
              "sarkhati-gate-", "sarkhati-state-ladder", "sarkhati-session-note"]


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def get(path: str):
    with urllib.request.urlopen("http://127.0.0.1:%s%s" % (PORT, path), timeout=25) as r:
        return r.status, r.headers.get("content-type"), json.loads(r.read().decode("utf-8"))


def post(path: str, payload=None, method="POST"):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:%s%s" % (PORT, path), data=data,
                                 method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_http_error": True}


def entry_chunk(d: str):
    for name in os.listdir(os.path.join(d, "assets")):
        if name.startswith("index-") and name.endswith(".js"):
            return name
    return None


out: dict = {"port": PORT, "bundle": BUNDLE}

# 1) PROVENANCE -----------------------------------------------------------------
src_chunk, pkg_chunk = entry_chunk(SRC_DIST), entry_chunk(SPA_DIST)
out["provenance"] = {
    "source_entry": src_chunk,
    "packaged_entry": pkg_chunk,
    "same_filename": src_chunk == pkg_chunk,
    "source_sha256": sha(os.path.join(SRC_DIST, "assets", src_chunk)) if src_chunk else None,
    "packaged_sha256": sha(os.path.join(SPA_DIST, "assets", pkg_chunk)) if pkg_chunk else None,
}
out["provenance"]["byte_identical"] = (
    out["provenance"]["source_sha256"] == out["provenance"]["packaged_sha256"])

js_path = os.path.join(SPA_DIST, "assets", pkg_chunk) if pkg_chunk else None
if js_path:
    # رابطِ تبِّ سرخطی درِ chunkِ تنبل (lazy) می‌نشیند، نه درِ ورودیِ index؛ پس
    # نشانه‌ها درِ *همه*یِ chunkها جست‌وجو می‌شوند. بی‌این، بسته‌ای سالم «بی‌UI»
    # خوانده می‌شد.
    assets = os.path.join(SPA_DIST, "assets")
    blob = "".join(open(os.path.join(assets, n), encoding="utf-8", errors="replace").read()
                   for n in os.listdir(assets) if n.endswith(".js"))
    out["packaged_ui_markers"] = {i: (i in blob) for i in NEW_UI_IDS}
    out["packaged_js_chunks"] = len([n for n in os.listdir(assets) if n.endswith(".js")])
    out["packaged_blob_bytes"] = len(blob)
else:
    out["packaged_ui_markers"] = "no packaged entry chunk"

# 2) PACKAGING ------------------------------------------------------------------
toc = os.path.join("build", "fts_terminal", "PYZ-00.toc")
if os.path.exists(toc):
    text = open(toc, encoding="utf-8", errors="replace").read()
    out["hiddenimports_in_bundle"] = {
        m: bool(re.search(r"['\"]%s['\"]\s*," % m, text))
        for m in ("execution_settings", "execution_easytrader", "execution_connect",
                  "execution_contract", "execution_ledger", "funnel_engine")}
else:
    out["hiddenimports_in_bundle"] = "PYZ-00.toc absent"

# 3) SAFE MODE, in the owner's order -------------------------------------------
st_code, st_ct, status = get("/api/execution/status")
out["first_status"] = {
    "http": st_code, "content_type": st_ct,
    "adapter": status.get("adapter"), "dry_run": status.get("dry_run"),
    "live_enabled": status.get("live_enabled"), "read_only": status.get("read_only"),
    "traffic_allowed": status.get("traffic_allowed"),
    "session": status.get("session"), "blocked_on": status.get("blocked_on"),
}
cfg_code, _ct, cfg = get("/api/execution/config")
out["config"] = {"http": cfg_code, "stored": cfg.get("stored"),
                 "effective": cfg.get("effective"),
                 "applies_on_restart": cfg.get("applies_on_restart"),
                 "secrets_stored": cfg.get("secrets_stored")}
p1_code, _ct, pf1 = get("/api/execution/portfolio")
out["portfolio_before_session"] = {"http": p1_code, "status": pf1.get("status"),
                                  "rows": pf1.get("rows"), "as_of": pf1.get("as_of"),
                                  "error": (pf1.get("error") or "")[:150]}
s_code, s_body = post("/api/execution/session", {"token": PROBE_TOKEN})
out["session_post"] = {"http": s_code, "status": s_body.get("status"),
                       "code": s_body.get("code"),
                       "detail": (s_body.get("detail") or "")[:150],
                       "echoes_token": PROBE_TOKEN in json.dumps(s_body)}
p2_code, _ct, pf2 = get("/api/execution/portfolio")
out["portfolio_after_session_attempt"] = {"http": p2_code, "status": pf2.get("status"),
                                          "rows": pf2.get("rows"),
                                          "error": (pf2.get("error") or "")[:150]}
d_code, d_body = post("/api/execution/session", None, method="DELETE")
out["session_delete"] = {"http": d_code, "status": d_body.get("status"),
                         "confirmations_voided": d_body.get("confirmations_voided"),
                         "session_state": (d_body.get("session") or {}).get("state"),
                         "proven": (d_body.get("session") or {}).get("proven"),
                         "echoes_token": PROBE_TOKEN in json.dumps(d_body)}
_v_code, _v_ct, ver = get("/api/update/version")
out["build_identity"] = {"http": _v_code, "version": ver.get("version"),
                        "mode": ver.get("mode"), "instance": ver.get("instance")}

print(json.dumps(out, ensure_ascii=False, indent=1))
