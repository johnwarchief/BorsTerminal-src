# Phase 4.8 Closeout S5 — helpers for the interactive repair harness.
#
# This is the tracked copy of the module that produced repair-evidence.json;
# the working wizard is driven by Computer Use through manual_repair.py. The
# abandoned PowerShell-UIA attempt stayed in the gitignored
# _audit/phase48closeout/repair/ tree and is not part of this module.
#
# The production installer is never launched. The test installer has its own
# AppId, its own registry key, a sandbox install directory, no password, no
# [Run]/[Icons]/[Tasks], and its cross-install helpers exit before taskkill or
# DelTree. Real installs, the real registry key and the operational DB are not
# on any code path here.
#
# Paths: ROOT is derived from this file; BASE/BUNDLE/SETUP can be overridden
# with PHASE48_REPAIR_BASE / PHASE48_REPAIR_BUNDLE / PHASE48_REPAIR_SETUP.
import hashlib
import json
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import winreg

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASE = os.environ.get("PHASE48_REPAIR_BASE") or os.path.join(
    ROOT, "_audit", "phase48closeout", "repair")
ISS = os.path.join(BASE, "bors_setup_repairtest.iss")
OUT = os.path.join(BASE, "out")


def _app_version():
    txt = open(os.path.join(ROOT, "bors_config.py"), encoding="utf-8", errors="replace").read()
    m = re.search(r"APP_VERSION\s*=\s*['\"]([^'\"]+)", txt)
    return m.group(1) if m else "0.0.0"


SETUP = os.environ.get("PHASE48_REPAIR_SETUP") or os.path.join(
    OUT, "BorsTerminal_RepairTest_Setup_v%s.exe" % _app_version())
BUNDLE = os.environ.get("PHASE48_REPAIR_BUNDLE") or os.path.join(
    ROOT, "_audit", "phase48closeout", "installer", "bundle")
SANDBOX = os.path.join(os.environ["LOCALAPPDATA"], "BorsTerminal_Phase48RepairTest", "app")
DRIVER = os.path.join(BASE, "drive_repair.ps1")
EVID = os.path.join(BASE, "repair-evidence.json")
PORT = 8158
TOKEN = os.environ.get("PHASE48_REPAIR_TOKEN") or secrets.token_hex(16)
TEST_APPID = "C3D84F60-2A19-4E7B-8C55-6F9A1B2D3E40"
REG_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{%s}_is1" % TEST_APPID
REPAIR_LABEL = "نصبِ مجدد / تعمیر فایلها در همان مسیر (توصیه‌شده)"

PROGRAM_FILES = ["BorsTerminal_Ultimate.exe", "BorsTerminal_Shell.exe",
                 "frontend/index.html", "apply_update.bat"]
USER_FILES = ["user.db", "oc/oc_client.db", "fts_thresholds.json",
              ".screener_cache.json", "price_basis.json"]

EV = {"meta": {"sandbox": SANDBOX, "setup": SETUP, "bundle": BUNDLE,
               "appid": TEST_APPID, "port": PORT}, "scenarios": {}}


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def pids_in(path):
    out = []
    root = os.path.normcase(os.path.abspath(path)) + os.sep
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            exe = p.info.get("exe") or ""
            if exe and os.path.normcase(exe).startswith(root):
                out.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def stop_pid(pid, tree=False):
    try:
        p = psutil.Process(pid)
        if tree:
            for c in p.children(recursive=True):
                try:
                    c.terminate()
                except psutil.NoSuchProcess:
                    pass
        p.terminate()
        try:
            p.wait(timeout=15)
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=15)
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def stop_sandbox():
    killed = []
    for pid in pids_in(SANDBOX):
        if stop_pid(pid, tree=True):
            killed.append(pid)
    return killed


def reg_location():
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            key = winreg.OpenKey(root, REG_PATH)
        except FileNotFoundError:
            continue
        try:
            loc, _ = winreg.QueryValueEx(key, "InstallLocation")
            return {"root": "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM",
                    "location": loc}
        finally:
            key.Close()
    return None


def run_setup(args, timeout=900):
    t0 = time.time()
    p = subprocess.run([SETUP] + list(args), capture_output=True, text=True,
                       timeout=timeout)
    return {"rc": p.returncode, "seconds": round(time.time() - t0, 2),
            "stdout_tail": p.stdout[-500:], "stderr_tail": p.stderr[-500:]}


