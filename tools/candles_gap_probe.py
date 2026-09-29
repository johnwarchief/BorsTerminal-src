"""candles_gap_probe.py — پیش‌وپسِ «کندل‌های عقب» رویِ همان نشانیِ زنده

«پیش» باید پیش ازِ ریلیز گرفته شود و «پس» پس ازِ نصبِ دلتا؛ مقایسه فقط با
خودِ این دو خروجیِ JSON معنا دارد. سه چیز را می‌سنجد:
  ۱) آخرینِ ۱۲ نشستِ `/api/chart-db/<نماد>` (همان که چارتِ محلی می‌خواند)
  ۲) آخرینِ تاریخِ `/api/chart/<نماد>` (CSVِ CDN — مرجعِ完整性)
  ۳) خودِ جدولِ `price_history` درِ بانکِ هدف + شمارِ ردیف‌هایِ بی‌هندسه
خواندنیِ محض است؛ هیچ چیزی نمی‌نویسد.

اجرا:  python tools/candles_gap_probe.py [--symbol فولاد] [--base http://127.0.0.1:8001]
                                        [--db "C:\\...\\market.db"]
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request


def get_json(base, path):
    try:
        req = urllib.request.Request(base + urllib.parse.quote(path, safe="/"),
                                     headers={"User-Agent": "BorsTerminal-probe"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as e:      # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="فولاد")
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    out = {"symbol": args.symbol, "base": args.base}
    v, err = get_json(args.base, "/api/update/version")
    out["app_version"] = (v or {}).get("version") if v else err

    d, err = get_json(args.base, "/api/chart-db/" + args.symbol)
    if d:
        cs = d.get("candles") or []
        out["chart_db"] = {
            "count": d.get("count"), "n": len(cs),
            "last_dates": [c.get("time") for c in cs[-12:]],
            "last": cs[-1] if cs else None,
            "liveInjected": d.get("liveInjected"), "degraded": d.get("degraded"),
            "fts": d.get("fts"),
        }
        # فاصله‌ها: چند روزِ میانی غایب است — «کندل‌ها عقبند» دقیقاً همین
        ds = sorted({c.get("time") for c in cs if c.get("time")})
        gaps = []
        import datetime as dt
        prev = None
        for x in ds[-40:]:
            try:
                cur = dt.date.fromisoformat(x)
            except Exception:
                continue
            if prev and (cur - prev).days > 3:
                gaps.append("%s → %s: %d روز" % (prev.isoformat(), x,
                                                 (cur - prev).days))
            prev = cur
        out["chart_db"]["gaps_last40"] = gaps
    else:
        out["chart_db"] = err

    d, err = get_json(args.base, "/api/chart/" + args.symbol)
    if d:
        # پاسخِ CDN newest-first است؛ برایِ مقایسه باید مرتب شود
        cs = sorted(d.get("candles") or [], key=lambda c: c.get("time") or "")
        out["chart_cdn"] = {"count": d.get("count"), "n": len(cs),
                            "last_dates": [c.get("time") for c in cs[-6:]],
                            "last": cs[-1] if cs else None,
                            "adjustEvents": len(d.get("adjustEvents") or [])}
    else:
        out["chart_cdn"] = err

    db = args.db or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                                 "BorsTerminal Ultimate", "market.db")
    if os.path.exists(db):
        try:
            c = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
            rows = c.execute("SELECT date,open,high,low,close,volume FROM price_history "
                             "WHERE symbol=? ORDER BY date DESC LIMIT 12",
                             (args.symbol,)).fetchall()
            out["price_history"] = {
                "db": db, "rows_last12": [r[0] for r in rows],
                "newest": rows[0] if rows else None,
                "max_date": c.execute("SELECT MAX(date) FROM price_history").fetchone()[0],
                "total": c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
                "bad_geometry": c.execute(
                    "SELECT COUNT(*) FROM price_history WHERE open>0 AND close>0 AND ("
                    "COALESCE(high,0) < MAX(open,close) OR COALESCE(low,0)=0 OR "
                    "COALESCE(low,999999999999) > MIN(open,close) OR "
                    "COALESCE(high,0)<=0)").fetchone()[0],
                "symbols_today": c.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM price_history WHERE "
                    "date=(SELECT MAX(date) FROM price_history)").fetchone()[0],
                "board_newest": str(c.execute("SELECT MAX(d_even) FROM daily_prices")
                                    .fetchone()[0]),
            }
            c.close()
        except Exception as e:      # noqa: BLE001
            out["price_history"] = f"{type(e).__name__}: {e}"
    else:
        out["price_history"] = "no db at " + db

    print(json.dumps(out, ensure_ascii=False, indent=1))
    io.open(os.path.join("_audit", "candles_gap_%s.json" %
                         (out.get("app_version") or "unknown")), "w",
            encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
