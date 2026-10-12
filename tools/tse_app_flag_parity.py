"""پاراللِ اپ در برابرِ اجرایِ واقعیِ فیلترهایِ سایت (نام‌به‌نام).

مرجع = `_audit/tse_saved_filter_eval.json` که `tools/tse_saved_filter_eval.mjs`
می‌سازد: همان `PrepareFilterCode` و همان `try/eval/catch` سایت رویِ باندهایِ خامِ
خودش. این ابزار همان مرجع را با پرچم‌هایِ `/api/market` (یعنی
`tape_flags.apply_tape_flags` رویِ قابِ واقعیِ تابلو) می‌سنجد و اختلاف را درِ
سطحِ نامِ نماد می‌شمارد — نه با سبز شدنِ تست‌ها.

اجرا:
  PYTHONIOENCODING=utf-8 python tools/tse_app_flag_parity.py [--db market.db]
"""
import argparse
import io
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
# ابزار درِ tools/ است؛ ریشۀ ریپو لازم است تا `api.market` و `tape_flags`ِ
# همان اپ (نه یک نسخۀ دوم) بارگذاری شوند.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NAME = {"clock": "f_clock", "susp": "f_susp", "jet": "f_jet", "roobi": "f_roobi",
        "noqteh": "f_noqteh", "smart": "f_smart", "legal": "f_legal"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="_audit/market_copy_slots3.db")
    ap.add_argument("--ref", default="_audit/tse_saved_filter_eval.json")
    ap.add_argument("--out", default="_audit/tse_app_flag_parity.json")
    a = ap.parse_args()

    import api._core as C
    import api.market as M

    ref = json.load(io.open(a.ref, encoding="utf-8"))
    # بانکِ **کپی**: مسیر درِ `api._core` را عوض می‌کنیم تا `_build_market_response`
    # همان زنجیرۀ منتشرشده (کوئری + مشتقات + پرچم‌ها) رویِ همین بانک بدود؛
    # نیمه‌اش را درِ این ابزار بازنویسی نمی‌کنیم، وگرنه سنجش مدرکِ خودِ اپ نیست.
    C.DB_PATH = a.db
    M.get_db = C.get_db

    class _Req:
        headers = {}

    body = json.loads(M._build_market_response(_Req(), drop_unused=False,
                                                store_cache=False).body)
    rows = body.get("data") or body.get("rows") or []
    if not rows:
        raise SystemExit(f"بدنهٔ /api/market خالی بود: {list(body)[:6]}")
    df = __import__("pandas").DataFrame(rows)
    codes = {str(c): s for c, s in zip(df["ins_code"], df["symbol"])}
    print(f"قابِ تابلو: {len(df):,} ردیف | [is6] دار: {int(df['is6'].notna().sum()) if 'is6' in df else 0:,}"
          f" | زنده: {int(df['is_live'].sum()) if 'is_live' in df else -1:,}")

    # ── آمادگیِ داده پیش از هر ادعایِ تطبیق (رأیِ مالک ۱۴۵-۰۷-۲۱، بند ۲) ──
    # بی‌این، پنجرۀ کهنه یا نبودِ `tse_inst_stat` داوری را خاموش می‌کرد و
    # «اختلافِ صفر» هم ازِ آن درمی‌آمد (ردیفِ بی‌پنجره ⇒ پرچم False ⇒ با مرجعِ
    # بی‌همان ردیف یکی به‌نظر می‌رسید). پس اول سنسور، بعد مقایسه.
    ready = []
    conn = sqlite3.connect(a.db)
    try:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t, minimum in (("tape_ih_slot", 60_000), ("tse_inst_stat", 1)):
            if t not in have:
                ready.append(f"جدولِ {t} درِ این بانک نیست — مسیرِ کهنه جاری است")
                continue
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n < minimum:
                ready.append(f"{t} فقط {n:,} ردیف دارد (کفِ لازم: {minimum:,})")
        max_slot = (conn.execute("SELECT MAX(slot) FROM tape_ih_slot").fetchone()[0]
                    if "tape_ih_slot" in have else None)
        if max_slot is not None and max_slot < 29:
            ready.append(f"بیشینۀ اسلاتِ [ih] فقط {max_slot} است — پنجرۀ سی‌تایی کامل نیست")
    finally:
        conn.close()
    if not df.columns.size or "is6" not in df.columns:
        ready.append("ستونِ is6 درِ بدنهٔ تابلو نیست — «پول هوشمند/کدبه‌کد» بی‌مبناء می‌مانند")
    n_is6 = int(df["is6"].notna().sum()) if "is6" in df.columns else 0
    if n_is6 == 0:
        ready.append("هیچ ردیفی [is6] ندارد — سینکِ InstValue هرگز ننوشته")
    # رأیِ بند ۱: «زنده‌بودن» حقِ ندارد نمادی را که سایت واجد می‌داند رد کند.
    try:
        payload = json.load(io.open("_audit/tse_cache_mw_rows.json", encoding="utf-8"))
        published = {str(x.get("insCode")) for x in payload}
        live = {str(r["ins_code"]) for r in rows if r.get("is_live") is True}
        suppressed = {c for c in published if c in codes and c not in live}
        print(f"باندِ سایت={len(published):,} | از آن‌ها در تابلویِ ما غیرزنده: {len(suppressed):,}")
        if suppressed:
            ready.append("چند نمادِ منتشرشدهٔ سایت درِ ما غیرزنده است و داوری‌اش "
                         "نمایش داده نمی‌شود: " + ", ".join(codes.get(c, c) for c in sorted(suppressed)[:8]))
    except OSError:
        print("[warn] باندِ مرجع (`_audit/tse_cache_mw_rows.json`) نیست — "
              "قیدِ «زنده‌بودن» سنجیده نشد")
    if ready:
        for line in ready:
            print("DATA-NOT-READY:", line)
        raise SystemExit("پیش از اعلامِ تطبیق، دادهٔ لازمِ این مسیر آماده نیست.")

    lines = []
    for k, col in NAME.items():
        want = set((ref["codes"].get(k) or "").split())
        # پرچم از همان بدنه‌ای خوانده می‌شود که رویِ سیم می‌رود؛ دوباره
        # حساب‌کردنش درِ این ابزار مدرکِ مسیرِ منتشرشده نمی‌داد.
        got = {str(r["ins_code"]) for r in rows if r.get(col) is True}
        inter = want & got
        only_app, only_ref = sorted(got - want), sorted(want - got)
        lines.append({"filter": k, "app_col": col, "ref_n": len(want), "app_n": len(got),
                      "shared": len(inter), "only_app": only_app, "only_ref": only_ref})
        print(f"{k:7s} مرجع={len(want):4d} اپ={len(got):4d} مشترک={len(inter):4d}"
              f" فقط‌اپ={len(only_app):3d} فقط‌سایت={len(only_ref):3d}")
        if only_app:
            print("      فقط‌اپ:", ", ".join(codes.get(x, x) for x in only_app[:8]))
        if only_ref:
            print("      فقط‌سایت:", ", ".join(codes.get(x, x) for x in only_ref[:8]))
    diff = sum(len(x["only_app"]) + len(x["only_ref"]) for x in lines)
    print(f"\nجمعِ اختلاف‌هایِ نامی درِ هفت فیلتر: {diff}")
    with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
        json.dump({"db": a.db, "ref": a.ref, "board_rows": len(df),
                   "rows_with_is6": int(df["is6"].notna().sum()) if "is6" in df else 0,
                   "total_name_diffs": diff, "filters": lines},
                  fh, ensure_ascii=False, indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
