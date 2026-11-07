"""Guard: the install watchdog must never hang before setup starts.

2026-10-23, a real in-app update on this machine: the watchdog bat waited for
the app's PID with `tasklist | find`, the find process blocked on stdin, setup
never ran, and the app stayed closed. The replacement waits with PowerShell
`Wait-Process`, closes stdin explicitly, and does not depend on PATH.

The guard checks the rendered line and then runs a watchdog bat for real:
a dummy process is waited on, and a marker must appear only after it exits.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CHECKS = []
FAILED = 0


def check(name, ok, detail=""):
    global FAILED
    CHECKS.append(name)
    if ok:
        print("PASS  %s" % name)
    else:
        FAILED += 1
        print("FAIL  %s%s" % (name, (": " + detail) if detail else ""))


def _run_bat(bat_path, flags):
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=flags, close_fds=True)


def _wait_for(path, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if os.path.exists(path):
            return True
        time.sleep(0.25)
    return False


def _wait_for_missing(path, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if not os.path.exists(path):
            return True
        time.sleep(0.25)
    return False


def main():
    if os.name != "nt":                            # watchdog is Windows-only
        print("SKIP  installer watchdog: non-Windows host")
        return 0
    import api.update as upd

    line = upd._wait_for_exit_line(4242)
    check("wait line uses Wait-Process", "Wait-Process -Id 4242" in line)
    check("wait line closes stdin", "<nul" in line)
    check("wait line uses the absolute PowerShell path",
          "System32\\WindowsPowerShell\\v1.0\\powershell.exe" in line)
    check("wait line has no tasklist pipe",
          "tasklist" not in line and "| find" not in line)
    check("watchdog is not spawned DETACHED_PROCESS",
          not (upd.WATCHDOG_CREATIONFLAGS & 0x00000008),
          "DETACHED_PROCESS leaves the wait child without a console")

    with tempfile.TemporaryDirectory(prefix="bors_watchdog_") as tmp:
        marker = os.path.join(tmp, "marker.txt")
        dummy = subprocess.Popen(["cmd", "/c", "ping -n 5 127.0.0.1 >nul"])
        try:
            bat = os.path.join(tmp, "watch.cmd")
            with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\r\n".join([
                    "@echo off",
                    upd._wait_for_exit_line(dummy.pid),
                    'echo RAN > "%s"' % marker,
                ]) + "\r\n")
            _run_bat(bat, upd.WATCHDOG_CREATIONFLAGS)
            time.sleep(1.5)
            check("watchdog waits while the target is alive",
                  not os.path.exists(marker))
            check("watchdog proceeds after the target exits",
                  _wait_for(marker, 30))
        finally:
            dummy.wait()

        dead = subprocess.Popen(["cmd", "/c", "exit 0"])
        dead.wait()
        marker2 = os.path.join(tmp, "marker2.txt")
        bat2 = os.path.join(tmp, "watch_dead.cmd")
        with open(bat2, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\r\n".join([
                "@echo off",
                upd._wait_for_exit_line(dead.pid),
                'echo RAN > "%s"' % marker2,
            ]) + "\r\n")
        started = time.time()
        _run_bat(bat2, upd.WATCHDOG_CREATIONFLAGS)
        ok = _wait_for(marker2, 20)
        check("already-dead PID does not hang the watchdog",
              ok and time.time() - started < 15,
              "%.1fs" % (time.time() - started))

    # End-to-end: the real _spawn_install writes the batch, the batch waits for
    # the app's PID and then runs the installer. os.getpid is shimmed to a dummy
    # process so the test process itself is not the thing being waited on.
    with tempfile.TemporaryDirectory(prefix="bors_spawn_") as tmp:
        class _OsShim:
            def __getattr__(self, name):
                return getattr(os, name)

            def getpid(self):
                return dummy2.pid

        # A real .exe installer, not a .cmd: `start /WAIT` opens a .cmd with
        # cmd /K and never returns, which would hang the guard itself.
        spawn_marker = os.path.join(tmp, "spawn_marker.txt")
        comspec = os.path.join(os.environ["SystemRoot"], "System32", "cmd.exe")
        dummy2 = subprocess.Popen(["cmd", "/c", "ping -n 4 127.0.0.1 >nul"])
        saved = (upd.os, upd.CACHE_DIR, upd._app_exe_path, upd._delayed_exit)
        try:
            upd.os = _OsShim()
            upd.CACHE_DIR = tmp
            upd._app_exe_path = lambda: None
            upd._delayed_exit = lambda seconds: None
            upd._spawn_install(comspec, ["/c", "copy", "NUL", spawn_marker])
            check("_spawn_install runs the installer after the app exits",
                  _wait_for(spawn_marker, 30))
            check("_spawn_install deletes its watchdog script",
                  _wait_for_missing(os.path.join(tmp, "bors_install.cmd"), 10))
        finally:
            upd.os, upd.CACHE_DIR, upd._app_exe_path, upd._delayed_exit = saved
            dummy2.wait()

    print("%d checks, %d failed" % (len(CHECKS), FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
