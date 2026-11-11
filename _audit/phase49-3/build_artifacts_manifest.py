#!/usr/bin/env python3
"""Write the Phase 4.9.3 artifact SHA-256 manifest.

Deterministic: no wall clock anywhere in the payload, so a rerun over unchanged
inputs is byte-identical.  The file lists itself nowhere (a self-hash cannot
converge).  Licensed inputs that stay out of git are listed with the SHA-256
*recorded by the phase that produced them*: when the bytes are present they are
re-measured here and must match, and when they are absent the recorded hash is
kept and marked ABSENT rather than retyped.  Working-DB facts are read back from
committed stage evidence, never hardcoded.
"""
from __future__ import annotations

import hashlib
import gzip
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3")
AUDIT = os.path.join(ROOT, "_audit", "phase49-3")
OUT = os.path.join(DOCS, "ARTIFACTS-SHA256.txt")
CI = os.path.join(DOCS, "CI-FINAL-RESULTS.json")
SELF = "docs/opportunity-center/phase49-3/ARTIFACTS-SHA256.txt"

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"
VERDICT = "PARTIAL"

CODE = [
    "backend-go/internal/chart/measured.go",
    "backend-go/internal/chart/canonical.go",
    "backend-go/internal/chart/chartdb.go",
    "backend-go/internal/chart/handlers.go",
    "backend-go/internal/candlebuild/candlebuild.go",
    "backend-go/cmd/candlebuild/main.go",
    "backend-go/internal/httpapi/server.go",
    "dev/symbol_identity.py",
    "dev/run_all_tests.py",
    "dev/suite_registry.json",
    "dev/persian_glyph_guard.py",
    "dev/phase49_rules_guard.py",
    "dev/suite_registry_guard.py",
    "dev/test_workflows_layout.py",
    "scripts/check_seed_release.py",
    "scripts/test_check_seed_release.py",
    ".github/workflows/guards.yml",
    "_audit/.gitignore",
    "_audit/phase49-full-verification/stage03_step_ledger.py",
    "_audit/phase49-full-verification/stage05_symbol_ledger.py",
    "_audit/phase49-2/build_coverage_ledger.py",
    "docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv",
    "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv",
    "docs/opportunity-center/phase49-2/ARTIFACTS-SHA256.txt",
    "_audit/phase49-full-verification/evidence/capture-summary.json",
    "_audit/phase49-full-verification/evidence/ledger-counts.json",
]

# (path, note, where the recorded sha256/size come from)
PRIOR_MANIFEST = "docs/opportunity-center/phase49-2/ARTIFACTS-SHA256.txt"
CAPTURE_SUMMARY = "_audit/phase49-full-verification/evidence/capture-summary.json"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


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


