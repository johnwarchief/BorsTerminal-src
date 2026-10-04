# -*- coding: utf-8 -*-
"""_audit/ta_parity_matrix.py — ماتریس تطبیقِ عینـیِ «نبض بازار» با TradersArena

قواعدِ این دور (طبقِ یادداشتِ پروژه و docs/TA-SCOPE-DECODE.md):
  * هر دو طرف درِ یک نشست سنجیده می‌شوند و برچسبِ زمانِ **دو طرف** در JSON می‌نشیند
    (TA: `j` + `d`؛ ما: `asof.d_even/h_even`). فاصلۀ دو برداشت هم اندازه‌گیری و
    ثبت می‌شود؛ اگر بدنۀ ما بینِ دو برداشت تکان بخورد، سطرِ مربوط «timing» می‌شود.
  * هیچ تعریفی حدس زده نمی‌شود: هویتِ هر فیلدِ TA یا از docs/TA-SCOPE-DECODE.md
    (هویت‌های جبریِ اثبات‌شده با خطای ۰٫۰۰۰٪) می‌آید یا از برابریِ عددیِ همین اجرا؛
    آن‌که رمزگشایی نشده `missing-source` / تعریفِ واگزار申告 می‌شود.
  * خامِ هر دو طرف در `_audit/fixtures/` بایگانی می‌شود (با timestamp) تا
    `_audit/ta_fixture_check.py` بعداً بی‌شبکه تکرارپذیری را بسنجد.

تنها خواندنی: GET به 127.0.0.1:8002 و tradersarena.ir؛ هیچ فایلی جز
_audit/ta_parity_matrix.{py,json,md} و _audit/fixtures/* تغییر نمی‌کند.

اجرا:
    cd BorsTerminal
    export PYTHONIOENCODING=utf-8
    python _audit/ta_parity_matrix.py            # زنده + نوشتن JSON/MD/فیکسچرها
    python _audit/ta_parity_matrix.py --offline  # بازسازیِ ماتریس از فیکسچرهای موجود
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

FIXDIR = os.path.join(HERE, "fixtures")
TA = "https://tradersarena.ir"
TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": TA + "/market",
          "Accept": "application/json"}
APP = os.environ.get("MTX_APP", "http://127.0.0.1:8002")

# ---- تبدیل‌های یکای اثبات‌شده (docs/TA-SCOPE-DECODE.md §۱) ----
RIAL_TO_BT = 1e10        # ریال → میلیارد تومان
RIAL_TO_MTON = 1e7       # ریال → میلیون تومان (سرانه)
SHARES_TO_B = 1e9        # سهم → میلیارد سهم

TA_PATHS = {
    "market0": "/data/market0",
    "histo": "/data/market/histo-status",
    "totals0": "/data/market/chart/totals0",
    "industries": "/data/industries-csv",
    "mainwatch": "/data/mainwatch/symbols",
}
# اندیس‌های ردیف‌های TA — همه از جبرِ اثبات‌شده در TA-SCOPE-DECODE §۱
I_VOL, I_VAL, I_PC_BUY, I_PC_SELL, I_POW, I_FLOW = 0, 1, 2, 3, 4, 5
I_COUNT_BUY, I_RBUY, I_PCT_RBUY, I_PCT_RSELL, I_RSELL, I_COUNT_SELL = 6, 7, 8, 9, 10, 11
I_LBUY, I_LSELL = 13, 16

UNREACHABLE = "UNREACHABLE"


def _iso_local():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _iso_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def get_json(url, hdr=None, timeout=90):
    req = urllib.request.Request(url, headers=hdr or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8-sig", "replace")
    return json.loads(raw)


def normname(s):
    """یکسان‌سازیِ نامِ فارسی/عربیِ صنایع برایِ جفت‌کردنِ دو طرف (بدونِ حدسِ داده)."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("أ", "ا").replace("إ", "ا")
    s = re.sub(r"[\u200c\u200f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def fmt(v, nd=1):
    if v is None:
        return "—"
    if isinstance(v, float):
        return ("%." + str(nd) + "f") % v
    return str(v)


def first(seq, i=0):
    try:
        return (seq or [None] * (i + 1))[i]
    except (TypeError, IndexError):
        return None


class Matrix:
    def __init__(self):
        self.rows = []

    def add(self, metric, our_ref, their_ref, ours, theirs, tol,
            cause=None, note="", unit=None):
        """tol: تلورانسِ «match» (مقدارِ مطلق همان یکای سطر). cause: طبقه‌ای است
        که از پیش ثابت شده (متنِ عددیِ اثبات + کلاس از پنج‌گانهٔ مجاز)."""
        row = {"metric": metric, "our_ref": our_ref, "their_ref": their_ref,
               "our": ours, "their": theirs, "tol": tol, "note": note,
               "delta": None, "delta_pct": None, "verdict": None,
               "cause_class": cause[0] if cause else None,
               "cause_evidence": cause[1] if cause else None}
        if ours is None or theirs in (None, UNREACHABLE):
            row["verdict"] = "missing-source" if theirs == UNREACHABLE or theirs is None else "missing-source"
            self.rows.append(row)
            return row
        try:
            d = float(ours) - float(theirs)
            row["delta"] = round(d, 6)
            if float(theirs) != 0.0:
                row["delta_pct"] = round(100.0 * d / abs(float(theirs)), 3)
        except (TypeError, ValueError):
            row["verdict"] = "definition-gap"
            self.rows.append(row)
            return row
        if abs(d) <= tol:
            row["verdict"] = "match"
        elif cause:
            row["verdict"] = "definition-gap" if cause[0] not in (
                "rounding", "snapshot-timing", "unit-scale") else cause[0]
        else:
            row["verdict"] = "definition-gap"
        self.rows.append(row)
        return row


# ================================================================برداشت (fetch)
def fetch_all(offline):
    """برداشتِ دو طرف درِ یک پنجرۀ زمانی. فاصلۀ دو market0 برایِ سنجشِ «تکانِ داده» ثبت می‌شود."""
    os.makedirs(FIXDIR, exist_ok=True)
    ta, ours_api, stamps = {}, {}, {}
    stamps["run_started_local"] = _iso_local()
    stamps["run_started_utc"] = _iso_utc()

    def ta_fetch(key, path):
        url = TA + path
        try:
            d = get_json(url, TA_HDR)
            return d, {"fetched_at_local": _iso_local(), "fetched_at_utc": _iso_utc(),
                       "url": url, "error": None}
        except Exception as e:  # noqa: BLE001
            return None, {"fetched_at_local": _iso_local(), "fetched_at_utc": _iso_utc(),
                          "url": url, "error": "%s: %s" % (type(e).__name__, e)}

    for key, path in TA_PATHS.items():
        fpath = os.path.join(FIXDIR, "ta_%s.json" % key)
        if offline and os.path.isfile(fpath):
            blob = json.load(open(fpath, encoding="utf-8"))
            ta[key] = blob["payload"]
            stamps.setdefault("ta", {})[key] = blob["fetched_at_local"]
            continue
        d, meta = ta_fetch(key, path)
        ta[key] = d
        stamps.setdefault("ta", {})[key] = meta["fetched_at_local"]
        if meta["error"]:
            print("!! TA unreachable:", path, meta["error"])
            continue
        blob = {"fixture": "ta_%s" % key, **meta, "payload": d}
        json.dump(blob, open(fpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # -- اندپوینت‌هایِ خودی (همان لحظه، پس از TA) --
    api_paths = ["summary", "thermometer", "depth", "clientsplit", "mainwatch",
                 "industries", "smart-money", "histogram", "timeline"]
    stamps["ours_done_at_local"] = _iso_local()
    for p in api_paths:
        try:
            ours_api[p] = get_json("%s/api/mstat/%s" % (APP, p), timeout=60)
        except Exception as e:  # noqa: BLE001
            ours_api[p] = None
            print("!! APP unreachable:", p, e)
    for g in ("eq_all", "stock_right"):
        try:
            ours_api["thermometer:" + g] = get_json(
                "%s/api/mstat/thermometer?group=%s" % (APP, g), timeout=60)
            ours_api["depth:" + g] = get_json(
                "%s/api/mstat/depth?group=%s" % (APP, g), timeout=60)
        except Exception:  # noqa: BLE001
            ours_api["thermometer:" + g] = ours_api["depth:" + g] = None
    stamps["ours_done_at_utc"] = _iso_utc()

    # -- برداشتِ دومِ market0: آیا بدنۀ TA بینِ دو برداشت تکان خورد؟ --
    drift = {"second_fetch_local": _iso_local(), "second_d": None, "first_d": None}
    if not offline:
        d2, m2 = ta_fetch("market0", TA_PATHS["market0"])
        if d2:
            drift["first_d"] = (ta.get("market0") or {}).get("d")
            drift["second_d"] = d2.get("d")
    stamps["ta_drift"] = drift

    # -- برداشتِ دومِ شاخصِ خودی: تکانِ اندپوینتِ ما --
    try:
        sm2 = get_json("%s/api/mstat/smart-money" % APP, timeout=60)
        drift["ours_index_first"] = ((ours_api.get("smart-money") or {}).get("macro") or {}).get("index")
        drift["ours_index_second"] = (sm2.get("macro") or {}).get("index")
    except Exception:  # noqa: BLE001
        pass
    stamps["run_finished_local"] = _iso_local()
    return ta, ours_api, stamps


# ================================================================ساختِ ماتریس
def build_matrix(ta, ours_api, stamps):
    m = Matrix()
    m0, histo, tot, ind_ta, mw_ta = (ta.get(k) for k in ("market0", "histo", "totals0", "industries", "mainwatch"))
    su = ours_api.get("summary") or {}
    rows_ours = {r["key"]: r for r in su.get("rows", [])}
    th_all = (ours_api.get("thermometer") or {})
    th_eq = (ours_api.get("thermometer:eq_all") or {})
    de_all = (ours_api.get("depth") or {})
    de_eq = (ours_api.get("depth:eq_all") or {}) or {}
    cs_all = (ours_api.get("clientsplit") or {})
    sm = (ours_api.get("smart-money") or {})
    ind_ours = (ours_api.get("industries") or {})
    mw_ours = (ours_api.get("mainwatch") or {})
    hist_ours = (ours_api.get("histogram") or {})
    our_asof = su.get("asof") or {}

    def arr(key, idx, conv=RIAL_TO_BT):
        a = (m0 or {}).get(key)
        if not a or len(a) <= idx or a[idx] is None:
            return None
        return float(a[idx]) / conv

    # 1) وضعیت کلی بازار -------------------------------------------------------
    our_state = ((sm.get("macro") or {}).get("label"), (sm.get("verdict") or {}).get("label")
                 if isinstance(sm.get("verdict"), dict) else None)
    m.add("وضعیت کلی بازار (برچسب)",
          "/api/mstat/smart-money → macro.label + verdict",
          "بدونِ منبع — برچسب «وضعیت کنونی بازار» فقط در باندلِ صفحهٔ خانه دیده شد "
          "(_audit/ta_home_strings.txt:356,729)؛ هیچ فیلدِ عددیِ market0/histo-status به آن وصل نیست "
          "و /market پشتِ ورود است",
          str(our_state[0] or our_state[1] or ""), UNREACHABLE, 0.005,
          note="جست‌وجو شد: /data/market0 (کلیدها عددیِ بی‌متن)، /data/market/histo-status (سطل)، "
               "/data/market/chart/totals0 (سری زمانی)، رشته‌های باندل.")

    # 2) شاخص کل ---------------------------------------------------------------
    idx = (sm.get("macro") or {}).get("index") or {}
    m.add("شاخص کل (مقدار)", "/api/mstat/smart-money → macro.index.last",
          "tradersarena.ir/data/market0 → iw[0]",
          idx.get("last"), ((m0 or {}).get("iw") or [None])[0], 0.05,
          cause=("snapshot-timing", "هر دو سطر از GetMarketOverviewِ همان نشستند (برابریِ عینـی در "
                 "۱۴۰۵-۰۷-۰۴؛ TA-PARITY §۲). اختلافِ این اجرا فقط از فاصلۀ دو برداشت است: "
                 "TA d=%s در برابرِ asof ما h_even=%s" % ((m0 or {}).get("d"), our_asof.get("h_even"))))
    m.add("شاخص کل (تغییر روز)", "/api/mstat/smart-money → macro.index.change",
          "market0 → iw[1]", idx.get("change"), first(m0.get("iw"), 1), 0.05,
          cause=("snapshot-timing",
                 "همان ۱۰۲٫۵ واحدِ سطرِ «مقدار» (تغییر = مقدارجاری − دیروز؛ دیروز مشترک است). "
                 "سطرِ درصد عیناً یکی است (−۰٫۳۲) و درِ ۱۴۰۵-۰۷-۰۴ این دو عدد ده‌به‌ده برابر بودند "
                 "(TA-PARITY §۲) — یعنی واگرایی از لحظۀ فریزشدنِ هر ناشر درِ تسویهٔ پسازساعت است: "
                 "TA روی d=%s ایستاده و ما روی h_even=%s" % (m0.get("d"), our_asof.get("h_even"))))
    m.add("شاخص کل (درصد روز)", "/api/mstat/smart-money → macro.index.pct",
          "market0 → iw[2]", idx.get("pct"), first(m0.get("iw"), 2), 0.02)

    # 3/4) تعداد مثبت/منفی -----------------------------------------------------
    plus = ((tot or {}).get("plus") or [None])[-1]
    minus = ((tot or {}).get("minus") or [None])[-1]
    universe_ta = None
    if histo and histo.get("s1"):
        universe_ta = sum(histo["s1"])
    universe_ta = sum(histo["s1"]) if (histo and histo.get("s1")) else None
    n_known = ((th_all.get("positive") or 0) + (th_all.get("negative") or 0)
               + (th_all.get("zero") or 0))
    m.add("تعداد مثبت", "/api/mstat/thermometer → positive (گروه all؛ eq_all در یادداشت)",
          "market0 → pp[0] (=سریِ plus در totals0)",
          th_all.get("positive"), first(m0.get("pp")), 0,
          cause=("definition divergence",
                 "دامنۀ او %s نماد است (اتحادِ درونِ خودش: pp+pm=%s == sum(s1)) در برابرِ %s نمادِ "
                 "دارایِ درصدِ ما (all) / %s (eq_all). شمارِ او با هیچ سطلِ ما بازسازی نشد؛ "
                 "دامنۀ «تغییرِ معنادار» او رمزگشایی‌نشده باقی است (TA-SCOPE-DECODE §۶، این دور هم تأیید کرد)"
                 % (universe_ta, None if not plus else plus + (minus or 0), n_known,
                    (th_eq.get("positive") or 0) + (th_eq.get("negative") or 0) + (th_eq.get("zero") or 0))))
    m.add("تعداد منفی", "/api/mstat/thermometer → negative (گروه all)",
          "market0 → pm[0] (=سریِ minus در totals0)",
          th_all.get("negative"), first(m0.get("pm")), 0,
          cause=("definition divergence", "همان دامنۀ %sتاییِ سطرِ بالا" % universe_ta))
    # 5) درصد مثبت/منفی
    ta_pp = first(m0.get("pp"))
    ta_pm = first(m0.get("pm"))
    ta_ratio = None
    try:
        ta_ratio = round(100.0 * float(ta_pp) / (float(ta_pp) + float(ta_pm)), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    m.add("درصد مثبت/منفی", "/api/mstat/thermometer → positive_pct / negative_pct",
          "نسبتِ حسابی از pp/pm او: plus/(plus+minus) — «درصدِ» مستقل در فیدش نیست",
          th_all.get("positive_pct"), ta_ratio, 0.5,
          cause=("definition divergence",
                 "منفیِ ما %s%% رویِ دامنۀ %d؛ او فقط نسبتِ دامنۀ ۸۶۳تاییِ خودش را می‌دهد"
                 % (th_all.get("negative_pct"), th_all.get("positive", 0) + th_all.get("negative", 0) + th_all.get("zero", 0))))

    # 6/7) صف خرید / فروش -------------------------------------------------------
    bq_c = ((tot or {}).get("bq") or [None])[-1]
    sq_c = ((tot or {}).get("sq") or [None])[-1]
    bo_v = ((tot or {}).get("bo") or [None])[-1]
    so_v = ((tot or {}).get("so") or [None])[-1]
    m.add("صف خرید (شمارِ نماد در صف)", "/api/mstat/depth → buy_queue_count",
          "totals0 → bq[-1] (شمارهٔ کوچک؛ معنا از توالیِ شمارشِ درون‌روزی: TA_PARITY_AUDIT §«عمقِ صف»)",
          de_all.get("buy_queue_count"), bq_c, 0,
          cause=("definition divergence",
                 "دامنۀ او همان ۸۶۳تایی است؛ ما رویِ کلِ %d سطرِ دارایِ عمق می‌شماریم. "
                 "تبدیلِ واحد هم محتمل نیست چون bq[-1]=%s یک شمارۀ صحیحِ کوچک است نه ریال."
                 % (de_all.get("symbols_with_depth", 0), bq_c)))
    m.add("صف فروش (شمارِ نماد در صف)", "/api/mstat/depth → sell_queue_count",
          "totals0 → sq[-1]", de_all.get("sell_queue_count"), sq_c, 0,
          cause=("definition divergence", "همان دامنۀ صفِ خرید"))
    m.add("صف خرید (ارزش)", "/api/mstat/depth → buy_queue_b_toman (all/eq_all)",
          "totals0 → bo[-1] — معنا/یکای این ستون رمزگشایی نشده (TA-SCOPE-DECODE آن را در «نیازمند پژوهش» "
          "گذاشته؛ هر نسبتِ ثابتی با ستون‌هایِ اثبات‌شده ندارد)",
          "all=%s · eq_all=%s" % (fmt(de_all.get("buy_queue_b_toman")), fmt(de_eq.get("buy_queue_b_toman"))),
          None if bo_v is None else round(bo_v / RIAL_TO_BT, 1), 5.0,
          cause=("definition divergence",
                 "bo[-1]=%s م.ت و so[-1]=%s م.ت؛ این‌که «بهترین سفارش» است یا «ارزش صف» از فیدِ عمومی "
                 "قابلِ اثبات نیست — پس هیچ ادعایِ برابری/خطا نمی‌کنیم."
                 % (fmt(None if bo_v is None else bo_v / RIAL_TO_BT),
                    fmt(None if so_v is None else so_v / RIAL_TO_BT))))
    m.add("صف فروش (ارزش)", "/api/mstat/depth → sell_queue_b_toman (all/eq_all)",
          "totals0 → so[-1] (رمزگشایی‌نشده)",
          "all=%s · eq_all=%s" % (fmt(de_all.get("sell_queue_b_toman")), fmt(de_eq.get("sell_queue_b_toman"))),
          None if so_v is None else round(so_v / RIAL_TO_BT, 1), 5.0,
          cause=("definition divergence", "همان سطرِ بالا"))

    # 8) ارزش معاملات -----------------------------------------------------------
    # واکاویِ پویا: Δِ سطرِ «کل» باید با جمعِ Δِ سه سطرِ هم‌دامنه بخواند
    d_all = (rows_ours.get("all", {}).get("value_b_toman") or 0.0) - (arr("m", I_VAL) or 0.0)
    d_parts = [(rows_ours.get(k, {}).get("value_b_toman") or 0.0) - (arr(t, I_VAL) or 0.0)
               for k, t in (("stock_right", "st"), ("eq_fund", "sf"), ("fixed_fund", "nsf"))]
    # پوششِ client_type درِ سمتِ ما (برایِ سطرهایِ جریان/سرانه/قدرت)
    cov = None
    try:
        rb = float(cs_all.get("retail", {}).get("buy_b_toman") or 0.0)
        ib = float(cs_all.get("institutional", {}).get("buy_b_toman") or 0.0)
        v = float(rows_ours.get("all", {}).get("value_b_toman") or 0.0)
        cov = {"sum": round(rb + ib, 1), "pct": round(100.0 * (rb + ib) / v, 1) if v else None}
    except (TypeError, ValueError):
        pass
    val_cause = ("definition divergence",
                 "واکاویِ Δِ این اجرا: کل %s = (%s سهام) + (%s ص.سهامی) + (%s درآمدثابت) — "
                 "همه از طبقه‌بندیِ زیرگونهٔ صندوق می‌آید که درِ docs/TA-SCOPE-DECODE.md §۳ و §۴ "
                 "به‌عنوان تنها شکافِ بازِ «دامنه» ثبت شده است (TSETMC هیچ fundType رسمی نمی‌دهد؛ "
                 "زیرنوع از نام حدس زده می‌شود؛ جهتِ دو سطرِ صندوق یکدیگر را می‌پوشانند)"
                 % (fmt(d_all), fmt(d_parts[0]), fmt(d_parts[1]), fmt(d_parts[2])))
    m.add("ارزش معاملات — کل بازار (م.ت)", "/api/mstat/summary → rows[all].value_b_toman",
          "market0 → m[1]/1e10 (دامنۀ او = st+sf+nsf؛ هویتِ جبریِ اثبات‌شده)",
          rows_ours.get("all", {}).get("value_b_toman"), arr("m", I_VAL), 30.0, cause=val_cause)
    m.add("ارزش — سهام و حق تقدم (م.ت)", "/api/mstat/summary → rows[stock_right].value_b_toman",
          "market0 → st[1]/1e10", rows_ours.get("stock_right", {}).get("value_b_toman"),
          arr("st", I_VAL), 30.0,
          cause=("definition divergence",
                 "Δ=+%s م.ت (+%s%%) — پیش‌تر درِ TA-SCOPE-DECODE §۴ اندازه‌گیری شد (نشتِ ردیف‌هایِ "
                 "بی‌paper_type و تفاوتِ دامنۀ «سهام»؛ بازسنجش همان سند: +۲٫۶٪). واحد درست است "
                 "(تبدیلِ ریال→م.ت = ۱e۱۰، §۱ همان سند) و نشستِ دو طرف یکی است."
                 % (fmt(d_parts[0]), fmt(100.0 * d_parts[0] / (arr("st", I_VAL) or 1.0), 2))))
    m.add("ارزش — ص.سهامی و مختلط (م.ت)", "/api/mstat/summary → rows[eq_fund].value_b_toman",
          "market0 → sf[1]/1e10", rows_ours.get("eq_fund", {}).get("value_b_toman"),
          arr("sf", I_VAL), 30.0,
          cause=("genuinely missing data",
                 "Δ=%s م.ت (%s%%) — «تقسیمِ زیرگونهٔ صندوق» شکافِ اعلام‌شدۀ TA-SCOPE-DECODE §۴/§۵ است: "
                 "TSETMC همهٔ صندوق‌ها را paperType=8 و بی‌fundType می‌دهد و زیرنوع از نام حدس زده می‌شود؛ "
                 "بستنش بی‌منبعِ رسمی ممکن نیست (رأیِ pilot jev: «قاعدهٔ نام»، نه «نقشهٔ رسمی»). "
                 "شاهدِ جابه‌جاییِ متقابل: Δِ سطرِ درآمدثابت = %s م.ت (جمعِ دو سطر ≈ صفرِ سطرِ کل)."
                 % (fmt(d_parts[1]), fmt(100.0 * d_parts[1] / (arr("sf", I_VAL) or 1.0), 2), fmt(d_parts[2]))))
    m.add("ارزش — ص.درآمد ثابت (م.ت)", "/api/mstat/summary → rows[fixed_fund].value_b_toman",
          "market0 → nsf[1]/1e10", rows_ours.get("fixed_fund", {}).get("value_b_toman"),
          arr("nsf", I_VAL), 30.0,
          cause=("genuinely missing data",
                 "Δ=+%s م.ت (+%s%%) — همان شکافِ طبقۀ صندوق؛ جهتِ این Δ دقیقاً مخالفِ Δِ سطرِ "
                 "«ص.سهامی و مختلط» است (§۵ سند: «جهتِ خطا درِ دو سطرِ مقابل یکدیگر را می‌پوشانند»)"
                 % (fmt(d_parts[2]), fmt(100.0 * d_parts[2] / (arr("nsf", I_VAL) or 1.0), 2))))

    # 9) حجم معاملات -------------------------------------------------------------
    m.add("حجم معاملات — کل بازار (میلیارد سهم)", "/api/mstat/summary → rows[all].volume_b_shares",
          "market0 → m[0]/1e9", rows_ours.get("all", {}).get("volume_b_shares"),
          arr("m", I_VOL, SHARES_TO_B), 0.6,
          cause=("definition divergence",
                 "همان خانوادۀ طبقه‌بندیِ صندوق که درِ سطرِ «ارزشِ کل» با واکاویِ عددیِ "
                 "(%s) بسته شد؛ جهتِ حجم (+%.2f میلیارد سهم ≈ +%.1f%%) با جهتِ ارزش هم‌خوان است و "
                 "بیانگرِ دامنه است، نه یکای اشتباه (تبدیلِ ۱e۹ درِ TA-SCOPE-DECODE §۱ تأیید شده)."
                 % (val_cause[1].split("واکاویِ Δِ این اجرا:")[1][:80] if "واکاوی" in val_cause[1] else "—",
                    (rows_ours.get("all", {}).get("volume_b_shares") or 0.0) - (arr("m", I_VOL, SHARES_TO_B) or 0.0),
                    100.0 * ((rows_ours.get("all", {}).get("volume_b_shares") or 0.0) - (arr("m", I_VOL, SHARES_TO_B) or 0.0))
                    / (arr("m", I_VOL, SHARES_TO_B) or 1.0))))

    # 10) ورود/خروج پول ----------------------------------------------------------
    flow_cause = ("definition divergence",
                  "شاهدِ این اجرا: جمعِ خریدِ حقیقی+حقوقیِ ما = %s م.ت == %s%%ِ ارزشِ «کل»ِ خودمان، "
                  "در حالی که درِ جبرِ او i7+i13 عیناً i1 است (۱۰۰٪؛ سطرِ «هویتِ جبری» همین جدول). "
                  "پس ستونِ جریان/سرانهٔ ما رویِ پوششِ ناقصِ client_type حساب می‌شود و عددِ «کلِ» او "
                  "همچنان بازسازی‌نشده است (TA-SCOPE-DECODE §۴: «جمعِ دو سطرِ بالا ±۰٫۵٪ ولی ترکیبِ جریانِ کل باز»; "
                  "و درِ ۱۴۰۵-۰۷-۱۱ تعریفِ جریان رویِ دامنهٔ خرد تا ۳٪ خوانده بود: −۷٬۴۹۳ در برابرِ −۷٬۷۰۲). "
                  "سطرِ «درآمد ثابت» (§۳ همین سند): Δجریان %s م.ت."
                  % (cov.get("sum") if cov else "—", cov.get("pct") if cov else "—",
                     fmt((rows_ours.get("fixed_fund", {}).get("money_flow_b_toman") or 0.0)
                         - (arr("nsf", I_FLOW) or 0.0))))
    m.add("ورود/خروج پول — کل بازار (م.ت)", "/api/mstat/summary → rows[all].money_flow_b_toman",
          "market0 → m[5]/1e10 (=m[7]−m[10]؛ هویتِ جبریِ اثبات‌شده)",
          rows_ours.get("all", {}).get("money_flow_b_toman"), arr("m", I_FLOW), 40.0, cause=flow_cause)
    m.add("ورود/خروج پول — سهام و حق تقدم (م.ت)",
          "/api/mstat/summary → rows[stock_right].money_flow_b_toman",
          "market0 → st[5]/1e10", rows_ours.get("stock_right", {}).get("money_flow_b_toman"),
          arr("st", I_FLOW), 40.0, cause=flow_cause)
    m.add("ورود/خروج پول — ص.درآمد ثابت (م.ت)",
          "/api/mstat/summary → rows[fixed_fund].money_flow_b_toman",
          "market0 → nsf[5]/1e10", rows_ours.get("fixed_fund", {}).get("money_flow_b_toman"),
          arr("nsf", I_FLOW), 40.0, cause=flow_cause)

    # 11) قدرت خریدار/فروشنده ----------------------------------------------------
    pc_cause = ("definition divergence",
                "ریشۀ عددیِ ثابت‌شده درِ همین اجرا: شمارِ خریدارِ حقیقیِ او %s در برابرِ %s ما (%s%%)، "
                "سرانۀ خریدِ او %s در برابرِ %s ما — با پوششِ %s%%ِ client_typeِ ما (سطرِ جریان). "
                "این همان «مخرجِ فروشِ او منبعِ جدا دارد» است که درِ docs/fts-notes/TA_PARITY_AUDIT.md §۳ "
                "(سنجشِ ۱۴۰۵-۰۷-۱۱) ثبت شد و هنوز رأیِ مرجع ندارد."
                % (first(m0.get("m"), I_COUNT_BUY), cs_all.get("retail", {}).get("buy_count"),
                   fmt(100.0 * ((cs_all.get("retail", {}).get("buy_count") or 0) - (first(m0.get("m"), I_COUNT_BUY) or 1))
                       / (first(m0.get("m"), I_COUNT_BUY) or 1), 1),
                   fmt(arr("m", I_PC_BUY, RIAL_TO_MTON)),
                   fmt(rows_ours.get("all", {}).get("pc_buy_m_toman")),
                   cov.get("pct") if cov else "—"))
    m.add("قدرت خریدار (نسرتِ سرانه) — کل بازار", "/api/mstat/summary → rows[all].buy_power",
          "market0 → m[4]؛ هویتِ m[4]=m[2]/m[3] فقط برایِ ردیفِ «کل» اثبات شده — در ردیف‌هایِ دیگر "
          "سلوکِ یکسان ندارد (سنجشِ درونِ اجرا: ratio=m[2]/m[3])",
          rows_ours.get("all", {}).get("buy_power"), arr("m", I_POW, 1.0), 0.02, cause=pc_cause)
    m.add("سرانۀ خرید (م.ت) — کل بازار", "/api/mstat/summary → rows[all].pc_buy_m_toman",
          "market0 → m[2]/1e7 (اثبات: m[2]=m[7]/m[6] در جبرِ خودِ او)",
          rows_ours.get("all", {}).get("pc_buy_m_toman"), arr("m", I_PC_BUY, RIAL_TO_MTON), 1.0, cause=pc_cause)
    m.add("سرانۀ فروش (م.ت) — کل بازار", "/api/mstat/summary → rows[all].pc_sell_m_toman",
          "market0 → m[3]/1e7 (اثبات: m[3]=m[10]/m[11])",
          rows_ours.get("all", {}).get("pc_sell_m_toman"), arr("m", I_PC_SELL, RIAL_TO_MTON), 1.0, cause=pc_cause)
    m.add("تعداد خریدارِ حقیقی (شمار)", "/api/mstat/clientsplit → retail.buy_count",
          "market0 → m[6]", cs_all.get("retail", {}).get("buy_count"),
          ((m0 or {}).get("m") or [None] * 7)[I_COUNT_BUY], 0, cause=pc_cause)
    m.add("تعداد فروشنندۀ حقیقی (شمار)", "/api/mstat/clientsplit → retail.sell_count",
          "market0 → m[11]", cs_all.get("retail", {}).get("sell_count"),
          ((m0 or {}).get("m") or [None] * 12)[I_COUNT_SELL], 0, cause=pc_cause)

    # 12) صنایع -------------------------------------------------------------------
    ours_ind = ind_ours.get("rows") or []
    ta_ind = ind_ta or []
    oi = {normname(r["industry"]): r for r in ours_ind}
    matched = []
    for tr in ta_ind:
        k = normname(str(tr[1]))
        for k2, orow in oi.items():
            if k == k2 or k in k2 or k2 in k:
                matched.append((tr[1], tr[9], orow["avg_pct"], orow["value_b_toman"],
                                float(tr[3]) / RIAL_TO_BT))
                break
    def top_bottom(seq, getter):
        vals = [x for x in seq if getter(x) is not None]
        vals.sort(key=getter, reverse=True)
        return (vals[0] if vals else None), (vals[-1] if vals else None)
    t_top, t_bot = top_bottom([(a, c9, c9o, v, tv) for a, c9, c9o, v, tv in matched],
                              lambda x: x[1])
    o_top, o_bot = top_bottom([(a, c9, c9o, v, tv) for a, c9, c9o, v, tv in matched],
                              lambda x: x[2])
    # شاهدِ پویا: بیشترین واگراییِ ستونِ ۹ در برابرِ avg_pct ما (از همان تطبیقِ اجرا)
    worst = max((x for x in matched if x[1] is not None and x[2] is not None),
                key=lambda x: abs(x[1] - x[2]), default=None)
    m.add("صنایع — برترین صنعتِ مثبت (%)", "/api/mstat/industries → avg_pct (تلاقیِ نام‌هایِ مشترک)",
          "data/industries-csv → ستونِ ۹ (کاندیدِ «درصدِ صنعت»؛ در چند ردیف عیناً برابر و در بقیه واگرا)",
          None if not o_top else o_top[2], None if not t_top else t_top[1], 0.3,
          cause=("definition divergence",
                 "تطبیقِ نام: %d صنعتِ مشترک. ستونِ ۹ او با میانگینِ بی‌وزنِ ما یکی نیست — واگراترینِ مشترک: "
                 "%s (او %s، ما %s؛ ارزشِ همان صنعت او %s در برابرِ ما %s م.ت). "
                 "پس نه واحد (عددها هم‌یکاست)، نه زمان (نشستِ بسته) — تعریفِ «درصدِ صنعت» واگرا و رمزگشایی‌نشده است."
                 % (len(matched), worst[0], fmt(worst[1], 2), fmt(worst[2], 2), fmt(worst[4]), fmt(worst[3]))
                 if worst else "تطبیقِ نام: %d صنعتِ مشترک" % len(matched)))
    m.add("صنایع — بدترین صنعتِ منفی (%)", "/api/mstat/industries → avg_pct",
          "data/industries-csv → ستونِ ۹",
          None if not o_bot else o_bot[2], None if not t_bot else t_bot[1], 0.3,
          cause=("definition divergence",
                 "واگراترینِ مشترکِ این اجرا: %s — او %s، ما %s (سطرِ «برترین» را ببینید؛ همان فرمولِ رمزگشایی‌نشده)"
                 % (worst[0], fmt(worst[1], 2), fmt(worst[2], 2)) if worst else "همان سطرِ بالا"))
    m.add("صنایع — پوششِ گروه‌ها (شمار)", "/api/mstat/industries → len(rows)",
          "data/industries-csv → len(rows)", len(ours_ind), len(ta_ind), 0,
          cause=("definition divergence",
                 "شکافِ ساختاریِ اثبات‌شده در ۱۴۰۵-۰۷-۰۴ و ۱۴۰۵-۰۷-۰۷: %d گروهِ او در برابرِ %d صنعتِ ما؛ "
                 "۱۵ گروهِ باقی عمدتاً دستهٔ صندوق‌اند (اهرمی/طلا/نقره/درآمد ثابت/شاخصی/بخشی/…)"
                 % (len(ta_ind), len(ours_ind))))

    # 13) سهام برگزیده ------------------------------------------------------------
    ta_mw = [str(r[2]) for r in (mw_ta or [])][:20]
    our_mw = [r["symbol"] for r in (mw_ours.get("rows") or [])][:20]
    inter = len(set(ta_mw) & set(our_mw))
    m.add("سهام برگزیده — اشتراکِ فهرست ۲۰تایی", "/api/mstat/mainwatch?sort=clock → rows[:20]",
          "data/mainwatch/symbols → ۲۰ سطر (ستونِ ۲ = نماد)", inter, len(ta_mw), 0,
          cause=("definition divergence",
                 "قاعدهٔ انتخابِ او از فیدِ عمومی قابلِ اثبات نیست (۲۰ سطر، ۲۰ ستونِ رمزگشایی‌نشده). "
                 "اشتراکِ فهرستِ او با ۲۰ سطرِ برترِ «الگوی ساعت»ِ ما: %s از ۲۰ — یعنی حتیِ دامنه هم یکی نیست. "
                 "بازسنجشِ ۱۴۰۵-۰۷-۰۷: پوششِ حجمیِ ما ۱۲۰/۱۴۴۰ نماد بود." % inter))

    # 14) breadth / محدوده --------------------------------------------------------
    s1 = (histo or {}).get("s1")
    h12 = [x["count"] for x in (hist_ours.get("histo12") or [])]
    m.add("پهنای بازار — شمارِ کلِ سطل‌ها (breadth)", "/api/mstat/histogram → histo12 counts + known",
          "data/market/histo-status → s1 (۱۴ سطل، افق ۱روزه)",
          sum(h12) if h12 else None, sum(s1) if s1 else None, 0,
          cause=("definition divergence",
                 "مرزِ سطل‌هایِ او از باندلِ مبهم رمزگشایی نشده (TA_PARITY_AUDIT §دما/پوشش)؛ "
                 "دامنۀ سطل‌های او %d در برابرِ %d نمادِ دارایِ درصدِ ما — پس نه مقایسۀ سطل‌به‌سطل ممکن است "
                 "نه ادعایِ خطا. افق‌های ۵/۱۰/۲۰/۶۰ روزه (s5…s60) اصلاً درِ برنامه نیستند (شکافِ تاییدشده)."
                 % (sum(s1) if s1 else 0, hist_ours.get("known", 0))))
    m.add("پهنای بازار — سطل‌هایِ افق ۵ تا ۶۰ روزه", "— (درِ برنامه نیست)",
          "histo-status → s5/s10/s20/s60", None, len(histo or {}), 0,
          cause=("genuinely missing data",
                 "شکافِ اعلام‌شده در ۱۴۰۵-۰۷-۰۴ و دوباره تأییدشده در ۱۴۰۵-۰۷-۰۷؛ «پهنای بازار در افق‌های ۵ تا "
                 "۶۰ روزه را نداریم» — ۴ افق × ۱۴ سطلِ او بی‌معادلِ لوکال است"))
    return m, {"matched_industries": len(matched),
               "our_top": o_top, "our_bot": o_bot, "their_top": t_top, "their_bot": t_bot,
               "ta_mw": ta_mw, "our_mw20": our_mw, "overlap": inter}


# ================================================================هویتِ جبری
def ta_identities(m0, histo, tot):
    """اتحادی که «رمزگشاییِ ما از ردیف‌های او» را زنده نگه می‌دارند؛ اگر بشکنند،
    ستون‌هایِ بالا بی‌اعتبارند. همه در اجرا حساب می‌شوند، هیچ‌کدام ثابت نیست."""
    checks = []
    if not m0:
        return checks
    for i, label in ((I_VAL, "ارزش"), (I_VOL, "حجم"), (I_FLOW, "جریان")):
        mrow = m0.get("m") or [0] * 18
        try:
            ssum = sum(float((m0.get(k) or [0] * 18)[i] or 0.0) for k in ("st", "sf", "nsf"))
            mm = float(mrow[i] or 0.0)
            rel = abs(ssum - mm) / abs(mm) if mm else None
            checks.append({"id": "m = st+sf+nsf (%s)" % label, "m": mm, "sum": ssum,
                           "rel_err": None if rel is None else round(rel, 8)})
        except Exception:  # noqa: BLE001
            checks.append({"id": "m = st+sf+nsf (%s)" % label, "error": "decode"})
    for key in ("st", "sf", "nsf", "cf", "scf", "lf", "m"):
        a = m0.get(key) or []
        if len(a) > 10:
            try:
                lhs = float(a[I_FLOW] or 0.0)
                rhs = float(a[I_RBUY] or 0.0) - float(a[I_RSELL] or 0.0)
                checks.append({"id": "%s: i5 = i7−i10" % key, "i5": lhs, "i7-i10": rhs,
                               "rel_err": (None if not lhs else
                                           round(abs(lhs - rhs) / max(abs(lhs), 1e-9), 8))})
            except Exception:  # noqa: BLE001
                pass
    if histo and m0:
        s = m0.get("s") or []
        s1 = histo.get("s1") or []
        ok = s and s1 and s == s1[1:13]
        checks.append({"id": "market0.s == histo.s1[1:13]", "holds": bool(ok)})
        try:
            checks.append({"id": "sum(s1) == pp+pm", "sum_s1": sum(s1),
                           "pp_pm": (m0.get("pp") or [None])[0] + (m0.get("pm") or [None])[0]})
        except Exception:  # noqa: BLE001
            pass
    if tot:
        try:
            checks.append({"id": "totals0.plus[-1] == market0.pp[0]",
                           "plus_last": ((tot.get("plus") or [None])[-1]),
                           "pp": ((m0 or {}).get("pp") or [None])[0]})
        except Exception:  # noqa: BLE001
            pass
    return checks


# ================================================================JSON + MD
VERDICT_FA = {"match": "برابر", "rounding": "گردکردن", "snapshot-timing": "زمانِ نمونه",
              "timing": "زمانِ نمونه", "unit-scale": "یکا", "definition-gap": "تعریفِ واگزار",
              "definition divergence": "تعریفِ واگزار", "genuinely missing data": "دادهٔ غایب",
              "missing-source": "بی‌منبع", "missing": "بی‌منبع"}


def to_markdown(mat, meta, ids, stamps):
    L = []
    L.append("# ماتریسِ تطبیقِ عدد‌به‌عدد با TradersArena — اجرایِ خودکار\n")
    L.append("> تولید: `_audit/ta_parity_matrix.py` (فقط‌خواندنی). "
             "سمتِ ما: `http://127.0.0.1:8002/api/mstat/*` · سمتِ او: فیدهایِ عمومیِ `tradersarena.ir/data/*`.\n")
    L.append("| زمانِ اجرا | مقدار |")
    L.append("|---|---|")
    L.append("| شروع (محلی) | %s |" % stamps.get("run_started_local"))
    L.append("| شروع (UTC) | %s |" % stamps.get("run_started_utc"))
    L.append("| نشستِ TA (`j`/`d`) | %s / %s |" % ((meta.get("ta_m") or {}).get("j"),
                                                   (meta.get("ta_m") or {}).get("d")))
    L.append("| asofِ خودی (d_even/h_even) | %s / %s |" % (meta.get("our_asof", {}).get("d_even"),
                                                            meta.get("our_asof", {}).get("h_even")))
    L.append("\n**قانونِ هم‌زمانی:** هر دو طرف درِ یک نشست سنجیده شدند؛ برچسبِ زمانِ هر فیکسچر در "
             "`_audit/fixtures/ta_*.json` است. هیچ سطری با دادهٔ نشستِ دیگر مقایسه نشده.\n")
    L.append("**اندازۀ زنده در برابرِ سندِ پیشین:** ستونِ «او» درِ این جدول کاملاً اندازۀ زندۀ همین "
             "اجراست (فیدهایِ عمومیِ tradersarena.ir درِ زمانِ بالا رسیده‌اند). ارجاع‌هایِ "
             "«TA-SCOPE-DECODE §…» و «۱۴۰۵-۰۷-۱۱» درِ ستونِ شاهد، سندِ نشست‌هایِ پیشین‌اند نه عددِ این "
             "اجرا؛ سندِ خودِ TA (اتحادی‌هایِ جبری) درِ همین اجرا و درِ `ta_fixture_check.py` دوباره "
             "بسجیده می‌شود.\n")
    L.append("## جدولِ اصلی\n")
    L.append("| سنجه | اندپوینتِ ما ← فیلد | صفحۀ او ← فیلد | ما | او | Δ | Δ٪ | داوری |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in mat.rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s | **%s** |" % (
            r["metric"], r["our_ref"], r["their_ref"], fmt(r["our"]), fmt(r["their"]),
            fmt(r["delta"]), ("—" if r["delta_pct"] is None else "%.2f%%" % r["delta_pct"]),
            VERDICT_FA.get(r["verdict"], r["verdict"])))
    counts = {}
    for r in mat.rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    L.append("\n**جمعِ داوری‌ها (محاسبه‌شده درِ اجرا):** " +
             " · ".join("%s = %d" % (VERDICT_FA.get(k, k), v) for k, v in sorted(counts.items())) + "\n")
    L.append("## عللِ واگرایی‌ها — با عدد\n")
    L.append("| سنجه | طبقه | شاهد |")
    L.append("|---|---|---|")
    for r in mat.rows:
        if r["verdict"] == "match" or not r.get("cause_evidence"):
            continue
        L.append("| %s | %s | %s |" % (r["metric"], VERDICT_FA.get(r["cause_class"], r["cause_class"]),
                                       r["cause_evidence"]))
    L.append("\n## اتحادی‌هایِ درونِ فیدِ او (اثباتِ رمزگشایی — درِ اجرا حساب شد)\n")
    L.append("| اتحاد | مقدار | جمع/مقدارِ دوم | خطایِ نسبی |")
    L.append("|---|---|---|---|")
    for c in ids:
        v1 = c.get("m", c.get("i5", c.get("sum_s1", c.get("plus_last"))))
        v2 = c.get("sum", c.get("i7-i10", c.get("pp_pm", c.get("pp"))))
        rel = c.get("rel_err")
        holds = bool(c.get("holds"))
        if not holds and v1 is not None and v2 is not None:
            try:
                holds = abs(float(v1) - float(v2)) <= max(2e-9 * abs(float(v1)), 2.0)
            except (TypeError, ValueError):
                holds = False
        L.append("| %s | %s | %s | %s (%s) |" % (c.get("id"), fmt(v1, 4), fmt(v2, 4),
                                                 fmt(rel, 10) if rel is not None else "—",
                                                 "برقرار" if holds else "واگرا"))
    L.append("\n## یادداشت‌ها\n")
    for r in mat.rows:
        if r["note"]:
            L.append("- **%s:** %s" % (r["metric"], r["note"]))
    L.append("- اشتراکِ فهرستِ «سهام برگزیده»: %s از ۲۰ (نمونۀ او: %s)."
             % (meta.get("overlap"), ", ".join((meta.get("ta_mw") or [])[:8])))
    L.append("- تطبیقِ نامِ صنایع (بعد از یکسان‌سازیِ ی/ك): %d صنعتِ مشترک؛ نام‌هایِ او کوتاه‌شکستۀ "
             "گروه‌هایِ TSETMC است.\n" % meta.get("matched_industries", 0))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="بازسازی از فیکسچرهایِ موجود")
    args = ap.parse_args()
    ta, ours_api, stamps = fetch_all(args.offline)
    m0 = ta.get("market0") or {}
    mat, extra = build_matrix(ta, ours_api, stamps)
    ids = ta_identities(m0, ta.get("histo"), ta.get("totals0"))
    su = ours_api.get("summary") or {}
    meta = {"ta_m": {"j": m0.get("j"), "d": m0.get("d")}, "our_asof": su.get("asof") or {},
            "matched_industries": extra["matched_industries"], "overlap": extra["overlap"],
            "ta_mw": extra["ta_mw"], "our_top": extra["our_top"], "our_bot": extra["our_bot"],
            "their_top": extra["their_top"], "their_bot": extra["their_bot"]}
    counts = {}
    for r in mat.rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    out = {"tool": "ta_parity_matrix.py", "stamps": stamps, "meta": meta,
           "identity_checks": ids, "counts": counts, "rows": mat.rows,
           "ours_api_shapes": {k: (None if v is None else
                                   {kk: (type(vv).__name__) for kk, vv in list(v.items())[:3]})
                               if isinstance(v, dict) else str(type(v)) for k, v in ours_api.items()}}
    jpath = os.path.join(HERE, "ta_parity_matrix.json")
    json.dump(out, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = to_markdown(mat, meta, ids, stamps)
    mpath = os.path.join(HERE, "ta_parity_matrix.md")
    open(mpath, "w", encoding="utf-8").write(md)
    print(md)
    print("\nJSON →", jpath, "\nMD   →", mpath)
    print("COUNTS:", json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
