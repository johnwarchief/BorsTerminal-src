# -*- coding: utf-8 -*-
# dev/market_treemap_scope_v1.py — گاردِ دامنۀِ نقشۀ بازار (مرحلۀ ۲ مأموریت 2026-10-19)
#
# دو باگِ واقعی که این گارد میخکوب می‌کند — هر دو ازِ سنجشِ زندهٔ همین پایۀ کد:
#   الف) `group=top50` (که کرکرۀِ خودِ رابط پیشنهادش می‌کند) می‌ترکید:
#      `mstat_panels._scope` دامنه را با فهرستِ None به `in_category` می‌داد،
#      در حالی که خودِ `enrich` هر ردیف را با `_top50` مُهر می‌کند. پاسخِ خطا
#      هم باِ HTTP 200 می‌آمد، پس رابط «خانه‌ای نماند» می‌گفت نه «خطا».
#   ب) شش کلیدِ معتبرِ دروازه (`stock`, `gold`, `fixed`, `lev`, `silver`,
#      `eq_funds`) درِ `TREEMAP_GROUPS` نبودند ⇒ بی‌صدا «کل بازار» (۱۰۵ نماد)
#      برمی‌گشت در حالی که برچسب همان «صندوق‌های طلا» را می‌گفت.
#
# بانک لازم ندارد: `enrich` بدل می‌شود، پس درِ CI هم سبز می‌ماند (قاعدهٔ مخزن:
# گاردی که به `market.db`ِ gitignored بشکند، گاردِ داده است نه منطق).

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as E                                    # noqa: E402
import mstat_panels as P                                    # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


def row(sym, cls, kind, top50=False, sector="ص", pct=1.0, val=10.0, cap=100.0):
    # واحدها هم‌مقیاسِ خودِ موتور: `val` ریال است (پنل بر ۱e9 تقسیم می‌کند تا
    # «میلیارد تومان» بدهد) و `vol` سهم (بر ۱e6). بی‌این، هر چهار معیار درِ
    # دقتِ `round(size, 3)` صفر می‌شد و ردیف‌ها به‌درستی ازِ نقشه بیرون می‌رفتند —
    # یعنی گارد، fixture‌اش را باِ باگِ واقعی اشتباه می‌گرفت.
    return {"symbol": sym, "ins_code": sym + "-ic", "name": sym, "cls": cls, "kind": kind,
            "sector_name": sector, "pct": pct, "p_closing": 100.0,
            "market_cap": cap * 1e9, "total_shares": 1.0, "_top50": top50,
            "_m": {"val": val * 1e9, "vol": val * 2 * 1e6,
                   "trades": int(val * 10), "has_ct": True}}


ROWS = [
    row("A", "stock", "", top50=True, val=90.0),
    row("B", "stock", "", val=80.0),
    row("C", "right", "", val=70.0),
    row("D", "fund", "equity", val=60.0),
    row("E", "fund", "fixed", val=50.0),
    row("F", "fund", "gold", val=40.0),
    row("G", "fund", "lev", val=30.0),
    row("H", "fund", "silver", val=20.0),
    row("I", "fund", "etf", val=10.0),
    row("J", "fund", "mixed", val=5.0),
]
META = {"d_even": 20261019, "h_even": 123000, "market_cap": True, "top50": 1, "n": len(ROWS)}


