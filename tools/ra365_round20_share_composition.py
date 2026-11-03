# -*- coding: utf-8 -*-
"""Round 20: fetch public CODAL funding composition for share-change events.

This is a read-only reference audit.  It never writes a market DB and never
invents a missing amount.  Results are checkpointed and can be resumed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra_parity import g2j, j2g  # noqa: E402

UA = {"User-Agent": "BorsTerminal-parity-audit/1.0",
      "Accept": "text/html,application/json"}
SEARCH = "https://search.codal.ir/api/search/v2/q"
IN = os.path.join(ROOT, "artifacts", "ra365", "r20", "share-events.csv")
OUT = os.path.join(ROOT, "artifacts", "ra365", "r20", "share-composition.jsonl")
HTMLDIR = os.environ.get("RA365_R20_CODAL_HTML", "D:/BorsTerminal-tmp/r20_codal_html")
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
NUM = r"([0-9][0-9,\.]*)"


def jfmt(d):
    y, m, dd = g2j(d.year, d.month, d.day)
    return f"{y:04d}/{m:02d}/{dd:02d}"


def parse_fa_date(s):
    s = "".join(ch for ch in str(s).split(" ")[0].translate(FA_DIGITS)
                if ch.isdigit() or ch == "/")
    try:
        y, m, d = (int(x) for x in s.split("/"))
        return j2g(y, m, d)
    except Exception:
        return None


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
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
        st, body = fetch(url)
        j = json.loads(body.decode("utf-8"))
        batch = j.get("Letters") or []
        letters.extend(batch)
        if len(batch) < 20 or len(letters) >= (j.get("Total") or 0):
            break
        time.sleep(2)
    return letters


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.translate(FA_DIGITS)
    text = re.sub(r"[\u200c\u200f\u202b\u202c]", "", text)
    return re.sub(r"\s+", " ", text)


def amount_after(text, label, window=220):
    idx = text.find(label)
    if idx < 0:
        return None
    chunk = text[idx + len(label):idx + len(label) + window]
    stops = [chunk.find(x) for x in ("از محل", "و از ", "، از ", ")")
             if chunk.find(x) > 0]
    if stops:
        chunk = chunk[:min(stops)]
    m = re.search(r"مبلغ\s*" + NUM, chunk) or re.match(r"\s*" + NUM, chunk)
    try:
        return float(m.group(1).replace(",", "")) if m else None
    except Exception:
        return None


def amount_before(text, label):
    idx = text.find(label)
    if idx < 0:
        return None
    m = re.findall(NUM, text[max(0, idx - 50):idx])
    try:
        return float(m[-1].replace(",", "")) if m else None
    except Exception:
        return None


def amount(text, label):
    idx = text.find(label)
    if idx >= 0 and "مبلغ" in text[idx + len(label):idx + len(label) + 120]:
        return amount_after(text, label)
    return amount_before(text, label) or amount_after(text, label)


def total_increase(text):
    m = re.search(r"افزایش سرمای[^)]{0,500}?از مبلغ\s*" + NUM +
                  r"\s*میلیون ریال\s*بهمبلغ\s*" + NUM, text)
    if m:
        try:
            return float(m.group(2).replace(",", "")) - float(m.group(1).replace(",", ""))
        except Exception:
            return None
    m = re.search(r"مبلغ افزایش سرمایه\s*:?\s*" + NUM, text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except Exception:
            return None
    return None


def composition(text):
    total = total_increase(text)
    vals = {
        "capital_increase": total,
        "paid_cash": amount(text, "آورده نقدی"),
        "claims": amount(text, "مطالبات"),
        "retained": amount(text, "سود انباشته"),
        "reserve_dev": amount(text, "اندوخته طرح و توسعه"),
        "reserve_other": amount(text, "سایر اندوخته"),
        "revaluation": amount(text, "تجدید ارزیابی"),
        "shares_new": None,
        "par": None,
        "unit": "million_rial" if "میلیون ریال" in text else "rial",
    }
    m = re.search(r"تعداد سهام قابل انتشار\s*:?\s*" + NUM, text)
    if m:
        vals["shares_new"] = float(m.group(1).replace(",", ""))
    m = re.search(r"ارزش اسمی هر سهم\s*:?\s*" + NUM, text)
    if m:
        vals["par"] = float(m.group(1).replace(",", ""))
    comps = ("paid_cash", "claims", "retained", "reserve_dev",
             "reserve_other", "revaluation")
    known = sum(v for k, v in vals.items() if k in comps and v)
    vals["complete"] = bool(total and abs(known / total - 1.0) <= 0.005)
    return vals


def normalize_rial(c):
    mult = 1_000_000.0 if c.get("unit") == "million_rial" else 1.0
    for k in ("capital_increase", "paid_cash", "claims", "retained",
              "reserve_dev", "reserve_other", "revaluation"):
        if c.get(k) is not None:
            c[k] = c[k] * mult
                # par/shares are not monetary
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pace", type=float, default=2.5)
    args = ap.parse_args()
    os.makedirs(HTMLDIR, exist_ok=True)
    rows = list(csv.DictReader(open(IN, encoding="utf-8-sig")))
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                j = json.loads(line)
                done.add((str(j["ins_code"]), j["share_date"]))
            except Exception:
                pass
    out = open(OUT, "a", encoding="utf-8")
    n = 0
    for r in rows:
        key = (str(r["ins_code"]), r["share_date"])
        if key in done:
            continue
        if args.limit and n >= args.limit:
            break
        n += 1
        step = dt.date.fromisoformat(r["share_date"])
        rec = {"symbol": r["symbol"], "ins_code": str(r["ins_code"]),
               "asset_id": r["asset_id"], "share_date": r["share_date"],
               "step_date": r["step_date"], "shares_old": r["shares_old"],
               "shares_new": r["shares_new"], "share_ratio": r["share_ratio"],
               "ref_ratio": r["ref_ratio"], "prod_ratio": r["prod_ratio"],
               "status": None, "letter": None, "composition": None}
        try:
            letters = search(r["symbol"], jfmt(step - dt.timedelta(days=400)),
                             jfmt(step + dt.timedelta(days=60)))
            caps = []
            for L in letters:
                title = L.get("Title") or ""
                if "افزایش سرمایه" not in title:
                    continue
                pub = parse_fa_date(L.get("PublishDateTime"))
                if pub is None or pub > step + dt.timedelta(days=90):
                    continue
                caps.append((pub, L, title))
            caps.sort(key=lambda x: (x[0], x[1].get("TracingNo") or 0))
            best = None
            for pub, L, title in caps[-8:]:
                url = "https://codal.ir" + (L.get("Url") or "").replace("&amp;", "&")
                try:
                    st, body = fetch(url)
                    html = body.decode("utf-8", "replace")
                    fn = os.path.join(HTMLDIR, f"{r['ins_code']}_{step.isoformat()}_{L.get('TracingNo')}.html")
                    open(fn, "w", encoding="utf-8").write(html)
                    comp = normalize_rial(composition(clean(html)))
                    cand = {"publish": pub.isoformat(), "tracing_no": L.get("TracingNo"),
                            "title": title, "url": url, "body_file": fn,
                            "composition": comp}
                    if comp.get("complete") and (best is None or
                            (comp.get("capital_increase") or 0) >=
                            (best["composition"].get("capital_increase") or 0)):
                        best = cand
                    time.sleep(args.pace)
                except Exception as e:
                    rec["last_error"] = type(e).__name__ + ":" + str(e)[:120]
            if best:
                rec["status"] = "COMPLETE"
                rec["letter"] = {k: best[k] for k in ("publish", "tracing_no", "title",
                                                      "url", "body_file")}
                rec["composition"] = best["composition"]
            elif caps:
                rec["status"] = "LETTERS_NO_COMPLETE_COMPOSITION"
            else:
                rec["status"] = "NO_CAPITAL_LETTER"
        except Exception as e:
            rec["status"] = "SEARCH_ERROR:" + type(e).__name__
            rec["last_error"] = str(e)[:200]
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        print(rec["symbol"], rec["share_date"], rec["status"],
              (rec.get("composition") or {}).get("unit"), flush=True)
        time.sleep(args.pace)
    out.close()
    print("done", n)


if __name__ == "__main__":
    main()
