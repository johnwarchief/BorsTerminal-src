# -*- coding: utf-8 -*-
"""Watch the patch apply: PID churn, cmd/bat workers, and install-dir mtimes."""
import os
import subprocess
import sys
import time

INSTALL = os.environ.get(
    "BORS_INSTALL_DIR",
    r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate")
TRACK = ["Version.txt", "apply_update.bat", "BorsTerminal_Update.zip",
         os.path.join("_internal", "api", "chart.py"),
         os.path.join("_internal", "frontend", "dist", "index.html"),
         "BorsTerminal_Ultimate.exe", "user.db", ".screener_cache.json"]


def q(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=25, encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    except Exception:
        return ""


def pids(image):
    out = q('tasklist /FI "IMAGENAME eq %s" /FO CSV /NH' % image)
    ids = []
    for line in out.splitlines():
        parts = line.replace('"', "").split(",")
        if len(parts) >= 2 and parts[0].lower() == image.lower():
            ids.append(parts[1])
    return ids


def stamp(rel):
    p = os.path.join(INSTALL, rel)
    if not os.path.isfile(p):
        return "ABSENT"
    st = os.stat(p)
    return "%10d %s" % (st.st_size, time.strftime("%H:%M:%S", time.localtime(st.st_mtime)))


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    t0 = time.time()
    seen_app = set(pids("BorsTerminal_Ultimate.exe"))
    base = {r: stamp(r) for r in TRACK}
    for r in TRACK:
        print("  base %-46s %s" % (r, base[r]), flush=True)
    while time.time() - t0 < seconds:
        now_app = set(pids("BorsTerminal_Ultimate.exe"))
        cmds = pids("cmd.exe")
        line = []
        if now_app != seen_app:
            line.append("APP %s->%s" % (",".join(sorted(seen_app)) or "-",
                                        ",".join(sorted(now_app)) or "-"))
            seen_app = now_app
        changed = [r for r in TRACK if stamp(r) != base[r]]
        if changed:
            line.append("MOVED:" + ",".join(changed))
            for r in changed:
                base[r] = stamp(r)
        if line:
            print("[%6.1fs] %s   [cmd:%s]" % (time.time() - t0, " ".join(line),
                                              ",".join(cmds) or "-"), flush=True)
        time.sleep(1.0)
    print("[%6.1fs] watcher done. app pids=%s cmd=%s" % (
        time.time() - t0, ",".join(sorted(seen_app)) or "-",
        ",".join(pids("cmd.exe")) or "-"), flush=True)
    print("=== final state ===")
    for r in TRACK:
        print("  %-46s %s" % (r, stamp(r)), flush=True)
    vp = os.path.join(INSTALL, "Version.txt")
    if os.path.isfile(vp):
        print("--- Version.txt ---")
        print(open(vp, encoding="utf-8", errors="replace").read())


if __name__ == "__main__":
    main()
