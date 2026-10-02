# یک‌بارمصرف — «عنوانِ صورتِ مالی» یا «ستونِ is_consolidated»؟
# اگر موتور از ستون (که مسیرِ واکشی از خودِ گزارش می‌خواند) به‌جای عنوان استفاده کند،
# ردیفِ مرجعِ چندِ نماد عوض می‌شود؟ (عددِ لازم برایِ تصمیمِ مالک)
import sqlite3
import sys

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import codal_periods as CP          # noqa: E402
import fts_engine as FE             # noqa: E402

conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
SQL = ("SELECT period_end, period_months, title, tracing_no, COALESCE(is_consolidated,0),"
       " revenue, gross_profit, operating_profit, net_profit, basic_eps"
       " FROM financial_statements WHERE symbol=? AND period_months>=12")


def ref(rows, use_column):
    by_year = {}
    for d in rows:
        cons = bool(d["cons_col"]) if use_column else FE._is_consolidated(d["title"] or "")
        rk = FE.statement_rank(FE.FS_NUMBER_KEYS, cons,
                               FE.row_completeness(FE.FS_NUMBER_KEYS, d), d["tn"] or 0)
        cur = by_year.get(d["fy"])
        if cur is None or rk < cur[0]:
            by_year[d["fy"]] = (rk, {**d, "consolidated": cons, "audited": True})
    cand = sorted(by_year.values(), key=lambda t: str(t[1]["fy"]), reverse=True)
    for want in (lambda a, c: a and not c, lambda a, c: not c, lambda a, c: True):
        for _rk, r in cand:
            if want(bool(r["audited"]), bool(r["consolidated"])):
                return r
    return None


def margin(d):
    if not d or not d.get("revenue") or d.get("gross_profit") is None:
        return None
    return round(d["gross_profit"] / d["revenue"] * 100.0, 1)


symbols = [r[0] for r in conn.execute(
    "SELECT DISTINCT symbol FROM financial_statements WHERE period_months>=12")]
both = changed = 0
samples = []
for sym in symbols:
    rows = []
    for pe, pm, title, tn, cons, rev, gp, op, np_, eps in conn.execute(SQL, (sym,)):
        rows.append({"period_end": pe, "period_months": pm, "title": title, "tn": tn,
                     "cons_col": cons, "revenue": rev, "gross_profit": gp,
                     "operating_profit": op, "net_profit": np_, "basic_eps": eps,
                     "fy": CP.fiscal_year(pe)})
    a, b = ref(rows, False), ref(rows, True)
    if not a or not b:
        continue
    both += 1
    if a["tn"] != b["tn"]:
        changed += 1
        if margin(a) != margin(b):
            samples.append((sym, margin(a), margin(b), a["fy"], b["fy"]))
print("نمادهای دارای سالانۀ قابل‌مقایسه:", both)
print("ردیفِ مرجع عوض می‌شود:", changed, "(%.1f%%)" % (100.0 * changed / max(both, 1)))
print("و حاشیۀ ناخالص هم عددش عوض می‌شود:", len(samples))
for s in samples[:12]:
    print("   %-9s عنوان‌محور=%s%% (FY%s) | ستون‌محور=%s%% (FY%s)"
          % (s[0], s[1], s[3], s[2], s[4]))
