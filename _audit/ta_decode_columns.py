"""Decode TraderArena's compact column arrays by matching them to our own
TSETMC-derived numbers, instead of guessing the order.

For every field TraderArena publishes for a symbol (mainwatch) or an industry
(industries-csv), find which of our fields has the same value. A field with no
match on our side is a real gap, not a naming problem.

    python _audit/ta_decode_columns.py
"""
import json
import urllib.request


def norm(s):
    """TSETMC writes Arabic ي/ك and ZWNJ; TraderArena writes the Persian forms."""
    import re as _re
    s = str(s or "").replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    return _re.sub(r"[‌‏\s]+", " ", s).strip()


TA = "https://tradersarena.ir"
APP = "http://127.0.0.1:8001"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def close(a, b, rel=0.01, abs_tol=1.0):
    if a is None or b is None:
        return False
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if abs(a - b) <= abs_tol:
        return True
    m = max(abs(a), abs(b))
    return m > 0 and abs(a - b) / m <= rel


mw = get(TA + "/data/mainwatch/symbols")
ours = get(APP + "/api/market")
rows = ours["data"] if isinstance(ours, dict) else ours
by_sym = {}
for r in rows:
    s = str(r.get("symbol") or r.get("l_val18") or "").strip()
    if s:
        by_sym.setdefault(s, r)

NUMERIC_OURS = ["q_tot_tran", "z_tot_tran", "q_tot_cap", "p_last", "p_closing",
                "percent_change", "price_yesterday", "buy_i_vol", "sell_i_vol",
                "buy_count_i", "sell_count_i", "buy_n_vol", "sell_n_vol",
                "buy_q_vol", "buy_q_val", "sell_q_vol", "sell_q_val",
                "month_avg_vol", "prev_day_vol", "vol_ratio", "buyer_power"]

print(f"mainwatch ردیف‌ها={len(mw)}  عرضِ آرایه={len(mw[0])}")
pairs = {}
for idx in range(len(mw[0])):
    vals, syms = [], []
    for row in mw:
        v = row[idx]
        if isinstance(v, (int, float)):
            our = by_sym.get(str(row[2]).strip())
            if our is not None:
                vals.append(float(v))
                syms.append(our)
    if len(vals) < 5:
        continue
    hits = []
    for col in NUMERIC_OURS:
        got = [s.get(col) for s in syms]
        ok = sum(1 for a, b in zip(vals, got) if b is not None and close(a, b))
        if ok >= max(3, int(0.8 * len(vals))):
            hits.append(f"{col}({ok}/{len(vals)})")
    # scaled variants: میلیارد / میلیون
    for col in NUMERIC_OURS:
        got = [s.get(col) for s in syms]
        ok = sum(1 for a, b in zip(vals, got)
                 if b is not None and close(a, float(b) / 1e9))
        if ok >= max(3, int(0.8 * len(vals))):
            hits.append(f"{col}/۱e۹({ok}/{len(vals)})")
    pairs[idx] = hits
    print(f"  [{idx:>2}] نمونه={vals[0]:>18,.2f}   ← {' '.join(hits) if hits else '★ هیچ ستونی در ما مطابق نیست'}")

print("\n--- صنایع ---")
ind = get(TA + "/data/industries-csv")
print(f"ردیف‌ها={len(ind)}  عرض={len(ind[0])}")
mine_ind = {norm(r["industry"]): r for r in get(APP + "/api/mstat/industries")["rows"]}
ta_head = ["کد", "نام"] + ["حجم", "ارزش", "ارزش خرید حقیقی", "ارزش فروش حقیقی",
                           "ارزش سفارش خرید", "ارزش سفارش فروش", "برآیند سفارش", "بازدهی هموزن",
                           "سرانه خرید", "سرانه فروش", "قدرت خرید", "درصد خرید حقیقی", "درصد فروش حقیقی",
                           "ورود پول", "درصد ارزش از خرد", "شاخص سهم", "ارزش/میانگین۵", "ارزش/میانگین۲۰",
                           "ارزش ۵r", "ارزش ۲۰r", "سرانهx۵r", "سرانهx۲۰r", "سرانهف۵r", "سرانهف۲۰r",
                           "قدرت۵r", "قدرت۲۰r", "ورودپول۵r", "ورودپول۲۰r", "تعداد نماد"]
for idx in range(len(ind[0])):
    vals, mine = [], []
    for row in ind:
        name = norm(row[1])
        if name in mine_ind and isinstance(row[idx], (int, float)):
            vals.append(float(row[idx]))
            mine.append(mine_ind[name])
    if len(vals) < 5:
        label = ta_head[idx] if idx < len(ta_head) else f"ستون{idx}"
        print(f"  [{idx:>2}] {label:<18} ({len(vals)} تطابق نام) → بی‌نام")
        continue
    label = ta_head[idx] if idx < len(ta_head) else f"ستون{idx}"
    hits = []
    for col in ["volume_b_shares", "value_b_toman", "flow_b_toman", "avg_pct", "symbols",
                "positive", "negative", "buy_queue_b_toman", "sell_queue_b_toman"]:
        ok = sum(1 for a, m in zip(vals, mine) if close(a, m.get(col), rel=0.02)
                 or close(a, float(m.get(col) or 0) * 1e9, rel=0.02)
                 or close(a, float(m.get(col) or 0) / 1e9, rel=0.02))
        if ok >= max(3, int(0.8 * len(vals))):
            hits.append(f"{col}({ok}/{len(vals)})")
    print(f"  [{idx:>2}] {label:<18} نمونه={vals[0]:>16,.2f}  ← {' '.join(hits) if hits else '★ در ما نیست'}")

print("\n--- بازدهی دوره‌ای (histo-status) ---")
hs = get(TA + "/data/market/histo-status")
for k, v in hs.items():
    print(f"  {k}: len={len(v)}  {v}")
