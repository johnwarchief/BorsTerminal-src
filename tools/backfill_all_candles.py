#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill full daily candles for every instrument, resumable and auditable.

Why this exists: the chart route reads the full TSETMC CSV live, while
price_history only holds a shallow cache (max ~525 bars in the 2026-11 DB).
This tool fills price_history from the same published CSV source, records a
per-symbol state row, and emits a coverage report. It never deletes rows and
never writes to the production DB unless pointed at it explicitly.

Usage:
  python tools/backfill_all_candles.py --pilot 20
  python tools/backfill_all_candles.py --all --limit 500
  python tools/backfill_all_candles.py --symbols فولاد,وبملت --refresh
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import socket
import sqlite3
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import candle_contract as CC  # noqa: E402

# TSETMC moved the working CDN to the .ir host in 2026-11; .com returns 403.
BASE = os.environ.get("BORS_TSETMC_BASE", "https://cdn.tsetmc.ir/api")
PIN_IP = os.environ.get("BORS_TSETMC_PIN_IP", "86.104.39.107").strip()
CSV_FLOOR = "19900101"
MIN_BARS = 60
DEFAULT_DB = os.environ.get("BORS_DB") or "D:/BorsTerminal-data/market.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
}
PILOT = [
    "فولاد", "وبملت", "شپنا", "فنوال", "شبهرن", "خودرو", "شستا", "فارس",
    "فملي", "وپاسار", "وغدير", "نوري", "پارسان", "شتران", "تاپيكو", "شبندر",
    "اخابر", "همراه", "خساپا", "وبصادر",
]

STATE_DDL = """
CREATE TABLE IF NOT EXISTS candle_backfill_state (
  symbol TEXT PRIMARY KEY,
  ins_code TEXT,
  status TEXT NOT NULL,
  bars INTEGER DEFAULT 0,
  first_date TEXT,
  last_date TEXT,
  source_first TEXT,
  source_last TEXT,
  rows_seen INTEGER DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  error TEXT,
  fetched_at TEXT
)
"""


class NoDataError(RuntimeError):
    """The source has no CSV for this instrument (404/400), not a network fault."""


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(STATE_DDL)
    con.commit()
    return con


def load_instruments(con: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    rows = con.execute(
        "SELECT l_val18, ins_code, paper_type FROM instruments "
        "WHERE l_val18 IS NOT NULL AND ins_code IS NOT NULL AND TRIM(l_val18) <> '' "
        "ORDER BY l_val18"
    ).fetchall()
    seen: set[str] = set()
    out: list[tuple[str, str, str | None]] = []
    for sym, code, ptype in rows:
        sym = str(sym).strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append((sym, str(code), ptype))
    return out


def state(con: sqlite3.Connection, symbol: str):
    return con.execute(
        "SELECT status, bars, first_date, last_date, source_last, attempts, fetched_at, error "
        "FROM candle_backfill_state WHERE symbol=?", (symbol,)
    ).fetchone()


def save_state(con: sqlite3.Connection, symbol: str, ins: str, *, status: str,
               bars: int, first_date: str | None, last_date: str | None,
               source_first: str | None, source_last: str | None,
               rows_seen: int, attempts: int, error: str | None) -> None:
    con.execute(
        "INSERT INTO candle_backfill_state "
        "(symbol,ins_code,status,bars,first_date,last_date,source_first,source_last,"
        " rows_seen,attempts,error,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(symbol) DO UPDATE SET ins_code=excluded.ins_code,status=excluded.status,"
        " bars=excluded.bars,first_date=excluded.first_date,last_date=excluded.last_date,"
        " source_first=excluded.source_first,source_last=excluded.source_last,"
        " rows_seen=excluded.rows_seen,attempts=excluded.attempts,error=excluded.error,"
        " fetched_at=excluded.fetched_at",
        (symbol, ins, status, bars, first_date, last_date, source_first, source_last,
         rows_seen, attempts, error, now()),
    )
    con.commit()


def fetch_csv(session: requests.Session, ins_code: str, timeout: int, retries: int,
              min_interval: float, max_429: int, sleep_fn=time.sleep) -> tuple[str, int]:
    url = f"{BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/{CSV_FLOOR}"
    last_err = ""
    consecutive_429 = 0
    for attempt in range(1, retries + 1):
        sleep_fn(min_interval)
        try:
            r = session.get(url, timeout=(15, timeout))
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            sleep_fn(min(2 ** attempt, 8))
            continue
        if r.status_code == 429:
            consecutive_429 += 1
            if consecutive_429 > max_429:
                raise RuntimeError(f"HTTP 429 budget exhausted ({consecutive_429})")
            sleep_fn(min(60 * (2 ** (consecutive_429 - 1)), 600))
            continue
        if r.status_code in (400, 404, 410):
            raise NoDataError(f"HTTP {r.status_code}")
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code}"
            sleep_fn(min(2 ** attempt, 8))
            continue
        return r.text, attempt
    raise RuntimeError(last_err or "request failed")


