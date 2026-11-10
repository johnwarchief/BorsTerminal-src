# Phase 4.9.1 — Plan A: CI Migration & Zero-Python Runtime

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `python-guards` from the Production gate, classify all 254 Python suites, fix or port production-critical checks, split Data-Tooling from Legacy, and prove zero-Python runtime with bundle, process, and installer evidence.

**Architecture:** A machine-readable suite registry drives `run_all_tests.py` profiles and a guard that enforces every suite has a category, disposition, and real Go/TS equivalent. Production CI keeps Go/frontend/delivery/data-integrity/repo-hygiene plus a new Go `runtimecheck`; Python data tests move to `python-tooling.yml`, legacy tests to report-only `python-legacy.yml`.

**Tech Stack:** Go 1.26, Python 3.12, Node 22, GitHub Actions, PowerShell on Windows runners.

**Spec:** [docs/superpowers/specs/2026-11-10-phase49-full-verification-design.md](../specs/2026-11-10-phase49-full-verification-design.md)

## Global Constraints

- Branch `mission/phase49-full-verification-python-ci-2026-11-10`; no merge/tag/release/force push.
- No threshold changes, no weakened asserts, no skipped or ignored failures, no hand-edited goldens.
- Every category A suite keeps a real guard until its Go/TS equivalent exists.
- Never add Python to the production runtime; Python is CI data/build tooling only.
- Do not modify repository branch protection or visibility.

---

### Task A1: Suite registry generator and guard

**Files:**
- Create: `dev/suite_registry_guard.py`
- Create: `dev/build_suite_registry.py`
- Create: `dev/test_suite_registry_guard.py`
- Create: `dev/suite_registry.json` (generated)

**Interfaces:**
- Produces `parse_suites(path) -> dict[str, dict]` with keys `script`, `label`, `kind`.
- Produces `validate(registry, suites) -> list[str]`.
- Registry schema: `{"schema": 1, "suites": {script: {script,label,kind,category,disposition,profile,go_equivalent,ts_equivalent,reason,retirement_date}}}`.

- [ ] **Step 1: Write the failing test**

Create `dev/test_suite_registry_guard.py`:
```python
#!/usr/bin/env python3
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import suite_registry_guard as G  # noqa: E402


def base_entry(**kw):
    e = {"script": "a.py", "label": "x", "kind": "SUITES", "category": "A",
         "disposition": "KEEP", "profile": "production",
         "go_equivalent": None, "ts_equivalent": None,
         "reason": "contract guard", "retirement_date": None}
    e.update(kw)
    return e


def run_case(name, entry, want_ok):
    reg = {"schema": 1, "suites": {"a.py": entry}}
    suites = {"a.py": {"script": "a.py", "label": "x", "kind": "SUITES"}}
    errors = G.validate(reg, suites)
    ok = not errors
    assert ok == want_ok, (name, errors)
    print("ok  ", name)


def main():
    assert len(G.parse_suites()) >= 250, "runner must expose >=250 suites"
    run_case("valid keep", base_entry(), True)
    run_case("missing label", base_entry(label=""), False)
    run_case("bad category", base_entry(category="Z"), False)
    run_case("A must be production",
             base_entry(profile="legacy"), False)
    run_case("migrate needs equivalent",
             base_entry(disposition="MIGRATE", profile="legacy"), False)
    run_case("migrate with missing file",
             base_entry(disposition="MIGRATE", profile="legacy",
                        go_equivalent="backend-go/internal/nope/no_test.go:TestX"),
             False)
    run_case("remove needs reason",
             base_entry(disposition="REMOVE", profile="legacy", reason="",
                        retirement_date="2026-11-10"), False)
    run_case("remove needs date",
             base_entry(disposition="REMOVE", profile="legacy", reason="obsolete",
                        retirement_date=None), False)
    with tempfile.NamedTemporaryFile("w", suffix=".go", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("package x\nfunc TestReal(t *testing.T) {}\n")
        tmp = fh.name
    try:
        rel = os.path.relpath(tmp, G.ROOT).replace("\\", "/")
        run_case("migrate with real test",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"), True)
    finally:
        os.unlink(tmp)
    print("SUITE REGISTRY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python dev/test_suite_registry_guard.py`
Expected: `ModuleNotFoundError: No module named 'suite_registry_guard'`.

- [ ] **Step 3: Implement the guard**

