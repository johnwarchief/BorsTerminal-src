# یک‌بارمصرف — اثباتِ عددی: درِ جمعِ تکراری‌ها هیچِ ردیفِ عدددار/باکیفیتی صرفاً به‌خاطرِ
# period_endِ جدیدتر حذف نشد؛ بازمانده در هر گروه کامل‌ترینِ ردیف است.
# مقایسه: اسنپ‌شاتِ قبلِ جمع ← market.db فعلی.
import json
import sqlite3
import sys

sys.path.insert(0, r"C:\Users\PCMOD\Desktop\BorsTerminal")
import fts_engine as FE  # noqa: E402  (FS_NUMBER_KEYS/MS_NUMBER_KEYS = تک‌منبعِ کامل‌بودن)

PRE = r"C:/Users/PCMOD/AppData/Local/Temp/market_pre_dupcollapse_2iboln_j/market.db.snapshot"
PRE0 = r"C:/Users/PCMOD/AppData/Local/Temp/market_pre_collapse_tfubvs5r/market.db.snapshot"
POST = r"C:/Users/PCMOD/Desktop/BorsTerminal/market.db"
TABLES = (("financial_statements", FE.FS_NUMBER_KEYS), ("monthly_sales", FE.MS_NUMBER_KEYS))


def load(path):
    """{(table, symbol, period_end): (n_rows, n_numeric_filled, max_tracing)}"""
    c = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    out = {}
    for table, keys in TABLES:
        exprs = " + ".join('CASE WHEN "%s" IS NOT NULL THEN 1 ELSE 0 END' % k for k in keys)
        for sym, pe, n, filled, tn in c.execute(
                'SELECT symbol, period_end, COUNT(*), COALESCE(SUM(%s),0), MAX(tracing_no)'
                ' FROM "%s" WHERE period_end GLOB "[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]"'
                ' GROUP BY symbol, period_end' % (exprs, table)):
            out[(table, sym, pe)] = (n, filled, tn)
    c.close()
    return out


def main():
    pre, post = load(PRE), load(POST)
    dups = {k: v for k, v in pre.items() if v[0] > 1}
    print("گروهِ (نماد، دوره) پیش/پس از جمع: %d / %d" % (len(pre), len(post)))
    print("گروهِ چندردیفیِ پیش از جمع: %d" % len(dups))
    lost_key, less, same, more, removed = [], [], 0, [], 0
    for k, (n, filled, tn) in dups.items():
        if k not in post:
            lost_key.append(k)
            continue
        pn, pf, ptn = post[k]
        removed += n - pn
        if pf < filled:
            less.append((k, n, filled, pn, pf))
        elif pf == filled:
            same += 1
        else:
            more.append((k, n, filled, pn, pf))
    print("\n۱) کلیدِ گروهی کاملاً حذف شد (باید ۰): %d" % len(lost_key))
    for k in lost_key[:20]:
        print("    ", k, pre[k])
    print("۲) بازمانده عددِ کمتری دارد = ردیفِ عدددار رفت (باید ۰): %d" % len(less))
    for row in less[:20]:
        print("    ", row)
    print("۳) بازمانده عددِ بیشتری دارد (اصلاحِ به‌سود): %d" % len(more))
    for row in more[:20]:
        print("    ", row)
    print("۴) تعدادِ عددِ برابر (تعویضِ بی‌ضرر/یکسان): %d" % same)
    print("\nردیفِ حذف‌شده در گروه‌هایِ dated: %d" % removed)
    c1, c2 = sqlite3.connect("file:%s?mode=ro" % PRE, uri=True), \
             sqlite3.connect("file:%s?mode=ro" % POST, uri=True)
    for table, keys in TABLES:
        exprs = " + ".join('CASE WHEN "%s" IS NOT NULL THEN 1 ELSE 0 END' % k for k in keys)
        tot1, num1 = c1.execute('SELECT COUNT(*), COALESCE(SUM(%s),0) FROM "%s"' % (exprs, table)).fetchone()
        tot2, num2 = c2.execute('SELECT COUNT(*), COALESCE(SUM(%s),0) FROM "%s"' % (exprs, table)).fetchone()
        print("۵) %s: ردیف %d→%d (تفاوت %d) | ستونِ عددیِ پُرشده %d→%d (تفاوت %+d)"
              % (table, tot1, tot2, tot2 - tot1, num1, num2, num2 - num1))
    c1.close(); c2.close()
    json.dump({"groups_pre": len(pre), "groups_post": len(post), "dup_groups": len(dups),
               "lost_key": [list(x) for x in lost_key],
               "less": [[list(x[0]), *x[1:]] for x in less],
               "more": [[list(x[0]), *x[1:]] for x in more],
               "same": same, "removed_rows": removed},
              open(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\dup_collapse_verify.json",
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
