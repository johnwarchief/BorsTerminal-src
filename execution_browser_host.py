# -*- coding: utf-8 -*-
"""execution_browser_host.py — پنجرهٔ مرورگرِ پایدارِ مالک با CDPِ محلی.

مالک خودش در این پنجره وارد می‌شود. نشست فقط با اقدامِ صریحِ مالک (دکمهٔ
«دریافت نشست از مرورگر») خوانده می‌شود و صرفاً در حافظهٔ پروسه می‌ماند؛ هیچ
token/cookie روی دیسک یا در log نوشته نمی‌شود. runtime با Playwright به همان
context متصل می‌شود (connect_over_cdp) و پس از logout/انقضا/بسته‌شدن،
اتصال/اجرا باید مسدود شود.

CDP فقط روی 127.0.0.1 و بندرِ تصادفیِ همان اجرا باز است. این مرز برایِ
برنامهٔ تک‌کاربرهٔ ویندوز است؛ هیچ بایندِ عمومی پذیرفته نمی‌شود.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from typing import Any

import bors_config

STATUS_NAME = "bors_browser_host.json"
DEFAULT_URL = "https://d.easytrader.ir/"
PROFILE_NAME = "browser_host_profile"


def _host_suffix(name: str = "") -> str:
    """نامِ امن برایِ میزبانِ نام‌دار؛ پیش‌فرض بی‌نام همان hostِ EasyTrader است."""
    clean = re.sub(r"[^a-z0-9_-]", "", str(name or "").lower())
    return ("_" + clean) if clean else ""


def status_path(name: str = "") -> str:
    env = os.environ.get("BORS_BROWSER_HOST_STATUS") if not name else ""
    if env:
        return env
    base, ext = os.path.splitext(STATUS_NAME)
    return os.path.join(bors_config.WORK_DIR, base + _host_suffix(name) + ext)


def _health(cdp_url: str, timeout: float = 0.6) -> bool:
    if not cdp_url:
        return False
    try:
        with urllib.request.urlopen(cdp_url.rstrip("/") + "/json/version",
                                    timeout=timeout) as r:
            return int(getattr(r, "status", 0) or 0) == 200
    except Exception:
        return False


def read_status(check: bool = True, name: str = "") -> dict[str, Any]:
    try:
        with open(status_path(name), encoding="utf-8") as f:
            got = json.load(f)
    except Exception:
        return {"status": "closed", "healthy": False, "cdp_url": "", "name": name}
    if not isinstance(got, dict):
        return {"status": "closed", "healthy": False, "cdp_url": "", "name": name}
    out = dict(got)
    out["name"] = str(out.get("name") or name)
    out["healthy"] = _health(str(out.get("cdp_url") or "")) if check else False
    if check and not out["healthy"]:
        out["status"] = "closed"
    return out


def _write_status(data: dict[str, Any], name: str = "") -> None:
    path = status_path(name)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _browser_candidates() -> list[str]:
    env = (os.environ.get("BORS_BROWSER_HOST_EXE") or "").strip()
    if env:
        return [env]
    la = os.environ.get("LOCALAPPDATA") or ""
    pf = os.environ.get("ProgramFiles") or r"C:\Program Files"
    pf86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    out = [
        os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(la, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(la, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        os.path.join(la, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
    ]
    try:
        import glob
        out.extend(sorted(glob.glob(os.path.join(
            la, "ms-playwright", "chromium-*", "chrome-win64", "chrome.exe")),
            reverse=True))
    except Exception:
        pass
    return out


def _profile(name: str = "") -> str:
    raw = ((os.environ.get("BORS_BROWSER_HOST_PROFILE") or "").strip()
           if not name else "")
    base, ext = os.path.splitext(PROFILE_NAME)
    return raw or os.path.join(bors_config.WORK_DIR, base + _host_suffix(name) + ext)


def _pid_matches(pid: int, port: int, profile: str) -> bool:
    """پیش از kill، مطمئن شو همان hostِ ماست (PID بازچرخانی نشده)."""
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % int(pid)],
            capture_output=True, text=True, timeout=8)
        cmd = (p.stdout or "").strip()
        return "--remote-debugging-port=%d" % int(port) in cmd and profile in cmd
    except Exception:
        return False


def start_host(*, url: str = "", port: int = 0, wait_s: float = 30.0,
               hold: bool = False, name: str = "") -> dict[str, Any]:
    existing = read_status(check=True, name=name)
    if existing.get("healthy"):
        return existing
    exe = next((p for p in _browser_candidates() if p and os.path.isfile(p)), "")
    if not exe:
        return {"status": "error", "code": "NO_BROWSER", "healthy": False,
                "name": name}
    port = int(port or (os.environ.get("BORS_BROWSER_HOST_PORT")
                       if not name else 0) or 0)
    if port <= 0:
        port = _free_port()
    profile = _profile(name)
    os.makedirs(profile, exist_ok=True)
    if name and not url:
        # hostِ نام‌دار نباید بی‌نشانی، صفحهٔ پیش‌فرضِ EasyTrader را در پروفایلِ
        # خودش باز کند؛ نشانی باید صریح باشد.
        url = (os.environ.get("BORS_BROWSER_HOST_URL") or "").strip()
        if not url:
            return {"status": "error", "code": "URL_REQUIRED",
                    "healthy": False, "name": name}
    target = (url or DEFAULT_URL).strip()
    args = [
        exe,
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=%d" % port,
        "--remote-allow-origins=http://127.0.0.1:%d" % port,
        "--user-data-dir=%s" % profile,
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--disable-background-networking", "--new-window", target,
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    cdp = "http://127.0.0.1:%d" % port
    data = {"status": "starting", "pid": proc.pid, "port": port,
            "cdp_url": cdp, "profile": profile, "url": target, "name": name,
            "started_at": time.time(), "healthy": False}
    _write_status(data, name)
    deadline = time.monotonic() + max(3.0, float(wait_s))
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            data["status"] = "closed"
            _write_status(data, name)
            return {**data, "code": "BROWSER_EXITED"}
        if _health(cdp):
            data.update({"status": "ready", "healthy": True})
            _write_status(data, name)
            if hold:
                try:
                    proc.wait()
                except KeyboardInterrupt:
                    pass
                finally:
                    data["status"] = "closed"
                    data["healthy"] = False
                    _write_status(data, name)
            return data
        time.sleep(0.25)
    data["status"] = "timeout"
    _write_status(data, name)
    return data


def stop_host(name: str = "") -> dict[str, Any]:
    got = read_status(check=False, name=name)
    pid = int(got.get("pid") or 0)
    port = int(got.get("port") or 0)
    profile = str(got.get("profile") or "")
    if not pid:
        return {"status": "closed", "detail": "no host pid", "name": name}
    if not _pid_matches(pid, port, profile):
        return {"status": "error", "code": "PID_NOT_OUR_HOST", "name": name}
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=15)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": type(e).__name__, "name": name}
    for _ in range(40):
        if not read_status(check=True, name=name).get("healthy"):
            break
        time.sleep(0.1)
    got.update({"status": "closed", "healthy": False, "name": name})
    _write_status(got, name)
    return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BorsTerminal browser session host")
    ap.add_argument("--url", default="")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--wait", type=float, default=30.0)
    ap.add_argument("--name", default="")
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    got = start_host(url=args.url, port=args.port, wait_s=args.wait,
                     hold=not args.print_only, name=args.name)
    print(json.dumps(got, ensure_ascii=False))
    return 0 if got.get("status") == "ready" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