Create `dev/suite_registry_guard.py`:
```python
#!/usr/bin/env python3
"""Validate dev/suite_registry.json against dev/run_all_tests.py."""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "dev", "run_all_tests.py")
REGISTRY = os.path.join(ROOT, "dev", "suite_registry.json")
CATEGORIES = {"A", "B", "C", "D"}
DISPOSITIONS = {"KEEP", "MIGRATE", "DEPRECATE", "REMOVE"}
PROFILES = {"production", "data", "legacy"}


def parse_suites(path=RUNNER):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ("SUITES", "JS_SUITES"):
            continue
        for elt in node.value.elts:
            script, label = ast.literal_eval(elt)
            if script in out:
                raise ValueError("duplicate suite in runner: %s" % script)
            out[script] = {"script": script, "label": label, "kind": target.id}
    return out


def _equiv_exists(value):
    if not value:
        return False
    path, _, test = value.partition(":")
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return False
    if not test:
        return True
    text = open(full, encoding="utf-8", errors="replace").read()
    return re.search(r"\b%s\b" % re.escape(test), text) is not None


def validate(registry, suites):
    errors = []
    if registry.get("schema") != 1:
        errors.append("schema must be 1")
    entries = registry.get("suites") or {}
    for script in sorted(set(suites) - set(entries)):
        errors.append("unregistered suite: %s" % script)
    for script in sorted(set(entries) - set(suites)):
        errors.append("registry entry not in runner: %s" % script)
    for script in sorted(set(suites) & set(entries)):
        e = entries[script]
        if not e.get("label"):
            errors.append("%s: label missing" % script)
        cat, disp, prof = e.get("category"), e.get("disposition"), e.get("profile")
        if cat not in CATEGORIES:
            errors.append("%s: bad category %r" % (script, cat))
        if disp not in DISPOSITIONS:
            errors.append("%s: bad disposition %r" % (script, disp))
        if prof not in PROFILES:
            errors.append("%s: bad profile %r" % (script, prof))
        if cat == "A" and prof not in ("production", "data"):
            errors.append("%s: category A must be production or data" % script)
        if cat == "B" and prof != "data":
            errors.append("%s: category B must be data" % script)
        if cat in ("C", "D") and prof != "legacy":
            errors.append("%s: category %s must be legacy" % (script, cat))
        if disp == "KEEP" and prof == "legacy":
            errors.append("%s: KEEP cannot be legacy" % script)
        if disp == "KEEP" and not e.get("reason"):
            errors.append("%s: KEEP needs an evidence reason" % script)
        if disp == "MIGRATE":
            if prof != "legacy":
                errors.append("%s: MIGRATE must be legacy until retired" % script)
            eq = e.get("go_equivalent") or e.get("ts_equivalent")
            if not eq:
                errors.append("%s: MIGRATE needs go_equivalent or ts_equivalent" % script)
            elif not _equiv_exists(eq):
                errors.append("%s: equivalence missing: %s" % (script, eq))
        if disp in ("DEPRECATE", "REMOVE"):
            if not e.get("reason"):
                errors.append("%s: %s needs a reason" % (script, disp))
            if not e.get("retirement_date"):
                errors.append("%s: %s needs retirement_date" % (script, disp))
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    reg = json.load(open(args.registry, encoding="utf-8"))
    suites = parse_suites()
    errors = validate(reg, suites)
    if errors:
        print("SUITE REGISTRY GUARD FAIL")
        for e in errors[:60]:
            print(" -", e)
        return 1
    print("SUITE REGISTRY GUARD OK: %d suites" % len(suites))
    return 0


def selftest():
    suites = {"a.py": {"script": "a.py", "label": "x", "kind": "SUITES"}}
    good = {"schema": 1, "suites": {"a.py": {
        "script": "a.py", "label": "x", "kind": "SUITES", "category": "A",
        "disposition": "KEEP", "profile": "production",
        "go_equivalent": None, "ts_equivalent": None,
        "reason": "contract", "retirement_date": None}}}
    cases = [("valid", good, True)]
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"]["category"] = "Z"
    cases.append(("bad category", bad, False))
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"].update(
        disposition="MIGRATE", profile="legacy")
    cases.append(("migrate without equivalence", bad, False))
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"].update(
        disposition="REMOVE", profile="legacy", reason="", retirement_date="2026-11-10")
    cases.append(("remove without reason", bad, False))
    ok_all = True
    for name, reg, want_ok in cases:
        got_ok = not validate(reg, suites)
        ok = got_ok == want_ok
        print(("ok  " if ok else "FAIL") + " selftest: " + name)
        ok_all = ok_all and ok
    print("SELFTEST OK" if ok_all else "SELFTEST FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python dev/test_suite_registry_guard.py`
Expected: all cases print `ok`, final line `SUITE REGISTRY TESTS OK`.

- [ ] **Step 5: Generate the draft registry**

Create `dev/build_suite_registry.py`:
```python
#!/usr/bin/env python3
"""Create/merge dev/suite_registry.json from the runner's SUITES lists."""
from __future__ import annotations

import argparse
import json
import os

from suite_registry_guard import REGISTRY, parse_suites


def merge(existing, suites):
    out = existing if existing else {"schema": 1, "suites": {}}
    out["schema"] = 1
    kept = {}
    for script, info in suites.items():
        cur = out["suites"].get(script, {})
        kept[script] = {
            "script": script,
            "label": info["label"],
            "kind": info["kind"],
            "category": cur.get("category", "UNCLASSIFIED"),
            "disposition": cur.get("disposition", "UNCLASSIFIED"),
            "profile": cur.get("profile", "legacy"),
            "go_equivalent": cur.get("go_equivalent"),
            "ts_equivalent": cur.get("ts_equivalent"),
            "reason": cur.get("reason", ""),
            "retirement_date": cur.get("retirement_date"),
        }
    out["suites"] = dict(sorted(kept.items()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    existing = json.load(open(REGISTRY, encoding="utf-8")) if os.path.isfile(REGISTRY) else None
    reg = merge(existing, parse_suites())
    if args.write:
        with open(REGISTRY, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(reg, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("wrote %d entries -> %s" % (len(reg["suites"]), REGISTRY))
    else:
        print(json.dumps(reg, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:
```bash
python dev/build_suite_registry.py --write
python dev/suite_registry_guard.py
```
Expected: guard FAIL listing unregistered/UNCLASSIFIED entries. This is the work queue for Task A3/A4.

- [ ] **Step 6: Commit**
```bash
git add dev/suite_registry_guard.py dev/build_suite_registry.py dev/test_suite_registry_guard.py dev/suite_registry.json
git commit -m "feat(phase49): add machine-readable suite registry and guard"
```

---

### Task A2: Runner profiles, list, and single-suite mode

**Files:**
- Modify: `dev/run_all_tests.py:24-27` (gate delegation), `dev/run_all_tests.py:31` and after `JS_SUITES`, before execution.
- Test: `dev/test_runner_profiles.py` (new).

**Interfaces:**
- `python dev/run_all_tests.py --list --profile data` prints selected suites and exits 0 without running.
- `python dev/run_all_tests.py --only <script>` runs exactly one suite through the normal gate wrapper.
- `--profile production|data|legacy|all`; default `all`.

- [ ] **Step 1: Write the failing test**

Create `dev/test_runner_profiles.py`:
```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python dev/test_runner_profiles.py`
Expected: failure because `--list`/`--profile` are not implemented.

- [ ] **Step 3: Implement argument handling**

In `dev/run_all_tests.py`, replace the `if __name__ == "__main__"` gate block with:
```python
def _arg_value(name):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


