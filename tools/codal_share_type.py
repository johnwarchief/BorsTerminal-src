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
    chunk = text[max(0, idx - 50):idx]
    m = re.findall(NUM, chunk)
    if not m:
        return None
    try:
        return float(m[-1].replace(",", ""))
    except Exception:
        return None


def amount_after(text, label, window=220):
    """عددِ پس از برچسب («... <label> ... مبلغ X میلیون ریال»).

    The registration letters often put the amount after the funding label.
    Stop at the next component label so a missing amount never borrows the
    next field's number.
    """
    idx = text.find(label)
    if idx < 0:
        return None
    chunk = text[idx + len(label):idx + len(label) + window]
    stops = [chunk.find(x) for x in ("از محل", "و از ", "، از ", ")") if chunk.find(x) > 0]
    if stops:
        chunk = chunk[:min(stops)]
    m = re.search(r"مبلغ\s*([0-9][0-9,\.]*)", chunk)
    if not m:
        m = re.match(r"\s*([0-9][0-9,\.]*)", chunk)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _amount(text, label):
    idx = text.find(label)
    if idx >= 0 and "مبلغ" in text[idx + len(label):idx + len(label) + 120]:
        return amount_after(text, label)
    return amount_before(text, label) or amount_after(text, label)


def _total_increase(text):
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


def _stage_paid_cash(text):
    """Paid cash stated as a stage: «از مبلغ X ... به مبلغ Y ... آورده نقدی»."""
    m = re.search(r"مرحله[^)]{0,500}?از مبلغ\s*" + NUM +
                  r"\s*(?:میلیون\s*)?ریال\s*به مبلغ\s*" + NUM +
                  r"[^)]{0,250}?آورده نقدی", text)
    if not m:
        return None
    try:
        return float(m.group(2).replace(",", "")) - float(m.group(1).replace(",", ""))
    except Exception:
        return None


def composition(text):
    total = _total_increase(text)
    vals = {
        "capital_increase": total,
        "paid_cash": _amount(text, "آورده نقدی"),
        "claims": _amount(text, "مطالبات"),
        "retained": _amount(text, "سود انباشته"),
        "reserve_dev": _amount(text, "اندوخته طرح و توسعه"),
        "reserve_other": _amount(text, "سایر اندوخته"),
        "revaluation": _amount(text, "تجدید ارزیابی"),
    }
    unit = "million_rial" if "میلیون ریال" in text else "rial"
    derived = []
    comps = ("paid_cash", "claims", "retained", "reserve_dev",
             "reserve_other", "revaluation")
    known = sum(vals[k] for k in comps if k != "paid_cash" and vals[k])
    if (vals["paid_cash"] is None and "آورده نقدی" in text and total
            and abs(known / total - 1.0) <= 0.005):
        vals["paid_cash"] = 0.0
        derived.append("paid_cash")
    total_known = sum(vals[k] for k in comps if vals[k])
    stage_paid = _stage_paid_cash(text)
    if stage_paid and stage_paid > 0:
        vals["paid_cash"] = stage_paid
        if "paid_cash_stage" not in derived:
            derived.append("paid_cash_stage")
    vals["unit"] = unit
    vals["derived"] = derived
    vals["complete"] = bool(total and abs(total_known / total - 1.0) <= 0.005)
    return vals


def classify(c):
    vals = {k: (c.get(k) or 0.0) for k in
            ("paid_cash", "claims", "retained", "reserve_dev", "reserve_other", "revaluation")}
    total = sum(vals.values())
    if c.get("capital_increase") and not c.get("complete"):
        # A narrative letter with a paid-cash stage but no component split
        # is still PAID_IN; never promote it to a no-cash type.
        if (c.get("paid_cash") or 0) > 0:
            return "PAID_IN"
        return "UNPARSED"
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
