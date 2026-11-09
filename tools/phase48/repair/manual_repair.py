# Phase 4.8 Closeout S5: staged interactive-repair harness.
#
# `init`    resets the isolated test install, silently installs the base
#           bundle and seeds user-state sentinels.
# `start`   applies the scenario damage, records the before state, and opens
#           the interactive wizard. The UI is driven through Computer Use; the
#           harness never launches the production installer.
# `verify`  runs after the wizard closes: compares program-file hashes with the
#           bundle, checks user data and market.db are byte-identical, starts
#           the repaired app on port 8158 and probes /healthz, then judges.
# `_wait`   internal: records the setup exit code and waits for the test setup
#           processes to finish.
#
# Tracked copy: paths come from repair_helpers.py (PHASE48_REPAIR_* overrides).
import json
import os
import re
import subprocess
import sys
import time
import winreg

import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repair_helpers as h  # noqa: E402

BASE = h.BASE
EVID = h.EVID
STATE = os.path.join(BASE, "manual-state.json")
SETUP_NAME_PREFIX = "BorsTerminal_RepairTest_Setup"
LABELS = ["healthy", "deleted_file", "corrupted_frontend"]


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))


def test_setup_pids():
    pids = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = p.info.get("name") or ""
            if name.startswith(SETUP_NAME_PREFIX):
                pids.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def delete_test_registry_if_sandbox():
    """Only the unique test AppId may be removed, and only when its recorded
    install location is inside the test sandbox. Any other location aborts."""
    for root_name, root in (("HKCU", winreg.HKEY_CURRENT_USER),
                            ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        try:
            key = winreg.OpenKey(root, h.REG_PATH)
        except FileNotFoundError:
            continue
        try:
            loc, _ = winreg.QueryValueEx(key, "InstallLocation")
        finally:
            key.Close()
        inside = os.path.normcase(os.path.abspath((loc or "").rstrip("\\/"))) == os.path.normcase(
            os.path.abspath(h.SANDBOX))
        if not inside:
            raise SystemExit(f"refusing: test AppId registered at {root_name} outside sandbox: {loc}")
        if root_name == "HKLM":
            # The test installer is per-user; a machine-wide key is never ours.
            raise SystemExit("refusing: test AppId exists under HKLM; manual review required")
        winreg.DeleteKey(root, h.REG_PATH)
        return {"deleted": f"{root_name}\\{h.REG_PATH}", "location": loc}
    return None


def cmd_init():
    log("stopping test setup processes")
    for pid in test_setup_pids():
        h.stop_pid(pid, tree=True)
    h.stop_sandbox()
    reg = h.reg_location()
    cleanup = {"before": reg}
    if reg:
        unins = os.path.join(h.SANDBOX, "unins000.exe")
        if os.path.exists(unins):
            log("running the sandbox uninstaller")
            subprocess.run([unins, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                           capture_output=True, timeout=600)
        cleanup["uninstaller_ran"] = os.path.exists(unins)
        cleanup["registry_deleted"] = delete_test_registry_if_sandbox()
    if os.path.isdir(h.SANDBOX):
        for _ in range(20):
            try:
                import shutil
                shutil.rmtree(h.SANDBOX)
                break
            except PermissionError:
                time.sleep(0.5)
    os.makedirs(h.SANDBOX, exist_ok=True)
    if test_setup_pids():
        raise SystemExit("test setup processes are still running; aborting")
    base = {"cleanup": cleanup, "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    base["install"] = h.run_setup(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                                   "/CURRENTUSER", "/NOICONS", "/LANG=english",
                                   "/DIR=" + h.SANDBOX,
                                   "/LOG=" + os.path.join(BASE, "setup-base.log")])
    base["files"] = {rel: os.path.exists(os.path.join(h.SANDBOX, rel))
                     for rel in h.PROGRAM_FILES + ["market.db", "unins000.exe"]}
    base["registry"] = h.reg_location()
    if base["install"]["rc"] != 0 or not all(base["files"][rel] for rel in h.PROGRAM_FILES):
        base["status"] = "FAIL"
        json.dump(base, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        out({"init": "FAIL", "base": base})
        return 1
    h.seed_user_data()
    base["bundle_hashes"] = h.bundle_hashes()
    base["base_state"] = h.state()
    base["setup_sha256"] = h.sha(h.SETUP)
    base["setup_size"] = os.path.getsize(h.SETUP)
    base["iss_sha256"] = h.sha(h.ISS)
    base["status"] = "PASS"
    json.dump(base, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    out({"init": "PASS", "files": base["files"], "registry": base["registry"]})
    return 0


def cmd_start(label):
    if label not in LABELS:
        raise SystemExit("unknown label: " + label)
    base = json.load(open(STATE, encoding="utf-8"))
    if base.get("status") != "PASS":
        raise SystemExit("base install is not PASS; run init")
    exe = os.path.join(h.SANDBOX, "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe) or not os.path.exists(os.path.join(h.SANDBOX, "frontend/index.html")):
        raise SystemExit("sandbox install is incomplete; run init")
    if test_setup_pids():
        raise SystemExit("a test setup process is already running")
    sc = {"label": label, "damage": None, "bundle_hashes": base["bundle_hashes"]}
    if label == "deleted_file":
        pre = h.sha(exe)
        os.remove(exe)
        sc["damage"] = {"file": "BorsTerminal_Ultimate.exe", "action": "delete",
                        "pre_sha": pre, "bundle_sha": base["bundle_hashes"]["BorsTerminal_Ultimate.exe"],
                        "missing_after_damage": not os.path.exists(exe)}
    elif label == "corrupted_frontend":
        path = os.path.join(h.SANDBOX, "frontend/index.html")
        pre = h.sha(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write("<!doctype html><title>PHASE48 CORRUPTED FRONTEND</title>")
        sc["damage"] = {"file": "frontend/index.html", "action": "corrupt",
                        "pre_sha": pre, "corrupt_sha": h.sha(path),
                        "bundle_sha": base["bundle_hashes"]["frontend/index.html"]}
    sc["before"] = h.state()
    sc["installed_before"] = h.installed_hashes()
    log_path = os.path.join(BASE, f"setup-{label}.log")
    for old in (log_path, os.path.join(BASE, f"rc-{label}.json")):
        try:
            os.remove(old)
        except OSError:
            pass
    args = [h.SETUP, "/LANG=english", "/CURRENTUSER", "/NOICONS", f"/LOG={log_path}"]
    logf = open(os.path.join(BASE, f"setup-{label}.stdout.log"), "wb")
    p = subprocess.Popen(args, cwd=BASE, stdin=subprocess.DEVNULL, stdout=logf,
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    sc["setup_pid"] = p.pid
    sc["setup_log"] = log_path
    sc["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(sc, open(os.path.join(BASE, f"scenario-{label}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    waiter = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_wait", label, str(p.pid)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    out({"start": label, "pid": p.pid, "waiter_pid": waiter.pid,
         "damage": sc["damage"], "log": log_path,
         "message": f"READY {label}: drive the wizard with Computer Use"})
    return 0


def cmd_wait(label, pid):
    pid = int(pid)
    rc = None
    try:
        rc = psutil.Process(pid).wait(timeout=1800)
    except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
        rc = None
    deadline = time.time() + 600
    while time.time() < deadline:
        if not test_setup_pids():
            break
        time.sleep(0.5)
    payload = {"label": label, "pid": pid, "rc": rc,
               "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "leftover_test_setup_pids": test_setup_pids()}
    json.dump(payload, open(os.path.join(BASE, f"rc-{label}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


def judge(label, sc):
    u = sc.get("uia") or {}
    pages = u.get("pages") or {}
    maint = pages.get("maintenance") or {}
    opts = maint.get("options") or []
    chosen = (pages.get("directory") or {}).get("chosen")
    checks = {
        "ui_source_computer_use": u.get("source") == "computer-use" and bool(u.get("ok")),
        "setup_finished": (sc.get("setup_rc") == 0) or sc.get("setup_log_succeeded"),
        "four_options": len(opts) == 4,
        "repair_option_first": bool(opts) and opts[0].get("name") == h.REPAIR_LABEL,
        "repair_option_selected": bool(opts) and opts[0].get("selected") is True,
        "directory_is_sandbox": bool(chosen) and os.path.normcase(
            os.path.abspath(chosen.rstrip("\\/"))) == os.path.normcase(os.path.abspath(h.SANDBOX)),
        "user_data_unchanged": not sc.get("user_diff"),
        "sentinels_intact": all(sc.get("after", {}).get(k) for k in
                                ("user_sentinel", "oc_sentinel", "market_sentinel")),
        "market_db_unchanged": sc.get("market_db_unchanged") is True,
        "program_files_restored": sc.get("files_match_bundle") is True,
        "app_health": bool((sc.get("app") or {}).get("health")),
    }
    sc["checks"] = checks
    sc["reasons"] = [k for k, v in checks.items() if not v]
    sc["status"] = "PASS" if not sc["reasons"] else "FAIL"
    return sc["status"]


def cmd_verify(label):
    if label not in LABELS:
        raise SystemExit("unknown label: " + label)
    if test_setup_pids():
        out({"verify": label, "status": "STILL_RUNNING", "pids": test_setup_pids()})
        return 2
    sc = json.load(open(os.path.join(BASE, f"scenario-{label}.json"), encoding="utf-8"))
    rc_path = os.path.join(BASE, f"rc-{label}.json")
    wait = json.load(open(rc_path, encoding="utf-8")) if os.path.exists(rc_path) else {}
    sc["setup_rc"] = wait.get("rc")
    sc["waiter"] = wait
    log_path = sc.get("setup_log")
    log_text = ""
    if log_path and os.path.exists(log_path):
        log_text = open(log_path, "rb").read().decode("utf-8", "replace")
    sc["setup_log_succeeded"] = "Installation process succeeded." in log_text
    sc["setup_log_closed"] = "Log closed." in log_text
    sc["setup_log_tail"] = log_text[-1500:]
    ui_path = os.path.join(BASE, f"manual-ui-{label}.json")
    sc["uia"] = json.load(open(ui_path, encoding="utf-8")) if os.path.exists(ui_path) else {}
    sc["after"] = h.state()
    sc["user_diff"] = h.diff_state(sc["before"], sc["after"])
    sc["installed_after"] = h.installed_hashes()
    sc["files_match_bundle"] = all(sc["installed_after"][rel] == sc["bundle_hashes"][rel]
                                   for rel in h.PROGRAM_FILES)
    sc["market_db_unchanged"] = sc["before"]["market.db"] == sc["after"]["market.db"]
    sc["app"] = h.app_check(label)
    sc["status"] = judge(label, sc)
    ev = {}
    if os.path.exists(EVID):
        try:
            ev = json.load(open(EVID, encoding="utf-8"))
        except Exception:
            ev = {}
    ev.setdefault("meta", {}).update({
        "sandbox": h.SANDBOX, "setup": h.SETUP, "bundle": h.BUNDLE,
        "appid": h.TEST_APPID, "port": h.PORT,
        "ui_driver": "computer-use (ComputerUse SDK)",
        "test_iss": h.ISS,
    })
    ev.setdefault("scenarios", {})[label] = sc
    failures = [k for k, v in ev["scenarios"].items() if v.get("status") != "PASS"]
    ev["summary"] = {"scenarios": len(ev["scenarios"]), "failures": failures,
                     "pass": len(ev["scenarios"]) - len(failures)}
    json.dump(ev, open(EVID, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    out({"verify": label, "status": sc["status"], "reasons": sc["reasons"],
         "checks": sc["checks"], "summary": ev["summary"]})
    return 0 if sc["status"] == "PASS" else 1


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: manual_repair.py init|start <label>|verify <label>|_wait <label> <pid>")
    cmd = argv[1]
    if cmd == "init":
        return cmd_init()
    if cmd == "start":
        return cmd_start(argv[2])
    if cmd == "verify":
        return cmd_verify(argv[2])
    if cmd == "_wait":
        return cmd_wait(argv[2], argv[3])
    raise SystemExit("unknown command: " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
