"""سنجشِ أثرِ رأیِ ۱۳ رویِ بانکِ واقعی (فقط خواندنی).

«چند نماد تا دیروز شاخص ۲ را با شاهدِ تلفیقی پاس می‌گرفتند و از این به بعد
N/A می‌شوند؟» — قاعدۀ کهنه در `eps_assessment` این بود:

    if all(e == audited): audited
    elif low_quality_track: year_end_plus_interim     # ← تلفیقی را می‌بلعد
    elif consolidated_used: consolidated_year_end
    elif relaxed: year_end_unaudited

یعنی هر پنجره‌ای که **یک** اسلاتِ میاندوره داشت و **یک** اسلاتِ تلفیقی، بی‌هیچ
برچسبی با EPSِ تلفیقی داوری می‌شد. در شعبۀ `partial` هم `consolidated_used`
هرگز گذاشته نمی‌شد.
اجرا:  PYTHONIOENCODING=utf-8 py -3.14 _audit/f2_consolidated_impact.py
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as F  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)


def old_tier(ladder, ev):
    """همان سلسلۀ معیوبِ قبل از این اصلاح — برایِ سنجشِ «چه چیزی عوض شد»."""
    if ev and all(e == "audited_year_end" for e in ev):
        return "audited_year_end"
    if ladder.get("low_quality_track"):
        return "year_end_plus_interim"
    if ladder.get("consolidated_used"):
        return "consolidated_year_end"
    if ladder.get("relaxed_evidence"):
        return "year_end_unaudited"
    return "insufficient"


symbols = [r[0] for r in conn.execute(
    "SELECT DISTINCT symbol FROM financial_statements WHERE basic_eps IS NOT NULL")]
cfg = F.load_fts_config()
need = int(cfg.get("eps_years", 3) or 3)

rows = []
for s in symbols:
    ladder = F.eps_ladder(conn, s, years=need) or {}
    ev = [str(x or "") for x in (ladder.get("evidence") or [])]
    if not ev:
        continue
    cons = [y for y, x in zip(ladder.get("period_slots") or [], ev)
            if x.startswith("consolidated_")]
    if not cons:
        continue
    new = F.eps_assessment(conn, s, years=need) or {}
    ot = old_tier(ladder, ev)
    old_verdict = bool(ladder.get("pass")) and ot != "consolidated_year_end"
    rows.append({"sym": s, "old_tier": ot, "old_pass": old_verdict,
                 "new_pass": bool(new.get("pass")), "new_na": bool(new.get("na")),
                 "new_tier": new.get("evidence_tier"), "cons": cons, "ev": ev,
                 "partial": bool(ladder.get("partial"))})

flipped = [r for r in rows if r["old_pass"] and not r["new_pass"]]
na_now = [r for r in rows if r["new_na"]]
still = [r for r in rows if r["new_pass"]]
swallowed = [r for r in rows if r["old_tier"] == "year_end_plus_interim"]
part = [r for r in rows if r["partial"]]

print("کل نمادهای دارای EPS در بانک            : %d" % len(symbols))
print("پنجرۀ EPSِ دارایِ ≥۱ اسلاتِ تلفیقی      : %d" % len(rows))
print("  در قاعدۀ کهنه «پاس» می‌گرفتند          : %d" % sum(1 for r in rows if r["old_pass"]))
print("  از این پس na + data_gap                 : %d" % len(na_now))
print("  تغییرِ حکم (پاس ← N/A)                  : %d" % len(flipped))
print("  همچنان پاس (باید ۰ باشد)                : %d" % len(still))
print("  بلعیده‌شدۀ قبلی توسط tierِ میاندوره      : %d" % len(swallowed))
print("  شعبۀ partialِ بی‌برچمِ تلفیقی (قبلی)     : %d" % len(part))
if still:
    print("\n✗ نقضِ باقی‌ماندۀ رأی ۱۳:", [r["sym"] for r in still][:20])
print("\n۱۲ ردیفِ تغییریافته:")
print("%-9s %-22s %-6s %-6s %-5s %s" % ("نماد", "tier کهنه", "کهنه", "تازه", "na", "اسلاتِ تلفیقی"))
for r in (flipped or rows)[:12]:
    print("%-9s %-22s %-6s %-6s %-5s %s" % (r["sym"], r["old_tier"], r["old_pass"],
                                            r["new_pass"], r["new_na"], ",".join(r["cons"])))
conn.close()
