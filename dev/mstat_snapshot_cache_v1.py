"""MSTAT-SNAP-CACHE v1 — گاردِ کشِ اسنپ‌شاتِ مشترک (PERF-S3)

`mstat_engine.load_snapshot()` پیش از این روی «خودِ شیء اتصال» قفل بود و چون
`api/_core.get_db()` برای هر درخواست اتصالِ تازه می‌سازد، درِ HTTP هرگز به کش
نمی‌رسید: هر پنلِ «وضعیت بازار» اسکنِ کاملِ بانک را می‌دوخت (سنجش: 304ms × 12
پنل در یک بازِ تب = 6.4s CPU). حالا کشِ سطح‌پروسه با کلیدِ
(آدرسِ فایل بانک، امضایِ داده، revision) هست و ردیف‌ها میانِ درخواست‌ها مشترک
می‌شوند — پس سه چیز باید ثابت بماند:

  ۱) هیچ پنلی روی ردیفِ اسنپ‌شات نمی‌نویسد (اشتراکِ بدونِ آلودگی).
  ۲) نوشتنِ تازه ⇒ اسنپ‌شاتِ تازه؛ عددِ کهنه سرو نمی‌شود.
  ۳) دو فایلِ بانکِ مختلف با محتوای یکسان هرگز یکی نشمرده می‌شوند
     (همان نقصی که قفلِ «هویتِ اتصال» برایش گذاشته شده بود).

بانک آزمون کپیِ کوچکی از market.db واقعی است (سه‌صدِ نماد، ATTACH read-only)؛
market.db کاری هرگز نوشته نمی‌شود.

usage: python dev/mstat_snapshot_cache_v1.py
"""
import os
import shutil
import sqlite3
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(REPO)
sys.path.insert(0, REPO)
os.chdir(REPO)

SRC_DB = os.path.join(REPO, "market.db")
TABLES = ("market_watch", "instruments", "client_type", "client_type_value",
          "daily_prices", "price_history", "mstat_snap")

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def build_tiny_db(path):
    """کپیِ خواندنی-کوچکِ بانکِ کاری، با همان ستون‌ها و انواعِ داده."""
    con = sqlite3.connect("file:" + path.replace("\\", "/"), uri=True, timeout=30)
    con.execute("ATTACH DATABASE ? AS ro",
                ("file:" + SRC_DB.replace("\\", "/") + "?mode=ro",))
    kept = {}
    codes = [r[0] for r in con.execute("SELECT ins_code FROM ro.market_watch LIMIT 300")]
    if not codes:
        raise SystemExit("market.db در دسترس نیست — گارد بدونِ بانک نمی‌دود")
    qmarks = ",".join("?" * len(codes))
    for t in TABLES:
        try:
            cols = [r[1] for r in con.execute("PRAGMA ro.table_info(%s)" % t)]
        except sqlite3.Error:
            continue
        if not cols:
            continue
        pick = "ins_code" if "ins_code" in cols else ("symbol" if "symbol" in cols else None)
        where = "WHERE %s IN (%s)" % (pick, qmarks) if pick else ""
        con.execute("CREATE TABLE %s (%s)" % (t, ", ".join('"%s"' % c for c in cols)))
        con.execute("INSERT INTO %s SELECT %s FROM ro.%s %s" %
                    (t, ", ".join('"%s"' % c for c in cols), t, where), codes if where else [])
        kept[t] = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    con.commit()
    con.close()
    return kept


