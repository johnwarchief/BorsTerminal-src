"""Restart-safety proof on the *frozen* package (mission 2026-10-18, stage five).

Runs one phase against a running packaged app and reports (a) what the four
connection endpoints say, and (b) whether the packaged process holds any
non-loopback TCP peer at that moment — the cheap, honest version of "nothing
went out to the broker".

phases:
  save-config    POST /config {adapter:easytrader, read_only:true}  (writes to
                 THIS build's own data dir; needs a restart to take effect)
  after-restart  first words of the fresh process: status + config + portfolio
  with-token     POST a probe session address, then status + portfolio
  cleared        DELETE the address, then status

usage: python tools/frozen_readonly_restart_proof_1018.py <port> <phase> <pid>
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.request

PORT, PHASE, PID = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "")


def req(path: str, payload=None, method="GET"):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    r = urllib.request.Request("http://127.0.0.1:%s%s" % (PORT, path), data=data,
                              method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=25) as res:
        return res.status, json.loads(res.read().decode("utf-8"))


BROKER_HOSTS = ("api-mts.orbis.easytrader.ir", "d.easytrader.ir", "account.emofid.com",
                "login.emofid.com", "mts.tradersarena.ir")
MARKET_HOSTS = ("www.tsetmc.com", "tsetmc.com", "cdn.tsetmc.com", "codal.ir",
                "www.codal.ir", "github.com", "objects.githubusercontent.com",
                "api.github.com")


def classify(remote: str) -> str:
    """Which known group does this peer belong to? (resolved once, at call time)"""
    ip = remote.split(":")[0]
    for group, names in (("broker", BROKER_HOSTS), ("market/reference", MARKET_HOSTS)):
        for h in names:
            try:
                if socket.gethostbyname(h) == ip:
                    return group + ":" + h
            except (socket.gaierror, OSError):
                continue
    return "unknown"


def outbound(pid: str):
    """Remote TCP peers of this PID that are not loopback."""
    if not pid:
        return {"skipped": True}
    out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                        text=True, timeout=30).stdout
    peers = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-1] == pid:
            local, remote, state = parts[1], parts[2], parts[3]
            if remote.startswith(("127.", "[::1]", "0.0.0.0")) or local.startswith("127."):
                continue
            peers.append({"remote": remote, "state": state, "who": classify(remote)})
    return {"non_loopback_peers": len(peers),
            "broker_peers": len([p for p in peers if p["who"].startswith("broker")]),
            "peers": peers[:10]}


def digest(body: dict) -> dict:
    sess = body.get("session") or {}
    return {
        "adapter": body.get("adapter"), "live_enabled": body.get("live_enabled"),
        "read_only": body.get("read_only"), "traffic_allowed": body.get("traffic_allowed"),
        "session_live": body.get("session_live"), "dry_run": body.get("dry_run"),
        "session_state": sess.get("state"), "session_origin": sess.get("origin"),
        "proven": sess.get("proven"), "verified_by": sess.get("verified_by"),
        "blocked_on": body.get("blocked_on"),
        "capabilities_place": (body.get("capabilities") or {}).get("place"),
        "capabilities_balances": (body.get("capabilities") or {}).get("balances"),
    }


PROBE_TOKEN = "BORS-FROZEN-PROBE-NOT-A-REAL-SESSION"
report: dict = {"phase": PHASE, "port": PORT, "pid": PID}

if PHASE == "save-config":
    code, body = req("/api/execution/config",
                     {"adapter": "easytrader", "read_only": True}, method="POST")
    report["config_post"] = {"http": code, "status": body.get("status"),
                             "stored": body.get("stored"), "effective": body.get("effective"),
                             "applies_on_restart": body.get("applies_on_restart"),
                             "applied_now": body.get("applied_now"),
                             "secrets_stored": body.get("secrets_stored")}
elif PHASE in ("after-restart", "cleared"):
    code, status = req("/api/execution/status")
    report["status"] = digest(status)
    code2, pf = req("/api/execution/portfolio")
    report["portfolio"] = {"http": code2, "status": pf.get("status"), "rows": pf.get("rows"),
                           "as_of": pf.get("as_of"), "session_proven": pf.get("session_proven"),
                           "error": (pf.get("error") or "")[:160]}
    if PHASE == "cleared":
        code3, dele = req("/api/execution/session", None, method="DELETE")
        report["delete"] = {"http": code3, "status": dele.get("status"),
                            "session": dele.get("session"),
                            "echoes_token": PROBE_TOKEN in json.dumps(dele)}
        code4, status2 = req("/api/execution/status")
        report["status_after_delete"] = digest(status2)
elif PHASE == "with-token":
    code, sess = req("/api/execution/session", {"token": PROBE_TOKEN}, method="POST")
    report["session_post"] = {"http": code, "status": sess.get("status"),
                              "code": sess.get("code"),
                              "detail": (sess.get("detail") or "")[:200],
                              "confirmations_voided": sess.get("confirmations_voided"),
                              "session": sess.get("session"),
                              "echoes_token": PROBE_TOKEN in json.dumps(sess)}
    code2, status = req("/api/execution/status")
    report["status"] = digest(status)
    code3, pf = req("/api/execution/portfolio")
    report["portfolio"] = {"http": code3, "status": pf.get("status"), "rows": pf.get("rows"),
                           "as_of": pf.get("as_of"), "session_proven": pf.get("session_proven"),
                           "error": (pf.get("error") or "")[:160]}
else:
    report["error"] = "unknown phase"

report["network"] = outbound(PID)
print(json.dumps(report, ensure_ascii=False, indent=1))