def parse_csv(symbol: str, text: str) -> tuple[list[dict], str | None, str | None, int]:
    bars: list[dict] = []
    source_first = None
    source_last = None
    rows_seen = 0
    lines = text.splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split(",")
        date = CC.iso_from_csv(fields)
        if date:
            rows_seen += 1
            source_first = date if source_first is None or date < source_first else source_first
            source_last = date if source_last is None or date > source_last else source_last
        bar = CC.from_csv_row(symbol, fields)
        if bar:
            bars.append(bar)
    # TSETMC returns newest-first; the state/report assume oldest-first.
    bars.sort(key=lambda b: b["time"])
    if bars:
        # source_last must be the last *traded* bar, not the last CSV row:
        # a no-trade tail day would otherwise look like a stale database.
        source_first, source_last = bars[0]["time"], bars[-1]["time"]
    return bars, source_first, source_last, rows_seen


def process_symbol(con: sqlite3.Connection, session: requests.Session, symbol: str,
                   ins_code: str, *, force: bool, timeout: int, retries: int,
                   min_interval: float, max_429: int) -> dict:
    old = state(con, symbol)
    if old and old[0] in ("complete", "no_data") and not force:
        return {"symbol": symbol, "status": old[0], "bars": old[1], "skipped": True,
                "first": old[2], "last": old[3]}
    attempts = (old[5] if old else 0) + 1
    try:
        text, tries = fetch_csv(session, ins_code, timeout, retries, min_interval, max_429)
        bars, source_first, source_last, rows_seen = parse_csv(symbol, text)
        if bars:
            con.executemany(CC.UPSERT_SQL, [CC.upsert_row(b) for b in bars])
            con.commit()
        first_date = bars[0]["time"] if bars else None
        last_date = bars[-1]["time"] if bars else None
        status = "complete" if bars else "no_data"
        save_state(con, symbol, ins_code, status=status, bars=len(bars),
                   first_date=first_date, last_date=last_date,
                   source_first=source_first, source_last=source_last,
                   rows_seen=rows_seen, attempts=attempts, error=None)
        return {"symbol": symbol, "status": status, "bars": len(bars),
                "first": first_date, "last": last_date, "rows_seen": rows_seen,
                "tries": tries, "skipped": False}
    except NoDataError as exc:
        save_state(con, symbol, ins_code, status="no_data", bars=0, first_date=None,
                   last_date=None, source_first=None, source_last=None, rows_seen=0,
                   attempts=attempts, error=str(exc))
        return {"symbol": symbol, "status": "no_data", "bars": 0, "error": str(exc),
                "skipped": False}
    except Exception as exc:  # noqa: BLE001 - one symbol must not kill the run
        # Keep the last successful coverage; a refresh failure must not erase it.
        cur = con.execute(
            "UPDATE candle_backfill_state SET status='failed', attempts=?, error=?, "
            "fetched_at=? WHERE symbol=?",
            (attempts, f"{type(exc).__name__}: {exc}", now(), symbol),
        )
        if cur.rowcount == 0:
            save_state(con, symbol, ins_code, status="failed", bars=0, first_date=None,
                       last_date=None, source_first=None, source_last=None, rows_seen=0,
                       attempts=attempts, error=f"{type(exc).__name__}: {exc}")
        con.commit()
        return {"symbol": symbol, "status": "failed", "bars": 0, "error": str(exc),
                "skipped": False}


