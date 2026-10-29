#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/test_fts_sector_v11.py — صنایعِ دستوریِ شاخص ۵ = همان سه صنعتِ جزوه.

حکمِ مالک (Task 8): فهرستِ الزامیِ قیمت‌گذاریِ دستوری فقط خودرو/قطعات،
نیروگاه (تولید/عرضه/توزیع برق) و لاستیک است. قند و شکر، شوینده و بیمه الزامی
نیستند؛ دارو و غذا مجازند (نه الزامی). بیمه یک وتویِ سختِ جداگانه است و از
فهرستِ دستوری حذف نمی‌شود — فقط جایش عوض می‌شود.

هستهٔ آزمون بدونِ دیتابیس اجرا می‌شود: sector_filter/pricing_mode/is_insurance_sector
خالص‌اند و risk_gates هم با conn=None (شاخه‌های تعلیق در try/except) قابلِ سنجش است.
اگر market.db روی ماشین باشد، scan_symbol هم روی همان بانک **فقط‌خواندنی** با
reject_insurance روشن/خاموش سنجیده می‌شود؛ نبودنش SKIP است، نه شکست.

اجرا:  python dev/test_fts_sector_v11.py
خروج: ۰ اگر همه درست، ۱ اگر حتی یک بررسی شکست بخورد.
"""
import json
import os
import sqlite3
import sys
import tempfile

try:                       # پیام‌های فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bors_config                                          # noqa: E402
import fts_engine as F                                       # noqa: E402
from api import fundamental as FD                            # noqa: E402
from api import market as M                                  # noqa: E402

PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


EXPECTED = ["خودرو", "نیروگاه", "لاستیک"]
INSURANCE_SECTOR = "بيمه وصندوق بازنشستگي به جزتامين اجتماعي"

# نام‌هایِ واقعیِ TSETMC (با ي/ك عربی) — همان چیزی که در instruments هست.
MANDATORY_SECTORS = [
    "خودرو و ساخت قطعات",
    "عرضه برق، گاز، بخار و آب گرم",
    "لاستيك و پلاستيك",
]
ALLOWED_SECTORS = [
    "محصولات غذايي و آشاميدني به جز قند و شكر",
    "مواد و محصولات دارويي",
    "قند و شكر",
    "شوينده",
]


def main():
    cfg = dict(bors_config.FTS_DEFAULTS)

    # ── ۱) فهرستِ زندهٔ سرور (bors_config.FTS_DEFAULTS) ──────────────────
    chk(cfg.get("mandatory_sectors") == EXPECTED,
        "FTS_DEFAULTS.mandatory_sectors دقیقاً سه صنعتِ جزوه است",
        cfg.get("mandatory_sectors"))
    chk("بیمه" not in " ".join(cfg.get("mandatory_sectors") or []),
        "بیمه در فهرستِ دستوریِ سرور نیست (وتویِ جدا دارد)")
    chk(cfg.get("reject_insurance") is True,
        "FTS_DEFAULTS.reject_insurance پیش‌فرض True است",
        cfg.get("reject_insurance"))

    # ── ۲) فال‌بکِ موتور (وقتی کلید از config بیفتد) ────────────────────
    joined = " ".join(F.MANDATORY_PRICING_TOKENS)
    for bad in ("شوینده", "قند", "بیمه"):
        chk(bad not in joined, "MANDATORY_PRICING_TOKENS بی «%s» است" % bad)
    for good in ("خودرو", "نقلیه موتور", "لاستیک", "نیروگاه",
                 "عرضه برق", "تولید برق", "توزیع برق"):
        chk(good in joined, "MANDATORY_PRICING_TOKENS «%s» را دارد" % good)

    # ── ۳) sector_filter با فال‌بکِ موتور (cfg خالی) ─────────────────────
    for sector in MANDATORY_SECTORS:
        res = F.sector_filter(sector)
        chk(res["verdict"] == "mandatory" and res["pass"] is False,
            "فال‌بک: «%s» دستوری و مردود است" % sector, res["verdict"])
    for sector in ALLOWED_SECTORS:
        res = F.sector_filter(sector)
        chk(res["verdict"] != "mandatory" and res["pass"] is True,
            "فال‌بک: «%s» دستوری نیست و از شاخص ۵ می‌گذرد" % sector,
            res["verdict"])

    # ── ۴) sector_filter با پیکربندیِ زندهٔ سرور ─────────────────────────
    for sector in MANDATORY_SECTORS:
        res = F.sector_filter(sector, cfg=cfg)
        chk(res["verdict"] == "mandatory" and res["pass"] is False,
            "پیکربندیِ سرور: «%s» دستوری و مردود است" % sector, res["verdict"])
    for sector in ALLOWED_SECTORS:
        res = F.sector_filter(sector, cfg=cfg)
        chk(res["verdict"] != "mandatory" and res["pass"] is True,
            "پیکربندیِ سرور: «%s» دستوری نیست و از شاخص ۵ می‌گذرد" % sector,
            res["verdict"])

    # ── ۵) pricing_mode (مسیرِ داوریِ صنعت‌هایِ بی‌تطبیق) ────────────────
    for sector in ("قند و شكر", "شوينده", INSURANCE_SECTOR):
        chk(F.pricing_mode(sector) != "mandatory",
            "pricing_mode «%s» را دستوری نمی‌داند" % sector,
            F.pricing_mode(sector))

    # ── ۶) بیمه: تشخیص و وتویِ سختِ جداگانه ─────────────────────────────
    chk(F.is_insurance_sector(INSURANCE_SECTOR) is True,
        "صنعتِ بیمه شناسایی می‌شود")
    chk(F.is_insurance_sector("بیمه") is True,
        "«بیمه» (نوشتارِ فارسی) شناسایی می‌شود")
    base = {"filter_m141": False, "min_trade_val": 0, "mcap_min_hmt": 0}
    on = FD.risk_gates(None, "آسيا", INSURANCE_SECTOR, 1e13,
                       cfg=dict(base, reject_insurance=True))
    off = FD.risk_gates(None, "آسيا", INSURANCE_SECTOR, 1e13,
                        cfg=dict(base, reject_insurance=False))
    chk(any("بیمه" in r for r in on),
        "risk_gates با reject_insurance=True بیمه را حذف می‌کند", on)
    chk(not any("بیمه" in r for r in off),
        "risk_gates با reject_insurance=False بیمه را حذف نمی‌کند", off)

    # ── ۶ب) همان کلید در موتور (scan_symbol) — اگر بانکِ محلی هست، فقط‌خواندنی
    db = os.path.join(ROOT, "market.db")
    if os.path.isfile(db):
        conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        try:
            row = conn.execute(
                "SELECT i.l_val18, i.sector_name FROM instruments i "
                "JOIN financial_statements f ON f.symbol = i.l_val18 "
                "WHERE i.sector_name LIKE '%بيمه%' LIMIT 1").fetchone()
            if row:
                sym, ins_sector = row
                s_on = F.scan_symbol(conn, sym, 0.0, 0.0, ins_sector,
                                     cfg={"reject_insurance": True})
                s_off = F.scan_symbol(conn, sym, 0.0, 0.0, ins_sector,
                                      cfg={"reject_insurance": False})
                chk(s_on["excluded"] and
                    any("بیمه" in r for r in s_on["exclusion_reasons"]),
                    "scan_symbol با reject_insurance=True بیمه را وتو می‌کند",
                    s_on["exclusion_reasons"])
                chk(not any("بیمه" in r for r in s_off["exclusion_reasons"]),
                    "scan_symbol با reject_insurance=False وتویِ بیمه را کنار می‌گذارد",
                    s_off["exclusion_reasons"])
            else:
                print("SKIP  scan_symbol: نمادِ بیمه‌ای با صورتِ مالی در بانک نیست")
        finally:
            conn.close()
    else:
        print("SKIP  scan_symbol: market.db نیست — فقط بررسی‌هایِ خالص اجرا شد")

    # ── ۷) مهاجرتِ فایلِ قدیمی: فهرستِ ۸تاییِ ذخیره‌شده باید به سه برسد ────
    # فایلِ config در نصب‌های قدیمی با همین superset ذخیره شده بود؛ load باید
    # آن را بی‌نیاز از Save کاربر به سه صنعتِ جزوه نرمال کند.
    old_eight = ["خودرو", "دارو", "نیروگاه", "قند و شکر", "غذا",
                 "لاستیک", "شوینده", "بیمه"]
    original_path = M.FTS_CONFIG_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="fts-sector-") as tmp:
            path = os.path.join(tmp, "fts_thresholds.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"mandatory_sectors": old_eight}, f, ensure_ascii=False)
            M.FTS_CONFIG_PATH = path
            migrated = M.load_fts_config()
            chk(migrated["mandatory_sectors"] == EXPECTED,
                "فایلِ قدیمی: load فهرستِ ۸تایی را به سه صنعتِ جزوه می‌رساند",
                migrated["mandatory_sectors"])
            for sector in ALLOWED_SECTORS:
                res = F.sector_filter(sector, cfg=migrated)
                chk(res["verdict"] != "mandatory" and res["pass"] is True,
                    "فایلِ قدیمی: «%s» پس از مهاجرت از شاخص ۵ می‌گذرد" % sector,
                    res["verdict"])

            # Save نیز نباید superset را روی دیسک بنویسد (پدافندِ همان قاعده).
            saved = M.set_fts_config({"mandatory_sectors": old_eight,
                                      "reject_insurance": "false"})
            chk(saved.get("status") == "success",
                "set_fts_config فهرستِ قدیمی را بی‌خطا می‌پذیرد", saved.get("message"))
            chk(saved["config"]["mandatory_sectors"] == EXPECTED,
                "set_fts_config فهرستِ قدیمی را به سه صنعت نرمال می‌کند",
                saved["config"]["mandatory_sectors"])
            chk(saved["config"]["reject_insurance"] is True,
                "set_fts_config رشتهٔ \"false\" را به پیش‌فرضِ True برمی‌گرداند",
                saved["config"]["reject_insurance"])
    finally:
        M.FTS_CONFIG_PATH = original_path

    # ── ۸) وتویِ بیمه: null/رشته نباید بی‌صدا وتو را خاموش کند ────────────
    original_path = M.FTS_CONFIG_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="fts-veto-") as tmp:
            path = os.path.join(tmp, "fts_thresholds.json")
            M.FTS_CONFIG_PATH = path
            for bad, label in ((None, "null"), ("false", "رشتهٔ \"false\"")):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"reject_insurance": bad}, f, ensure_ascii=False)
                veto = M.load_fts_config()["reject_insurance"]
                chk(veto is True,
                    "reject_insurance=%s در فایل به پیش‌فرضِ True برمی‌گردد" % label,
                    veto)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"reject_insurance": False}, f, ensure_ascii=False)
            veto = M.load_fts_config()["reject_insurance"]
            chk(veto is False,
                "reject_insurance=false واقعی همان False می‌ماند", veto)
    finally:
        M.FTS_CONFIG_PATH = original_path

    print("\n%d/%d checks passed" % (PASS, PASS + FAIL))
    if FAIL:
        print("FTS SECTOR v11 FAILED (%d failed)" % FAIL)
        return 1
    print("OK sector lists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
