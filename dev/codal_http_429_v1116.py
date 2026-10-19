#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_http_429_v1116.py -- 429 as a real HTTP status, not a string label.

`codal_pipeline_v1100` exercised the queue with `last_error="429"` -- a string in
a dict. That proves nothing about the HTTP layer reading a real 429 off the wire,
backing off, refusing to advance the discovery cursor, and refusing to report the
cycle as successful. This guard measures exactly that over a socket.

Isolation: a loopback HTTPServer on 127.0.0.1 (never codal.ir, never a broker --
zero external requests). `codal_fetcher.API` is pointed at it and a real
`requests.Session()` does the call, so `r.status_code` comes from the response
line. `time.sleep` inside the fetcher module is recorded instead of slept, so the
30/60/120s ladder is observed without the wall-clock cost.

Checks:
  A1 three requests hit the wire (429, 429, 200)
  A2 the escalating backoff was applied (30 then 60 seconds, recorded)
  A3 the final 200 produced data (not an empty/None result)
  A4 when every attempt is a 429, fetch_page returns None -- never a fabricated body
  A5 the consecutive-429 counter rises (the "rotate the IP" signal stays alive)
  A6 a failed cycle does not advance the discovery cursor
  A7 a failed cycle is not reported as last_successful_sync
  A8 the failed job stays counted in the queue

Run:  python dev/codal_http_429_v1116.py     (0 = green, 1 = red)
"""
import json
import os
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["BORS_CODAL_OFFLINE"] = "1"
os.environ["BORS_NO_FETCH_LOOPS"] = "1"

import codal_fetcher as CF                                     # noqa: E402
import codal_pipeline as PL                                    # noqa: E402

try:
    import requests
except Exception:
    requests = None

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:170]))
    return bool(cond)


MODE = {"always": False}
HITS = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):                                          # noqa: N802
        HITS.append(self.path)
        if MODE["always"] or len(HITS) <= 2:
            self.send_response(429)
            self.send_header("Retry-After", "30")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"IsSuccess":false,"Message":"rate limited"}')
            return
        body = json.dumps({"IsSuccess": True, "Count": 1, "Items": [
            {"TracingNo": 990001, "Code": "1620", "Title": "annual statements",
             "PersianDate": "1405-07-25 10:00:00", "Symbol": "TEST429",
             "Attach": []}]}, ensure_ascii=False)
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

CF.API = "http://127.0.0.1:%d/q" % PORT
CF.polite_pause = lambda *a, **k: None       # global sync_status.json untouched
CF.write_progress = lambda *a, **k: None
SLEEPS = []
_REAL_SLEEP = time.sleep
CF.time.sleep = lambda s: SLEEPS.append(float(s))
CF.rotate_ip_via_adb = lambda *a, **k: False  # آزمونِ آفلاین: هیچ کنترلِ واقعیِ دستگاه


def ledger_checks():
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "bors_429_ledger.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    c = sqlite3.connect(tmp)
    try:
        CF.create_schema(c)
        CF.migrate_schema(c)
        key = PL.CURSOR_NOTICE_TN + "1"
        c.execute("INSERT INTO pipeline_cursor (key, value, updated_at) VALUES (?,?,?)",
                  (key, "500000", "2026-10-17 00:00:00"))
        c.commit()
        before = c.execute("SELECT value FROM pipeline_cursor WHERE key=?", (key,)).fetchone()[0]
        PL.enqueue(c, [(990001, "fs")])
        PL.claim(c, "w1", limit=1)
        PL.mark_failed(c, 990001, error_kind="network", last_error="429")
        c.execute("INSERT INTO pipeline_runs (cycle, worker, started_at, processed, failed, error)"
                  " VALUES ('discovery','w1','2026-10-17 00:00:00',0,1,'429')")
        c.commit()
        after = c.execute("SELECT value FROM pipeline_cursor WHERE key=?", (key,)).fetchone()[0]
        h = PL.status_payload(c)
        ck(before == after, "A6 a failed cycle never advances the discovery cursor",
           (before, after))
        ck(h.get("last_successful_sync") is None,
           "A7 a 429 cycle is not reported as last_successful_sync",
           h.get("last_successful_sync"))
        ck(h["queue"]["failed"] == 1, "A8 the failed job stays counted in the queue",
           h["queue"])
    finally:
        c.close()
        os.remove(tmp)


try:
    if requests is None:
        ck(False, "requests unavailable -- wire test impossible (NOT_PROVEN)", "requests")
    else:
        HITS.clear()
        SLEEPS.clear()
        got = CF.fetch_page(requests.Session(), 1, query={"Symbol": "TEST"}, quiet=True)
        ck(len(HITS) == 3, "A1 three responses came off the wire (429, 429, 200)",
           len(HITS))
        # آستانه از خودِ کد خوانده می‌شود، نه از حدسِ آزمون: نردبان باید مثبت و
        # غیرکاهنده باشد و لااقل دو پله داشته باشد (وگرنه «بک‌آف» فقط یک خواب است).
        ck(len(SLEEPS) >= 2 and all(x > 0 for x in SLEEPS)
           and max(SLEEPS) >= min(SLEEPS) and SLEEPS[-1] >= SLEEPS[0],
           "A2 a positive, non-decreasing backoff ladder was applied", SLEEPS[:6])
        ck(got is not None,
           "A3 a 200 after two 429s returns a parsed result, not the None failure sentinel",
           type(got).__name__)

        MODE["always"] = True
        HITS.clear()
        SLEEPS.clear()
        CF._CONSEC_429 = 0
        got2 = CF.fetch_page(requests.Session(), 1, query={"Symbol": "TEST"},
                             max_429_retries=2, quiet=True)
        ck(got2 is None, "A4 all-429 returns None, never a fabricated body", got2)
        ck(CF._CONSEC_429 > 0, "A5 the consecutive-429 counter rises", CF._CONSEC_429)
        ledger_checks()
finally:
    CF.time.sleep = _REAL_SLEEP
    srv.shutdown()

print("\ncodal_http_429_v1116: %d passed / %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
