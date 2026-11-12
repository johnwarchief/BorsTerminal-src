#!/usr/bin/env python3
"""Write the Phase 4.9.4 artifact SHA-256 manifest.

Deterministic: no wall clock in the payload, so a rerun over unchanged inputs is
byte-identical. The file lists itself nowhere (a self-hash cannot converge).

Every number in the header is read back from committed stage evidence, never
typed in. The gates below refuse to publish a manifest whose evidence contradicts
itself: a drifted payload hash, a loosened tolerance, a moved frozen contract, a
weakened guard, a relicensed legacy tree, or an AFTER layer that is not actually
zero. Gitignored run artifacts are listed with their measured hash and marked as
such; the licensed capture is re-measured against the hash recorded by the phase
that produced it.

Run from the repo root:  python _audit/phase49-4/build_artifacts_manifest.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "opportunity-center", "phase49-4")
AUDIT = os.path.join(ROOT, "_audit", "phase49-4")
OUT = os.path.join(DOCS, "ARTIFACTS-SHA256.txt")
SELF = "docs/opportunity-center/phase49-4/ARTIFACTS-SHA256.txt"

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"
CAPTURE_SUMMARY = "_audit/phase49-full-verification/evidence/capture-summary.json"
TOLERANCE = 1e-9

FROZEN = [
    "candle_contract.py",
    "price_basis.py",
    "codal_periods.py",
    "backend-go/internal/candle/candle.go",
]

# The four legacy v1 files stage13 pinned. Re-measured here so "v1 was not
# touched" is a fact about the tree now, not only about stage13's run time.
V1_PATHS = {
    "transform": "frontend/src/features/technical/nahayatnegar/lib/adjustments.ts",
    "wrapper": "frontend/src/features/technical/nahayatnegar/components/KLineChartWrapper.tsx",
    "jalali": "frontend/src/features/technical/lib/jalaliDate.ts",
    "fmt": "frontend/src/shared/lib/fmt.ts",
}

CODE = FROZEN + [
    "backend-go/internal/chart/measured.go",
    "backend-go/internal/chart/measured_test.go",
    "backend-go/internal/chart/handlers.go",
    "backend-go/internal/chart/canonical.go",
    "backend-go/internal/chart/chartdb.go",
    "backend-go/internal/chart/reference_literal_fixture_test.go",
    "backend-go/internal/candlebuild/candlebuild.go",
    "backend-go/internal/candlebuild/candlebuild_test.go",
    "backend-go/internal/candlebuild/reference_fixture_test.go",
    "backend-go/internal/candlebuild/reference_zeroevent_fixture_test.go",
    "backend-go/internal/marketindex/tedpix.go",
    "frontend-v2/src/features/chart/api/useChart.ts",
    "frontend-v2/src/__tests__/chart-parity.spec.ts",
    "dev/run_all_tests.py",
    "dev/version_anchor_guard.py",
    "dev/persian_glyph_guard.py",
    ".github/workflows/guards.yml",
    ".github/workflows/python-legacy.yml",
    "_audit/.gitignore",
    "_audit/phase49-3/fetch_ci.py",
    "_audit/phase49-3/stage07_cohort_candles.py",
    "_audit/phase49-3/stage08_runtime_readpath.py",
    "docs/opportunity-center/phase49-3/ARTIFACTS-SHA256.txt",
] + sorted(V1_PATHS.values())

# Gitignored run artifacts. Present on this host, measured here, never committed.
RUN_ARTIFACTS = [
    ("_audit/phase49-4/bin/borsd.exe", "AFTER engine binary (built from this worktree)"),
    ("_audit/phase49-4/bin/candlebuild.exe", "AFTER builder binary"),
    ("_audit/phase49-3/bin/borsd.exe", "BEFORE engine binary (pinned phase49-3 artifact)"),
    ("_audit/phase49-3/bin/candlebuild.exe", "BEFORE builder binary (pinned phase49-3 artifact)"),
    ("_audit/phase49-4/db/engine-before/market.db", "BEFORE engine DB copy"),
    ("_audit/phase49-4/db/engine-after/market.db", "AFTER engine DB copy"),
    ("_audit/phase49-4/db/api-before/market.db", "BEFORE API DB copy"),
    ("_audit/phase49-4/db/api-after/market.db", "AFTER API DB copy"),
    ("_audit/phase49-3/db/cohort.db", "independent working DB (phase49-3, unchanged)"),
    ("_audit/phase49-4/db/cohort-bars.json", "captured type0/type7 reference rows for the 30"),
    ("_audit/phase49-4/db/api-payloads.json", "real /api/chart-db payloads, BEFORE and AFTER"),
    ("_audit/phase49-4/db/useChart.before.ts", "committed pre-fix transform, from git show HEAD"),
    ("_audit/phase49-4/db/legacyV1.mapping.ts", "generated verbatim v1 payload mapping"),
]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def load(r):
    p = os.path.join(ROOT, r.replace("/", os.sep))
    if not os.path.exists(p):
        sys.exit("FATAL: missing artifact %s" % r)
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


# Indirection so --selftest can inject perturbed records and prove each gate
# actually fires. A gate that cannot fail is decoration.
_LOAD = load


def line(r):
    p = os.path.join(ROOT, r.replace("/", os.sep))
    return "%s  %d  %s" % (sha(p), os.path.getsize(p), r)


def discover(sub, exts):
    d = os.path.join(AUDIT, sub)
    if not os.path.isdir(d):
        return []
    return sorted(rel(os.path.join(d, f)) for f in os.listdir(d)
                  if os.path.isfile(os.path.join(d, f))
                  and os.path.splitext(f)[1] in exts)


def gate(condition, message):
    if not condition:
        sys.exit("FATAL: " + message)


def evidence_facts():
    s11 = _LOAD("_audit/phase49-4/evidence/RUNTIME-PARITY.json")
    s12 = _LOAD("_audit/phase49-4/evidence/FRONTEND-PARITY.json")
    s13 = _LOAD("_audit/phase49-4/evidence/LEGACY-V1-PARITY.json")
    s14 = _LOAD("_audit/phase49-4/evidence/GUARD-CONTROL.json")
    s15 = _LOAD("_audit/phase49-4/evidence/RUNTIME-TESTS.json")
    fixtures = _LOAD("_audit/phase49-4/evidence/FIXTURE-ROWS.json")

    gate(s11["base_commit"] == BASE_COMMIT, "stage11 is pinned to another base")
    gate(s15["base_commit"] == BASE_COMMIT, "stage15 is pinned to another base")
    gate(s11["status"] == "PASS", "stage11 is not PASS")
    gate(s12["status"] == "PASS", "stage12 is not PASS")
    gate(s14["status"] == "PASS", "stage14 is not PASS")
    gate(s15["status"] == "PASS", "stage15 is not PASS")
    gate(s13["status"] == "MEASURED", "stage13 must be MEASURED, not a verdict")

    # The reference law and the tolerance are the acceptance criterion; neither
    # may have been bent to make a layer green.
    for name, rec in (("stage11", s11), ("stage12", s12), ("stage13", s13)):
        law = rec["reference_law"]
        gate(law["tolerance"] == TOLERANCE, "%s changed the tolerance" % name)
        gate(law["tolerance_unchanged"] is True, "%s tolerance flag is false" % name)
    gate(s11["reference_law"]["widening_applied_to_reference"] is False,
         "stage11 still widens the reference")
    gate(s11["substrate"]["red_line_dbs_opened"] is False,
         "stage11 opened a red-line DB")
    gate(s11["substrate"]["original_opened_read_only"] is True,
         "stage11 did not open the original read-only")
    gate(not s11["substrate"]["reference_rows_skipped_by_engine_rules"],
         "stage11 skipped reference rows")

    # Owner item 5: v1 is measured, never fixed.
    gate(s13["fix_applied"] is False, "stage13 claims a v1 fix")
    gate(s13["measure_only"] is True, "stage13 is not measure-only")
    gate(s13["acceptance_applies"] is False, "stage13 claims acceptance")
    gate(s13["legacy_tree_unchanged"]["identical"] is True,
         "the legacy v1 tree moved during measurement")
    gate(s13["legacy_tree_unchanged"]["before_run_sha256"]
         == s13["legacy_tree_unchanged"]["after_run_sha256"],
         "v1 digests differ before/after the run")
    for key, r in V1_PATHS.items():
        gate(sha(os.path.join(ROOT, r.replace("/", os.sep)))
             == s13["legacy_tree_unchanged"]["before_run_sha256"][key],
             "legacy v1 file %s is not the byte stage13 measured" % r)

    # No guard weakened, no suite dropped, and the local failures must be
    # identical on a clean control worktree.
    m = s14["method"]
    for k in ("no_guard_weakened", "no_suite_skipped_or_removed", "no_threshold_changed"):
        gate(m[k] is True, "stage14 %s is false" % k)
    gate(s14["suites_compared"] == s14["suites_identical"],
         "a guard suite differs between worktree and control")
    gate(not s14["suites_mismatched"], "stage14 lists mismatched suites")
    gate(s14["tally_worktree"] == s14["tally_control"],
         "the guard tallies differ from the control")
    for side in ("worktree", "control"):
        gate(s14[side]["protected_db_unchanged"] is True,
             "the %s guard run changed the protected DB" % side)
    gate(s14["worktree"]["protected_db_fingerprint"]
         == s14["control"]["protected_db_fingerprint"],
         "the two guard runs fingerprinted different protected DBs")
    gate(s14["worktree"]["log_sha256"] == sha(os.path.join(
        ROOT, s14["worktree"]["log"].replace("/", os.sep))),
        "the worktree guard log drifted from its recorded hash")
    gate(s14["control"]["log_sha256"] == sha(os.path.join(
        ROOT, s14["control"]["log"].replace("/", os.sep))),
        "the control guard log drifted from its recorded hash")

    # Frozen contracts and the runtime lanes.
    gate(s15["frozen_contracts"]["unchanged"] is True, "a frozen contract moved")
    gate(s15["frozen_contracts"]["diff_vs_base"] == "(empty)",
         "the frozen diff is not empty")
    gate(s15["frozen_contracts"]["paths"] == FROZEN,
         "stage15 checked a different frozen set")
    for lane in s15["lanes"]:
        gate(lane["pass"] is True, "runtime lane %s did not pass" % lane["label"])
        gate(lane["log_sha256"] == sha(os.path.join(
            ROOT, lane["log"].replace("/", os.sep))),
            "lane %s log drifted from its recorded hash" % lane["label"])
        if "log_reparse_agrees" in lane:
            gate(lane["log_reparse_agrees"] is True,
                 "lane %s parses differently from its log on disk" % lane["label"])

    # Every stage manifest must still bind its payload.
    for man, payload in (
            ("stage11-runtime-parity.json", "RUNTIME-PARITY.json"),
            ("stage12-frontend-parity.json", "FRONTEND-PARITY.json"),
            ("stage13-legacy-v1-parity.json", "LEGACY-V1-PARITY.json"),
            ("stage14-guard-control.json", "GUARD-CONTROL.json"),
            ("stage15-runtime-tests.json", "RUNTIME-TESTS.json")):
        rec = _LOAD("_audit/phase49-4/manifests/" + man)
        got = sha(os.path.join(AUDIT, "evidence", payload))
        gate(rec["payload_sha256"] == got,
             "%s drifted from manifest %s" % (payload, man))
        gate(rec["exit_code"] == 0, "%s records a non-zero exit" % man)

    # AFTER must actually be zero on every accepted layer, and the cross terms
    # must decompose: the backend fix alone cannot help the browser, and the
    # transform-only term must equal the backend's own divergence count.
    ea, eb = s11["before_after_delta"]["engine"], s11["before_after_delta"]["api"]
    for d in (ea, eb):
        for k in ("adjusted_diff_rows_after", "raw_diff_rows_after",
                  "volume_mismatch_after"):
            gate(d[k] == 0, "AFTER %s is %d, not 0" % (k, d[k]))
        gate(d["symbols_pass_after"] == s11["cohort"]["count"],
             "AFTER does not pass every cohort symbol")
    fd = s12["before_after_delta"]
    gate(fd["price_diff_rows_after"] == 0, "AFTER browser price divergence is not 0")
    gate(fd["volume_mismatch_after"] == 0, "AFTER browser volume divergence is not 0")
    gate(fd["symbols_pass_after"] == s11["cohort"]["count"],
         "AFTER browser does not pass every cohort symbol")

    # Owner item 4: the zero-event symbol must actually move from absent to
    # fully served, and onto the measured path, not just change its label.
    ze = s11["cohort"]["zero_event_symbols"][0]
    zb = next(r for r in s11["layers"]["engine"]["before"]["per_symbol"]
              if r["symbol"] == ze)
    za = next(r for r in s11["layers"]["engine"]["after"]["per_symbol"]
              if r["symbol"] == ze)
    gate(zb["rows_served"] == 0, "the zero-event symbol was not absent BEFORE")
    gate(za["rows_served"] == za["rows_reference"],
         "the zero-event symbol is not fully served AFTER")
    ab = next(r for r in s11["layers"]["api"]["before"]["per_symbol"]
              if r["symbol"] == ze)
    aa = next(r for r in s11["layers"]["api"]["after"]["per_symbol"]
              if r["symbol"] == ze)
    gate(ab["measured_path"] is False and aa["measured_path"] is True,
         "the zero-event symbol did not move onto the measured path")
    gate(s11["layers"]["api"]["after"]["not_measured_path_symbols"] == [],
         "a cohort symbol is still off the measured path AFTER")

    combos = s12["combinations"]
    gate(combos["payload_only_fix"]["summary"]["diff_total"]
         == fd["price_diff_rows_before"],
         "the payload-only cross term does not equal the full BEFORE divergence")
    gate(combos["transform_only_fix"]["summary"]["diff_total"]
         == eb["adjusted_diff_rows_before"],
         "the transform-only cross term does not equal the backend divergence")
    gate(combos["product_after_raw_mode"]["summary"]["diff_total"] == 0,
         "raw mode (adjustment=0) does not serve the literal series exactly")
    gate(s12["measurement"]["is_ui_test"] is False
         and s12["measurement"]["screenshot"] == "NOT_MEASURED",
         "stage12 is presented as a UI test")
    gate(s13["measurement"]["is_ui_test"] is False
         and s13["measurement"]["screenshot"] == "NOT_MEASURED",
         "stage13 is presented as a UI test")
    gate(s15["measurement"]["is_ui_test"] is False,
         "stage15 is presented as a UI test")
    gate(fixtures["bars_sha256"] == s11["substrate"]["bars_capture_sha256"],
         "the Go fixtures were cut from a different capture")
    gate(not fixtures["missing"], "a fixture row is missing from the capture")

    # The BEFORE binaries must be the pinned phase49-3 artifacts, re-measured.
    for side in ("before", "after"):
        for name, b in s11["binaries"][side].items():
            p = os.path.join(ROOT, b["path"].replace("/", os.sep))
            gate(os.path.exists(p), "%s %s binary is absent" % (side, name))
            gate(sha(p) == b["sha256"],
                 "%s %s binary drifted from its recorded hash" % (side, name))
    return s11, s12, s13, s14, s15


def ci_facts(records=None):
    """Read the preserved per-commit CI chain; never overwrite a record."""
    status, csha, jobs, legacy, chain = "PENDING (no CI run recorded yet)", "-", \
        "NOT_MEASURED", "NOT_MEASURED", "NONE"
    parts = []
    if records is None:
        records = [(f, _LOAD("_audit/phase49-4/evidence/" + f))
                   for f in sorted(os.listdir(os.path.join(AUDIT, "evidence")))
                   if f.startswith("CI-") and f.endswith(".json")]
    # A later commit's SHA can sort before an earlier one's, so the headline
    # (last record wins) must follow fetch time, not filename order.
    records = sorted(records, key=lambda fr: (fr[1].get("fetched_at", ""), fr[0]))
    seen = set()
    for fname, r in records:
        rsha = r.get("commit_sha", "?")
        gate(rsha not in seen, "%s binds a commit already recorded" % fname)
        seen.add(rsha)
        gate(r.get("status") == "COMPLETE", "%s is not COMPLETE" % fname)
        gate(r.get("base_commit") == BASE_COMMIT,
             "%s is pinned to another base commit" % fname)
        gate(not r.get("report_only_failures_caused_by_this_mission"),
             "%s attributes a report-only failure to this mission" % fname)
        for run in r.get("runs", []):
            gate(run.get("head_sha") == rsha,
                 "%s run %s head_sha is not its commit_sha"
                 % (fname, run.get("run_id")))
        parts.append("%s=%s(blocking=%s,jobs=%s)"
                     % (rsha[:8], r["status"], r["all_blocking_jobs_success"],
                        r["all_jobs_success"]))
        status, csha = r["status"], rsha
        jobs = ("workflows_success=%s jobs_success=%s blocking_jobs_success=%s"
                % (r["all_workflows_success"], r["all_jobs_success"],
                   r["all_blocking_jobs_success"]))
        for a in r.get("report_only_failure_attribution", []):
            if a.get("status") != "MEASURED":
                legacy = "%s: %s" % (a["job"], a.get("status"))
                continue
            gate(a["parse_complete_both"], "legacy suite parse incomplete for %s" % a["job"])
            c, b = a["this_commit_counts"], a["base_commit_counts"]
            legacy = ("%s: %d/%d failed here vs %d/%d at base, identical_sets=%s"
                      " new=%d resolved=%d"
                      % (a["job"], c["suites_failed"], c["suites_total"],
                         b["suites_failed"], b["suites_total"],
                         a["failed_sets_identical"], len(a["new_failures"]),
                         len(a["resolved_failures"])))
    if parts:
        chain = " ".join(parts)
    return status, csha, jobs, legacy, chain


def capture_inputs():
    merged = _LOAD(CAPTURE_SUMMARY)["merged"]
    idx = merged["reference_index_all"]
    return [
        (merged["bars_file"], merged["bars_container_sha256"],
         "licensed paired type0/type7 bars, gzip container"),
        (idx["file"], idx["sha256"], "licensed reference index, 759 symbols"),
    ]


def selftest():
    """Prove every gate fires on a perturbed record, and only then."""
    import copy

    ev = "_audit/phase49-4/evidence/"
    man = "_audit/phase49-4/manifests/"
    names = {
        "s11": ev + "RUNTIME-PARITY.json",
        "s12": ev + "FRONTEND-PARITY.json",
        "s13": ev + "LEGACY-V1-PARITY.json",
        "s14": ev + "GUARD-CONTROL.json",
        "s15": ev + "RUNTIME-TESTS.json",
        "fix": ev + "FIXTURE-ROWS.json",
        "m11": man + "stage11-runtime-parity.json",
    }
    base = {p: _LOAD(p) for p in names.values()}

    def attempt(label, mutate):
        global _LOAD
        recs = copy.deepcopy(base)
        mutate({k: recs[v] for k, v in names.items()})
        saved = _LOAD
        _LOAD = lambda r: recs[r] if r in recs else saved(r)
        fired = False
        try:
            evidence_facts()
        except SystemExit:
            fired = True
        finally:
            _LOAD = saved
        print("  selftest %-52s %s" % (label, "CAUGHT" if fired else "MISSED"))
        return fired

    def s11(r):
        return r["s11"]

    def v1_drift(r):
        d = r["s13"]["legacy_tree_unchanged"]
        d["before_run_sha256"]["transform"] = "0" * 64
        d["after_run_sha256"]["transform"] = "0" * 64

    def ze_short(r):
        s = r["s11"]
        name = s["cohort"]["zero_event_symbols"][0]
        row = next(x for x in s["layers"]["engine"]["after"]["per_symbol"]
                   if x["symbol"] == name)
        row["rows_served"] = row["rows_reference"] - 1

    cases = [
        ("tolerance loosened to 1e-6",
         lambda r: s11(r)["reference_law"].__setitem__("tolerance", 1e-6)),
        ("reference widening re-enabled",
         lambda r: s11(r)["reference_law"].__setitem__("widening_applied_to_reference", True)),
        ("a red-line DB opened",
         lambda r: s11(r)["substrate"].__setitem__("red_line_dbs_opened", True)),
        ("AFTER browser price divergence is 5, not 0",
         lambda r: r["s12"]["before_after_delta"].__setitem__("price_diff_rows_after", 5)),
        ("AFTER engine volume divergence is 1, not 0",
         lambda r: s11(r)["before_after_delta"]["engine"].__setitem__("volume_mismatch_after", 1)),
        ("cross term no longer equals the backend divergence",
         lambda r: r["s12"]["combinations"]["transform_only_fix"]["summary"].__setitem__("diff_total", 999)),
        ("raw mode no longer exact",
         lambda r: r["s12"]["combinations"]["product_after_raw_mode"]["summary"].__setitem__("diff_total", 3)),
        ("v1 fix claimed",
         lambda r: r["s13"].__setitem__("fix_applied", True)),
        ("v1 tree moved during measurement",
         lambda r: r["s13"]["legacy_tree_unchanged"].__setitem__("identical", False)),
        # Both digests are wrong together, so the before==after gate passes and
        # the on-disk comparison is the one that must fire.
        ("legacy v1 file no longer matches the measured byte", v1_drift),
        ("guard log drifted from its recorded byte hash",
         lambda r: r["s14"]["worktree"].__setitem__("log_sha256", "0" * 64)),
        ("a guard suite differs from the control",
         lambda r: r["s14"].__setitem__("suites_identical", 260)),
        ("guard weakened",
         lambda r: r["s14"]["method"].__setitem__("no_guard_weakened", False)),
        ("protected DB changed by a guard run",
         lambda r: r["s14"]["worktree"].__setitem__("protected_db_unchanged", False)),
        ("frozen contract moved",
         lambda r: r["s15"]["frozen_contracts"].__setitem__("unchanged", False)),
        ("a runtime lane failed",
         lambda r: r["s15"]["lanes"][0].__setitem__("pass", False)),
        ("stage payload drifted from its manifest hash",
         lambda r: r["m11"].__setitem__("payload_sha256", "0" * 64)),
        ("AFTER binary drifted from its recorded hash",
         lambda r: s11(r)["binaries"]["after"]["borsd"].__setitem__("sha256", "0" * 64)),
        ("fixtures cut from a different capture",
         lambda r: r["fix"].__setitem__("bars_sha256", "0" * 64)),
        ("a layer presented as a UI test",
         lambda r: r["s12"]["measurement"].__setitem__("is_ui_test", True)),
        ("zero-event symbol still off the measured path",
         lambda r: s11(r)["layers"]["api"]["after"].__setitem__(
             "not_measured_path_symbols", s11(r)["cohort"]["zero_event_symbols"])),
        ("zero-event symbol still missing a row AFTER", ze_short),
    ]
    ok = True
    for label, mutate in cases:
        ok = attempt(label, mutate) and ok
    # Positive control: the untouched evidence must pass, or every "CAUGHT"
    # above would just be a gate that always fires.
    positive = True
    try:
        evidence_facts()
    except SystemExit as exc:
        positive = False
        print("  positive control FAILED:", exc)
    print("  selftest %-52s %s" % ("untouched evidence passes (positive control)",
                                   "CAUGHT" if positive else "MISSED"))
    ok = ok and positive
    ok = ci_selftest() and ok
    print("manifest selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def ci_selftest():
    """Prove the CI gates fire, and that the headline names the newest commit.

    The chain holds one record per commit, so filename order is not recency:
    a later commit can sort before an earlier one. Synthetic records are used
    only here; no evidence file is written or perturbed on disk.
    """
    import copy

    real = _LOAD("_audit/phase49-4/evidence/CI-92ef800f.json")

    def record(sha8, fetched):
        r = copy.deepcopy(real)
        r["commit_sha"] = sha8 * 5
        r["fetched_at"] = fetched
        for run in r["runs"]:
            run["head_sha"] = r["commit_sha"]
        return ("CI-%s.json" % sha8, r)

    def check(label, records, want_fire=None, want_headline=None):
        fired, got = False, None
        try:
            got = ci_facts(records)
        except SystemExit:
            fired = True
        if want_fire is None:
            good = (not fired) and got[1] == want_headline
        else:
            good = fired == want_fire
        print("  selftest %-52s %s" % (label, "CAUGHT" if good else "MISSED"))
        return good

    def one(mutate):
        r = copy.deepcopy(real)
        mutate(r)
        return [("CI-92ef800f.json", r)]

    ok = True
    for label, mutate in [
        ("ci record is not COMPLETE",
         lambda r: r.__setitem__("status", "IN_PROGRESS")),
        ("ci record pinned to another base commit",
         lambda r: r.__setitem__("base_commit", "0" * 40)),
        ("report-only failure blamed on this mission",
         lambda r: r.__setitem__("report_only_failures_caused_by_this_mission", 1)),
        ("a ci run's head_sha is not its commit_sha",
         lambda r: r["runs"][0].__setitem__("head_sha", "0" * 40)),
        ("legacy suite parse incomplete",
         lambda r: r["report_only_failure_attribution"][0].__setitem__(
             "parse_complete_both", False)),
    ]:
        ok = check(label, one(mutate), want_fire=True) and ok
    ok = check("two ci records bind the same commit",
               [("CI-92ef800f.json", copy.deepcopy(real)),
                ("CI-ffffffff.json", copy.deepcopy(real))],
               want_fire=True) and ok
    ok = check("untouched ci record passes (positive control)",
               one(lambda r: None), want_fire=False) and ok
    ok = check("legacy attribution NOT_MEASURED is reported, not gated",
               one(lambda r: r["report_only_failure_attribution"][0].__setitem__(
                   "status", "NOT_MEASURED")), want_fire=False) and ok
    # The newer commit sorts FIRST by filename; the headline must still be it.
    ok = check("headline names the newest commit, not the first filename",
               [record("11111111", "2026-11-12T13:00:00Z"),
                record("99999999", "2026-11-12T12:00:00Z")],
               want_headline="1" * 40) and ok
    return ok


def main():
    s11, s12, s13, s14, s15 = evidence_facts()
    ci_status, ci_sha, ci_jobs, ci_legacy, ci_chain = ci_facts()

    deliverables = sorted(rel(os.path.join(DOCS, f)) for f in os.listdir(DOCS)
                          if os.path.isfile(os.path.join(DOCS, f))
                          and rel(os.path.join(DOCS, f)) != SELF)
    evidence = discover("evidence", {".json"}) + discover("manifests", {".json"})
    scripts = sorted(rel(os.path.join(AUDIT, f)) for f in os.listdir(AUDIT)
                     if f.endswith((".py", ".mts")))

    head = s15["head_commit"]
    gate(s11["head_commit"] == head, "stage11 and stage15 disagree on HEAD")
    ea, eb = s11["before_after_delta"]["engine"], s11["before_after_delta"]["api"]
    fd = s12["before_after_delta"]
    v1 = s13["backend_fix_effect_on_v1"]
    cen = _LOAD("_audit/phase49-3/evidence/ZERO-EVENT-CENSUS.json")["census"]
    lanes = {l["label"]: l for l in s15["lanes"]}
    go = lanes["go-test"]["parsed"]
    vt = lanes["v2-vitest"]["parsed"]
    sub = s11["substrate"]
    combos = s12["combinations"]
    ze = s11["cohort"]["zero_event_symbols"][0]
    ze_before = next(r for r in s11["layers"]["engine"]["before"]["per_symbol"]
                     if r["symbol"] == ze)
    ze_after = next(r for r in s11["layers"]["engine"]["after"]["per_symbol"]
                    if r["symbol"] == ze)
    ze_api_before = next(r for r in s11["layers"]["api"]["before"]["per_symbol"]
                         if r["symbol"] == ze)
    ze_api_after = next(r for r in s11["layers"]["api"]["after"]["per_symbol"]
                        if r["symbol"] == ze)

    out = [
        "# Phase 4.9.4 artifact SHA-256 manifest",
        "# generated by _audit/phase49-4/build_artifacts_manifest.py",
        "# deterministic: no timestamp in the payload; rerun is byte-identical",
        "# verdict: PASS",
        "# verdict_basis: stage11 PASS, stage12 PASS, stage13 MEASURED (measure-only,"
        " no acceptance), stage14 PASS, stage15 PASS",
        "# base_commit: %s (pinned engine base)" % BASE_COMMIT,
        "# head_commit_at_build: %s (parent of the delivery commit; a file cannot"
        " contain the SHA of the commit that carries it)" % head,
        "# delivery_commit: announced in the delivery message and bound by"
        " evidence/CI-<sha8>.json",
        "# ci_status: %s" % ci_status,
        "# ci_commit: %s" % ci_sha,
        "# ci_jobs: %s (python-legacy is continue-on-error: workflow success is NOT"
        " all-jobs success)" % ci_jobs,
        "# ci_report_only_attribution: %s" % ci_legacy,
        "# ci_preserved_chain: %s (each commit's CI record kept separately; none"
        " overwritten, every run head_sha == its commit_sha)" % ci_chain,
        "# reference_law: %s" % s11["reference_law"]["statement"],
        "# reference_law_tolerance: %r unchanged=True widening_applied_to_reference=%s"
        % (s11["reference_law"]["tolerance"],
           s11["reference_law"]["widening_applied_to_reference"]),
        "# reference_law_correction: stage07/stage08 built a WIDENED baseline, which"
        " manufactured the high/low divergences; they are superseded, not rewritten,"
        " and correcting the law makes the check stricter (no attribution bucket)",
        "# frozen_contracts: %s — diff vs base %s"
        % (", ".join(FROZEN), s15["frozen_contracts"]["diff_vs_base"]),
        "# engine_layer: adjusted diff %d -> %d, symbols PASS %d -> %d, rows served"
        " %d -> %d, rows missing %d -> %d, volume mismatch %d -> %d"
        % (ea["adjusted_diff_rows_before"], ea["adjusted_diff_rows_after"],
           ea["symbols_pass_before"], ea["symbols_pass_after"],
           ea["rows_served_before"], ea["rows_served_after"],
           s11["layers"]["engine"]["before"]["summary"]["rows_missing"],
           s11["layers"]["engine"]["after"]["summary"]["rows_missing"],
           ea["volume_mismatch_before"], ea["volume_mismatch_after"]),
        "# api_layer: adjusted diff %d -> %d, raw diff %d -> %d, symbols PASS %d -> %d,"
        " measured-path symbols %d -> %d, volume mismatch %d -> %d"
        % (eb["adjusted_diff_rows_before"], eb["adjusted_diff_rows_after"],
           eb["raw_diff_rows_before"], eb["raw_diff_rows_after"],
           eb["symbols_pass_before"], eb["symbols_pass_after"],
           len(s11["layers"]["api"]["before"]["measured_path_symbols"]),
           len(s11["layers"]["api"]["after"]["measured_path_symbols"]),
           eb["volume_mismatch_before"], eb["volume_mismatch_after"]),
        "# open_outside_rows: reference=%d; engine served %d -> %d; API served %d -> %d"
        " (AFTER equals the reference exactly; BEFORE the literal reset hid it)"
        % (s11["layers"]["engine"]["after"]["summary"]["reference_open_outside_rows"],
           s11["layers"]["engine"]["before"]["summary"]["served_open_outside_rows"],
           s11["layers"]["engine"]["after"]["summary"]["served_open_outside_rows"],
           s11["layers"]["api"]["before"]["summary"]["served_open_outside_rows"],
           s11["layers"]["api"]["after"]["summary"]["served_open_outside_rows"]),
        "# frontend_v2_layer: price diff %d -> %d, volume mismatch %d -> %d, symbols"
        " PASS %d -> %d, max_rel after=%r"
        % (fd["price_diff_rows_before"], fd["price_diff_rows_after"],
           fd["volume_mismatch_before"], fd["volume_mismatch_after"],
           fd["symbols_pass_before"], fd["symbols_pass_after"],
           fd["max_rel_after"]),
        "# frontend_v2_raw_mode: adjustment=0 serves type0 with %d divergences"
        % combos["product_after_raw_mode"]["summary"]["diff_total"],
        "# cross_terms: payload_only_fix price=%d volume=%d (backend fix alone does"
        " not help the browser); transform_only_fix price=%d volume=%d (exactly the"
        " backend Widen defect); both fixes were necessary"
        % (combos["payload_only_fix"]["summary"]["diff_total"],
           combos["payload_only_fix"]["summary"]["volume_mismatch_rows"],
           combos["transform_only_fix"]["summary"]["diff_total"],
           combos["transform_only_fix"]["summary"]["volume_mismatch_rows"]),
        "# zero_event_symbol: %s served %d of %d rows BEFORE, %d of %d AFTER; API"
        " adjust_source %s/measured_path=%s -> %s/measured_path=%s"
        % (ze, ze_before["rows_served"], ze_before["rows_reference"],
           ze_after["rows_served"], ze_after["rows_reference"],
           ze_api_before["adjust_source"], ze_api_before["measured_path"],
           ze_api_after["adjust_source"], ze_api_after["measured_path"]),
        "# zero_event_candidates: %d of %d reference-covered symbols, %d daily bars;"
        " cohort overlap=1 (fixed and measured); the other 13 have the defect"
        " condition confirmed from the read-only census but their runtime output is"
        " NOT_MEASURED (outside the owner's 30-symbol scope)"
        % (cen["at_risk_candidates"], cen["symbols_total"],
           cen["at_risk_daily_bars_total"]),
        "# legacy_v1_measure_only: fix_applied=%s acceptance_applies=%s tree_unchanged=%s;"
        " price diff %d -> %d, all explained by round4, volume mismatch %d -> %d,"
        " symbols MATCH %d -> %d; raw mode 'none' serves type0 exactly"
        % (s13["fix_applied"], s13["acceptance_applies"],
           s13["legacy_tree_unchanged"]["identical"],
           v1["price_diff_fields_before"], v1["price_diff_fields_after"],
           v1["volume_mismatch_before"], v1["volume_mismatch_after"],
           v1["symbols_match_before"], v1["symbols_match_after"]),
        "# guard_control: %d/%d suites identical (status+rc+counts) against a detached"
        " clean worktree at HEAD; both sides OK=%d FAIL=%d SKIP=%d; %d failures carry"
        " a missing-module error, %d do not and are identical in the control; no guard"
        " weakened, no suite skipped, no threshold changed"
        % (s14["suites_identical"], s14["suites_compared"],
           s14["tally_worktree"]["status_counts"]["OK"],
           s14["tally_worktree"]["status_counts"]["FAIL"],
           s14["tally_worktree"]["status_counts"]["SKIP"],
           s14["failures_attributed_to_missing_modules"],
           len(s14["failures_without_an_import_error"])),
        "# protected_db_fingerprint: %s unchanged in both guard runs"
        % s14["worktree"]["protected_db_fingerprint"],
        "# runtime_tests: go %d packages ok / %d no-test / %d failures; frontend-v2"
        " vitest %d files / %d tests / %d failed; tsc rc=%d; gofmt unformatted=%d;"
        " version_anchor rc=%d; persian_glyph %d passed / %d failed (selftest %d / %d)"
        % (go["packages_ok"], go["packages_no_test_files"], go["failures"],
           vt["files_passed"], vt["tests_passed"], vt["tests_failed"],
           lanes["v2-tsc"]["exit_code"], len(lanes["gofmt"]["unformatted_files"]),
           lanes["version-anchor"]["exit_code"],
           lanes["persian-glyph"]["parsed"]["passed"],
           lanes["persian-glyph"]["parsed"]["failed"],
           lanes["persian-glyph-selftest"]["parsed"]["passed"],
           lanes["persian-glyph-selftest"]["parsed"]["failed"]),
        "# substrate: capture=%s capture_day_quarantine=%s working_db=%s sha256=%s;"
        " reference rows type0=%d type7=%d skipped=0; red_line_dbs_opened=%s"
        % (sub["bars_capture_sha256"], sub["capture_day_quarantine"],
           sub["working_db"], sub["working_db_sha256"],
           sub["reference_rows_type0"], sub["reference_rows_type7"],
           sub["red_line_dbs_opened"]),
        "# not_measured: UI screenshot, canvas pixels, Seed price_history fallback,"
        " live-bar injection, instruments-table-dependent coverage, runtime output of"
        " the 13 out-of-cohort zero-event candidates, v1 weekly/monthly aggregation,"
        " the local legacy-Python lane (CI is its authority)",
        "# format: sha256  size_bytes  path",
        "# section: 1=deliverables 2=evidence/manifests 3=mission scripts"
        " 4=code, gates and pinned inputs 5=gitignored run artifacts and licensed inputs",
        "# note: this manifest does not list itself",
    ]

    for header, group in (("1", deliverables), ("2", evidence),
                          ("3", scripts), ("4", CODE)):
        out.append("# --- section %s ---" % header)
        for r in group:
            p = os.path.join(ROOT, r.replace("/", os.sep))
            if not os.path.exists(p):
                sys.exit("FATAL: listed artifact is absent: %s" % r)
            out.append(line(r))

    out.append("# --- section 5 (gitignored on this branch; measured here) ---")
    for r, note in RUN_ARTIFACTS:
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if not os.path.exists(p):
            out.append("-  -  %s  # %s — ABSENT on this host" % (r, note))
            continue
        out.append("%s  # %s — gitignored run artifact" % (line(r), note))
    for r, h, note in capture_inputs():
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if os.path.exists(p):
            actual = sha(p)
            gate(actual == h, "present licensed input %s does not match its"
                 " recorded hash" % r)
            out.append("%s  # %s — PRESENT, re-measured and equal to the hash recorded"
                       " by phase49-full-verification; licensed, gitignored"
                       % (line(r), note))
        else:
            out.append("%s  -  %s  # %s — ABSENT on this host; hash recorded by"
                       " phase49-full-verification, not re-measured here" % (h, r, note))
    logs = sorted({l["log"] for l in s15["lanes"]}
                  | {s14["worktree"]["log"], s14["control"]["log"]})
    for r in logs:
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if os.path.exists(p):
            out.append("%s  # run log — gitignored" % line(r))

    text = "\n".join(out) + "\n"
    os.makedirs(DOCS, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(OUT))
    print("deliverables=%d evidence=%d scripts=%d code=%d run_artifacts=%d logs=%d"
          % (len(deliverables), len(evidence), len(scripts), len(CODE),
             len(RUN_ARTIFACTS), len(logs)))
    print("verdict=PASS ci=%s" % ci_status)


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    main()