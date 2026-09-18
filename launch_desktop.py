# -*- coding: utf-8 -*-
"""
launch_desktop.py - Standalone desktop app launcher & port waiter for BorsTerminal
Silently waits for frontend/backend port and launches Edge / Chrome / Brave in standalone app window.
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser


def find_chromium_browser() -> str | None:
    # 1. Common executable paths on Windows
    common_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return path

    # 2. Windows Registry App Paths
    try:
        import winreg

        for app in ["msedge.exe", "chrome.exe", "brave.exe"]:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app}",
                ) as k:
                    val = winreg.QueryValue(k, "")
                    if val and os.path.isfile(val):
                        return val
            except Exception:
                pass
    except Exception:
        pass

    # 3. PATH resolution
    for name in ["msedge", "chrome", "brave"]:
        p = shutil.which(name)
        if p and os.path.isfile(p):
            return p

    return None


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            s.connect((host, port))
            s.close()
            return True
        except OSError:
            s.close()
            time.sleep(0.4)
    return False


def launch(url: str):
    browser = find_chromium_browser()
    if browser:
        print(f"[Desktop App] Launching standalone app mode via: {browser}")
        subprocess.Popen([browser, f"--app={url}"])
    else:
        print(f"[Desktop App] Chromium browser not found, launching default browser: {url}")
        webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--url", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    target_url = args.url if args.url else f"http://localhost:{args.port}"

    if not args.no_wait:
        print(f"[Desktop App] Waiting for server on port {args.port} (silent socket check)...")
        ready = wait_for_port(args.port, args.host, timeout=args.timeout)
        if ready:
            print(f"[Desktop App] Server is ready on port {args.port}!")
        else:
            print(f"[Desktop App] Warning: Port {args.port} timed out after {args.timeout}s. Launching anyway...")

    launch(target_url)


if __name__ == "__main__":
    main()
