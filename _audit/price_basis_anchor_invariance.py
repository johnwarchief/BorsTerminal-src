# -*- coding: utf-8 -*-
"""قدمِ ۳/۴ — سنجشِ زنده: عوض‌شدنِ Price Source لنگرِ تعدیل را تکان نمی‌دهد.

قرارداد §۱-ث تضمینِ ۴: «با تغییرِ setting تعدادِ رویدادِ تعدیل و مقدارِ ضرایب باید
بیت‌به‌بیت یکسان بماند». این فایل همان را رویِ پنج نماد و دو حالتِ setting اندازه
می‌گیرد؛ هیچ عددی استدلال نیست.

دو مسیر سنجیده می‌شود:
  الف) `/api/chart` (CDN، کامل‌ترین سازندۀ کندل و تنها مسیری که رویدادِ تعدیل دارد)
  ب) `/api/chart-db` (بانکِ محلی؛ رویِ کپیِ market.db، با ردیف‌هایی که قدمِ ۲
     ستونِ last/value را از CSV پر کرده)

برایِ هر نماد گزارش می‌شود: تعدادِ رویدادها و امضایِ ratios تحتِ دو مبنای، تعدادِ
کندل‌هایی که closeِ نمایشی‌شان عوض می‌شود، و تعدادِ کندل‌هایی که last ندارند
(سری‌هایِ fallback). مسیرِ نوشتن هیچ‌جا بانکِ واقعی نیست: کپیِ mtime-محور.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import price_basis  # noqa: E402
import test_tsetmc as T  # noqa: E402
import bors_config  # noqa: E402

SRC_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042"),
        ("خودرو", "65883838195688438")]


def snapshot(res):
    """امضایِ لنگر: رویدادها + ضرایب. چیزی که نباید با setting عوض شود.

    `degraded` و `adjustSource` هم ثبت می‌شوند: اجرای اولِ این سنجش به‌خاطرِ
    ConnectTimeout درِ cdn.tsetmc.com برایِ هر پنج نماد به بانکِ محلی سقوط کرد و
    `all_events_equal: true` با صفرِ رویداد برگرداند — یعنی سبزیِ بی‌محتوا. حالا
    فقط ردیفی «verified» شمرده می‌شود که واقعاً از CDN آمده باشد و رویداد داشته باشد.
    """
    return {"events": [(e["date"], round(float(e["ratio"]), 10)) for e in res.get("adjustEvents") or []],
            "factors": [(f["time"], round(float(f["factor"]), 10)) for f in res.get("factors") or []],
            "adjustSource": res.get("adjustSource"), "degraded": bool(res.get("degraded"))}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cdn_only = "--cdn-only" in argv
    if "--symbols" in argv:
        want = argv[argv.index("--symbols") + 1].split(",")
        globals()["SYMS"] = [s for s in SYMS if s[0] in want] or SYMS
    work = tempfile.mkdtemp(prefix="pb_inv_")
    bors_config.PRICE_BASIS_PATH = os.path.join(work, "price_basis.json")
    price_basis._cache["sig"] = None
    out = {"symbols": {}, "cdn": {}, "notes": []}

    # ── الف) مسیرِ CDN ───────────────────────────────────────────────────────
    import api.chart as CH
    for name, ins in SYMS:
        CH.CDN_OFFLINE_UNTIL = 0.0
        CH.CHART_CACHE.pop(name, None)
        price_basis.set_basis("closing")
        r_c = CH.get_chart_tsetmc(name)
        sn_c = snapshot(r_c)
        price_basis.set_basis("last")
        r_l = CH.get_chart_tsetmc(name)
        sn_l = snapshot(r_l)
        if r_l.get("status") != "success":
            out["cdn"][name] = {"status": r_l.get("status"), "message": r_l.get("message")}
            continue
        cl_c = {c["time"]: (c["close"], c["closing"], c.get("last"),
                            c["high"], c["low"]) for c in r_c.get("candles") or []}
        cl_l = {c["time"]: (c["close"], c["closing"], c.get("last"),
                            c["high"], c["low"]) for c in r_l.get("candles") or []}
        common = set(cl_c) & set(cl_l)
        flip = [t for t in common if cl_c[t][0] != cl_l[t][0]]
        missing = [t for t in cl_l if cl_l[t][2] in (None, 0)]
        geom = sum(1 for t in common if cl_l[t][3:5] != cl_c[t][3:5])
        out["cdn"][name] = {
            "basis_applied_last_mode": r_l.get("priceBasis"),
            "basis_applied_closing_mode": r_c.get("priceBasis"),
            "candles": len(common),
            "from_cdn": not r_l.get("degraded") and bool(sn_l["events"] or sn_l["factors"]),
            "anchor_events_equal": sn_c["events"] == sn_l["events"],
            "anchor_factors_equal": sn_c["factors"] == sn_l["factors"],
            "adjust_events": len(sn_c["events"]),
            "adjust_events_equal_count": len(sn_l["events"]) == len(sn_c["events"]),
            "adjustSource_equal": sn_c["adjustSource"] == sn_l["adjustSource"],
            "adjustSource": sn_c["adjustSource"],
            "display_close_flips": len(flip),
            "display_close_flip_pct": round(100.0 * len(flip) / len(common), 2) if common else None,
            "closes_equal_under_both_for_closing_col": all(
                cl_l[t][1] == cl_c[t][1] for t in common),
            "last_missing_candles": len(missing),
            "wicks_widened_by_basis": geom,
            "reason_last_mode": r_l.get("priceBasisReason"),
            "sample_flip": (flip[0], cl_c[flip[0]][0], cl_l[flip[0]][0]) if flip else None,
        }
        print(json.dumps({"cdn/" + name: out["cdn"][name]}, ensure_ascii=False)[:900])

    # ── ب) مسیرِ بانکِ محلی (کپی) ────────────────────────────────────────────
    if cdn_only:
        out["notes"].append("بخشِ بانکِ محلی (--cdn-only) اجرا نشد")
        _verdict(out, work)
        return
    copy = os.path.join(work, "market_copy.db")
    a = sqlite3.connect(SRC_DB, timeout=60)
    b = sqlite3.connect(copy)
    with b:
        a.backup(b)
    a.close(); b.close()
    import api._core as CORE
    for mod in (CH, CORE, T):
        mod.DB_PATH = copy
    import mstat_engine
    cn = sqlite3.connect(copy)
    mstat_engine.ensure_schema(cn)
    cn.close()
    for name, ins in SYMS:
        T.fetch_price_history(name, since="2026-08-01")   # last/value را از CSV پر می‌کند
        price_basis.set_basis("closing")
        r_c = CH.get_chart_db(name)
        sn_c = snapshot(r_c)
        price_basis.set_basis("last")
        r_l = CH.get_chart_db(name)
        sn_l = snapshot(r_l)
        cl_c = {c["time"]: (c["close"], c["closing"], c.get("last"))
                for c in r_c.get("candles") or []}
        cl_l = {c["time"]: (c["close"], c["closing"], c.get("last"))
                for c in r_l.get("candles") or []}
        fresh = [t for t in cl_l if cl_l[t][2] is not None]
        flip = [t for t in set(cl_c) & set(cl_l) if cl_c[t][0] != cl_l[t][0]]
        out["symbols"][name] = {
            "candles": len(cl_l),
            "rows_with_last": len(fresh),
            "basis_applied": r_l.get("priceBasis"),
            "reason": r_l.get("priceBasisReason"),
            "anchor_events_equal": sn_c["events"] == sn_l["events"],
            "anchor_factors_equal": sn_c["factors"] == sn_l["factors"],
            "adjust_events": len(sn_c["events"]),
            "display_close_flips": len(flip),
            "closing_identical": all(cl_l[t][1] == cl_c[t][1] for t in cl_l),
            "sample_flip": (flip[0], cl_c[flip[0]][0], cl_l[flip[0]][0]) if flip else None,
        }
        print(json.dumps({"db/" + name: out["symbols"][name]}, ensure_ascii=False)[:700])
    _verdict(out, work)


def _verdict(out, work):
    for k in ("cdn", "symbols"):
        vals = [v for v in out.get(k, {}).values() if "anchor_events_equal" in v]
        if not vals:
            continue
        live = [v for v in vals if k == "symbols" or v.get("from_cdn")]
        out.setdefault("verdict", {})[k] = {
            "checked": len(vals),
            "counted": len(live),
            "all_events_equal": all(v["anchor_events_equal"] for v in live) if live else None,
            "all_factors_equal": all(v["anchor_factors_equal"] for v in live) if live else None,
            "all_adjustSource_equal": all(v.get("adjustSource_equal", True) for v in live) if live else None,
            "total_adjust_events": sum(v.get("adjust_events", 0) for v in live),
            "candles": sum(v.get("candles", 0) or 0 for v in live),
            "close_flips": sum(v.get("display_close_flips", 0) or 0 for v in live),
            # سنجشِ لنگر فقط وقتی معنادار است که رویدادِ تعدیل رویِ میز باشد و
            # مبنایِ منتخب هم دستِ کم یکِ کندل را جابه‌جا کند؛ وگرنه «true» بی‌محتواست.
            "leg_meaningful": bool(live) and sum(v.get("adjust_events", 0) for v in live) > 0
                              and sum(v.get("display_close_flips", 0) for v in live) > 0,
        }
    vacuous = [k for k in out.get("verdict", {})
               if isinstance(out["verdict"][k], dict) and out["verdict"][k].get("counted")
               and not out["verdict"][k].get("leg_meaningful")]
    if vacuous:
        out["verdict"]["warning"] = ("پایۀ %s سنجیدنی نبود (بی‌رویداد یا بی‌جابه‌جاییِ close)؛ "
                                     "بی‌تغیریِ لنگر رویِ آن اثبات نشده" % ",".join(vacuous))
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "_audit", "price_basis_anchor_invariance.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nVerdict:", json.dumps(out.get("verdict", {}), ensure_ascii=False))
    if vacuous:
        print("  ⚠ " + out["verdict"]["warning"])
    shutil.rmtree(work, ignore_errors=True)
    print("نوشته شد:", p)


if __name__ == "__main__":
    main()
