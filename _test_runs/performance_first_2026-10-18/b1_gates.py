# -*- coding: utf-8 -*-
# B1: باتریِ کامل + گیت‌هایِ فرانت، پشتِ‌سرِ‌هم (هرگز هم‌زمان)، هر کدام لاگِ .txt و rcِ خودش.
# پیش‌شرط: هیچ ریگِ من بالا نیست (پورتِ 8020 آزاد). سرویس‌هایِ مأموریت‌هایِ دیگر فقط ثبت می‌شوند، نه متوقف.
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
FE = os.path.join(WT, "frontend")
FIX = os.path.join(WT, "dev", "fixtures", "fts_v10_payloads.json")
FIX_BAK = os.path.join(HERE, "b1-backup", "fts_v10_payloads.json")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1")

STEPS = [
    ("run_all_tests", [sys.executable, "dev/run_all_tests.py"], WT, 5400),
    ("version_anchor_guard", [sys.executable, "dev/version_anchor_guard.py"], WT, 600),
    ("npm-ci", ["npm.cmd", "ci"], FE, 1800),
    ("tsc", ["npx.cmd", "tsc", "-b"], FE, 1200),
    ("vitest", ["npx.cmd", "vitest", "run"], FE, 2400),
    ("build", ["npm.cmd", "run", "build"], FE, 1200),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def port_open(port):
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def app_processes():
    q = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|py|node)\\.exe$' -and "
         "$_.CommandLine -match 'app:app|app\\.py|bors_entry|vite|run_all_tests' } | "
         "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate)|$($_.CommandLine)\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return [x for x in r.stdout.splitlines() if x.strip()]


def main():
    only = sys.argv[1:]
    tag = os.environ.get("GATES_TAG", "b1")
    out_path = os.path.join(HERE, "%s-gates.json" % tag)
    res = json.load(open(out_path, encoding="utf-8")) if only and os.path.exists(out_path) else {}
    res.setdefault("pre", {})
    res["pre"][time.strftime("%Y-%m-%d %H:%M:%S")] = {
        "port_8020_open": port_open(8020), "port_8123_open": port_open(8123),
        "port_8000_open": port_open(8000), "port_8010_open": port_open(8010),
        "app_processes": app_processes()}
    if port_open(8020):
        print("ABORT: :8020 (ریگِ من) هنوز بالاست")
        return 2
    os.makedirs(os.path.dirname(FIX_BAK), exist_ok=True)
    if not os.path.exists(FIX_BAK):
        shutil.copy2(FIX, FIX_BAK)
    res["fixture_sha_backup"] = sha(FIX_BAK)
    # باتری (`test_screener_funnel_gate_v1`) رویِ market.dbِ worktree می‌نویسد؛ پیش و پس ثبت و برگردانده می‌شود.
    db = os.path.join(WT, "market.db")
    db_bak = os.path.join(HERE, "%s-backup" % tag, "market.db")
    os.makedirs(os.path.dirname(db_bak), exist_ok=True)
    shutil.copyfile(db, db_bak)
    res["market_db_sha_before"] = sha(db)
    assert sha(db_bak) == res["market_db_sha_before"]
    res["src_sha256"] = {f: sha(os.path.join(WT, f)) for f in (
        "api/funnel.py", "app.py", "dev/run_all_tests.py", "dev/test_funnel_warm_deadlock_v1.py",
        "dev/funnel_body_cache_v1.py", "frontend/src/shared/lib/feedFreshness.ts",
        "frontend/src/shared/components/FreshnessBadge.tsx",
        "frontend/src/features/market/components/MarketStatusPanel.tsx")}
    res.setdefault("steps", {})
    for name, cmd, cwd, tmo in STEPS:
        if only and name not in only:
            continue
        log = os.path.join(HERE, "%s-%s.txt" % (tag, name))
        t0 = time.time()
        with open(log, "w", encoding="utf-8") as fh:
            fh.write("$ (cwd=%s) %s\n" % (os.path.relpath(cwd, WT) or ".", " ".join(cmd)))
            fh.flush()
            try:
                rc = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, env=ENV, timeout=tmo).returncode
            except subprocess.TimeoutExpired:
                rc = "TIMEOUT"
            fh.write("\nEXIT=%s\n" % rc)
        res["steps"][name] = {"cmd": " ".join(cmd), "cwd": os.path.relpath(cwd, WT), "rc": rc,
                              "start": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
                              "dur_s": round(time.time() - t0, 1), "log": os.path.basename(log)}
        print(name, rc, res["steps"][name]["dur_s"], flush=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    after = sha(FIX)
    res["fixture_sha_after_gates"] = after
    if after != res["fixture_sha_backup"]:
        shutil.copy2(FIX_BAK, FIX)
    res["fixture_sha_after_restore"] = sha(FIX)
    res["fixture_restored_ok"] = res["fixture_sha_after_restore"] == res["fixture_sha_backup"]
    res["market_db_sha_after_gates"] = sha(db)
    if res["market_db_sha_after_gates"] != res["market_db_sha_before"]:
        for suf in ("-wal", "-shm"):
            if os.path.exists(db + suf):
                os.remove(db + suf)
        shutil.copyfile(db_bak, db)
    res["market_db_sha_after_restore"] = sha(db)
    res["market_db_restored_ok"] = res["market_db_sha_after_restore"] == res["market_db_sha_before"]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("fixture", res["fixture_sha_backup"][:12], after[:12], res["fixture_restored_ok"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