def prior_inputs():
    """Read the not-committed input hashes back from the phase49-2 manifest."""
    out = {}
    p = os.path.join(ROOT, PRIOR_MANIFEST.replace("/", os.sep))
    with io.open(p, encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("#") or "  # " not in ln:
                continue
            body, note = ln.split("  # ", 1)
            parts = body.split()
            if len(parts) != 3:
                continue
            h, size, path = parts
            out[path] = (h, size, note.strip())
    return out


def capture_inputs():
    """Licensed capture inputs, restored by the owner over Git LFS.

    Each is listed with the hash recorded by phase49-full-verification. When the
    bytes are present they are re-measured here and must match that recorded
    hash; a mismatch aborts rather than publishing a stale manifest. When they
    are absent the recorded hash is kept and marked ABSENT, never re-typed.
    """
    p = os.path.join(ROOT, CAPTURE_SUMMARY.replace("/", os.sep))
    merged = json.load(io.open(p, encoding="utf-8"))["merged"]
    idx = merged["reference_index_all"]
    return [
        (merged["bars_file"], merged["bars_container_sha256"],
         "licensed paired type0/type7 bars, gzip container", "container"),
        (merged["bars_file"], merged["bars_payload_sha256"],
         "same file, uncompressed NDJSON payload hash", "payload"),
        (idx["file"], idx["sha256"],
         "licensed reference index, 759 symbols", "container"),
    ]


def measure_capture(path, kind):
    """Hash the container bytes, or the decompressed NDJSON payload."""
    if kind != "payload":
        return sha(path), os.path.getsize(path)
    h = hashlib.sha256()
    n = 0
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def cohort_db_facts():
    """Read the working-DB facts back from committed stage evidence."""
    ev = os.path.join(AUDIT, "evidence")
    mf = os.path.join(AUDIT, "manifests")
    s6 = json.load(io.open(os.path.join(ev, "RESTORED-CAPTURE-VERIFICATION.json"),
                           encoding="utf-8"))
    s7 = json.load(io.open(os.path.join(ev, "COHORT-CANDLES.json"),
                           encoding="utf-8"))
    s8 = json.load(io.open(os.path.join(ev, "RUNTIME-READPATH.json"),
                           encoding="utf-8"))
    s9 = json.load(io.open(os.path.join(ev, "IDEMPOTENCY.json"),
                           encoding="utf-8"))
    m7 = json.load(io.open(os.path.join(mf, "stage07-cohort-candles.json"),
                           encoding="utf-8"))
    s10 = json.load(io.open(os.path.join(ev, "ZERO-EVENT-CENSUS.json"),
                            encoding="utf-8"))
    m10 = json.load(io.open(os.path.join(mf, "stage10-zero-event-census.json"),
                            encoding="utf-8"))
    for name, rec in (("stage06", s6), ("stage07", s7), ("stage08", s8),
                      ("stage09", s9), ("stage10", s10)):
        if rec.get("base_commit") != BASE_COMMIT:
            sys.exit("FATAL: %s evidence is pinned to another base commit" % name)
    if s6["status"] != "PASS":
        sys.exit("FATAL: stage06 is not PASS; the capture bytes are not verified")
    if s7["status"] != "PASS":
        sys.exit("FATAL: stage07 is not PASS; refusing to publish its rows")
    if s9["status"] != "PASS":
        sys.exit("FATAL: stage09 is not PASS; refusing to claim idempotency")
    if s7["engine_source_diff_vs_base"] != "(empty)":
        sys.exit("FATAL: engine source differs from base")
    if s7["working_db"]["red_line_dbs_opened_for_write"]:
        sys.exit("FATAL: a red-line DB was opened for write")
    if s8["substrate"]["red_line_dbs_opened"]:
        sys.exit("FATAL: stage08 opened a red-line DB")
    if not s9["checks"]["pinned_db_untouched"]:
        sys.exit("FATAL: stage09 did not leave the pinned DB untouched")
    if m7["payload_sha256"] != sha(os.path.join(ev, "COHORT-CANDLES.json")):
        sys.exit("FATAL: stage07 payload drifted from its manifest hash")
    pinned = s9["pinned_working_db"]
    if pinned["sha256_before"] != m7["working_db_sha256"]:
        sys.exit("FATAL: stage09 pinned a different working DB than stage07 built")
    if pinned["sha256_after"] != pinned["sha256_before"]:
        sys.exit("FATAL: stage09 changed the pinned working DB")
    if s9["pinned_revision"] != s7["revision"]:
        sys.exit("FATAL: stage09 pinned a different revision than stage07 wrote")
    if s10["status"] != "PASS":
        sys.exit("FATAL: stage10 is not PASS; refusing to publish its census")
    if s10["controls_passed"] != s10["controls_total"]:
        sys.exit("FATAL: a stage10 control failed")
    if s10["db_opened"] or s10["bars_scanned"] or s10["candles_built"]:
        sys.exit("FATAL: stage10 claims a side effect it must not have")
    if m10["payload_sha256"] != sha(os.path.join(ev, "ZERO-EVENT-CENSUS.json")):
        sys.exit("FATAL: stage10 payload drifted from its manifest hash")
    if m10["exit_code"] != 0:
        sys.exit("FATAL: stage10 manifest records a non-zero exit")
    cen = s10["census"]
    if (cen["at_risk_candidates"] + cen["symbols_with_changes"]
            + cen["unpaired_symbols"] != cen["symbols_total"]):
        sys.exit("FATAL: stage10 partition does not sum to its universe")
    live = s10["live_zero_event_symbols_from_stage08"]
    if not live or not set(live) <= set(s10["at_risk_keys"]):
        sys.exit("FATAL: stage10 census contradicts the stage08 live finding")
    return s6, s7, s8, s9, m7, s10


def main():
    deliverables = sorted(
        rel(os.path.join(DOCS, f)) for f in os.listdir(DOCS)
        if os.path.isfile(os.path.join(DOCS, f))
        and rel(os.path.join(DOCS, f)) != SELF)

    evidence = (discover("ledgers", {".csv"})
                + discover("evidence", {".json"})
                + discover("manifests", {".json"}))
    scripts = sorted(rel(os.path.join(AUDIT, f)) for f in os.listdir(AUDIT)
                     if f.endswith(".py"))

    # The docs copies must be byte-identical to the audit originals.
    pairs = [("docs/opportunity-center/phase49-3/COHORT-SELECTION.json",
              "_audit/phase49-3/evidence/COHORT-SELECTION.json"),
             ("docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-MAP.csv",
              "_audit/phase49-3/ledgers/COVERAGE-EXPANSION-MAP.csv")]
    for a, b in pairs:
        pa = os.path.join(ROOT, a.replace("/", os.sep))
        pb = os.path.join(ROOT, b.replace("/", os.sep))
        if not os.path.exists(pa) or not os.path.exists(pb):
            sys.exit("FATAL: missing docs/audit pair %s | %s" % (a, b))
        if sha(pa) != sha(pb):
            sys.exit("FATAL: docs copy drifted from audit original: %s" % a)

    ci_status = "PENDING (no CI run recorded yet)"
    ci_sha = "-"
    ci_jobs = "NOT_MEASURED"
    ci_legacy = "NOT_MEASURED"
    ci_data_lane = "NOT_MEASURED"
    if os.path.exists(CI):
        rec = json.load(io.open(CI, encoding="utf-8"))
        ci_status = rec.get("status", "UNKNOWN")
        ci_sha = rec.get("commit_sha", "?")
        ci_jobs = ("workflows_success=%s jobs_success=%s blocking_jobs_success=%s"
                   % (rec.get("all_workflows_success"),
                      rec.get("all_jobs_success"),
                      rec.get("all_blocking_jobs_success")))
        for run in rec.get("runs", []):
            for j in run.get("jobs", []):
                if "--profile data" in j["name"]:
                    ci_data_lane = ("%s conclusion=%s report_only=%s"
                                    % (j["name"], j["conclusion"],
                                       j["report_only"]))
        attr = rec.get("report_only_failure_attribution", [])
        if rec.get("report_only_failures_caused_by_this_mission"):
            sys.exit("FATAL: a report-only CI failure gained suites at this"
                     " commit; the manifest must not call it pre-existing")
        for a in attr:
            if a.get("status") != "MEASURED":
                ci_legacy = "%s: %s" % (a["job"], a.get("status"))
                continue
            if not a["parse_complete_both"]:
                sys.exit("FATAL: legacy suite parse incomplete for %s" % a["job"])
            c, b = a["this_commit_counts"], a["base_commit_counts"]
            ci_legacy = ("%s: %d/%d failed here vs %d/%d at base,"
                         " identical_sets=%s new=%d resolved=%d"
                         % (a["job"], c["suites_failed"], c["suites_total"],
                            b["suites_failed"], b["suites_total"],
                            a["failed_sets_identical"], len(a["new_failures"]),
                            len(a["resolved_failures"])))

    gates = json.load(io.open(os.path.join(AUDIT, "evidence", "gates.json"),
                              encoding="utf-8"))
    go = gates["go"]
    prod = gates["profiles"]["production"]
    data = gates["profiles"]["data"]
    dl = gates["data_lane_failures"]
    if dl["caused_by_this_mission"]:
        sys.exit("FATAL: a data-lane failure is attributed to this mission;"
                 " the manifest must not call it pre-existing")
    for s in dl["suites"]:
        if not s["counts_identical"]:
            sys.exit("FATAL: control counts differ at base for %s" % s["suite"])
    if len(dl["suites"]) != dl["count"]:
        sys.exit("FATAL: data-lane failure count disagrees with its suite list")

    s6, s7, s8, s9, m7, s10 = cohort_db_facts()
    cnt = s7["counts"]
    anchor = s7["anchor_invariant"]
    geo = s8["candle_geometry_finding"]
    cen = s10["census"]

    out = [
        "# Phase 4.9.3 artifact SHA-256 manifest",
        "# generated by _audit/phase49-3/build_artifacts_manifest.py",
        "# deterministic: no timestamp in the payload; rerun is byte-identical",
        "# verdict: %s" % VERDICT,
        "# verdict_basis: stage06 PASS, stage07 PASS, stage08 PARTIAL,"
        " stage09 PASS, stage10 PASS",
        "# code_commit: %s (base; this mission changed no engine code)" % BASE_COMMIT,
        "# ci_status: %s" % ci_status,
        "# ci_commit: %s" % ci_sha,
        "# ci_jobs: %s (python-legacy is continue-on-error: workflow success is"
        " NOT all-jobs success)" % ci_jobs,
        "# ci_report_only_attribution: %s" % ci_legacy,
        "# ci_data_lane: %s (the local --profile data run failed 5 suites on a"
        " host without fastapi/pypdfium2; CI is the authority for that lane)"
        % ci_data_lane,
        "# independent_db_revision: %s" % s7["revision"],
        "# independent_db: %s (fresh from the frozen Phase 4.9.2 SCHEMA; NOT a"
        " copy of the Seed Candidate or the Pilot DB, both absent on this host)"
        % s7["working_db"]["path"],
        "# independent_db_sha256: %s (%d bytes)" % (
            m7["working_db_sha256"], m7["working_db_size_bytes"]),
        "# independent_db_rows: raw=%d adjusted=%d factors=%d candles=%d"
        " (written to the working DB only; no red-line DB was opened)" % (
            cnt["reference_raw_rows"], cnt["reference_adjusted_rows"],
            cnt["adjustment_factors"], s7["candlebuild_result"]["adjusted_rows"]),
        "# cohort_symbols: %d ingested, %d materialized by the builder,"
        " %d zero-event (see stage08)" % (
            cnt["symbols_ingested"], s7["builder_coverage"]["symbols_materialized"],
            len(s7["builder_coverage"]["zero_event_symbols"])),
        "# candle_parity: close max_rel=%r mismatch_rows=%d volume_mismatch=0" % (
            s7["parity"]["field_max_rel_error"]["close"],
            s7["parity"]["close_diff_rows"]),
        "# anchor_invariant: %d/%d symbols hold q(last)==1, max_abs_q_minus_one=%r"
        % (anchor["symbols_checked"] - anchor["violations"],
           anchor["symbols_checked"], anchor["max_abs_q_minus_one"]),
        "# runtime_readpath: %s; measured-path symbols=%d/%d; adjusted close"
        " max_rel=%r; is_ui_test=%s; screenshot=%s" % (
            s8["status"], len(s8["measured_path_symbols"]),
            s8["measurement"]["symbols_queried"],
            s8["adjusted_close_max_rel_overall"],
            s8["measurement"]["is_ui_test"], s8["measurement"]["screenshot"]),
        "# runtime_finding: %d served candles with invalid geometry, all on %s;"
        " %s attributed to the literal high/low reset, %d unattributed;"
        " NOT fixed — owner ruling required" % (
            geo["served_rows_invalid_total"],
            ",".join(sorted(geo["served_rows_with_invalid_geometry"])),
            geo["raw_diff_attributed_to_literal_reset"],
            len(geo["raw_diff_unattributed_symbols"])),
        "# idempotency: %d/%d checks pass, negative control included;"
        " factor details compared semantically (int/float serialization artifact"
        " disclosed in the payload)" % (
            sum(1 for v in s9["checks"].values() if v), len(s9["checks"])),
        "# zero_event_census: %d candidates of %d reference-covered symbols,"
        " %d daily bars, %d q-bitwise-constant; cohort overlap=%d (%s);"
        " read-only, no DB/bar/candle; controls %d/%d; live confirmation outside"
        " the cohort and absolute q level NOT_MEASURED" % (
            cen["at_risk_candidates"], cen["symbols_total"],
            cen["at_risk_daily_bars_total"], cen["at_risk_q_bitwise_constant"],
            s10["cohort_overlap"]["count"],
            ",".join(s10["cohort_overlap"]["keys"]),
            s10["controls_passed"], s10["controls_total"]),
        "# capture_day_quarantine: rule date >= capture_day applied;"
        " capture_day=%s, last captured bar=%s, quarantined=%d" % (
            s7["capture"]["capture_day"], s6["bars_recount"]["last_date"],
            sum(s7["capture"]["quarantined_bars"].values())),
        "# restored_capture: bars=%d symbols=%d type0=%d type7=%d;"
        " cohort type0/day=%d type7/day=%d fully_covered=%s" % (
            s6["bars_recount"]["bars_total"], s6["bars_recount"]["symbols_identity_keys"],
            s6["bars_recount"]["per_type"]["type0"],
            s6["bars_recount"]["per_type"]["type7"],
            s6["cohort_summary"]["type0_daily_bars_total"],
            s6["cohort_summary"]["type7_daily_bars_total"],
            s6["cohort_summary"]["cohort_fully_covered"]),
        "# go: %s packages ok, %s without test files, %s failures" % (
            go["packages_ok"], go["packages_no_test_files"], go["failures"]),
        "# profile production: exit %s, %s suites counted, ALL_SUITES_PASSED=%s" % (
            prod["exit_code"], prod["suites_counted"], prod["all_suites_passed"]),
        "# profile data: exit %s, %s suites counted, %s failed suites"
        " (pre-existing local dependency gap; identical counts on a pristine"
        " base-commit control worktree)" % (
            data["exit_code"], data["suites_counted"], dl["count"]),
        "# format: sha256  size_bytes  path",
        "# section: 1=deliverables 2=ledgers/evidence/manifests 3=mission scripts"
        " 4=code, gates and pinned inputs 5=licensed/absent inputs (recorded hashes)",
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

    out.append("# --- section 5 (recorded sha256, recorded size, path) ---")
    prior = prior_inputs()
    absent = []
    wanted = [
        "_audit/phase49-full-verification/seed/market.db",
        "_audit/phase49-full-verification/seed/market.db.lzma",
        "_audit/phase49-full-verification/seed/market.db.gz",
        "_audit/phase49-2/db/market.db",
        "_audit/phase49-2/rahavard/pilot-capture.json",
    ]
    for r in wanted:
        if r not in prior:
            sys.exit("FATAL: no recorded hash for input %s" % r)
        h, size, note = prior[r]
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if os.path.exists(p):
            actual = sha(p)
            if actual != h:
                sys.exit("FATAL: present input %s does not match its recorded"
                         " hash; refusing to publish a stale manifest" % r)
            out.append("%s  %s  %s  # %s" % (actual, os.path.getsize(p), r, note))
        else:
            absent.append(r)
            out.append("%s  %s  %s  # %s — ABSENT on this host; hash recorded by"
                       " phase49-2, not re-measured here" % (h, size, r, note))
    restored = []
    for r, h, note, kind in capture_inputs():
        p = os.path.join(ROOT, r.replace("/", os.sep))
        label = "%s (%s)" % (note, kind)
        if os.path.exists(p):
            actual, size = measure_capture(p, kind)
            if actual != h:
                sys.exit("FATAL: present input %s [%s] does not match its"
                         " recorded hash; refusing to publish a stale manifest"
                         % (r, kind))
            restored.append(r)
            out.append("%s  %d  %s  # %s — PRESENT, re-measured here and equal"
                       " to the hash recorded by phase49-full-verification;"
                       " licensed, gitignored on this branch" % (actual, size, r, label))
        else:
            absent.append(r)
            out.append("%s  -  %s  # %s — ABSENT on this host; hash recorded by"
                       " phase49-full-verification, not re-measured here"
                       % (h, r, label))

    text = "\n".join(out) + "\n"
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(OUT))
    print("deliverables=%d evidence=%d scripts=%d code=%d absent_inputs=%d"
          " restored_inputs=%d"
          % (len(deliverables), len(evidence), len(scripts), len(CODE),
             len(set(absent)), len(set(restored))))
    print("verdict=%s ci=%s" % (VERDICT, ci_status))


if __name__ == "__main__":
    main()