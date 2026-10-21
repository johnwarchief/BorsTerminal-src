#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumable CODAL share-type evidence collector (Round 15).

Improves Round 12/14 behaviour:
  * one durable row per (symbol, step_date) with an explicit status
  * successful bodies are cached and never re-downloaded
  * 429 honors Retry-After; otherwise exponential backoff with jitter
  * 429 is NEVER recorded as "no letter"
  * concurrency = 1; no IP rotation, no immediate retry storm
  * --dry-run rebuilds the checkpoint from Round 12/14 caches without network

Statuses: COMPLETE | RETRY_PENDING | RATE_LIMITED | FAILED | SOURCE_NOT_FOUND
"""
import argparse
import atexit
import csv
import datetime as dt
import json
import os
import random
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import codal_share_type as C  # noqa: E402

EVID = os.path.join(ROOT, "docs", "audit", "ra365-round12-share-only-evidence.csv")
ROUND12 = "D:/BorsTerminal-tmp/ra365_round12/codal_type_evidence.jsonl"
ROUND14 = "D:/BorsTerminal-tmp/ra365_round14/codal_type_evidence_round14.jsonl"
UA = "BorsTerminal-parity-audit/1.0"
SEARCH = C.SEARCH
PACE = 6.0
TMP = "D:/BorsTerminal-tmp/ra365_round15"


def jfmt(d):
    jy, jm, jd = C.g2j(d.year, d.month, d.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def load_cache():
    out = {}
    for path in (ROUND12, ROUND14):
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            key = (j.get("symbol"), j.get("step_date"))
            if (j.get("body_status") == "OK"
                    and j.get("event_type") not in (None, "NO_LETTER")):
                out[key] = j
    return out


def http_fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, b"", dict(e.headers or {})
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        return None, str(e).encode("utf-8", "replace"), {}


def retry_after_seconds(headers):
    raw = (headers or {}).get("Retry-After")
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        try:
            when = dt.datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z")
            return max(0, int((when - dt.datetime.utcnow()).total_seconds()))
        except Exception:
            return None


def search_letters(symbol, frm, to):
    letters = []
    for page in range(1, 4):
        q = {"search": "true", "audited": "true", "notAudited": "true",
             "symbol": symbol, "FromDate": frm, "ToDate": to}
        if page > 1:
            q["Page"] = str(page)
        code, body, headers = http_fetch(SEARCH + "?" + urllib.parse.urlencode(q))
        if code is None:
            return letters, "NETWORK", None
        if code == 429:
            return letters, "RATE_LIMITED", retry_after_seconds(headers)
        if code != 200:
            return letters, f"HTTP_{code}", retry_after_seconds(headers)
        try:
            j = json.loads(body.decode("utf-8"))
        except Exception:
            return letters, "BADJSON", None
        batch = j.get("Letters") or []
        letters.extend(batch)
        if len(batch) < 20 or len(letters) >= (j.get("Total") or 0):
            break
        time.sleep(PACE)
    return letters, "OK", None


def row_base(r):
    return {"symbol": r["symbol"], "step_date": r["step_date"],
            "share_ratio": r["share_ratio"], "ref_ratio": r["ref_ratio"],
            "ins_code": r["ins_code"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=os.path.join(
        ROOT, "docs", "audit", "ra365-round15-codal-checkpoint.csv"))
    ap.add_argument("--cache", default=os.path.join(TMP, "codal_checkpoint.jsonl"))
    ap.add_argument("--html-dir", default=os.path.join(TMP, "codal_html_round15"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-rate-limited", action="store_true")
    ap.add_argument("--max-requests", type=int, default=11)
    ap.add_argument("--attempts", type=int, default=1)
    ap.add_argument("--max-wait", type=int, default=90)
    ap.add_argument("--pace", type=float, default=PACE)
    ap.add_argument("--jitter", type=float, default=0.3)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.checkpoint), exist_ok=True)
    os.makedirs(os.path.dirname(a.cache), exist_ok=True)
    os.makedirs(a.html_dir, exist_ok=True)
    lock = os.path.join(TMP, "codal_share_type_resume.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 7200:
        print("another collector is running (lock: %s)" % lock)
        return 2
    open(lock, "w", encoding="utf-8").write(dt.datetime.now().isoformat())
    atexit.register(lambda: os.path.exists(lock) and os.remove(lock))

    cache = load_cache()
    rows = [r for r in csv.DictReader(open(EVID, encoding="utf-8-sig"))
            if r["status"] == "SHARE_RATIO_EXACT_TYPE_UNVERIFIED"]
    # Cached HTML bodies are the durable evidence: a completed body is never
    # lost even if a later checkpoint write was interrupted or raced.
    html_hits = {}
    for r in rows:
        fn = os.path.join(a.html_dir, "%s_%s.html" % (r["ins_code"], r["step_date"]))
        if not os.path.exists(fn):
            continue
        try:
            html = open(fn, encoding="utf-8").read()
            comp = C.composition(C.clean(html))
            et = C.classify(comp)
        except Exception:
            continue
        if et in ("RESERVE_ONLY", "COMBINED_CLAIMS") and float(comp.get("paid_cash") or 0) <= 0:
            html_hits[(r["symbol"], r["step_date"])] = (et, comp, fn)
    state = {}
    for r in rows:
        key = (r["symbol"], r["step_date"])
        rec = row_base(r)
        body = html_hits.get(key)
        hit = cache.get(key)
        if body:
            et, comp, fn = body
            rec.update({
                "status": "COMPLETE", "attempts": 1, "last_http": 200,
                "retry_after": "", "event_type": et,
                "paid_cash": comp.get("paid_cash"), "claims": comp.get("claims"),
                "retained": comp.get("retained"),
                "revaluation": comp.get("revaluation"),
                "letter_tracing": (hit or {}).get("letter_tracing", ""),
                "body_file": fn, "note": "cached HTML body (authoritative)",
            })
        elif hit:
            rec.update({
                "status": "COMPLETE", "attempts": 1, "last_http": 200,
                "retry_after": "", "event_type": hit.get("event_type"),
                "paid_cash": (hit.get("composition") or {}).get("paid_cash"),
                "claims": (hit.get("composition") or {}).get("claims"),
                "retained": (hit.get("composition") or {}).get("retained"),
                "revaluation": (hit.get("composition") or {}).get("revaluation"),
                "letter_tracing": (hit.get("letter") or {}).get("tracing_no"),
                "body_file": hit.get("body_file") or "",
                "note": "cached successful body (Round 12/14)",
            })
        elif r["codal_status"] == "EVIDENCE_OK":
            rec.update({
                "status": "COMPLETE", "attempts": 1, "last_http": 200,
                "retry_after": "", "event_type": r["codal_event_type"],
                "paid_cash": r["paid_cash"], "claims": r["claims"],
                "retained": r["retained"], "revaluation": r["revaluation"],
                "letter_tracing": r["codal_tracing_no"], "body_file": "",
                "note": "evidence row in Round 12 CSV",
            })
        elif r["codal_status"] == "RATE_LIMITED":
            rec.update({"status": "RATE_LIMITED", "attempts": 1, "last_http": 429,
                        "retry_after": "", "event_type": "", "note": "Round 14 HTTP 429; never treated as no-letter"})
        elif r["codal_status"] == "RATE_LIMITED_NOT_RETRIED":
            rec.update({"status": "RETRY_PENDING", "attempts": 0, "last_http": "",
                        "retry_after": "", "event_type": "", "note": "Round 12 rate limit; not retried"})
        else:
            rec.update({"status": "RETRY_PENDING", "attempts": 0, "last_http": "",
                        "retry_after": "", "event_type": "", "note": r["codal_status"] or "not queried"})
        rec["last_attempt"] = ""
        state[key] = rec

    def save():
        fields = ["symbol", "step_date", "share_ratio", "ref_ratio", "ins_code",
                  "status", "attempts", "last_http", "retry_after", "event_type",
                  "paid_cash", "claims", "retained", "revaluation",
                  "letter_tracing", "body_file", "last_attempt", "note"]
        with open(a.checkpoint, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for rec in state.values():
                w.writerow({k: rec.get(k, "") for k in fields})
        with open(a.cache, "w", encoding="utf-8") as fh:
            for rec in state.values():
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("status counts:",
          {s: sum(1 for r in state.values() if r["status"] == s)
           for s in ("COMPLETE", "RETRY_PENDING", "RATE_LIMITED", "FAILED", "SOURCE_NOT_FOUND")})
    if a.dry_run:
        save()
        print("dry run; checkpoint ->", a.checkpoint)
        return

    todo = [r for r in state.values() if r["status"] in ("RETRY_PENDING", "RATE_LIMITED")]
    if not a.include_rate_limited:
        todo = [r for r in todo if r["status"] != "RATE_LIMITED"]
    budget = a.max_requests
    stop = False
    for rec in todo:
        if stop or budget <= 0:
            break
        key = (rec["symbol"], rec["step_date"])
        step = dt.date.fromisoformat(rec["step_date"])
        for attempt in range(1, a.attempts + 1):
            if budget <= 0:
                break
            wait = a.pace * (1 + random.uniform(0, a.jitter))
            time.sleep(wait)
            budget -= 1
            letters, status, retry = search_letters(
                rec["symbol"], jfmt(step - dt.timedelta(days=260)),
                jfmt(step + dt.timedelta(days=45)))
            rec["attempts"] = int(rec.get("attempts") or 0) + 1
            rec["last_attempt"] = dt.datetime.now().isoformat(timespec="seconds")
            rec["last_http"] = status
            rec["retry_after"] = retry if retry is not None else ""
            if status == "RATE_LIMITED":
                rec["status"] = "RATE_LIMITED"
                rec["note"] = "429; Retry-After honored, not a no-letter verdict"
                print(rec["symbol"], rec["step_date"], "RATE_LIMITED",
                      "retry_after", retry, flush=True)
                save()
                if retry is not None and retry <= a.max_wait and attempt < a.attempts:
                    time.sleep(retry)
                    continue
                stop = True
                break
            if status == "NETWORK" or status.startswith("HTTP_5"):
                rec["status"] = "RETRY_PENDING"
                rec["note"] = status
                backoff = min(900, (2 ** attempt) * 15) * (1 + random.uniform(0, a.jitter))
                print(rec["symbol"], rec["step_date"], status,
                      "backoff %.0fs" % backoff, flush=True)
                save()
                time.sleep(backoff)
                continue
            if status != "OK":
                rec["status"] = "FAILED"
                rec["note"] = status
                print(rec["symbol"], rec["step_date"], status, flush=True)
                save()
                break
            caps = []
            for L in letters:
                title = L.get("Title") or ""
                if "افزایش سرمایه" not in title:
                    continue
                pub = C.parse_fa_date(L.get("PublishDateTime"))
                if pub and pub <= step + dt.timedelta(days=45):
                    caps.append((pub, L, title))
            caps.sort(key=lambda x: (x[0], x[1].get("TracingNo") or 0))
            if not caps:
                rec["status"] = "SOURCE_NOT_FOUND"
                rec["note"] = "search OK; no capital-increase letter in window"
                print(rec["symbol"], rec["step_date"], "SOURCE_NOT_FOUND", flush=True)
                save()
                break
            pub, L, title = caps[-1]
            url = "https://codal.ir" + (L.get("Url") or "").replace("&amp;", "&")
            budget -= 1
            code, body, headers = http_fetch(url)
            rec["last_http"] = code if code is not None else "NETWORK"
            rec["letter_tracing"] = L.get("TracingNo")
            if code == 429:
                rec["status"] = "RATE_LIMITED"
                rec["retry_after"] = retry_after_seconds(headers) or ""
                rec["note"] = "body 429; Retry-After honored"
                print(rec["symbol"], rec["step_date"], "BODY_429", flush=True)
                save()
                stop = True
                break
            if code is None or code != 200:
                rec["status"] = "RETRY_PENDING"
                rec["note"] = f"body {rec['last_http']}"
                save()
                break
            html = body.decode("utf-8", "replace")
            fn = os.path.join(a.html_dir, f'{rec["ins_code"]}_{step.isoformat()}.html')
            open(fn, "w", encoding="utf-8").write(html)
            comp = C.composition(C.clean(html))
            rec["event_type"] = C.classify(comp)
            rec["paid_cash"] = comp.get("paid_cash")
            rec["claims"] = comp.get("claims")
            rec["retained"] = comp.get("retained")
            rec["revaluation"] = comp.get("revaluation")
            rec["body_file"] = fn
            rec["status"] = ("COMPLETE" if rec["event_type"] != "UNPARSED"
                             else "RETRY_PENDING")
            rec["note"] = "body parsed" if rec["status"] == "COMPLETE" else "body unparsed"
            print(rec["symbol"], rec["step_date"], rec["event_type"],
                  comp, rec["status"], flush=True)
            save()
            break
    save()
    print("done; checkpoint ->", a.checkpoint)


if __name__ == "__main__":
    main()