def seed_user_data():
    for rel, value in (("user.db", "user-db-v1"), ("oc/oc_client.db", "oc-db-v1")):
        path = os.path.join(SANDBOX, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        con = sqlite3.connect(path)
        con.execute("create table if not exists phase48_repair_sentinel(v text)")
        con.execute("insert into phase48_repair_sentinel values (?)", (value,))
        con.commit()
        con.close()
    con = sqlite3.connect(os.path.join(SANDBOX, "market.db"))
    con.execute("create table if not exists phase48_repair_sentinel(v text)")
    con.execute("insert into phase48_repair_sentinel values ('market-db-v1')")
    con.commit()
    con.close()
    open(os.path.join(SANDBOX, "fts_thresholds.json"), "w", encoding="utf-8").write(
        '{"sentinel":"fts-v1"}\n')
    open(os.path.join(SANDBOX, ".screener_cache.json"), "w", encoding="utf-8").write(
        '{"sentinel":"cache-v1"}\n')
    open(os.path.join(SANDBOX, "price_basis.json"), "w", encoding="utf-8").write(
        '{"sentinel":"basis-v1"}\n')


def sentinel(db, value):
    try:
        con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
        try:
            row = con.execute("select count(*) from phase48_repair_sentinel where v=?",
                              (value,)).fetchone()
            return bool(row and row[0] == 1)
        finally:
            con.close()
    except sqlite3.Error:
        return False


def state():
    st = {}
    for rel in USER_FILES:
        p = os.path.join(SANDBOX, rel)
        st[rel] = sha(p) if os.path.exists(p) else None
    st["market.db"] = sha(os.path.join(SANDBOX, "market.db"))
    st["user_sentinel"] = sentinel(os.path.join(SANDBOX, "user.db"), "user-db-v1")
    st["oc_sentinel"] = sentinel(os.path.join(SANDBOX, "oc/oc_client.db"), "oc-db-v1")
    st["market_sentinel"] = sentinel(os.path.join(SANDBOX, "market.db"), "market-db-v1")
    return st


def diff_state(before, after):
    return {k: [before.get(k), after.get(k)] for k in before if before.get(k) != after.get(k)}


def bundle_hashes():
    return {rel: sha(os.path.join(BUNDLE, rel)) for rel in PROGRAM_FILES}


def installed_hashes():
    return {rel: sha(os.path.join(SANDBOX, rel)) if os.path.exists(os.path.join(SANDBOX, rel)) else None
            for rel in PROGRAM_FILES}


def start_app(log_path):
    exe = os.path.join(SANDBOX, "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        return None, None, "exe missing"
    env = dict(os.environ)
    env["BORS_API_TOKEN"] = TOKEN
    env["BORS_DATA_DIR"] = SANDBOX
    logf = open(log_path, "wb")
    p = subprocess.Popen([exe, "--port", str(PORT), "--no-shell", "--no-loops",
                          "--db-dir", SANDBOX],
                         cwd=SANDBOX, env=env, stdout=logf, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    return p, logf, None


def wait_health(timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(0.5)
    return None


def api_get(path, timeout=120):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}",
                                 headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return {"status": r.status, "bytes": len(raw)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def app_check(label):
    log_path = os.path.join(BASE, f"app-{label}.log")
    p, logf, err = start_app(log_path)
    res = {"started": p is not None, "pid": p.pid if p else None}
    if err:
        res["error"] = err
        return res
    h = wait_health()
    res["health"] = h
    if h:
        res["ma"] = api_get("/api/ma/" + urllib.parse.quote("فولاد"))
        res["market"] = api_get("/api/market")
    else:
        res["log_tail"] = open(log_path, "rb").read()[-2000:].decode("utf-8", "replace")
    try:
        logf.close()
    except Exception:
        pass
    if p and p.poll() is None:
        res["stopped"] = stop_pid(p.pid, tree=True)
    else:
        res["stopped"] = False
        res["early_exit"] = p.returncode if p else None
    time.sleep(1)
    res["leftover_pids"] = pids_in(SANDBOX)
    return res


