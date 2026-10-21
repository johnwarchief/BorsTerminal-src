# -*- coding: utf-8 -*-
"""Round 12: official CODAL type evidence for share-only capital events.

For each share-only step row, searches the public CODAL search API inside a
date window and fetches the capital-increase letter body to read the funding
composition.  Read-only, paced, no credentials.  Cache lives on D:.
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = r"C:\Users\Johnkallnaya\Desktop\Borsterminal"
WT = os.path.join(ROOT, ".worktrees", "ra365-round8")
sys.path.insert(0, os.path.join(WT, "tools"))
from ra_parity import g2j, j2g  # noqa: E402

EVID = os.path.join(WT, "docs", "audit", "ra365-round12-share-only-evidence.csv")
OUTDIR = r"D:\BorsTerminal-tmp\ra365_round12"
CACHE = os.path.join(OUTDIR, "codal_type_evidence.jsonl")
HTMLDIR = os.path.join(OUTDIR, "codal_html")
SEARCH = "https://search.codal.ir/api/search/v2/q"
UA = "BorsTerminal-parity-audit/1.0"
PACE = 3.0

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def jfmt(d):
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def parse_fa_date(s):
    s = "".join(ch for ch in str(s).split(" ")[0].translate(FA_DIGITS) if ch.isdigit() or ch == "/")
    try:
        y, m, d = (int(x) for x in s.split("/"))
        return j2g(y, m, d)
    except Exception:
        return None


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def search(symbol, frm, to):
    letters = []
    for page in range(1, 4):
        q = {"search": "true", "audited": "true", "notAudited": "true",
             "symbol": symbol, "FromDate": frm, "ToDate": to}
        if page > 1:
            q["Page"] = str(page)
        url = SEARCH + "?" + urllib.parse.urlencode(q)
        try:
            st, body = fetch(url)
        except Exception as e:
            return letters, "SEARCH_" + type(e).__name__
        try:
            j = json.loads(body.decode("utf-8"))
        except Exception:
            return letters, "SEARCH_BADJSON"
        batch = j.get("Letters") or []
        letters.extend(batch)
        if len(batch) < 20 or len(letters) >= (j.get("Total") or 0):
            break
        time.sleep(PACE)
    return letters, "OK"


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.translate(FA_DIGITS)
    text = re.sub(r"[\u200c\u200f\u202b\u202c]", "", text)
    return re.sub(r"\s+", " ", text)


NUM = r"([0-9][0-9,\.]*)"


def amount_before(text, label):
    """عددِ پیش از برچسب در فاصلۀ کوتاه (متنِ کدال: «X ریال از محل <label>»)."""
    idx = text.find(label)
    if idx < 0:
        return None
    chunk = text[max(0, idx - 120):idx]
    m = re.findall(NUM, chunk)
    if not m:
        return None
    try:
        return float(m[-1].replace(",", ""))
    except Exception:
        return None


def composition(text):
    cap = None
    m = re.search(r"مبلغ افزایش سرمایه\s*:?\s*" + NUM, text)
    if m:
        cap = float(m.group(1).replace(",", ""))
    return {
        "capital_increase": cap,
        "paid_cash": amount_before(text, "از محل آورده نقدی سهامداران"),
        "claims": amount_before(text, "از محل مطالبات حال شده سهامداران"),
        "retained": amount_before(text, "از محل سود انباشته"),
        "reserve_dev": amount_before(text, "از محل اندوخته طرح و توسعه"),
        "reserve_other": amount_before(text, "از محل سایر اندوخته"),
        "revaluation": amount_before(text, "از محل مازاد تجدید ارزیابی"),
    }


def classify(c):
    vals = {k: (c.get(k) or 0.0) for k in
            ("paid_cash", "claims", "retained", "reserve_dev", "reserve_other", "revaluation")}
    total = sum(vals.values())
    if total <= 0:
        return "UNPARSED"
    if vals["paid_cash"] > 0 and (vals["retained"] + vals["reserve_dev"] +
                                  vals["reserve_other"] + vals["revaluation"]) > 0:
        return "COMBINED_PAID_IN"
    if vals["paid_cash"] > 0:
        return "PAID_IN"
    if vals["claims"] > 0 and (vals["retained"] + vals["reserve_dev"] +
                               vals["reserve_other"] + vals["revaluation"]) > 0:
        return "COMBINED_CLAIMS"
    if vals["claims"] > 0:
        return "CLAIMS_ONLY"
    return "RESERVE_ONLY"


def main():
    rows = [r for r in csv.DictReader(open(EVID, encoding="utf-8-sig"))
            if r["status"] == "SHARE_RATIO_EXACT_TYPE_UNVERIFIED"]
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(HTMLDIR, exist_ok=True)
    done = set()
    if os.path.exists(CACHE):
        for line in open(CACHE, encoding="utf-8"):
            try:
                j = json.loads(line)
                done.add((j["symbol"], j["step_date"]))
            except Exception:
                pass
    out = open(CACHE, "a", encoding="utf-8")
    for r in rows:
        key = (r["symbol"], r["step_date"])
        if key in done:
            print("cached", key, flush=True)
            continue
        step = dt.date.fromisoformat(r["step_date"])
        frm = jfmt(step - dt.timedelta(days=200))
        to = jfmt(step + dt.timedelta(days=30))
        letters, status = search(r["symbol"], frm, to)
        time.sleep(PACE)
        caps = []
        for L in letters:
            title = L.get("Title") or ""
            if "افزایش سرمایه" not in title:
                continue
            pub = parse_fa_date(L.get("PublishDateTime"))
            caps.append((pub, L, title))
        caps = [c for c in caps if c[0] and c[0] <= step + dt.timedelta(days=45)]
        caps.sort(key=lambda x: (x[0], x[1].get("TracingNo") or 0))
        rec = {"symbol": r["symbol"], "ins_code": r["ins_code"],
               "step_date": r["step_date"], "share_ratio": r["share_ratio"],
               "ref_ratio": r["ref_ratio"], "shares_old": r["shares_old"],
               "shares_new": r["shares_new"], "search_status": status,
               "search_letters": len(letters), "cap_letters": len(caps),
               "letter": None, "composition": None, "event_type": "NO_LETTER"}
        if caps:
            pub, L, title = caps[-1]
            url = "https://codal.ir" + (L.get("Url") or "").replace("&amp;", "&")
            rec["letter"] = {"tracing_no": L.get("TracingNo"), "title": title,
                             "publish": pub.isoformat() if pub else None,
                             "url": url, "letter_code": L.get("LetterCode")}
            try:
                st, body = fetch(url)
                html = body.decode("utf-8", "replace")
                fn = os.path.join(HTMLDIR, f'{r["ins_code"]}_{step.isoformat()}.html')
                open(fn, "w", encoding="utf-8").write(html)
                comp = composition(clean(html))
                rec["composition"] = comp
                rec["event_type"] = classify(comp)
                rec["body_status"] = "OK"
                rec["body_file"] = fn
            except Exception as e:
                rec["body_status"] = type(e).__name__
            time.sleep(PACE)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        print(r["symbol"], r["step_date"], rec["event_type"],
              rec["composition"], rec["body_status"] if rec["letter"] else "-", flush=True)
    out.close()
    print("done", len(rows))


if __name__ == "__main__":
    main()
