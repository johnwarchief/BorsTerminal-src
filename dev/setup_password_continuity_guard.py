"""Guard: the installer password must stay compatible with the installed app.

Why: a silent in-app update runs the *new* installer with the password bundled
inside the *running* version (`api/update.py::_install_flags`). If the new
installer is built with a different password, every older client aborts on the
first wizard page with "wrong password" and never upgrades.

Reproduced 2026-10-23: an isolated v1.0.95 install rejected the v1.0.97 setup
with «گذرواژه وارد شده اشتباه است» (exit 1), because v1.0.95 bundled the old
password while v1.0.97 was built with a new one. The same check passed once the
v1.0.97 setup was given the password bundled in v1.0.95.

This guard compares `installer/.setup_password.iss` with the file bundled in
the installed app (`<InstallLocation>/_internal/.setup_password.iss`). It SKIPs
when either side is unavailable: CI has no installed app, and a fresh checkout
has no local password file.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_FILE = os.path.join(ROOT, "installer", ".setup_password.iss")
UNINSTALL_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1"
)
PASSWORD_RE = re.compile(r'#define\s+SetupPassword\s+"([^"]*)"')


def parse_password(text: str):
    m = PASSWORD_RE.search(text)
    return m.group(1) if m else None


def read_password(path: str):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return parse_password(f.read())
    except OSError:
        return None


def installed_dir():
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, UNINSTALL_KEY) as key:
                value, _ = winreg.QueryValueEx(key, "InstallLocation")
        except OSError:
            continue
        if value and os.path.isdir(value):
            return value
    return None


def bundled_password(install_dir: str):
    for rel in (os.path.join("_internal", ".setup_password.iss"),
                ".setup_password.iss"):
        value = read_password(os.path.join(install_dir, rel))
        if value is not None:
            return value
    return None


def compare(local_password, installed_password):
    """Return (ok, reason). Both values are never printed."""
    if local_password is None:
        return None, "installer/.setup_password.iss is missing or has no SetupPassword"
    if installed_password is None:
        return None, "the installed app does not bundle a readable password file"
    if local_password != installed_password:
        return False, ("installer password differs from the installed app; "
                       "silent updates from that version will fail")
    return True, "installer password matches the installed app"


def selftest() -> int:
    checks = 0
    failures = []

    def check(name, got, want):
        nonlocal checks
        checks += 1
        if got != want:
            failures.append("%s: got %r want %r" % (name, got, want))

    with tempfile.TemporaryDirectory() as tmp:
        p1 = os.path.join(tmp, "a.iss")
        p2 = os.path.join(tmp, "b.iss")
        with open(p1, "w", encoding="ascii") as f:
            f.write('#define SetupPassword "alpha"\n')
        with open(p2, "w", encoding="ascii") as f:
            f.write('#define SetupPassword "beta"\n')
        check("parse", parse_password(open(p1, encoding="ascii").read()), "alpha")
        check("equal", compare("alpha", "alpha")[0], True)
        check("different", compare("alpha", "beta")[0], False)
        check("missing-local", compare(None, "alpha")[0], None)
        check("missing-installed", compare("alpha", None)[0], None)
        check("file-read", read_password(p1), "alpha")
    if failures:
        for line in failures:
            print("selftest FAIL " + line)
        return 1
    print("selftest: %d checks, 0 failed" % checks)
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()

    local_file = LOCAL_FILE
    install_dir = None
    for i, arg in enumerate(argv):
        if arg == "--local-file" and i + 1 < len(argv):
            local_file = argv[i + 1]
        elif arg == "--installed-dir" and i + 1 < len(argv):
            install_dir = argv[i + 1]
    if install_dir is None:
        install_dir = installed_dir()

    local_password = read_password(local_file)
    installed_password = bundled_password(install_dir) if install_dir else None
    ok, reason = compare(local_password, installed_password)

    if ok is None:
        print("SKIP  setup password continuity: " + reason)
        return 0
    if ok:
        print("PASS  setup password continuity: " + reason)
        print("1 checks, 0 failed")
        return 0
    print("FAIL  setup password continuity: " + reason)
    print("1 checks, 1 failed")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
