#!/usr/bin/env python3
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "dev", "run_all_tests.py")


def run(args):
    return subprocess.run([sys.executable, RUNNER] + args, capture_output=True,
                          text=True, encoding="utf-8", cwd=ROOT)


def main():
    r = run(["--list", "--profile", "data"])
    assert r.returncode == 0, r.stderr
    assert "struct_check.py" not in r.stdout, "legacy suite leaked into data"
    r2 = run(["--list", "--profile", "legacy"])
    assert r2.returncode == 0
    assert "struct_check.py" in r2.stdout
    print("RUNNER PROFILE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