def write_report(con: sqlite3.Connection, path: str) -> dict:
    # State rows already carry bars/first/last; avoid scanning the 654MB
    # price_history table just to rebuild the same numbers.
    latest = con.execute(
        "SELECT MAX(last_date) FROM candle_backfill_state WHERE last_date IS NOT NULL"
    ).fetchone()[0]
    rows = con.execute(
        "SELECT s.symbol, s.ins_code, i.paper_type, s.status, s.bars, "
        "s.first_date, s.last_date, s.source_first, s.source_last, "
        "s.rows_seen, s.attempts, s.error "
        "FROM candle_backfill_state s LEFT JOIN instruments i ON i.l_val18=s.symbol "
        "ORDER BY s.symbol"
    ).fetchall()
    latest_date = dt.date.fromisoformat(latest) if latest else None
    out = []
    counts: dict[str, int] = {}
    for (sym, ins, ptype, st, bars, first, last, sfirst, slast, seen, attempts, err) in rows:
        status = st
        n = int(bars or 0)
        if st in ("complete", "no_data"):
            if not n:
                status = "no_data"
            elif n < MIN_BARS:
                status = "sparse"
            elif latest_date and last and                     dt.date.fromisoformat(last) < latest_date - dt.timedelta(days=7):
                status = "inactive"
            else:
                status = "complete"
        counts[status] = counts.get(status, 0) + 1
        out.append({
            "symbol": sym, "ins_code": ins, "paper_type": ptype, "status": status,
            "bars": n, "first_date": first, "last_date": last,
            "source_first": sfirst, "source_last": slast, "rows_seen": seen,
            "attempts": attempts, "error": err or "",
        })
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out[0].keys()) if out else
                                ["symbol", "status"])
        writer.writeheader()
        writer.writerows(out)
    summary = {"at": now(), "latest_source_date": latest, "symbols": len(out),
               "counts": counts, "report": path}
    with open(os.path.splitext(path)[0] + ".summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--pilot", type=int, default=0, help="run the first N pilot symbols")
    ap.add_argument("--symbols", default="", help="comma-separated symbol list")
    ap.add_argument("--all", action="store_true", help="all instruments (default)")
    ap.add_argument("--limit", type=int, default=0, help="max symbols this run")
    ap.add_argument("--shard", type=int, default=0, help="shard index (0-based)")
    ap.add_argument("--shards", type=int, default=1, help="number of parallel shards")
    ap.add_argument("--refresh", action="store_true", help="re-fetch complete symbols")
    ap.add_argument("--min-interval", type=float, default=0.15)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--max-429", type=int, default=3)
    ap.add_argument("--max-consecutive-failures", type=int, default=5,
                    help="stop cleanly after this many failed symbols in a row")
    ap.add_argument("--proxy", default="", help="optional proxy URL; default direct")
    ap.add_argument("--pin-ip", default=PIN_IP, help="pin cdn.tsetmc.ir to this IP")
    ap.add_argument("--report", default="")
    ap.add_argument("--report-only", action="store_true", help="write coverage from existing state")
    args = ap.parse_args()

    if args.pin_ip:
        _orig_gai = socket.getaddrinfo
        def _pinned_gai(host, port, *a, **k):
            if host == "cdn.tsetmc.ir":
                host = args.pin_ip
            return _orig_gai(host, port, *a, **k)
        socket.getaddrinfo = _pinned_gai
        print(f"dns-pin cdn.tsetmc.ir -> {args.pin_ip}", flush=True)

    con = connect(args.db)
    if args.report_only:
        report = args.report or os.path.join(ROOT, "_audit", "rebuild", "candles", "coverage-final.csv")
        summary = write_report(con, report)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        con.close()
        return 0
    instruments = load_instruments(con)
    by_symbol = {s: (c, p) for s, c, p in instruments}
    if args.symbols:
        wanted = [s.strip() for s in args.symbols.split(",") if s.strip()]
    elif args.pilot:
        wanted = PILOT[: args.pilot]
    else:
        wanted = [s for s, _, _ in instruments]
    todo = [(s, by_symbol[s][0]) for s in wanted if s in by_symbol]
    missing = [s for s in wanted if s not in by_symbol]
    if args.shards > 1:
        wanted = [s for i, s in enumerate(wanted) if i % args.shards == args.shard]
        todo = [(s, by_symbol[s][0]) for s in wanted if s in by_symbol]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("no symbols matched", missing[:10])
        return 2

    session = requests.Session()
    session.trust_env = False  # direct TSETMC; system proxy breaks it
    session.headers.update(HEADERS)
    if args.proxy:
        session.proxies.update({"http": args.proxy, "https": args.proxy})

    print(f"db={args.db} instruments={len(instruments)} todo={len(todo)} "
          f"missing={len(missing)} direct={not args.proxy}", flush=True)
    started = time.time()
    done = failed = 0
    consecutive_failures = 0
    for idx, (sym, ins) in enumerate(todo, 1):
        res = process_symbol(con, session, sym, ins, force=args.refresh,
                             timeout=args.timeout, retries=args.retries,
                             min_interval=args.min_interval, max_429=args.max_429)
        done += 1
        if res.get("status") == "failed":
            failed += 1
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        if idx % 5 == 0 or idx == len(todo) or res.get("status") == "failed":
            print(f"[{idx}/{len(todo)}] {sym} {res.get('status')} "
                  f"bars={res.get('bars')} last={res.get('last')} "
                  f"err={res.get('error', '')}", flush=True)
        if consecutive_failures >= args.max_consecutive_failures:
            print(f"STOP: {consecutive_failures} consecutive failures; "
                  f"network looks down. Resume with the same command.", flush=True)
            break
    report = args.report or os.path.join(
        ROOT, "_audit", "rebuild", "candles",
        f"coverage-{dt.datetime.now().strftime('%Y%m%d-%H%M')}.csv")
    summary = write_report(con, report)
    summary.update({"elapsed_s": round(time.time() - started, 1), "failed_this_run": failed,
                    "missing_symbols": missing})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    con.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