def new_conn(path):
    """اتصالِ تازه، دقیقاً مثلِ هرِ درخواستِ HTTP (بدونِ هیچِ کشِ اتحالی)."""
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def main():
    if not os.path.exists(SRC_DB):
        print("SKIP: market.db پیدا نشد")
        return 0
    tmp = tempfile.mkdtemp(prefix="bors_snapguard_")
    a = os.path.join(tmp, "market_a.db")
    b = os.path.join(tmp, "market_b.db")
    try:
        kept = build_tiny_db(a)
        shutil.copy2(a, b)
        print("tiny bank rows:", ", ".join("%s=%s" % kv for kv in kept.items() if kv[1]))

        import mstat_engine as E
        import mstat_panels as P

        conn = new_conn(a)
        rows1, meta1 = E.enrich(conn)
        rows2, meta2 = E.enrich(conn)
        ck("enrich دو‌بار در یکِ اتصال یکِ نتیجه می‌دهد (نه دو‌بار محاسبه)",
           rows1 is rows2 and meta1["n"] == meta2["n"], "n=%s" % meta1["n"])

        # ---- ۱) هیچ پنلی روی ردیفِ مشترک نمی‌نویسد
        before = [{k: v for k, v in r.items()} for r in rows1]
        ids = [id(r) for r in rows1]
        panels = [
            ("summary", lambda: E.summary(conn)),
            ("thermometer", lambda: E.thermometer(conn, "eq_all")),
            ("histogram", lambda: E.histogram(conn, "eq_all")),
            ("depth", lambda: E.depth(conn, "eq_all")),
            ("client_split", lambda: E.client_split(conn, "all")),
            ("mainwatch", lambda: E.mainwatch(conn, "eq_all", "", "clock", True, 20)),
            ("industries", lambda: E.industries(conn)),
            ("smart_money", lambda: E.smart_money(conn)),
            ("phases", lambda: E.phases(conn)),
            ("treemap", lambda: P.treemap(conn, "eq_all", "", "value", 60)),
            ("tops", lambda: P.tops(conn, "eq_all", 5)),
            ("orderflows", lambda: P.order_book_flows(conn, "eq_all", 10)),
            ("ownership", lambda: P.ownership_change(conn, "eq_all", 10)),
            ("gold", lambda: P.gold_market(conn, 30)),
        ]
        ran, errors = 0, []
        for name, fn in panels:
            try:
                out = fn()
                ran += 1
                if isinstance(out, dict) and out.get("status") == "error":
                    errors.append("%s: %s" % (name, out.get("message")))
            except Exception as e:                            # noqa: BLE001
                errors.append("%s raised %s: %s" % (name, type(e).__name__, e))
        ck("همۀ پنل‌ها بی‌خطا اجرا می‌شوند", not errors, "; ".join(errors)[:220])
        after = [{k: v for k, v in r.items()} for r in rows1]
        touched = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
        ck("ردیف‌هایِ اسنپ‌شات پس ازِ پنزدهِ پنل دست‌نخورده‌اند (اشتراکِ بی‌آلودگی)",
           not touched, "%d ردیف عوض شد" % len(touched))
        ck("هویتِ ردیف‌ها همانِ شیءِ مشترک ماند (کپیِ پنهان ساخته نشد)",
           [id(r) for r in rows1] == ids)
        conn.close()

        # ---- ۲) دو فایلِ بانک با محتوای یکسان نباید یکی شوند (پیش ازِ نوشتن:
        #        نوشتن رویِ A امضا را عوض می‌کند و شرطِ «امضایِ یکسان» می‌سوزد)
        c3 = new_conn(a)
        c4 = new_conn(b)
        sig_a = E._signature(c3)
        sig_b = E._signature(c4)
        s_a = E.load_snapshot(c3)
        s_b = E.load_snapshot(c4)
        ck("امضایِ دوِ بانکِ کپی‌شده واقعاً یکسان است (تستِ درستِ شرط)", sig_a == sig_b, str(sig_a))
        ck("بانکِ B با وجودِ امضایِ یکسان، اسنپ‌شاتِ بانکِ A را نمی‌گیرد",
           s_a is not s_b and E._db_identity(c3) != E._db_identity(c4),
           "%s vs %s" % (os.path.basename(E._db_identity(c3)), os.path.basename(E._db_identity(c4))))
        c5 = new_conn(a)
        ck("اتصالِ تازه روی همانِ بانک و همانِ حالت ⇒ اسنپ‌شاتِ مشترک (بی‌اسکنِ دوباره)",
           E.load_snapshot(c5) is E.load_snapshot(c5))
        c3.close(); c4.close(); c5.close()

        # ---- ۳) نوشتن ⇒ اسنپ‌شاتِ تازه؛ عددِ کهنه سرو نمی‌شود
        w = new_conn(a)
        # ردیفی که واقعاً داخلِ اسنپ‌شات است (همانِ روزِ بیشینه) — وگرنه «نیست»
        # با «کهنه» اشتباه خوانده می‌شود
        row_day = w.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
        sym_row = w.execute("SELECT ins_code, p_last FROM market_watch "
                            "WHERE d_even = ? AND p_last IS NOT NULL LIMIT 1", (row_day,)).fetchone()
        ic, old_last = sym_row[0], sym_row[1]
        want = float(old_last) + 77.0
        snap_before = E.load_snapshot(w)
        w.execute("UPDATE market_watch SET p_last = ?, fetched_at = ? WHERE ins_code = ?",
                  (want, "9999-12-31 23:59:59", ic))
        w.commit()
        w.close()
        c2 = new_conn(a)
        snap_after = E.load_snapshot(c2)
        rows_after, _m = E.enrich(c2)
        got = next((r["p_last"] for r in rows_after if r["ins_code"] == ic), None)
        ck("کشِ اسنپ‌شات با نوشتنِ تازه باطل می‌شود (شیءِ تازه)", snap_after is not snap_before)
        ck("عددِ تازه سرو می‌شود، نه قیمتِ کهنه",
           got is not None and abs(float(got) - want) < 1e-6, "%s ← %s" % (got, old_last))
        c2.close()

        # ---- ۴) force=True باید حتماً دوباره بخواند
        c6 = new_conn(a)
        ck("load_snapshot(force=True) اسنپ‌شاتِ تازه می‌سازد",
           E.load_snapshot(c6, force=True) is not E.load_snapshot(c6, force=True))
        c6.close()

        ok = all(CHECKS)
        print("\n%d بررسی، %d سبز، %d سرخ" % (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
        print("MSTAT-SNAP-CACHE: " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