if __name__ == "__main__" and "--list" not in sys.argv and os.environ.get("BORS_GATE_ISOLATED") != "1":
    print("[gate] unisolated invocation — delegating to dev/gate_db_guard.py")
    _args = [sys.executable, os.path.join(_HERE, "gate_db_guard.py")] + sys.argv[1:]
    raise SystemExit(subprocess.call(_args))
```

After `JS_SUITES` and before `REQUIRES`, add:
```python
import json  # noqa: E402
_REGISTRY = json.load(open(os.path.join(_HERE, "suite_registry.json"), encoding="utf-8"))["suites"]
_PROFILE = _arg_value("--profile") or "all"
_ONLY = _arg_value("--only")

def _selected(script):
    if _ONLY and script != _ONLY:
        return False
    if _PROFILE == "all":
        return True
    return _REGISTRY[script]["profile"] == _PROFILE

if "--list" in sys.argv:
    for script, label in SUITES:
        if _selected(script):
            print("%s\t%s\t%s" % (_REGISTRY[script]["profile"], script, label))
    for script, label in JS_SUITES:
        if _selected(script):
            print("%s\t%s\t%s" % (_REGISTRY[script]["profile"], script, label))
    raise SystemExit(0)

SUITES = [(s, l) for s, l in SUITES if _selected(s)]
JS_SUITES = [(s, l) for s, l in JS_SUITES if _selected(s)]
```

After `FIXTURE_GEN` check, change the fixture line to:
```python
if os.path.exists(FIXTURE_GEN) and _PROFILE in ("all", "data", "legacy"):
    run([sys.executable, FIXTURE_GEN.replace('/', os.sep)], 'fixture: fts_v10 payloads')
```
and the total line to:
```python
total_suites = len(SUITES) + len(JS_SUITES) + (1 if os.path.exists(FIXTURE_GEN) and _PROFILE in ("all", "data", "legacy") else 0)
```

- [ ] **Step 4: Run tests**

Run:
```bash
python dev/test_runner_profiles.py
python dev/run_all_tests.py --list --profile production | head
```
Expected: tests pass; production listing shows only category A suites once Task A3 classifies them.

- [ ] **Step 5: Commit**
```bash
git add dev/run_all_tests.py dev/test_runner_profiles.py
git commit -m "feat(phase49): add profile, list, and single-suite runner modes"
```

---

### Task A3: Classify Category A/B suites and root-cause their failures

**Files:**
- Modify: `dev/suite_registry.json`
- Create: `_audit/phase49-full-verification/evidence/ci-failures.json`
- Create/modify: Go or TS tests named in `go_equivalent`/`ts_equivalent` when a category A check lacks coverage.

**Interfaces:**
- `ci-failures.json` is a list of `{suite, label, category, disposition, error, root_cause, decision, evidence, commit}`.

- [ ] **Step 1: Reproduce every known failing suite individually**

Run this loop (adjust the list as the CI annotation adds names):
```bash
mkdir -p _audit/phase49-full-verification/evidence/logs
for s in dev/fts_m141_parity_v97.py dev/confidence_engine_v973.py dev/soft_warnings_v974.py dev/mstat_local_v975.py dev/test_mstat_fixture_v1121.py dev/test_chart_fixture_b3.py dev/test_fundamental_fixture_b4.py dev/test_fundamental_vectors_b4.py; do
  n=$(basename "$s" .py)
  BORS_NO_FETCH_LOOPS=1 python dev/run_all_tests.py --only "$s" > "_audit/phase49-full-verification/evidence/logs/$n.log" 2>&1 || true
