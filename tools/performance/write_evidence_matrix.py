#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the six-round evidence matrix from the committed raw artifacts."""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROWS = [
    {
        "Round": "0", "Commit": "784d9d8a", "Optimized subsystem": "baseline",
        "Hypothesis": "Establish a reproducible baseline before changing code",
        "Benchmark/workload identifier": "api-baseline + fe-baseline + first-open (3 cold servers)",
        "Metric": "various", "Baseline value": "", "Pre-round best value": "",
        "Post-round value": "", "Unit": "", "Sample count": "", "Percentage delta": "",
        "Functional test status": "", "Resource metric delta": "",
        "Regression status": "", "Keep/revert decision": "reference",
        "Evidence file": "artifacts/performance/2026-10-22/api-baseline.json; fe-baseline.json; first-open-baseline-*.json",
    },
    {
        "Round": "1a", "Commit": "1147447a", "Optimized subsystem": "mstat snapshot build",
        "Hypothesis": "Concurrent cold panels rebuild the same snapshot (stampede)",
        "Benchmark/workload identifier": "ui_probe /market-status pass0",
        "Metric": "click_to_ready", "Baseline value": "10795", "Pre-round best value": "10795",
        "Post-round value": "7812", "Unit": "ms", "Sample count": "1",
        "Percentage delta": "-27.6%", "Functional test status": "PASS: snapshot cache 10/10, singleflight 4/4",
        "Resource metric delta": "snapshot builds under 8-way cold burst: 8 -> 1",
        "Regression status": "none observed", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/fe-baseline.json; fe-round1.json",
    },
    {
        "Round": "1b", "Commit": "1147447a", "Optimized subsystem": "mstat snapshot + boot panel warm-up",
        "Hypothesis": "Prewarmed panel caches remove cold fan-out from the first open",
        "Benchmark/workload identifier": "first_open /market-status, 3 cold servers + 3 fresh browser contexts",
        "Metric": "first_open_ready", "Baseline value": "10020", "Pre-round best value": "10020",
        "Post-round value": "3827", "Unit": "ms (median)", "Sample count": "3",
        "Percentage delta": "-61.8%", "Functional test status": "PASS: guards + py_compile + glyph",
        "Resource metric delta": "encoded panel payload median 226 -> 94 KiB",
        "Regression status": "none; port-ready 8s unchanged", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/first-open-baseline-*.json; first-open-round1-*.json",
    },
    {
        "Round": "2", "Commit": "77d32d90", "Optimized subsystem": "notifications source health",
        "Hypothesis": "Two full codal_notices scans per request are cacheable by DB content key",
        "Benchmark/workload identifier": "bench_api --only notifications, 30 samples",
        "Metric": "/api/notifications/sources p50", "Baseline value": "342.9",
        "Pre-round best value": "342.9", "Post-round value": "22.3", "Unit": "ms",
        "Sample count": "30", "Percentage delta": "-93.5%",
        "Functional test status": "PASS: test_notifications_v1 30/30, cache guard 6/6",
        "Resource metric delta": "canonical SQL per warm call: 1 -> 0",
        "Regression status": "none; TTL ceiling 120s + content key",
        "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/api-baseline.json; notifications-round2.json",
    },
    {
        "Round": "3a", "Commit": "cf9c0048", "Optimized subsystem": "TEDPIX index series",
        "Hypothesis": "Direct response + ETag removes repeated transform/serialization and payload",
        "Benchmark/workload identifier": "GET /api/index/tedpix?limit=0, 30 samples",
        "Metric": "unconditional 200 p50", "Baseline value": "171.2",
        "Pre-round best value": "171.2", "Post-round value": "43.9", "Unit": "ms",
        "Sample count": "30", "Percentage delta": "-74.4%",
        "Functional test status": "PASS: market_index_etag_v1 8/8, stale_wiring 19/19, tsc 0",
        "Resource metric delta": "repeat request: 136KB gzip -> 0B (304)",
        "Regression status": "none; candles equal builder output", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/tedpix-head-baseline.json; tedpix-round3.json",
    },
    {
        "Round": "3b", "Commit": "cf9c0048", "Optimized subsystem": "TEDPIX conditional request",
        "Hypothesis": "A fresh-cache 304 avoids body re-send/rebuild",
        "Benchmark/workload identifier": "If-None-Match repeat, 30 samples",
        "Metric": "conditional p50", "Baseline value": "171.2", "Pre-round best value": "171.2",
        "Post-round value": "5.43", "Unit": "ms", "Sample count": "30",
        "Percentage delta": "-96.8%", "Functional test status": "PASS: ETag guard 8/8",
        "Resource metric delta": "0 bytes on wire vs 136KB gzip",
        "Regression status": "none; expired cache never 304s", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/tedpix-round3.json",
    },
    {
        "Round": "4", "Commit": "e250b325", "Optimized subsystem": "landing data path (master/portfolio)",
        "Hypothesis": "Full 6.8MB board only needed for a closing price; palette fetched it while closed",
        "Benchmark/workload identifier": "landing_probe /master, 3 fresh contexts",
        "Metric": "encoded API bytes per landing (median)", "Baseline value": "1235",
        "Pre-round best value": "1235", "Post-round value": "43", "Unit": "KiB",
        "Sample count": "3", "Percentage delta": "-96.5%",
        "Functional test status": "PASS: vitest 33/33 (pipeline/palette/status), tsc 0, closes guard 5/5",
        "Resource metric delta": "/api/market removed from landing; closes map 31KB gzip; 304/0B when unchanged",
        "Regression status": "none; same p_closing values", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/landing-round4.json; landing-round4b.json; closes-round4.json",
    },
    {
        "Round": "5", "Commit": "e8bfcf07", "Optimized subsystem": "DB connection setup",
        "Hypothesis": "Idempotent schema DDL on every get_db is wasted CPU",
        "Benchmark/workload identifier": "300 sequential get_db calls, HEAD worktree vs current",
        "Metric": "CPU seconds", "Baseline value": "2.03", "Pre-round best value": "2.03",
        "Post-round value": "1.53", "Unit": "s / 300 connections", "Sample count": "300",
        "Percentage delta": "-24.6%",
        "Functional test status": "PASS: get_db_schema_once_v1 6/6, mstat cache 10/10, closes 5/5",
        "Resource metric delta": "p50 7.74 -> 6.45ms; external ALTER still invalidates",
        "Regression status": "none", "Keep/revert decision": "keep",
        "Evidence file": "artifacts/performance/2026-10-22/getdb-baseline.json; getdb-schema-once.json",
    },
    {
        "Round": "5b", "Commit": "e8bfcf07", "Optimized subsystem": "frontend conditional cache",
        "Hypothesis": "Unbounded per-URL parsed-body cache retains memory across many URLs",
        "Benchmark/workload identifier": "http-conditional-lru.spec.ts; sustained_session (6 cycles); chart_symbol_stress (60 symbols)",
        "Metric": "cache bound / heap", "Baseline value": "unbounded", "Pre-round best value": "unbounded",
        "Post-round value": "32 LRU", "Unit": "entries (bound)",
        "Sample count": "1 unit test + 6 cycles + 60 symbols",
        "Percentage delta": "inconclusive on heap (chart bodies carry no ETag)",
        "Functional test status": "PASS: LRU test 1/1, http-conditional 5/5",
        "Resource metric delta": "sustained heap 23.9 -> 34.4MB plateau; nodes/listeners flat; chart stress 27.8 -> 28.2MB after 60 switches",
        "Regression status": "none", "Keep/revert decision": "keep as prevention",
        "Evidence file": "artifacts/performance/2026-10-22/sustained-baseline.json; chart-stress-baseline.json",
    },
    {
        "Round": "6", "Commit": "941be7c0", "Optimized subsystem": "mstat panel durability",
        "Hypothesis": "45s TTL discards still-valid panels outside session; warm key captured before board build",
        "Benchmark/workload identifier": "first_open /market-status after 60s idle, same server",
        "Metric": "first_open_ready", "Baseline value": "7043",
        "Pre-round best value": "3827 (Round 1; different run conditions)",
        "Post-round value": "4333", "Unit": "ms", "Sample count": "1 each (expensive restart)",
        "Percentage delta": "-38.5% vs immediate prior baseline",
        "Functional test status": "PASS: durability 4/4, snapshot 10/10, singleflight 4/4",
        "Resource metric delta": "encoded 258 -> 125KiB; TTL 45s in session / 300s outside; key = four data markers",
        "Regression status": "in-session freshness unchanged (45s); remaining 21 requests/4 waves",
        "Keep/revert decision": "keep; board integration left as next step",
        "Evidence file": "artifacts/performance/2026-10-22/first-open-r6-before.json; first-open-r6-after4.json",
    },
]


def main():
    out = os.path.join(ROOT, "artifacts", "performance", "six-round-results.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()))
        w.writeheader()
        w.writerows(ROWS)
    print("wrote", out, "rows=", len(ROWS))


if __name__ == "__main__":
    main()