def main():
    print("market_treemap_scope_v1 — دامنهٔ نقشه، باِ ردیفِ ساختگی")

    # ── ۱) نگاشتِ کلید → دامنه ──
    for key, want, fell in (("gold", "gold_fund", False), ("silver", "silver_fund", False),
                            ("lev", "lev_fund", False), ("fixed", "fixed_fund", False),
                            ("stock", "stock_right", False), ("eq_funds", "eq_all", False),
                            ("top50", "top50", False), ("eq_all", "eq_all", False),
                            ("all", "all", False), ("bogus", "all", True), ("", "all", True)):
        got = P._resolve_group(key)
        ck(got == (want, fell), "نگاشتِ %r ⇒ %s%s" % (key, want, " + اعلامِ جایگزینی" if fell else ""),
           str(got))

    # ── ۲) دامنه‌ها واقعاً فیلتر می‌کنند ──
    def syms(g, ind=""):
        return [r["symbol"] for r in P._scope(ROWS, g, ind)]
    ck(syms("gold") == ["F"], "«طلا» فقط صندوقِ طلا می‌ماند (پیش از این: کلِ بازار)", str(syms("gold")))
    ck(syms("stock") == ["A", "B", "C"], "«سهام و حق تقدم» سهام+حق تقدم است", str(syms("stock")))
    ck(syms("fixed") == ["E"], "«درآمد ثابت» فقط صندوقِ ثابت", str(syms("fixed")))
    ck(syms("eq_funds") == ["A", "B", "C", "D", "I", "J"],
       "«ص.سهامی» معادلِ eq_all است", str(syms("eq_funds")))
    # «کل بازار» درِ خودِ موتور صندوقِ طلا/نقره/اهرمی را *ندارد* — آن‌ها سطرِ
    # «اوراق، اختیار و سایر» (`bonds_other`) هستند. انتظارِ «همه» اینجا غلط بود،
    # نه کد؛ همین تفاوت را صریح پین می‌کنیم تا کسی دوباره حدس نزند.
    ck(syms("all") == ["A", "B", "C", "D", "E", "I", "J"],
       "«کل بازار» = سهام+حق‌تقدم+صندوق‌های سهامی/مختلط/درآمدثابت", str(syms("all")))
    # سنجیدیم و همین را دیدیم: طلا/نقره/اهرمی درِ *هیچ‌کدام* از دو سطرِ aggregate
    # نمی‌نشینند (هم از `all` بیرون‌اند، هم از `bonds_other`). این رفتارِ خودِ
    # موتور است (`_ALL_FUND_KINDS + ("gold","silver","lev")`) و درِ
    # `docs/TA-SCOPE-DECODE.md` تعریف شده — پس پین می‌شود، قضاوت نه.
    ck(syms("bonds_other") == [] and set(syms("gold_fund")) == {"F"}
       and set(syms("lev_fund")) == {"G"},
       "طلا/نقره/اهرمی فقط ازِ دامنهٔ اختصاصیِ خودشان دیده می‌شوند",
       "bonds_other=%s" % syms("bonds_other"))
    ck(syms("bogus") == syms("all"), "کلیدِ بیگانه ⇒ کلِ بازار، نه فهرستِ خالی")
    ck(syms("all", "ص") == syms("all") and syms("all", "نexist") == [],
       "فیلترِ صنعت هم کار می‌کند و بی‌ردیف، خالی می‌دهد")

    # ── ۳) top50: همان مُهرِ خودِ موتور، بی‌ترکیدن ──
    ck(syms("top50") == ["A"], "top50 از مُهرِ `_top50`ِ خودِ enrich می‌آید", str(syms("top50")))
    try:
        E.in_category(ROWS[0], "top50", None)
        ck(False, "کنترلِ منفی: فراخوانیِ کهنه باِ None باید می‌ترکید")
    except TypeError:
        ck(True, "کنترلِ منفی: مسیرِ کهنه (None) واقعاً می‌ترکید — پس سبزِ بالا تهی نیست")

    # ── ۴) بدنهٔ پاسخ: برچسب باید دامنهٔ *اعمال‌شده* را بگوید ──
    real_enrich = E.enrich
    try:
        E.enrich = lambda conn: (ROWS, META)
        t = P.treemap(None, group="gold", metric="value")
        ck(t["status"] == "ok" and [r["symbol"] for r in t["rows"]] == ["F"],
           "پاسخِ «طلا» فقط یکِ خانه دارد", str(t.get("rows")))
        ck(t["group"] == "gold_fund" and t["group_label"] == P.TREEMAP_GROUPS["gold_fund"],
           "برچسب، دامنهٔ اعمال‌شده است نه کلیدِ خامِ درخواست",
           "%s / %s" % (t.get("group"), t.get("group_label")))
        ck(t["group_requested"] == "gold" and t["group_fallback"] is False,
           "پاسخ می‌گوید چه خواسته شد و آیا جایگزین شد یا نه")
        tb = P.treemap(None, group="not_a_group", metric="value")
        ck(tb["group"] == "all" and tb["group_fallback"] is True,
           "کلیدِ بیگانه: دامنهٔ all باِ اعلامِ صریحِ جایگزینی",
           "%s / %s" % (tb.get("group"), tb.get("group_fallback")))
        t50 = P.treemap(None, group="top50", metric="value")
        ck(t50["status"] == "ok" and t50["total_nodes"] == 1,
           "top50 درِ پاسخِ کامل هم می‌آید (پیش از این: بدنهٔ خطا)",
           "%s %s" % (t50.get("status"), str(t50.get("message"))[:60]))
        # رنگ از همان درصد می‌آید، و درصدِ غایب «بی‌داده» است نه صفر
        tp = P.treemap(None, group="all", metric="value")
        tones = {r["symbol"]: r["tone"] for r in tp["rows"]}
        ck(tones.get("A") == "pos", "درصدِ مثبت ⇒ tone مثبت", str(tones.get("A")))
        zero = [row("Z", "stock", "", pct=0.0), row("N", "stock", "", pct=None)]
        E.enrich = lambda conn: (ROWS + zero, META)
        tz = {r["symbol"]: r["tone"] for r in P.treemap(None, group="all")["rows"]}
        ck(tz.get("Z") == "zero" and tz.get("N") == "nodata",
           "صفرِ سنجیده باِ «بی‌داده» یکی نمی‌شود", "%s / %s" % (tz.get("Z"), tz.get("N")))
        # معیارِ بی‌منبع: cap درِ بانکِ بی‌ستون ⇒ no_source، نه مربعِ صفر
        E.enrich = lambda conn: (ROWS, dict(META, market_cap=False))
        tc = P.treemap(None, group="all", metric="cap")
        ck(any(n["key"] == "market_cap" for n in tc["no_source"]) and tc["total_nodes"] == 0,
           "معیارِ بی‌منبع صریح اعلام می‌شود و مربعِ صفر نمی‌سازد",
           "%s %s" % (tc["total_nodes"], tc["no_source"]))
        # ── ۵) شمارش‌ها باید باِ هم بخوانند: چیزی بی‌خبر غیب نشود ──
        tiny = [row("T1", "fund", "equity", val=0.0002), row("T2", "fund", "equity", val=0.0004)]
        # val=0.0002 ⇒ ۲۰۰٬۰۰ ریال ⇒ size=0.0002 میلیارد تومان ⇒ گردشدۀِ صفر
        E.enrich = lambda conn: (ROWS + tiny, META)
        tt = P.treemap(None, group="eq_fund", metric="value")
        # دامنهٔ eq_fund فقط صندوق‌هاست (سهام/حق‌تقدم درِ eq_all می‌آیند): D,I,J + T1,T2
        ck(tt["scope_nodes"] == 5 and tt["total_nodes"] == 3
           and tt["skipped_zerosize"] == 2 and tt["skipped_nodata"] == 0,
           "ردیفِ بی‌سطح ازِ rows بیرون می‌رود و جدا شمرده می‌شود",
           "scope=%s nodes=%s zero=%s" % (tt.get("scope_nodes"), tt.get("total_nodes"),
                                          tt.get("skipped_zerosize")))
        ck(all(r["size"] > 0 for r in tt["rows"]),
           "هیچ ردیفی باِ size صفر به چیدمان نمی‌رسد (دلیلِ غیب‌شدنِ ۱۳ صندوق)",
           str([r["size"] for r in tt["rows"] if not r["size"] > 0][:4]))
        ck(tt["shown"] + tt["skipped_nodata"] + tt["skipped_zerosize"] == tt["scope_nodes"],
           "سه شمارش باِ هم جمع می‌شوند: «چرا خانه کم است» جواب دارد",
           "%s+%s+%s != %s" % (tt["shown"], tt["skipped_nodata"],
                               tt["skipped_zerosize"], tt["scope_nodes"]))
    finally:
        E.enrich = real_enrich

    print("\nmarket_treemap_scope_v1: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