done
```
Note: do not set `BORS_GATE_ISOLATED=1`; the runner must delegate to `dev/gate_db_guard.py` so it works on an isolated DB copy.

- [ ] **Step 2: Classify A/B with evidence**

For each suite with category A or B, fill the registry entry and record in `ci-failures.json`. Decision rules:
- If the suite guards a live data/product contract and no Go/TS equivalent exists → `KEEP`, profile `production` (A) or `data` (B), and add the missing Go/TS test in the same task.
- If an equivalent Go/TS test exists → `MIGRATE`, profile `legacy`, `go_equivalent`/`ts_equivalent` filled with a real `path:TestName`.
- If the failure is a stale golden of a still-live contract → regenerate the golden from the current oracle, inspect the diff, commit generator + golden, record the diff in evidence. Never hand-edit expected values.
- If the failure is a real bug in live logic → fix the code and keep the suite as `KEEP`.
- If the failure is environmental → prove it (e.g., missing file, platform library), fix the environment, and record the proof; otherwise it is not environmental.

- [ ] **Step 3: Run the guard and the A/B suites**

Run:
```bash
python dev/suite_registry_guard.py
python dev/run_all_tests.py --profile production
python dev/run_all_tests.py --profile data
```
Expected: guard passes for A/B entries; every production/data suite that still exists passes. If a suite fails, stop and fix it; do not skip.

- [ ] **Step 4: Commit**
```bash
git add dev/suite_registry.json _audit/phase49-full-verification/evidence/ci-failures.json dev backend-go frontend-v2
git commit -m "feat(phase49): classify production/data Python suites and close root causes"
```

---

### Task A4: Classify Category C/D suites and retire them responsibly

**Files:**
- Modify: `dev/suite_registry.json`
- Modify: `_audit/phase49-full-verification/evidence/ci-failures.json`
- Create: `docs/opportunity-center/phase49/PYTHON-CI-MIGRATION.md` (first draft; finalized in Plan C)

- [ ] **Step 1: Map every remaining suite to C or D**

Use this decision tree:
- C (legacy Python backend): suite exercises FastAPI/static app behavior that `backend-go` or `frontend-v2` now owns. `go_equivalent`/`ts_equivalent` must name the real test.
- D (obsolete): suite checks deleted code, old golden, or a removed fixture. No Go/TS equivalent is possible; provide a reason and retirement date.
- If unsure, keep it in C with `reason` naming the exact Go/TS package and the missing coverage; do not invent a D reason.

For each entry set `disposition`:
- `MIGRATE` when a Go/TS equivalent exists and the Python suite is redundant.
- `DEPRECATE` when the behavior still exists but the Python harness is not the right gate; keep it in the legacy lane and name the replacement.
- `REMOVE` only when the tested code is deleted and the failure cannot recur; record commit and date.

- [ ] **Step 2: Remove the gate block**

Run:
```bash
python dev/suite_registry_guard.py
```
Expected: `SUITE REGISTRY GUARD OK: 254 suites` (or the exact measured count), with no UNCLASSIFIED entries.

- [ ] **Step 3: Write the migration table**

Create `docs/opportunity-center/phase49/PYTHON-CI-MIGRATION.md` with one row per suite:
```markdown
| Suite | Category | Disposition | Profile | Go/TS equivalent | Reason | Retirement |
| --- | --- | --- | --- | --- | --- | --- |
```
Every row must point to a real equivalence or a documented reason. Summarize the 24 root causes at the top with links to `evidence/logs/*.log`.

- [ ] **Step 4: Commit**
```bash
git add dev/suite_registry.json docs/opportunity-center/phase49/PYTHON-CI-MIGRATION.md _audit/phase49-full-verification/evidence/ci-failures.json
git commit -m "feat(phase49): classify legacy/obsolete Python suites and record dispositions"
```

---

### Task A5: Split the GitHub Actions workflows

**Files:**
- Modify: `.github/workflows/guards.yml`
- Create: `.github/workflows/python-tooling.yml`
- Create: `.github/workflows/python-legacy.yml`
- Create: `dev/test_workflows_layout.py`

**Interfaces:**
- `guards.yml` has no `python-guards` job and no `js-syntax` job.
- `python-tooling.yml` runs `--profile data`; `python-legacy.yml` runs `--profile legacy` with `continue-on-error: true`.

- [ ] **Step 1: Write the failing layout test**

Create `dev/test_workflows_layout.py`:
```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python dev/test_workflows_layout.py`
Expected: assertion failure (python-guards still present, new files missing).

- [ ] **Step 3: Edit `guards.yml`**

First verify every suite still named in the existing `data-integrity` job is category A after Task A3. If one is not, move it to `python-tooling.yml` or `python-legacy.yml`; `data-integrity` must not run legacy suites.

Delete the entire `python-guards:` job (lines 17–62 in the base file) and the entire `js-syntax:` job (lines 341–373). Add this job after `data-integrity`:
```yaml
  zero-python-runtime:
    name: zero-python runtime proof (Go process tree)
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-go@v5
        with:
          go-version: '1.27.3'
          check-latest: true
          cache-dependency-path: backend-go/go.sum

      - name: Build borsd
        working-directory: backend-go
        run: |
          mkdir -p ../dist-ci
          go build -o ../dist-ci/BorsTerminal_Ultimate.exe ./cmd/borsd

      - name: Launch borsd and prove no Python process
        shell: pwsh
        run: |
          $rt = Join-Path $env:RUNNER_TEMP "rt"
          New-Item -ItemType Directory -Force $rt | Out-Null
          Copy-Item market.db "$rt/market.db"
          ( cd backend-go; go run ./cmd/runtimecheck --borsd ../dist-ci/BorsTerminal_Ultimate.exe --data-dir $rt --port 18081 --out "$env:RUNNER_TEMP/runtimecheck.json" )
          if (-not (Test-Path "$env:RUNNER_TEMP/runtimecheck.json")) { Write-Output "::error::runtimecheck produced no report"; exit 1 }
          Get-Content "$env:RUNNER_TEMP/runtimecheck.json"

      - name: Upload runtime proof
        uses: actions/upload-artifact@v4
        with:
          name: zero-python-runtime
          path: ${{ runner.temp }}/runtimecheck.json
          if-no-files-found: error
```

In `delivery-contract`, after the installer build, add:
```yaml
      - name: Installer runtime proof (temp directory only)
        shell: pwsh
        run: |
          $setup = Get-ChildItem installer/out/BorsTerminal_Ultimate_Setup_v*.exe | Select-Object -First 1
          $dir = Join-Path $env:RUNNER_TEMP "bt-install"
          $rt = Join-Path $env:RUNNER_TEMP "bt-rt"
          New-Item -ItemType Directory -Force $rt | Out-Null
          Start-Process -FilePath $setup.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/SP-","/DIR=$dir","/PASSWORD=ci-test-only" -Wait
          $bad = Get-ChildItem -Recurse $dir -Include *.py,*.pyc,*.pyd,*.pyz,*.pyo,python*.exe,python*.dll,libpython* -ErrorAction SilentlyContinue
          if ($bad) { $bad | ForEach-Object { Write-Output "::error::python artifact: $($_.FullName)" }; exit 1 }
          Copy-Item "$dir/market.db" "$rt/market.db" -Force
          if (Test-Path "$dir/data") { Copy-Item -Recurse "$dir/data" "$rt/data" }
          ( cd backend-go; go run ./cmd/runtimecheck --borsd "$dir/BorsTerminal_Ultimate.exe" --data-dir $rt --port 18082 --out "$env:RUNNER_TEMP/runtimecheck-installed.json" )
          $uninst = Get-ChildItem $dir -Filter "unins*.exe" | Select-Object -First 1
          if ($uninst) { Start-Process -FilePath $uninst.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait }
```

- [ ] **Step 4: Create `python-tooling.yml`**
```yaml
name: python-tooling

on:
  push:
    branches: ['**']
  pull_request:
  workflow_dispatch:

jobs:
  data-tooling:
    name: data/research suites (python dev/run_all_tests.py --profile data)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Suite registry
        run: python dev/suite_registry_guard.py

      - name: Status rules (present after Plan B4)
        if: ${{ hashFiles('dev/phase49_rules_guard.py') != '' }}
        run: python dev/phase49_rules_guard.py

      - name: Data/research suites
        run: python dev/run_all_tests.py --profile data
```

- [ ] **Step 5: Create `python-legacy.yml`**
```yaml
name: python-legacy

on:
  push:
    branches: ['**']
  pull_request:
  workflow_dispatch:

jobs:
  legacy-maintenance:
    name: legacy Python maintenance (report-only)
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend deps for legacy API guards
        working-directory: frontend
        run: npm ci --ignore-scripts

      - name: Legacy suites
        run: python dev/run_all_tests.py --profile legacy

  legacy-static:
    name: legacy static JS syntax (report-only)
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Syntax-check first-party JS
        run: |
          set -e
          for f in \
            static/app.js static/fundamental_ui.js static/portfolio_ui.js \
            static/tech_rtv.js static/tech_tools.js static/tech_365.js \
            static/mstat.js static/selection.js static/calendar/calendar.js \
            static/calendar/calendarService.js static/vendor/drawing_math.js
          do
            if [ -f "$f" ]; then node --check "$f"; else echo "skip (not in repo): $f"; fi
          done
```

- [ ] **Step 6: Run the layout test and commit**
```bash
python dev/test_workflows_layout.py
git add .github/workflows/guards.yml .github/workflows/python-tooling.yml .github/workflows/python-legacy.yml dev/test_workflows_layout.py
git commit -m "feat(phase49): split production, data-tooling, and legacy CI lanes"
```

---

### Task A6: Go `runtimecheck` command

**Files:**
- Create: `backend-go/cmd/runtimecheck/main.go`
- Create: `backend-go/cmd/runtimecheck/proctree_windows.go`
- Create: `backend-go/cmd/runtimecheck/proctree_linux.go`
- Create: `backend-go/cmd/runtimecheck/main_test.go`

**Interfaces:**
- `runtimecheck --borsd <exe> --data-dir <dir> --port <n> --timeout 45s --out <json>`
- Exit 0 only when `/healthz` returns 200 and no descendant process is Python/Uvicorn/FastAPI.
- `bannedName(string) bool`, `descendants(root int, all []proc) []proc` are unit-tested.

- [ ] **Step 1: Write the failing unit test**

Create `backend-go/cmd/runtimecheck/main_test.go`:
```go
package main

import "testing"

func TestBannedName(t *testing.T) {
	for _, n := range []string{"python.exe", "python3", "python3.12.exe",
		"pythonw.exe", "libpython3.12.dll", "uvicorn.exe", "fastapi.exe"} {
		if !bannedName(n) {
			t.Errorf("%s must be banned", n)
		}
	}
	for _, n := range []string{"borsd.exe", "BorsTerminal_Ultimate.exe", "node.exe"} {
		if bannedName(n) {
			t.Errorf("%s must not be banned", n)
		}
	}
}

func TestDescendants(t *testing.T) {
	all := []proc{{PID: 1, Parent: 0, Name: "root"}, {PID: 2, Parent: 1, Name: "a"},
		{PID: 3, Parent: 2, Name: "python.exe"}, {PID: 4, Parent: 1, Name: "b"}}
	d := descendants(1, all)
	if len(d) != 3 {
		t.Fatalf("descendants = %d, want 3", len(d))
	}
	found := false
	for _, p := range d {
		if p.Name == "python.exe" {
			found = true
		}
	}
	if !found {
		t.Fatalf("python descendant missing: %+v", d)
	}
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend-go && go test ./cmd/runtimecheck -v`
Expected: package/build failure because `bannedName`/`proc` do not exist.

- [ ] **Step 3: Implement `main.go`**

Create `backend-go/cmd/runtimecheck/main.go`:
```go
// Command runtimecheck proves a borsd process tree contains no Python runtime.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type proc struct {
	PID    int    `json:"pid"`
	Parent int    `json:"parent"`
	Name   string `json:"name"`
}

type report struct {
	Borsd   string `json:"borsd"`
	DataDir string `json:"data_dir"`
	Port    int    `json:"port"`
	Health  string `json:"health"`
	PIDs    []int  `json:"pids"`
	Procs   []proc `json:"procs"`
	Banned  []proc `json:"banned"`
	OK      bool   `json:"ok"`
	Error   string `json:"error,omitempty"`
}

func bannedName(name string) bool {
	b := strings.ToLower(filepath.Base(name))
	b = strings.TrimSuffix(b, ".exe")
	b = strings.TrimSuffix(b, ".dll")
	switch b {
	case "python", "python3", "pythonw", "py", "uvicorn", "fastapi":
		return true
	}
	return strings.HasPrefix(b, "python3") || strings.HasPrefix(b, "libpython")
}

func descendants(root int, all []proc) []proc {
	byParent := map[int][]proc{}
	for _, p := range all {
		byParent[p.Parent] = append(byParent[p.Parent], p)
	}
	out := []proc{}
	queue := []int{root}
	seen := map[int]bool{root: true}
	for len(queue) > 0 {
		pid := queue[0]
		queue = queue[1:]
		for _, c := range byParent[pid] {
			if seen[c.PID] {
				continue
			}
			seen[c.PID] = true
			out = append(out, c)
			queue = append(queue, c.PID)
		}
	}
	return out
}

func healthy(port int, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	url := fmt.Sprintf("http://127.0.0.1:%d/healthz", port)
	for time.Now().Before(deadline) {
		resp, err := http.Get(url)
		if err == nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				return true
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}

func main() {
	borsd := flag.String("borsd", "", "path to borsd executable")
	dataDir := flag.String("data-dir", "", "directory containing market.db")
	port := flag.Int("port", 18081, "port")
	timeout := flag.Duration("timeout", 45*time.Second, "health timeout")
	outPath := flag.String("out", "", "write JSON report here")
	flag.Parse()
	if *borsd == "" || *dataDir == "" {
		fmt.Fprintln(os.Stderr, "--borsd and --data-dir are required")
		os.Exit(2)
	}
	rep := report{Borsd: *borsd, DataDir: *dataDir, Port: *port}
	cmd := exec.Command(*borsd, "--db-dir", *dataDir, "--port", strconv.Itoa(*port))
	cmd.Env = append(os.Environ(), "BORS_DATA_DIR="+*dataDir)
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	setProcGroup(cmd)
	if err := cmd.Start(); err != nil {
		rep.Error = err.Error()
		writeReport(rep, *outPath)
		os.Exit(1)
	}
	defer killTree(cmd.Process.Pid)
	if !healthy(*port, *timeout) {
		rep.Error = "healthz timeout"
		writeReport(rep, *outPath)
		os.Exit(1)
	}
	rep.Health = "ok"
	all, err := processTree()
	if err != nil {
		rep.Error = err.Error()
		writeReport(rep, *outPath)
		os.Exit(1)
	}
	rep.Procs = descendants(cmd.Process.Pid, all)
	rep.PIDs = []int{cmd.Process.Pid}
	for _, p := range rep.Procs {
		rep.PIDs = append(rep.PIDs, p.PID)
		if bannedName(p.Name) {
			rep.Banned = append(rep.Banned, p)
		}
	}
	rep.OK = len(rep.Banned) == 0
	writeReport(rep, *outPath)
	if !rep.OK {
		os.Exit(1)
	}
}

func writeReport(r report, path string) {
	b, _ := json.MarshalIndent(r, "", "  ")
	if path != "" {
		_ = os.WriteFile(path, b, 0o644)
	}
	fmt.Println(string(b))
}
```

- [ ] **Step 4: Implement platform files**

Create `backend-go/cmd/runtimecheck/proctree_windows.go`:
```go
//go:build windows

package main

import (
	"os/exec"
	"strconv"
	"unsafe"

	"golang.org/x/sys/windows"
)

func setProcGroup(cmd *exec.Cmd) {}

func processTree() ([]proc, error) {
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil, err
	}
	defer windows.CloseHandle(snap)
	var e windows.ProcessEntry32
	e.Size = uint32(unsafe.Sizeof(e))
	out := []proc{}
	for err = windows.Process32First(snap, &e); err == nil; err = windows.Process32Next(snap, &e) {
		out = append(out, proc{
			PID:    int(e.ProcessID),
			Parent: int(e.ParentProcessID),
			Name:   windows.UTF16ToString(e.ExeFile[:]),
		})
	}
	return out, nil
}

func killTree(pid int) {
	_ = exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(pid)).Run()
}
```

Create `backend-go/cmd/runtimecheck/proctree_linux.go`:
```go
//go:build linux

package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

func setProcGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func processTree() ([]proc, error) {
	ents, err := os.ReadDir("/proc")
	if err != nil {
		return nil, err
	}
	out := []proc{}
	for _, e := range ents {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		b, err := os.ReadFile(filepath.Join("/proc", e.Name(), "stat"))
		if err != nil {
			continue
		}
		s := string(b)
		i := strings.LastIndex(s, ")")
		if i < 0 {
			continue
		}
		f := strings.Fields(s[i+1:])
		if len(f) < 2 {
			continue
		}
		ppid, _ := strconv.Atoi(f[1])
		out = append(out, proc{PID: pid, Parent: ppid, Name: strings.TrimPrefix(s[:i], "(")})
	}
	return out, nil
}

func killTree(pid int) {
	_ = syscall.Kill(-pid, syscall.SIGKILL)
	_ = syscall.Kill(pid, syscall.SIGKILL)
}
```

- [ ] **Step 5: Run unit tests**

Run:
```bash
cd backend-go
go test ./cmd/runtimecheck -v
go vet ./cmd/runtimecheck
```
Expected: both tests PASS; vet clean.

- [ ] **Step 6: Integration test with a real borsd (local, isolated)**

Run from repo root:
```bash
mkdir -p _scratch/rt && cp market.db _scratch/rt/market.db
cd backend-go
go run ./cmd/runtimecheck --borsd ./dist-ci/BorsTerminal_Ultimate.exe --data-dir ../_scratch/rt --port 18083 --out ../_scratch/rt/runtimecheck.json
```
If `dist-ci/BorsTerminal_Ultimate.exe` does not exist, build it:
```bash
go build -o ../dist-ci/BorsTerminal_Ultimate.exe ./cmd/borsd
```
Expected: JSON with `"ok": true`, `"banned": []`, `"health": "ok"`. If it fails, inspect `runtimecheck.json`; do not fake the result.

- [ ] **Step 7: Commit**
```bash
git add backend-go/cmd/runtimecheck
git commit -m "feat(phase49): add Go runtimecheck proving no Python process in borsd tree"
```

---

### Task A7: Extend bundlecheck with required files and forbidden directories

**Files:**
- Modify: `backend-go/cmd/bundlecheck/main.go`
- Modify: `backend-go/cmd/bundlecheck/main_test.go`

- [ ] **Step 1: Write the failing test**

Append to `backend-go/cmd/bundlecheck/main_test.go`:
```go
func TestRequiredAndForbiddenLayout(t *testing.T) {
	dir := t.TempDir()
	if errs := scanLayout(dir); len(errs) == 0 {
		t.Fatal("empty dir must fail required-file scan")
	}
	for _, f := range requiredFiles {
		p := filepath.Join(dir, f)
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		_ = os.WriteFile(p, []byte("x"), 0o644)
	}
	if errs := scanLayout(dir); len(errs) != 0 {
		t.Fatalf("unexpected errors: %v", errs)
	}
	_ = os.MkdirAll(filepath.Join(dir, "_internal"), 0o755)
	if errs := scanLayout(dir); len(errs) == 0 {
		t.Fatal("_internal must fail the layout scan")
	}
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend-go && go test ./cmd/bundlecheck -run TestRequiredAndForbiddenLayout -v`
Expected: undefined `scanLayout`, `requiredFiles`.

- [ ] **Step 3: Implement**

Add to `backend-go/cmd/bundlecheck/main.go`:
```go
var requiredFiles = []string{
	"BorsTerminal_Ultimate.exe",
	"BorsTerminal_Shell.exe",
	"frontend/index.html",
	"Version.txt",
}

func scanLayout(root string) []Finding {
	out := []Finding{}
	for _, f := range requiredFiles {
		if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(f))); err != nil {
			out = append(out, Finding{Path: f, Reason: "required file missing"})
		}
	}
	for _, d := range []string{"_internal", "site-packages", "python3.12", "python3"} {
		if fi, err := os.Stat(filepath.Join(root, d)); err == nil && fi.IsDir() {
			out = append(out, Finding{Path: d, Reason: "forbidden runtime directory"})
		}
	}
	return out
}
```
Call `scanLayout` in `main` after the existing scan and merge findings. Ensure JSON output keeps the same shape.

- [ ] **Step 4: Run tests**

Run: `cd backend-go && go test ./cmd/bundlecheck -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend-go/cmd/bundlecheck
git commit -m "feat(phase49): require production bundle layout and forbid runtime directories"
```

---

### Task A8: Installer smoke and Seed release gate

**Files:**
- Create: `scripts/check_seed_release.py`
- Create: `scripts/test_check_seed_release.py`
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Write the failing test**

Create `scripts/test_check_seed_release.py`:
```python
#!/usr/bin/env python3
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "scripts", "check_seed_release.py")


def make_db(rows):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE seed_manifest(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO seed_manifest VALUES ('reference_derived_rows', ?)", (str(rows),))
    con.commit()
    con.close()
    return path


def main():
    p = make_db(3105)
    r = subprocess.run([sys.executable, TOOL, "--db", p], capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "SEED_RELEASE_BLOCKED" in r.stdout
    r = subprocess.run([sys.executable, TOOL, "--db", p,
                        "--owner-approved-reference-redistribution"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SEED_RELEASE_OK" in r.stdout
    p0 = make_db(0)
    r = subprocess.run([sys.executable, TOOL, "--db", p0], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    print("SEED RELEASE GATE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python scripts/test_check_seed_release.py`
Expected: file missing.

- [ ] **Step 3: Implement the gate**

Create `scripts/check_seed_release.py`:
```python
#!/usr/bin/env python3
"""Refuse Seed packaging while reference-derived rows lack owner approval."""
from __future__ import annotations

import argparse
import sqlite3
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--owner-approved-reference-redistribution", action="store_true")
    args = ap.parse_args()
    con = sqlite3.connect("file:%s?mode=ro" % args.db.replace("\\", "/"), uri=True)
    try:
        row = con.execute(
            "SELECT value FROM seed_manifest WHERE key='reference_derived_rows'").fetchone()
    except sqlite3.OperationalError:
        con.close()
        print("SEED_RELEASE_BLOCKED: seed_manifest is missing; the seed was not built "
              "by the Phase 4.9.1 pipeline")
        return 1
    finally:
        con.close()
    rows = int(row[0]) if row else 0
    if rows > 0 and not args.owner_approved_reference_redistribution:
        print("SEED_RELEASE_BLOCKED: %d reference-derived rows; "
              "owner approval for redistribution is required" % rows)
        return 1
    print("SEED_RELEASE_OK: reference_derived_rows=%d" % rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

Run: `python scripts/test_check_seed_release.py`
Expected: `SEED RELEASE GATE TESTS OK`.

- [ ] **Step 5: Wire into `release.yml`**

Add before the `Compile Inno Installer` step:
```yaml
      - name: Seed release gate
        shell: pwsh
        run: |
          if (Test-Path market.db) {
            python scripts/check_seed_release.py --db market.db
            if ($LASTEXITCODE -ne 0) { Write-Output "::error::[seed] release blocked"; exit 1 }
          } else {
            Write-Output "::error::[seed] market.db missing; cannot evaluate release gate"
            exit 1
          }
```
Note: this gate will block release until the owner approves reference redistribution. That is intentional; do not add the approval flag in CI without an owner decision.

- [ ] **Step 6: Commit**
```bash
git add scripts/check_seed_release.py scripts/test_check_seed_release.py .github/workflows/release.yml
git commit -m "feat(phase49): add Seed reference-data release gate"
```

---

### Task A9: Final CI evidence

**Files:**
- Create: `tools/phase49/fetch_ci_results.py`
- Create: `docs/opportunity-center/phase49/CI-FINAL-RESULTS.json`

- [ ] **Step 1: Push the branch and start CI**

Run:
```bash
git push -u origin mission/phase49-full-verification-python-ci-2026-11-10
gh run list --branch mission/phase49-full-verification-python-ci-2026-11-10 --limit 5
```
Expected: workflows `guards`, `python-tooling`, `python-legacy` appear. Wait for completion with `gh run watch <id>`.

- [ ] **Step 2: Fetch the final run evidence**

Create `tools/phase49/fetch_ci_results.py`:
```python
#!/usr/bin/env python3
"""Record the latest CI run per workflow for the final HEAD."""
import json
import subprocess
import sys

sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
raw = subprocess.check_output(
    ["gh", "run", "list", "--commit", sha, "--limit", "30", "--json",
     "databaseId,headSha,name,workflowName,status,conclusion,url"], text=True)
runs = json.loads(raw)
out = {"commit_sha": sha, "runs": []}
for r in runs:
    if r.get("status") != "completed":
        continue
    jobs_raw = subprocess.check_output(
        ["gh", "run", "view", str(r["databaseId"]), "--json",
         "jobs,headSha,conclusion,url,workflowName"], text=True)
    jobs = json.loads(jobs_raw).get("jobs", [])
    out["runs"].append({
        "workflow": r["workflowName"], "run_id": r["databaseId"],
        "url": r["url"], "conclusion": r["conclusion"],
        "jobs": [{"name": j["name"], "conclusion": j["conclusion"],
                  "details_url": j["html_url"]} for j in jobs],
    })
path = "docs/opportunity-center/phase49/CI-FINAL-RESULTS.json"
with open(path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print("wrote", path, "runs:", len(out["runs"]))
```

Run:
```bash
python tools/phase49/fetch_ci_results.py
```
Expected: JSON contains the final SHA and every job's conclusion; every Production job is `success`; legacy may be `failure` by design and is reported as non-blocking.

- [ ] **Step 3: Commit the evidence**
```bash
git add tools/phase49/fetch_ci_results.py docs/opportunity-center/phase49/CI-FINAL-RESULTS.json
git commit -m "docs(phase49): record final CI results on the mission HEAD"
```

## Plan A Acceptance

- `python dev/suite_registry_guard.py` → `SUITE REGISTRY GUARD OK`.
- `python dev/test_runner_profiles.py` → `RUNNER PROFILE TESTS OK`.
- `python dev/test_workflows_layout.py` → `WORKFLOW LAYOUT TESTS OK`.
- `go test ./cmd/runtimecheck ./cmd/bundlecheck` → PASS.
- CI: `guards` production jobs all green; `python-tooling` green; `python-legacy` report-only.
- `CI-FINAL-RESULTS.json` exists with the final SHA and real links.
