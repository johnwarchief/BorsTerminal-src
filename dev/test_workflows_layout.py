#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")


def text(name):
    return open(os.path.join(WF, name), encoding="utf-8").read()


def main():
    guards = text("guards.yml")
    assert "python-guards:" not in guards, "python-guards must leave the production gate"
    assert "python-tooling.yml" not in guards
    assert "zero-python-runtime" in guards, "runtime proof job missing"
    assert "js-syntax:" not in guards, "legacy static check must leave the production gate"
    tooling = text("python-tooling.yml")
    assert "--profile data" in tooling
    assert "suite_registry_guard.py" in tooling
    legacy = text("python-legacy.yml")
    assert "--profile legacy" in legacy
    assert "continue-on-error: true" in legacy
    print("WORKFLOW LAYOUT TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
