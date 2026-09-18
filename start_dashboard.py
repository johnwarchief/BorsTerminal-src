# -*- coding: utf-8 -*-
"""
start_dashboard.py - smart launcher for BorsTerminal_Ultimate

Behavior:
  1. Checks whether a dashboard server is already running on PORT.
  2. If YES  -> message + open browser, exit (do not start a second server).
  3. If NO   -> start uvicorn (through python -m) + open browser.
ASCII-only output (no Persian in terminal).

Usage:  python start_dashboard.py [--port 8001]
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def open_app_window(url: str) -> None:
    """Launch the terminal as a dedicated standalone desktop app window (no tabs, no address bar)."""
    try:
        from launch_desktop import launch
        launch(url)
        return
    except Exception:
        pass
    webbrowser.open(url)


def port_in_use(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.8)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_for_server(port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port):
            # also require HTTP to answer
            try:
                import urllib.request

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
        time.sleep(1.0)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    port = args.port
    url = f"http://localhost:{port}"

    print("=" * 66)
    print("  BorsTerminal_Ultimate - dashboard launcher")
    print("=" * 66)

    if port_in_use(port):
        print(f"  [OK]  A dashboard server is already running on port {port}.")
        print(f"  [OK]  Opening standalone app window: {url}")
        open_app_window(url)
        print("  [DONE] If the window does not load, close it and")
        print("         kill the python process in Task Manager, then retry.")
        print("=" * 66)
        return 0

    print(f"  [..]  Port {port} free - starting server ...")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", args.host, "--port", str(port)],
        env=env,
    )
    print(f"  [..]  Waiting for server on {url} ...")
    if wait_for_server(port):
        print(f"  [OK]  Dashboard is up: {url}")
        print("  [..]  Opening standalone app window ...")
        open_app_window(url)
        print("  [DONE] Server is running. Close this window to stop it.")
    else:
        print(f"  [ERR] Server did not respond on port {port} within 25s.")
        print("        Check app_runtime.log for details.")
        proc.terminate()
        return 1
    print("=" * 66)

    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
