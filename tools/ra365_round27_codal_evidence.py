#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27 Track C: bounded, checkpointed CODAL evidence retrieval.

Searches the public CODAL interface for the highest-impact residual events,
matches assembly/capital/DPS notices near the event date, fetches the letter
page, hashes it and saves a human-auditable excerpt. Honors Retry-After and
429 with bounded backoff; records an explicit state per event. It never
guesses `S`, never treats a Rahavard event as evidence and never writes the
production database.

Usage:
  python tools/ra365_round27_codal_evidence.py --out <dir> \
      --events D:/BorsTerminal-tmp/r26_bench/counterfactual/counterfactual.csv \
      --max-events 3 --max-requests 8
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ra_parity as RP  # noqa: E402

API = "https://search.codal.ir/api/search/v2/q"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
KEYS = ("افزایش سرمایه", "پذیره", "سود نقدی", "تقسیم سود", "مجمع")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), dict(r.headers)


def jdate(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return RP.g2j(y, m, d)


def month_end(jy, jm):
    # 6×31 + 5×30 + up to 29 for Esfand; a +2 month window is enough here
    return 31 if jm <= 6 else 30


def search(sym, iso):
    jy, jm, jd = jdate(iso)
    end_m = jm + 2
    end_y = jy + (end_m - 1) // 12
    end_m = (end_m - 1) % 12 + 1
    fd = "%04d/%02d/01" % (jy, jm)
    td = "%04d/%02d/%02d" % (end_y, end_m, month_end(end_y, end_m))
    q = {"PageNumber": 1, "PageSize": 20, "search": "true", "Symbol": sym,
         "Category": "6", "FromDate": fd, "ToDate": td}
    return API + "?" + urllib.parse.urlencode(q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--events", required=True)
    ap.add_argument("--max-events", type=int, default=3)
    ap.add_argument("--max-requests", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ledger_path = os.path.join(a.out, "evidence-ledger.jsonl")
    done = set()
    if os.path.exists(ledger_path):
        for line in open(ledger_path, encoding="utf-8"):
            try:
                r = json.loads(line)
                done.add((r.get("symbol"), r.get("date")))
            except Exception:
                pass
    rows = [r for r in csv.DictReader(open(a.events, encoding="utf-8-sig"))
            if r.get("date") and r["date"] >= "2020-01-01"]
    rows.sort(key=lambda r: -int(r.get("attributed_rows") or 0))
    requests = 0
    events = 0
    for r in rows:
        if events >= a.max_events or requests >= a.max_requests:
            break
        sym, date = r["symbol"], r["date"]
        if (sym, date) in done:
            continue
        events += 1
        rec = {"symbol": sym, "date": date, "class": r.get("class"),
               "attributed_rows": r.get("attributed_rows"),
               "search_url": search(sym, date), "state": "", "letters": [],
               "doc_sha256": "", "doc_url": "", "excerpt": "", "notes": ""}
        attempts = 0
        while attempts < 2 and requests < a.max_requests:
            attempts += 1
            requests += 1
            try:
                status, body, headers = get(rec["search_url"])
                doc = json.loads(body.decode("utf-8", "replace"))
                letters = doc.get("Letters") or []
                rec["http"] = status
                rec["letters"] = [{"title": (L.get("Title") or "").strip(),
                                   "tracing": str(L.get("TracingNo") or ""),
                                   "published": L.get("PublishDateTime"),
                                   "url": L.get("Url")} for L in letters[:20]]
                matches = [L for L in letters
                           if any(k in (L.get("Title") or "") for k in KEYS)]
                if not matches:
                    rec["state"] = "NOT_FOUND"
                    break
                def _pub_key(L):
                    title = L.get("Title") or ""
                    pref = 0 if "تصمیم" in title else 1
                    pub = str(L.get("PublishDateTime") or "")
                    try:
                        jy, jm, jd = (int(x) for x in pub.split(" ")[0].split("/"))
                        days = RP.j2g(jy, jm, jd).toordinal()
                    except Exception:
                        days = 0
                    return (pref, abs(days - ev_ord))
                ey, em, ed = jdate(date)
                ev_ord = RP.j2g(ey, em, ed).toordinal()
                L = sorted(matches, key=_pub_key)[0]
                u = str(L.get("Url") or "")
                rec["doc_url"] = u if u.startswith("http") else "https://codal.ir" + (u if u.startswith("/") else "/" + u)
                try:
                    s2, page, _h2 = get(rec["doc_url"])
                    rec["doc_sha256"] = sha_bytes(page)
                    text = re.sub(r"<[^>]+>", " ", page.decode("utf-8", "replace"))
                    text = re.sub(r"\s+", " ", text).strip()
                    idx = next((text.find(k) for k in KEYS if text.find(k) >= 0), -1)
                    rec["excerpt"] = text[max(0, idx - 120):idx + 420] if idx >= 0 else text[:400]
                    nums = re.findall(r"(?:سود نقدی|تقسیم سود|افزایش سرمایه|پذیره)[^0-9]{0,90}([0-9][0-9,./]{2,24})", text)
                    rec["extracted_numbers"] = nums[:8]
                    rec["state"] = "VERIFIED" if nums else "INCOMPLETE_DOCUMENT"
                except urllib.error.HTTPError as e:
                    rec["state"] = "AUTH_REQUIRED" if e.code in (401, 403) else "INCOMPLETE_DOCUMENT"
                    rec["notes"] = "document HTTP %s" % e.code
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    wait = min(int(ra) if ra and str(ra).isdigit() else 20, 60)
                    rec["state"] = "RATE_LIMITED"
                    rec["notes"] = "429; waited %ss" % wait
                    time.sleep(wait)
                    continue
                rec["state"] = "AUTH_REQUIRED" if e.code in (401, 403) else "TRANSIENT_FAILURE"
                rec["notes"] = "search HTTP %s" % e.code
                break
            except Exception as e:  # noqa: BLE001
                rec["state"] = "TRANSIENT_FAILURE"
                rec["notes"] = str(e)[:160]
                break
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(sym, date, rec["state"], rec.get("doc_url", ""))
        time.sleep(3)
    print(json.dumps({"events": events, "requests": requests,
                      "ledger": ledger_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
