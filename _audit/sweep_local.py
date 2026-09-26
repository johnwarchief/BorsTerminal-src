import os, re, sys, json, collections
sys.path.insert(0, os.getcwd())
import api.fundamental as AF

SYMS = ["فولاد", "خودرو", "شپدیس", "وغدير", "تاپیکست", "وشمال", "خساپا", "زگستر", "كگل", "مفاخر"]
FIELDS = ("reason", "basis", "outlook", "note", "why", "fix", "denominator_basis")
BAN = re.compile(r"api/|monthly_sales|financial_statements|fts_engine|annualize|backfill|mode=|\bNone\b|\bNaN\b|YoY|بک‌اند|→", re.I)
CLAIM = re.compile(r"تضمین|انحصاری|بهره‌وری عالی|حباب|جهش عملیاتی|قدرت فروش|حاشیه امن|سرکوب|بی‌معنا|تایید می‌شود")

seen = collections.Counter(); flags = collections.Counter()
for s in SYMS:
    try:
        d = AF.get_fundamental(s)
        if isinstance(d, tuple): d = d[0]
    except Exception as e:
        print("!!", s, type(e).__name__, str(e)[:120]); continue
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and k in FIELDS and v.strip():
                    seen[v.strip()] += 1
                    if BAN.search(v): flags["JARGON: " + v.strip()[:150]] += 1
                    if CLAIM.search(v): flags["CLAIM: " + v.strip()[:150]] += 1
                else: walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk({k: d.get(k) for k in ("indicators", "data_gaps")})

print("distinct visible strings:", len(seen))
print("--- still flagged ---")
for k, n in flags.most_common(30): print("%3d %s" % (n, k))
print("--- sample of what the user now sees ---")
for k, n in list(seen.most_common(14)): print("%3d %s" % (n, k[:150]))
