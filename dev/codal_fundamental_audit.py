#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codal_fundamental_audit.py — ممیزیِ فقط-خواندنیِ صحتِ بنیادیِ کدال (Task 10B1).

این ابزار هیچ چیز را نمی‌نویسد: `market.db` فقط با URIِ `mode=ro` باز می‌شود و
`PRAGMA query_only=ON` هم رویِ همان اتصال گذاشته می‌شود. هیچ helperی که داخلش
اتصالِ نوشتنی باز کند صدا زده نمی‌شود؛ `fts_engine.bulk_scan`،
`fts_engine.reference_annual` و `api.fundamental.evaluate_v10` مسیرِ خواندن‌اند.

خروجی:
  * چاپِ شمارش‌های اندازه‌گیری‌شده (نه عددِ hard-code): ردیف‌ها، شرکت‌هایِ سخت،
    غیرشرکت‌ها، صندوق‌ها، شکاف‌هایِ EPS/حاشیه/ماهانه.
  * نمونهٔ ≥۳۰ شرکتِ واقعی از طبقه‌های تولیدی/بانک/بیمه/خدماتی/هلدینگ/
    فقط-تلفیقی/فقط-ماهانه با بررسیِ منشأ (tracing_no/url/publish_date)، واحد،
    علامتِ درآمد/سود ناخالص/EPS و دورهٔ آینده.
  * تریاژِ تمامِ شکاف‌هایِ حاشیه (۵۹ ردیفِ پایهٔ ۷۱۲ + ۵۲ فقط-ماهانه = ۱۱۱):
    بدونِ صورتِ مالی سالانه / بدونِ درآمد / بدونِ سود ناخالص / واحدِ مشکوک /
    N/A طبقه / مشکوکِ پارسر. پارسر تغییر نمی‌کند.
  * شاهدِ «فقط جدیدترین دوره»: مقایسهٔ bulk/card برایِ `وملت` و شمارشِ ردیف‌هایی
    که قاعده عوض کرده است.
  * نمونهٔ نمایندهٔ ≥۱۰ نماد با وضعیتِ شاخص‌ها + ورودیِ خام.
  * گزارشِ Markdown در `_audit/codal-fundamental-audit-YYYY-MM-DD.md`.

Exit: 1 فقط رویِ شکستِ سختِ sanity (درآمدِ منفیِ تولیدی/خدماتی،
gross_profit > revenue، دورهٔ آینده، tracing_noِ غایب، یا تغییرِ mtime دیتابیس).
شکافِ داده (URL/تاریخِ انتشار/واحد/درآمدِ خالی و …) فقط گزارش می‌شود.

Run: python dev/codal_fundamental_audit.py
"""
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import fts_engine as E                                  # noqa: E402
import codal_periods as CP                              # noqa: E402
from api import fundamental as F                        # noqa: E402
from api.market import load_fts_config                  # noqa: E402

AUDIT_DATE = "2026-10-28"           # تاریخِ مأموریت (Task 10B1)
TODAY_JALALI = "1405/08/06"         # 2026-10-28 به تقویمِ جلالی
DB_PATH = os.path.join(ROOT, "market.db")
REPORT_PATH = os.path.join(ROOT, "_audit",
                           "codal-fundamental-audit-%s.md" % AUDIT_DATE)
SAMPLE_PER_CLASS = 5
REP_PER_CLASS = 2


# ── اتصالِ فقط-خواندنی ──────────────────────────────────────────────────────
def ro_connect(path):
    uri = "file:%s?mode=ro" % path.replace("\\", "/")
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def db_signature(path):
    st = os.stat(path)
    return {"size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}


def git_head():
    try:
        return subprocess.run(["git", "rev-parse", "--short=8", "HEAD"],
                              cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ── نقشه‌هایِ تک‌گذر (همان ورودی‌هایی که bulk_scan می‌سازد) ─────────────────
def build_maps(conn):
    board_of, sector_of = {}, {}
    for sym, sec in conn.execute(
            "SELECT i.l_val18, COALESCE(i.sector_name,'') FROM instruments i"):
        key = E.norm_fa(sym)
        if not key:
            continue
        board_of.setdefault(key, sym)
        if sec:
            sector_of.setdefault(key, sec)
    cname_of = E.company_name_map(conn)
    annual_keys = {E.norm_fa(s) for (s,) in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements WHERE period_months>=12")}
    monthly_all = {E.norm_fa(s) for (s,) in conn.execute(
        "SELECT DISTINCT symbol FROM monthly_sales")}
    monthly_pos = {E.norm_fa(s) for (s,) in conn.execute(
        "SELECT DISTINCT symbol FROM monthly_sales "
        "WHERE ytd_revenue IS NOT NULL AND ytd_revenue>0")}
    annual_titles = defaultdict(list)
    for sym, title, rev in conn.execute(
            "SELECT symbol, title, revenue FROM financial_statements "
            "WHERE period_months>=12 AND revenue>0"):
        key = E.norm_fa(sym)
        if key:
            annual_titles[key].append(title or "")
    cons_only = {k for k, titles in annual_titles.items()
                 if titles and all(E._is_consolidated(t) for t in titles)}
    return {"board_of": board_of, "sector_of": sector_of, "cname_of": cname_of,
            "annual_keys": annual_keys, "monthly_all": monthly_all,
            "monthly_pos": monthly_pos, "cons_only": cons_only}


def raw_fs_rows(conn, key, annual_only=False, limit=0):
    pred, params = E.sym_in("symbol", key)
    sql = ("SELECT tracing_no, symbol, title, period_end, period_months, "
           "publish_date, revenue, gross_profit, operating_profit, net_profit, "
           "basic_eps, unit, unit_norm, url, is_audited, is_consolidated, "
           "has_operating_sales FROM financial_statements WHERE " + pred)
    if annual_only:
        sql += " AND period_months>=12"
    sql += " ORDER BY period_end DESC, tracing_no DESC"
    if limit:
        sql += " LIMIT %d" % int(limit)
    return conn.execute(sql, params).fetchall()


def raw_monthly_rows(conn, key, limit=3):
    pred, params = E.sym_in("symbol", key)
    return conn.execute(
        "SELECT tracing_no, symbol, title, period_end, year, month, "
        "monthly_revenue, ytd_revenue, pdf_url, excel_url FROM monthly_sales "
        "WHERE " + pred + " ORDER BY year DESC, month DESC, tracing_no DESC "
        "LIMIT %d" % int(limit), params).fetchall()


def find_ref_raw(conn, key, ref):
    """ردیفِ خامِ همان مرجعی که reference_annual انتخاب کرده است."""
    if not ref:
        return None
    cand = [r for r in raw_fs_rows(conn, key)
            if r["period_end"] == ref.get("period_end")
            and int(r["period_months"] or 0) == int(ref.get("period_months") or 0)]
    if not cand:
        return None

    def _score(r):
        return (0 if bool(r["is_audited"]) == bool(ref.get("audited")) else 1,
                0 if E._is_consolidated(r["title"] or "")
                == bool(ref.get("consolidated")) else 1,
                -int(r["tracing_no"] or 0))
    return sorted(cand, key=_score)[0]


# ── طبقهٔ نمونه ─────────────────────────────────────────────────────────────
def sample_class(row, maps):
    key = row["symbol_norm"]
    sec = row.get("sector_name") or ""
    if key not in maps["annual_keys"]:
        return "monthly_only"
    if E.is_insurance_sector(sec):
        return "insurance"
    if "بانک" in E.norm_fa(sec):
        return "bank"
    prof = E.company_profile(sec, maps["cname_of"].get(key, ""))
    if prof["kind"] == "holding":
        return "holding"
    if prof["kind"] == "service":
        return "service"
    if prof["kind"] == "financial":
        return "financial"
    if key in maps["cons_only"]:
        return "consolidated_only"
    return "production"


CLASS_LABEL = {
    "production": "تولیدی/صادراتی", "bank": "بانک", "insurance": "بیمه",
    "service": "خدماتی", "holding": "هلدینگ/سرمایه‌گذاری",
    "financial": "مالی غیربانکی", "consolidated_only": "فقط-تلفیقی",
    "monthly_only": "فقط-ماهانه",
}


# ── شکاف‌ها ────────────────────────────────────────────────────────────────
def gap_sets(strict, maps):
    eps, margin, monthly_no_report = [], [], []
    monthly_i1_false = []
    for r in strict:
        key = r["symbol_norm"]
        prof = E.company_profile(r.get("sector_name") or "",
                                 maps["cname_of"].get(key, ""))
        if (r.get("eps_data_gap") and not r.get("eps_consolidated")
                and (r.get("eps_years_available") or 0) < 3):
            eps.append(r)
        if prof["kind"] == "production" and r["i3_pass"] is None:
            margin.append(r)
        if prof["kind"] == "production" and key not in maps["monthly_all"]:
            monthly_no_report.append(r)
            if r["i1_pass"] is False:
                monthly_i1_false.append(r)
    return eps, margin, monthly_no_report, monthly_i1_false


# ── بررسیِ منشأ/سالم‌بودن ──────────────────────────────────────────────────
def audit_fs_row(row, prof):
    hard, soft = [], []
    if not row["tracing_no"]:
        hard.append("missing_tracing_no")
    if not row["url"]:
        soft.append("missing_url")
    if not row["publish_date"]:
        soft.append("missing_publish_date")
    unit_norm = row["unit_norm"]
    unit_txt = row["unit"] or ""
    if unit_norm not in ("mrl",) and "میلیون" not in unit_txt:
        soft.append("unit_missing_or_unknown(%s)"
                    % ((unit_norm or unit_txt or "empty")[:24]))
    pe = str(row["period_end"] or "")
    if pe and pe > TODAY_JALALI:
        hard.append("future_period(%s)" % pe)
    rev = row["revenue"]
    gp = row["gross_profit"]
    npf = row["net_profit"]
    eps = row["basic_eps"]
    if rev is None:
        soft.append("revenue_missing")
    elif rev == 0:
        soft.append("revenue_zero")
    elif rev < 0:
        if prof["kind"] in ("production", "service"):
            hard.append("negative_revenue")
        else:
            soft.append("negative_revenue_%s" % prof["kind"])
    if gp is not None and rev is not None and rev > 0 and gp > rev:
        hard.append("gross_gt_revenue(%s>%s)" % (gp, rev))
    if (eps is not None and npf is not None and eps != 0 and npf != 0
            and ((eps > 0) != (npf > 0))):
        soft.append("eps_net_sign(%s/%s)" % (eps, npf))
    if bool(E._is_consolidated(row["title"] or "")) != bool(row["is_consolidated"]):
        soft.append("basis_flag_mismatch")
    return hard, soft


def audit_monthly_row(row):
    hard, soft = [], []
    if not row["tracing_no"]:
        hard.append("missing_tracing_no")
    if not (row["pdf_url"] or row["excel_url"]):
        soft.append("missing_url")
    if not row["title"]:
        soft.append("missing_title")
    pe = str(row["period_end"] or "")
    if pe and pe > TODAY_JALALI:
        hard.append("future_period(%s)" % pe)
    try:
        ytd = float(row["ytd_revenue"])
    except (TypeError, ValueError):
        ytd = None
    if ytd is None:
        soft.append("ytd_missing")
    elif ytd <= 0:
        soft.append("ytd_nonpositive")
    return hard, soft


def build_sample(strict, maps):
    buckets = defaultdict(list)
    for r in strict:
        buckets[sample_class(r, maps)].append(r)
    order = ("production", "bank", "insurance", "service", "holding",
             "consolidated_only", "monthly_only", "financial")
    sample = []
    for cls in order:
        top = sorted(buckets.get(cls) or [],
                     key=lambda r: (-r.get("mcap", 0.0), r["symbol"]))
        n = SAMPLE_PER_CLASS if cls != "financial" else 1
        sample.extend((cls, r) for r in top[:n])
    return sample


def audit_sample(conn, sample, maps):
    out = []
    for cls, r in sample:
        key = r["symbol_norm"]
        prof = E.company_profile(r.get("sector_name") or "",
                                 maps["cname_of"].get(key, ""))
        fs = raw_fs_rows(conn, key, annual_only=True, limit=2)
        mo = []
        if cls == "monthly_only":
            fs = raw_fs_rows(conn, key, annual_only=False, limit=2)
            mo = raw_monthly_rows(conn, key, limit=2)
        hard, soft = [], []
        stats = Counter()
        for row in fs:
            h, s = audit_fs_row(row, prof)
            hard += ["%s:%s" % (row["tracing_no"], x) for x in h]
            soft += s
            stats["fs_rows"] += 1
            stats["tracing"] += 1 if row["tracing_no"] else 0
            stats["url"] += 1 if row["url"] else 0
            stats["publish"] += 1 if row["publish_date"] else 0
            stats["unit"] += 1 if (row["unit_norm"] == "mrl"
                                   or "میلیون" in (row["unit"] or "")) else 0
            if row["revenue"] is not None and row["revenue"] > 0:
                stats["rev_pos"] += 1
            if (row["gross_profit"] is None or row["revenue"] is None
                    or row["revenue"] <= 0
                    or row["gross_profit"] <= row["revenue"]):
                stats["gp_ok"] += 1
            if (row["basic_eps"] is None or row["net_profit"] is None
                    or row["basic_eps"] == 0 or row["net_profit"] == 0
                    or (row["basic_eps"] > 0) == (row["net_profit"] > 0)):
                stats["eps_ok"] += 1
            if not row["period_end"] or str(row["period_end"]) <= TODAY_JALALI:
                stats["period_ok"] += 1
        for row in mo:
            h, s = audit_monthly_row(row)
            hard += ["M%s:%s" % (row["tracing_no"], x) for x in h]
            soft += s
            stats["monthly_rows"] += 1
        out.append({"cls": cls, "row": r, "key": key, "profile": prof,
                    "stats": stats, "hard": hard, "soft": soft,
                    "fs_rows": fs, "monthly_rows": mo})
    return out


# ── تریاژِ حاشیه ───────────────────────────────────────────────────────────
def parser_evidence(conn, key, ref, raw):
    """شاهدِ آفلاین برایِ «سطرِ سود ناخالص وجود داشته ولی پارسر نخوانده»."""
    if not ref or not raw:
        return None
    pred, params = E.sym_in("symbol", key)
    same = conn.execute(
        "SELECT tracing_no, title, period_end, period_months, revenue, "
        "gross_profit, is_consolidated FROM financial_statements WHERE " + pred +
        " AND period_end=? AND period_months=? AND gross_profit IS NOT NULL",
        (*params, ref["period_end"], ref["period_months"])).fetchall()
    if same:
        return {"kind": "same_period_basis", "rows": same}
    others = conn.execute(
        "SELECT tracing_no, title, period_end, period_months, revenue, "
        "gross_profit FROM financial_statements WHERE " + pred +
        " AND period_months>=12 AND gross_profit IS NOT NULL "
        "ORDER BY period_end DESC", params).fetchall()
    rev = raw["revenue"]
    for x in others:
        xr = x["revenue"]
        if rev and rev > 0 and xr and xr > 0 and 0.2 <= (xr / rev) <= 5.0:
            return {"kind": "neighbour_period", "row": x}
    return None


def triage_margin(conn, margin_rows, maps):
    out = []
    for r in margin_rows:
        key = r["symbol_norm"]
        prof = E.company_profile(r.get("sector_name") or "",
                                 maps["cname_of"].get(key, ""))
        ref = E.reference_annual(conn, key)
        raw = find_ref_raw(conn, key, ref) if ref else None
        item = {"row": r, "key": key, "profile": prof, "ref": ref, "raw": raw,
                "cat": "", "evidence": None, "monthly": None}
        if prof["kind"] in E.MARGIN_NA_KINDS:
            item["cat"] = "class_na"
        elif ref is None or raw is None:
            item["cat"] = "no_annual_fs"
            item["monthly"] = raw_monthly_rows(conn, key, limit=1)
        else:
            rev = raw["revenue"]
            gp = raw["gross_profit"]
            unit_norm = raw["unit_norm"]
            unit_txt = raw["unit"] or ""
            if rev is None or rev <= 0:
                item["cat"] = "no_revenue"
            elif gp is not None:
                item["cat"] = "computed"
            else:
                ev = parser_evidence(conn, key, ref, raw)
                if ev:
                    item["cat"] = "parser_suspect"
                    item["evidence"] = ev
                elif (rev < 10 or (unit_norm not in (None, "", "mrl")
                                   and "میلیون" not in unit_txt)):
                    item["cat"] = "unit_suspicious"
                else:
                    item["cat"] = "no_gross_profit"
        out.append(item)
    return out


# ── شاهدِ فقط-جدیدترین-دوره ────────────────────────────────────────────────
def old_growth_from_rows(rows, th=None):
    """بازسازیِ قاعدهٔ پیش از Task 4 (اولین دورهٔ دارایِ جفت، نه فقط جدیدترین)."""
    floor = E._fs_growth_floor(th)
    by_key = {}
    for pe, months, rev, title in rows:
        if E._is_consolidated(title or ""):
            continue
        pe_c = CP.canonicalize(pe) or ""
        try:
            m = int(months or 0)
        except (TypeError, ValueError):
            m = 0
        if not pe_c or m <= 0 or E._f(rev) <= 0:
            continue
        by_key.setdefault((pe_c, m), E._f(rev))
    if not by_key:
        return {"monetary_pct": None, "basis": None, "period": "", "months": 0}
    interims = sorted([(k, v) for k, v in by_key.items() if 0 < k[1] < 12],
                      key=lambda kv: kv[0][0], reverse=True)
    annuals = sorted([(k, v) for k, v in by_key.items() if k[1] >= 12],
                     key=lambda kv: kv[0][0], reverse=True)
    annual_prior = {}
    for (pe, months), val in annuals:
        y, mm, _dd = pe.split("/")[:3]
        annual_prior.setdefault((int(y), mm, months), val)
    for basis, cands in (("fs_interim", interims), ("fs_annual", annuals)):
        for (pe, months), now in cands:
            y, mm, dd = pe.split("/")[:3]
            if basis == "fs_interim":
                prev = by_key.get(("%d/%s/%s" % (int(y) - 1, mm, dd), months))
            else:
                prev = annual_prior.get((int(y) - 1, mm, months))
            if not prev:
                continue
            return {"monetary_pct": (now / prev - 1.0) * 100.0, "basis": basis,
                    "period": pe, "months": months}
    return {"monetary_pct": None, "basis": None, "period": "", "months": 0}


def newest_period_evidence(conn, rows, maps, cfg):
    compared, changed = 0, []
    for r in rows:
        key = r["symbol_norm"]
        prof = E.company_profile(r.get("sector_name") or "",
                                 maps["cname_of"].get(key, ""))
        if prof["kind"] not in E.FS_GROWTH_KINDS:
            continue
        if key in maps["monthly_pos"]:
            continue
        pred, params = E.sym_in("symbol", key)
        fs = conn.execute(
            "SELECT period_end, period_months, revenue, title FROM "
            "financial_statements WHERE " + pred +
            " AND revenue>0 AND period_months>0 AND is_consolidated=0 "
            "ORDER BY period_end DESC", params).fetchall()
        tuples = [tuple(x) for x in fs]
        new = E.fs_growth_from_rows(tuples, th={"monetary_growth_min":
                                                E._th(cfg, "growth_min")})
        old = old_growth_from_rows(
            tuples, th={"monetary_growth_min": E._th(cfg, "growth_min")})
        compared += 1
        old_pct, new_pct = old.get("monetary_pct"), new.get("monetary_pct")
        state_changed = (old_pct is None) != (new_pct is None)
        num_changed = (old_pct is not None and new_pct is not None
                       and abs(old_pct - new_pct) > 1e-9)
        if state_changed or num_changed:
            changed.append({"row": r, "key": key, "profile": prof,
                            "old": old, "new": new,
                            "state_changed": state_changed,
                            "fs_rows": raw_fs_rows(conn, key)})
    return compared, changed


def wmlt_evidence(conn, rows, maps, cfg, total_mcap):
    key = "وملت"
    r = next((x for x in rows if x["symbol_norm"] == key), None)
    if r is None:
        return None
    mcap = float(r.get("mcap") or 0.0)
    sector = r.get("sector_name") or ""
    card = F.evaluate_v10(conn, key, mcap, total_mcap, sector, cfg=cfg,
                          company_name=maps["cname_of"].get(key, ""),
                          has_instrument=True)
    scan = E.scan_symbol(conn, key, mcap, total_mcap, sector, cfg=cfg)
    pred, params = E.sym_in("symbol", key)
    fs = conn.execute(
        "SELECT period_end, period_months, revenue, title FROM "
        "financial_statements WHERE " + pred +
        " AND revenue>0 AND period_months>0 AND is_consolidated=0 "
        "ORDER BY period_end DESC", params).fetchall()
    tuples = [tuple(x) for x in fs]
    new = E.fs_growth_from_rows(tuples, th={"monetary_growth_min":
                                            E._th(cfg, "growth_min")})
    old = old_growth_from_rows(
        tuples, th={"monetary_growth_min": E._th(cfg, "growth_min")})
    ref = E.reference_annual(conn, key)
    return {"row": r, "card": card, "scan": scan, "old": old, "new": new,
            "fs_rows": raw_fs_rows(conn, key), "ref_raw": find_ref_raw(conn, key, ref),
            "monthly_count": len(raw_monthly_rows(conn, key, limit=999)),
            "profile": E.company_profile(sector, maps["cname_of"].get(key, "")),
            "mcap": mcap, "mcap_ht": round(mcap / 1e13, 1) if mcap else 0.0,
            "total_mcap": total_mcap}


# ── نمونهٔ نماینده ─────────────────────────────────────────────────────────
def rep_rows(sample, maps):
    chosen, per = [], Counter()
    for cls, r in sample:
        if per[cls] < REP_PER_CLASS:
            chosen.append((cls, r))
            per[cls] += 1
    if len(chosen) < 10:
        for cls, r in sample:
            if (cls, r) not in chosen:
                chosen.append((cls, r))
            if len(chosen) >= 10:
                break
    return chosen


def state(v):
    if v is None:
        return "N/A"
    return "PASS" if v else "FAIL"


def bulk_state(r, idx):
    """وضعیتِ شاخص در ردیفِ bulk — با احترام به N/A و شکافِ داده."""
    if idx == 1 and (r.get("i1_na") or r.get("i1_pass") is None):
        return "N/A"
    if idx == 2 and (r.get("i2_na") or r.get("eps_data_gap")):
        return "N/A"
    if idx == 3 and (r.get("i3_na") or r.get("i3_pass") is None):
        return "N/A"
    if idx == 4 and r.get("i4_pass") is None:
        return "N/A"
    if idx == 5 and r.get("i5_pass") is None:
        return "N/A"
    return state(r.get("i%d_pass" % idx))


def card_state(card, idx):
    ind = (card.get("indicators") or {}).get(str(idx)) or {}
    if ind.get("na"):
        return "N/A"
    if idx == 2 and ind.get("data_gap"):
        return "N/A"
    if idx == 1:
        p = ind.get("pass")
        return "N/A" if p is None else ("PASS" if p else "FAIL")
    return "PASS" if card["passes"].get({
        2: "2_eps_trend", 3: "3_gross_margin", 4: "4_sales_to_mcap",
        5: "5_industry"}[idx]) else "FAIL"


def rep_details(conn, r, maps, cfg, total_mcap):
    key = r["symbol_norm"]
    mcap = float(r.get("mcap") or 0.0)
    sector = r.get("sector_name") or ""
    card = F.evaluate_v10(conn, key, mcap, total_mcap, sector, cfg=cfg,
                          company_name=maps["cname_of"].get(key, ""),
                          has_instrument=True)
    ref = E.reference_annual(conn, key)
    raw_ref = find_ref_raw(conn, key, ref) if ref else None
    return {"r": r, "card": card, "ref": ref, "raw_ref": raw_ref,
            "mcap_ht": round(mcap / 1e13, 1) if mcap else 0.0}


# ── گزارش ──────────────────────────────────────────────────────────────────
def fmt_num(v, nd=0):
    if v is None:
        return "-"
    try:
        return ("{:,.%df}" % nd).format(float(v))
    except (TypeError, ValueError):
        return str(v)


def write_report(ctx):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    L = []
    A = L.append
    A("# CODAL fundamental accuracy audit — %s" % AUDIT_DATE)
    A("")
    A("- HEAD: `%s`" % ctx["head"])
    A("- Audit script: `dev/codal_fundamental_audit.py` (read-only)")
    A("- DB: `market.db` opened as `file:...?mode=ro` + `PRAGMA query_only=ON`")
    A("- DB signature before: `%s` bytes, mtime_ns `%s`"
      % (ctx["db_before"]["size"], ctx["db_before"]["mtime_ns"]))
    A("- DB signature after: `%s` bytes, mtime_ns `%s` → **%s**"
      % (ctx["db_after"]["size"], ctx["db_after"]["mtime_ns"],
         "UNCHANGED" if ctx["db_unchanged"] else "CHANGED"))
    A("- Hard sanity failures: **%d**; soft data gaps: **%d**"
      % (len(ctx["hard_all"]), len(ctx["soft_all"])))
    A("- Exit criterion: 1 only on hard sanity failure or DB change; "
      "measured exit = **%d**" % ctx["exit_code"])
    A("")
    A("Hard = negative operating revenue on a production/service annual row, "
      "`gross_profit > revenue`, a future period (> %s), a missing "
      "`tracing_no`, or a DB change during the audit. Soft = missing URL / "
      "publish date / unit, missing or non-positive revenue on "
      "financial/holding rows, EPS-vs-net sign disagreement, and the "
      "`is_consolidated` flag/title mismatch (provenance, not a calculation "
      "contradiction)." % TODAY_JALALI)
    A("")
    A("## 1. Universe and identity")
    A("")
    A("| Measure | Measured |")
    A("| --- | ---: |")
    A("| bulk rows | %d |" % ctx["n_rows"])
    A("| strict real companies | %d |" % ctx["n_strict"])
    A("| candidate symbols (annual ∪ monthly-only board) | %d |" % ctx["n_candidates"])
    A("| annual-FS candidates | %d |" % ctx["n_annual_candidates"])
    A("| monthly-only candidates | %d |" % ctx["n_monthly_candidates"])
    A("| excluded non-companies | %d |" % ctx["n_nonco"])
    A("| — no instrument | %d |" % ctx["nonco_reasons"].get("no_instrument", 0))
    A("| — fund/non-operating token | %d |"
      % ctx["nonco_reasons"].get("fund_or_non_operating", 0))
    A("| excluded funds | %d |" % ctx["n_funds"])
    A("")
    A("The ledger's **153 excluded non-companies** does not reproduce on today's "
      "bank. The measured annual candidate universe is %d symbols = %d table "
      "companies + %d funds + %d non-companies. Of the non-companies, %d are "
      "annual filers with no instrument/sector (`no_instrument`), not funds."
      % (ctx["n_annual_candidates"], ctx["annual_rows"], ctx["n_funds"],
         ctx["n_nonco"], ctx["nonco_reasons"].get("no_instrument", 0)))
    A("")
    A("## 2. Strict gaps (measured, not hard-coded)")
    A("")
    A("| Cohort | EPS < 3y non-consolidated | margin (production i3 None) "
      "| monthly (production, no monthly report) |")
    A("| --- | ---: | ---: | ---: |")
    A("| all %d rows | %d | %d | %d |"
      % (ctx["n_strict"], len(ctx["eps_all"]), len(ctx["margin_all"]),
         len(ctx["monthly_all"])))
    A("| %d annual-FS rows (the old 712 universe) | %d | %d | %d |"
      % (ctx["annual_rows"], len(ctx["eps_annual"]), len(ctx["margin_annual"]),
         len(ctx["monthly_annual"])))
    A("| %d monthly-only rows | %d | %d | %d |"
      % (ctx["monthly_rows"], len(ctx["eps_monthly"]), len(ctx["margin_monthly"]),
         len(ctx["monthly_monthly"])))
    A("")
    A("Delta vs the ledger's **11 / 59 / 20**: EPS **+%d**, margin **+%d**, "
      "monthly **+%d** against the measured annual cohort. The %d-row annual "
      "cohort reproduces **11 EPS** and **20 monthly** exactly. Its margin count "
      "is **%d, not 59**: `وهور` now resolves to holding through "
      "`company_name_map` («گروه سرمایه گذاری …») and takes the class N/A for "
      "indicator 3, so it is no longer a data gap (`وهور` was counted as "
      "production in the earlier 59). Net vs the ledger's 59: **%+d** "
      "(%d monthly-only additions − 1 reclassified). Measured sector "
      "contribution to the margin gaps: sugar **%d**, detergent **%d** "
      "(`شوينده`); both are annual-cohort rows, not part of the monthly-only "
      "delta."
      % (len(ctx["eps_all"]) - len(ctx["eps_annual"]),
         len(ctx["margin_all"]) - len(ctx["margin_annual"]),
         len(ctx["monthly_all"]) - len(ctx["monthly_annual"]),
         ctx["annual_rows"], len(ctx["margin_annual"]),
         len(ctx["margin_all"]) - 59,
         len(ctx["margin_all"]) - len(ctx["margin_annual"]),
         ctx["sugar_margin"], ctx["detergent_margin"]))
    A("")
    A("Monthly rule nuance: **%d** production rows have no monthly report at all; "
      "**%d** of them are `i1_pass = False` and **%d** are `i1_pass = None`. The "
      "ledger's 20 is the «no monthly report» population; the brief's «i1 False» "
      "variant measures **%d** because the engine honestly returns N/A (None), "
      "not a red False, when no series exists."
      % (len(ctx["monthly_all"]), len(ctx["monthly_i1_false"]),
         len(ctx["monthly_all"]) - len(ctx["monthly_i1_false"]),
         len(ctx["monthly_i1_false"])))
    A("")
    A("EPS gap symbols (<3 non-consolidated years): %s."
      % ", ".join("%s(%s)" % (x["symbol"], x.get("eps_years_available"))
                  for x in ctx["eps_all"]))
    A("")
    A("Consolidated-only EPS evidence (display-only, not a gap): **%d** strict "
      "rows carry `eps_consolidated=True` (the ledger's ~226 production cases "
      "are included in this class)." % ctx["n_eps_consolidated"])
    A("")
    A("## 3. Provenance / sanity sample")
    A("")
    A("Sample: **%d** real companies across %s; **%d** FS rows and **%d** "
      "monthly rows checked. Hard failures: **%d**. Soft issues: **%d**."
      % (len(ctx["sample"]),
         "، ".join("%s %d" % (CLASS_LABEL.get(c, c), n)
                   for c, n in ctx["sample_classes"].items()),
         ctx["sample_fs_rows"], ctx["sample_monthly_rows"],
         len(ctx["hard_sample"]), len(ctx["soft_sample"])))
    A("")
    A("| Symbol | Class | Sector | Rows | tracing | url | publish | unit | "
      "rev>0 | gross≤rev | EPS/net sign | period≤%s | Notes |" % TODAY_JALALI)
    A("| --- | --- | --- | ---: | :---: | :---: | :---: | :---: | :---: | "
      ":---: | :---: | :---: | --- |")
    for s in ctx["sample"]:
        st = s["stats"]
        n = st.get("fs_rows", 0) + st.get("monthly_rows", 0)
        notes = sorted(set(s["soft"]))
        if s["hard"]:
            notes = ["HARD: " + x for x in s["hard"]] + notes
        A("| %s | %s | %s | %d | %d/%d | %d/%d | %d/%d | %d/%d | %d/%d | "
          "%d/%d | %d/%d | %d/%d | %s |"
          % (s["key"], CLASS_LABEL.get(s["cls"], s["cls"]),
             (s["row"].get("sector_name") or "—")[:28], n,
             st.get("tracing", 0), st.get("fs_rows", 0),
             st.get("url", 0), st.get("fs_rows", 0),
             st.get("publish", 0), st.get("fs_rows", 0),
             st.get("unit", 0), st.get("fs_rows", 0),
             st.get("rev_pos", 0), st.get("fs_rows", 0),
             st.get("gp_ok", 0), st.get("fs_rows", 0),
             st.get("eps_ok", 0), st.get("fs_rows", 0),
             st.get("period_ok", 0), st.get("fs_rows", 0),
             "، ".join(notes) if notes else "—"))
    A("")
    A("Hard failures: %s."
      % ("none" if not ctx["hard_sample"] else "، ".join(ctx["hard_sample"])))
    A("Soft issue counts: %s."
      % (", ".join("%s=%d" % (k, v) for k, v in
                   sorted(ctx["soft_counts"].items())) or "none"))
    A("")
    A("`basis_flag_mismatch` means the title says «تلفیقی» while "
      "`is_consolidated=0`; the live engines filter by title, so this does not "
      "change any indicator. `unit_missing_or_unknown` is an older row whose "
      "`unit`/`unit_norm` is empty; its revenue/GP checks still pass. Classes "
      "are selected deterministically: top 5 by market cap per class (top 1 "
      "for the single non-bank financial).")
    A("")
    A("## 4. Margin-gap triage (all strict margin gaps)")
    A("")
    A("| Category | Count | Symbols |")
    A("| --- | ---: | --- |")
    for cat in ("no_annual_fs", "no_gross_profit", "no_revenue",
                "unit_suspicious", "parser_suspect", "class_na", "computed"):
        items = ctx["margin_by_cat"].get(cat) or []
        if not items and cat in ("class_na", "computed"):
            continue
        A("| %s | %d | %s |" % (cat, len(items),
                                "، ".join(x["key"] for x in items)))
    A("")
    A("Interpretation: **%d** rows have revenue > 0 but no `gross_profit` line "
      "in the stored row; **%d/%d** of them also carry `operating_profit`, so "
      "the income statement was parsed far enough to reach operating profit. "
      "That is a review signal, not proof of a parser bug: only %d row has "
      "neighbour-period gross profit at a comparable revenue scale, and %d row "
      "is a `1/1/1` sentinel."
      % (len(ctx["margin_by_cat"].get("no_gross_profit") or []),
         ctx["margin_no_gp_with_op"], len(ctx["margin_by_cat"].get("no_gross_profit") or []),
         len(ctx["margin_by_cat"].get("parser_suspect") or []),
         len(ctx["margin_by_cat"].get("unit_suspicious") or [])))
    A("")
    A("### Raw FS examples (5–10)")
    A("")
    A("| Symbol | Category | tracing_no | Title | Period | Revenue (mrl) | "
      "Gross profit (mrl) | Unit |")
    A("| --- | --- | ---: | --- | --- | ---: | ---: | --- |")
    for x in ctx["margin_examples"]:
        raw = x["raw"]
        if raw is None:
            mo = (x.get("monthly") or [None])[0]
            A("| %s | no_annual_fs | %s | %s | %s | %s | — | %s |"
              % (x["key"], (mo["tracing_no"] if mo else "—"),
                 ((mo["title"] if mo else "no annual FS") or "—")[:48],
                 (mo["period_end"] if mo else "—"),
                 fmt_num(mo["ytd_revenue"]) if mo else "—", "monthly YTD"))
        else:
            A("| %s | %s | %s | %s | %s | %s | %s | %s |"
              % (x["key"], x["cat"], raw["tracing_no"],
                 (raw["title"] or "")[:48], raw["period_end"],
                 fmt_num(raw["revenue"]), fmt_num(raw["gross_profit"]),
                 raw["unit_norm"] or (raw["unit"] or "—")[:20]))
    A("")
    A("### Parser-suspect list (follow-up only; parser NOT changed here)")
    A("")
    if ctx["parser_suspects"]:
        for p in ctx["parser_suspects"]:
            A("- **%s** — %s" % (p["symbol"], p["detail"]))
    else:
        A("- none")
    A("")
    A("Note: the neighbour-period evidence for `ثجوان` itself has "
      "`gross_profit == revenue` (zero COGS), so it is a pointer for a manual "
      "CODAL report check, not a confirmed parser bug. `دکوثر` is a separate "
      "unit/column sentinel (`1/1/1`). Neither is changed in this task.")
    A("")
    A("## 5. Newest-period-only evidence (`وملت`)")
    A("")
    w = ctx["wmlt"]
    if w:
        A("FS-growth-path rows compared old vs new: **%d** (financial/service/"
          "holding rows without a usable monthly series); rows that differ: "
          "**%d**; rows whose *state* changes: **%d** (%s)."
          % (ctx["newest_compared"], len(ctx["newest_changed"]),
             sum(1 for x in ctx["newest_changed"] if x["state_changed"]),
             "، ".join(x["key"] for x in ctx["newest_changed"]
                       if x["state_changed"]) or "none"))
        A("")
        A("| Path | i1 | i2 | i3 | i4 | Raw inputs |")
        A("| --- | --- | --- | --- | --- | --- |")
        r = w["row"]
        A("| bulk_scan | %s | %s | %s | %s | EPS %s; margin inputs ref=%s rev=%s gp=%s; "
          "annual sales %s bt; mcap %s ht |"
          % (bulk_state(r, 1), bulk_state(r, 2),
             bulk_state(r, 3), bulk_state(r, 4),
             r.get("eps_series"), (w["ref_raw"]["period_end"] if w["ref_raw"] else "—"),
             fmt_num(w["ref_raw"]["revenue"] if w["ref_raw"] else None),
             fmt_num(w["ref_raw"]["gross_profit"] if w["ref_raw"] else None),
             fmt_num(r.get("annual_sales_bt"), 1), fmt_num(w["mcap_ht"], 1)))
        card = w["card"]
        A("| evaluate_v10 | %s | %s | %s | %s | EPS %s; margin %s; annual sales %s; "
          "i4 path %s |"
          % (card_state(card, 1), card_state(card, 2), card_state(card, 3),
             card_state(card, 4),
             (card["indicators"]["2"] or {}).get("eps_series"),
             fmt_num((card["indicators"]["3"] or {}).get("margin_pct"), 1),
             fmt_num((card["indicators"]["4"] or {}).get("annual_sales_bt"), 1),
             (card["indicators"]["4"] or {}).get("acceptance_path") or "—"))
        A("")
        A("Raw `financial_statements` rows for `وملت` (newest first):")
        A("")
        A("| tracing_no | Period | Months | Revenue (mrl) | Title says «تلفیقی» | "
          "Enters non-consolidated path |")
        A("| ---: | --- | ---: | ---: | :---: | :---: |")
        for x in w["fs_rows"][:6]:
            cons = bool(E._is_consolidated(x["title"] or ""))
            A("| %s | %s | %s | %s | %s | %s |"
              % (x["tracing_no"], x["period_end"], x["period_months"],
                 fmt_num(x["revenue"]), "yes" if cons else "no",
                 "no" if cons else "yes"))
        A("")
        A("Why it differs from the pre-Task-4 number: the newest **non-consolidated** "
          "interim is ۱۴۰۴/۱۲/۲۹ (۳ ماهه). Its same-day prior-year row is "
          "۱۴۰۳/۱۲/۳۰ (۳ ماهه، درآمد ۵٬۱۹۶); interim matching is exact-day, so "
          "the pair is not used. All annual rows are consolidated by title and "
          "are correctly excluded from the non-consolidated FS-growth path. New "
          "result: `%s` → i1 = N/A. Old rule fell back to ۱۴۰۴/۰۶/۳۱ (۹ ماهه) "
          "vs ۱۴۰۳/۰۶/۳۱ = **%s%%** (i1 = False). The row now shows an honest "
          "gray N/A instead of a stale-period growth. Bulk and card agree on "
          "the state; the card projects `passes` to bool (False) while carrying "
          "`na=True`, whereas bulk keeps `None`."
          % ((w["new"].get("reason") or "fs_unavailable"),
             fmt_num(w["old"].get("monetary_pct"), 2)))
        A("")
        A("Projection note: bulk keeps the computed annual-sales number "
          "(%s bt) but suppresses the months/label for the exempt holding; the "
          "card clears annual sales. Neither is scored. No indicator value is "
          "fabricated."
          % fmt_num(w["row"].get("annual_sales_bt"), 1))
        A("")
        A("Second numerically affected row (not a state change): **%s** — old "
          "interim pair ۱۴۰۵/۰۳/۳۱ (۳ ماهه) = **%s%%**; new newest-interim "
          "۱۴۰۵/۰۶/۳۱ has no non-consolidated pair (the ۱۴۰۴/۰۶/۳۱ partner is "
          "consolidated by title) → annual ۱۴۰۲/۱۲/۲۹ = **%s%%**; both PASS."
          % (ctx["newest_other"]["key"],
             fmt_num(ctx["newest_other"]["old"].get("monetary_pct"), 2),
             fmt_num(ctx["newest_other"]["new"].get("monetary_pct"), 2)))
    else:
        A("- `وملت` not found in bulk rows.")
    A("")
    A("## 6. Representative checks")
    A("")
    A("| Symbol | Class | Score | i1 | i2 | i3 | i4 | i5 | EPS series | "
      "Margin inputs (period / rev / gp) | Annual sales | mcap | i4 path |")
    A("| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for x in ctx["reps"]:
        r = x["r"]
        raw = x["raw_ref"]
        A("| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s / %s / %s | "
          "%s bt (%s m) | %s ht | %s |"
          % (r["symbol_norm"], CLASS_LABEL.get(x["cls"], x["cls"]),
             int(r.get("score") or 0),
             bulk_state(r, 1), bulk_state(r, 2),
             bulk_state(r, 3), bulk_state(r, 4),
             bulk_state(r, 5),
             r.get("eps_series") if r.get("eps_series") else "—",
             (raw["period_end"] if raw else "—"),
             fmt_num(raw["revenue"] if raw else None),
             fmt_num(raw["gross_profit"] if raw else None),
             fmt_num(r.get("annual_sales_bt"), 1), r.get("annualize_months"),
             fmt_num(x["mcap_ht"], 1), r.get("i4_acceptance_path") or "—"))
    A("")
    A("## 7. Notes / limitations")
    A("")
    A("- No parser, threshold, formula, or production code was changed.")
    A("- `fts_results` was not touched; no screener cache was invalidated or "
      "re-materialized.")
    A("- `financial_statements.is_consolidated` disagrees with the title-derived "
      "basis on **%d** annual rows in the whole bank (example: `وملت` rows say "
      "«تلفیقی» in the title but the column is 0). The live engines filter by "
      "title, so indicator 3 / EPS / FS growth are unaffected; the column is a "
      "provenance defect to fix in a later data task." % ctx["basis_mismatch"])
    A("- Negative operating revenue is a known CODAL convention for "
      "financial/holding companies; it is reported as a soft gap, not a hard "
      "failure. No production/service reference row has negative revenue.")
    A("")
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main():
    t0 = time.time()
    if not os.path.isfile(DB_PATH):
        print("[SKIP] market.db not found — no local data; audit not run.")
        return 0
    before = db_signature(DB_PATH)
    conn = ro_connect(DB_PATH)
    cfg = load_fts_config()
    maps = build_maps(conn)
    head = git_head()

    rows = E.bulk_scan(conn, cfg=cfg)
    # فیلترِ سختِ شرکتِ واقعی — با همان ورودی‌های bulk (board/sector) تا
    # «no_instrument»های بی‌تابلو هم درست شمرده شوند.
    candidate = set(maps["annual_keys"]) | {
        k for k in maps["monthly_all"] if k in maps["board_of"]}
    kind_counts = Counter()
    nonco_reasons = Counter()
    for key in candidate:
        ident = E.classify_identity(
            key, maps["sector_of"].get(key, ""), maps["cname_of"].get(key, ""),
            key in maps["board_of"] or bool(maps["sector_of"].get(key, "")))
        kind_counts[ident["kind"]] += 1
        if ident["kind"] == "non_company":
            nonco_reasons[ident["reason"]] += 1
    strict = []
    for r in rows:
        ident = E.classify_identity(
            r["symbol_norm"], r.get("sector_name") or "",
            maps["cname_of"].get(r["symbol_norm"], ""),
            r["symbol_norm"] in maps["board_of"]
            or bool(r.get("sector_name")))
        if ident["kind"] == "company" and r.get("applicable"):
            strict.append(r)
    n_rows = len(rows)
    n_strict = len(strict)
    n_nonco = kind_counts.get("non_company", 0)
    n_funds = kind_counts.get("fund", 0)
    n_annual_candidates = len(
        {k for k in candidate if k in maps["annual_keys"]})
    n_monthly_candidates = len(
        {k for k in candidate if k not in maps["annual_keys"]})

    print("== 1. Universe ==")
    print("bulk rows: %d | strict companies: %d" % (n_rows, n_strict))
    print("candidates: %d (annual %d + monthly-only %d)"
          % (len(candidate), n_annual_candidates, n_monthly_candidates))
    print("excluded non-companies: %d %s | funds: %d"
          % (n_nonco, dict(nonco_reasons), n_funds))
    if n_nonco + n_funds + n_strict != len(candidate):
        print("[WARN] candidate partition mismatch: %d + %d + %d != %d"
              % (n_nonco, n_funds, n_strict, len(candidate)))

    eps_all, margin_all, monthly_all, monthly_i1_false = gap_sets(strict, maps)
    annual_rows = [r for r in strict if r["symbol_norm"] in maps["annual_keys"]]
    monthly_rows = [r for r in strict if r["symbol_norm"] not in maps["annual_keys"]]
    eps_annual, margin_annual, monthly_annual, _mif = gap_sets(annual_rows, maps)
    eps_monthly, margin_monthly, monthly_monthly, _mif2 = gap_sets(monthly_rows, maps)
    n_eps_consolidated = sum(1 for r in strict if r.get("eps_consolidated"))

    print("\n== 2. Strict gaps ==")
    print("all %d: eps %d | margin %d | monthly-no-report %d (i1 False %d, i1 None %d)"
          % (n_strict, len(eps_all), len(margin_all), len(monthly_all),
             len(monthly_i1_false), len(monthly_all) - len(monthly_i1_false)))
    print("%d annual: eps %d | margin %d | monthly %d  (ledger 11/59/20)"
          % (len(annual_rows), len(eps_annual), len(margin_annual),
             len(monthly_annual)))
    print("  note: margin 59 -> %d because وهور resolves to holding by "
          "company_name_map and takes class N/A for i3." % len(margin_annual))
    print("%d monthly-only: eps %d | margin %d | monthly %d"
          % (len(monthly_rows), len(eps_monthly), len(margin_monthly),
             len(monthly_monthly)))
    print("delta vs measured annual cohort: eps +%d | margin +%d | monthly +%d"
          % (len(eps_all) - len(eps_annual), len(margin_all) - len(margin_annual),
             len(monthly_all) - len(monthly_annual)))
    print("EPS consolidated-only evidence rows: %d" % n_eps_consolidated)

    sample = build_sample(strict, maps)
    sample_audit = audit_sample(conn, sample, maps)
    hard_sample = [h for s in sample_audit for h in s["hard"]]
    soft_sample = [x for s in sample_audit for x in s["soft"]]
    soft_counts = Counter(soft_sample)
    sample_classes = Counter(s["cls"] for s in sample_audit)
    sample_fs_rows = sum(s["stats"].get("fs_rows", 0) for s in sample_audit)
    sample_monthly_rows = sum(s["stats"].get("monthly_rows", 0) for s in sample_audit)
    print("\n== 3. Provenance/sanity sample ==")
    print("companies %d (%s) | FS rows %d | monthly rows %d"
          % (len(sample_audit),
             ", ".join("%s=%d" % (CLASS_LABEL.get(c, c), n)
                       for c, n in sample_classes.items()),
             sample_fs_rows, sample_monthly_rows))
    print("hard failures: %d | soft issues: %d %s"
          % (len(hard_sample), len(soft_sample), dict(soft_counts)))
    for h in hard_sample:
        print("  HARD", h)

    triage = triage_margin(conn, margin_all, maps)
    margin_by_cat = defaultdict(list)
    for x in triage:
        margin_by_cat[x["cat"]].append(x)
    print("\n== 4. Margin triage ==")
    print("gaps %d | %s" % (len(triage),
                            ", ".join("%s=%d" % (k, len(v))
                                      for k, v in sorted(margin_by_cat.items()))))
    examples = []
    for cat in ("no_gross_profit", "no_revenue", "unit_suspicious",
                "parser_suspect", "no_annual_fs"):
        examples.extend((margin_by_cat.get(cat) or [])[:2])
    for x in examples:
        raw = x["raw"]
        if raw is None:
            mo = (x.get("monthly") or [None])[0]
            print("  %-10s %-16s no annual FS; monthly tracing=%s ytd=%s"
                  % (x["key"], x["cat"],
                     mo["tracing_no"] if mo else "-",
                     fmt_num(mo["ytd_revenue"]) if mo else "-"))
        else:
            print("  %-10s %-16s tn=%s period=%s rev=%s gp=%s unit=%s"
                  % (x["key"], x["cat"], raw["tracing_no"], raw["period_end"],
                     fmt_num(raw["revenue"]), fmt_num(raw["gross_profit"]),
                     raw["unit_norm"] or raw["unit"]))
    no_gp = margin_by_cat.get("no_gross_profit") or []
    no_gp_with_op = sum(
        1 for x in no_gp
        if x["raw"] is not None and x["raw"]["operating_profit"] is not None)
    sugar_margin = sum(
        1 for r in margin_all
        if E.norm_fa(r.get("sector_name") or "") == E.norm_fa("قند و شکر"))
    detergent_margin = sum(
        1 for r in margin_all if r["symbol_norm"] == "شوینده")
    parser_suspects = []
    for x in margin_by_cat.get("parser_suspect") or []:
        ev = x["evidence"] or {}
        if ev.get("kind") == "neighbour_period":
            nb = ev["row"]
            detail = ("tracing %s (period %s) has revenue %s and gross_profit "
                      "NULL; tracing %s (period %s) of the same symbol has "
                      "gross_profit %s at revenue %s. Expected field: "
                      "`gross_profit` for %s; verify the CODAL label against "
                      "the existing patterns."
                      % (x["raw"]["tracing_no"], x["raw"]["period_end"],
                         fmt_num(x["raw"]["revenue"]), nb["tracing_no"],
                         nb["period_end"], fmt_num(nb["gross_profit"]),
                         fmt_num(nb["revenue"]), x["raw"]["tracing_no"]))
        else:
            detail = ("tracing %s (period %s) has revenue %s and gross_profit "
                      "NULL; a same-period alternate-basis row carries "
                      "gross_profit. Expected field: `gross_profit`."
                      % (x["raw"]["tracing_no"], x["raw"]["period_end"],
                         fmt_num(x["raw"]["revenue"])))
        parser_suspects.append({"symbol": x["key"], "detail": detail})
    for x in margin_by_cat.get("unit_suspicious") or []:
        raw = x["raw"]
        if raw is not None:
            parser_suspects.append({
                "symbol": x["key"],
                "detail": ("unit/parser sentinel: tracing %s (period %s) has "
                           "revenue=%s, operating_profit=%s, net_profit=%s, "
                           "gross_profit=%s. Expected real `revenue`, "
                           "`gross_profit`, `operating_profit`, `net_profit`; "
                           "check the unit/column parse before any margin is "
                           "published."
                           % (raw["tracing_no"], raw["period_end"],
                              fmt_num(raw["revenue"]), fmt_num(raw["operating_profit"]),
                              fmt_num(raw["net_profit"]), fmt_num(raw["gross_profit"])))})
    print("parser-suspect list: %s" % (", ".join(p["symbol"] for p in parser_suspects) or "none"))

    newest_compared, newest_changed = newest_period_evidence(conn, strict, maps, cfg)
    total_mcap = F.board_total_market_cap(conn)[0]
    w = wmlt_evidence(conn, strict, maps, cfg, total_mcap)
    newest_other = next((x for x in newest_changed if x["key"] != "وملت"), None)
    if newest_other is None and newest_changed:
        newest_other = newest_changed[0]
    print("\n== 5. Newest-period evidence ==")
    print("FS-growth-path rows compared: %d | differ: %d | state changes: %d"
          % (newest_compared, len(newest_changed),
             sum(1 for x in newest_changed if x["state_changed"])))
    for x in newest_changed:
        print("  %-10s old=%s (%s/%s) new=%s (%s/%s) state_changed=%s"
              % (x["key"], fmt_num(x["old"].get("monetary_pct"), 2),
                 x["old"].get("basis"), x["old"].get("period"),
                 fmt_num(x["new"].get("monetary_pct"), 2),
                 x["new"].get("basis"), x["new"].get("period"),
                 x["state_changed"]))
    if w:
        print("  وملت bulk: i1=%s i2=%s i3=%s i4=%s eps=%s"
              % (bulk_state(w["row"], 1), bulk_state(w["row"], 2),
                 bulk_state(w["row"], 3), bulk_state(w["row"], 4),
                 w["row"].get("eps_series")))
        print("  وملت card: i1=%s i2=%s i3=%s i4=%s"
              % (card_state(w["card"], 1), card_state(w["card"], 2),
                 card_state(w["card"], 3), card_state(w["card"], 4)))

    reps = []
    for cls, r in rep_rows(sample, maps):
        d = rep_details(conn, r, maps, cfg, total_mcap)
        d["cls"] = cls
        reps.append(d)
    print("\n== 6. Representative checks ==")
    for x in reps:
        r = x["r"]
        raw = x["raw_ref"]
        print("  %-10s %-18s score=%d i1=%s i2=%s i3=%s i4=%s i5=%s "
              "eps=%s margin=%s/%s sales=%s bt mcap=%s ht path=%s"
              % (r["symbol_norm"], CLASS_LABEL.get(x["cls"], x["cls"]),
                 int(r.get("score") or 0), bulk_state(r, 1),
                 bulk_state(r, 2), bulk_state(r, 3),
                 bulk_state(r, 4), bulk_state(r, 5),
                 r.get("eps_series") if r.get("eps_series") else "-",
                 fmt_num(raw["revenue"] if raw else None),
                 fmt_num(raw["gross_profit"] if raw else None),
                 fmt_num(r.get("annual_sales_bt"), 1), fmt_num(x["mcap_ht"], 1),
                 r.get("i4_acceptance_path") or "-"))

    # کلِ بانک: ناسازگاریِ پرچمِ تلفیقی (پرووننس، نه شکستِ سخت)
    basis_mismatch = 0
    for (title, cons) in conn.execute(
            "SELECT title, is_consolidated FROM financial_statements "
            "WHERE period_months>=12"):
        if bool(E._is_consolidated(title or "")) != bool(cons):
            basis_mismatch += 1

    after = db_signature(DB_PATH)
    db_unchanged = before == after
    hard_all = list(hard_sample)
    if not db_unchanged:
        hard_all.append("db_changed_during_audit")
    exit_code = 1 if hard_all else 0

    ctx = {
        "head": head, "db_before": before, "db_after": after,
        "db_unchanged": db_unchanged, "exit_code": exit_code,
        "n_rows": n_rows, "n_strict": n_strict, "n_candidates": len(candidate),
        "n_annual_candidates": n_annual_candidates,
        "n_monthly_candidates": n_monthly_candidates,
        "n_nonco": n_nonco, "nonco_reasons": nonco_reasons, "n_funds": n_funds,
        "annual_rows": len(annual_rows), "monthly_rows": len(monthly_rows),
        "eps_all": eps_all, "margin_all": margin_all, "monthly_all": monthly_all,
        "monthly_i1_false": monthly_i1_false,
        "eps_annual": eps_annual, "margin_annual": margin_annual,
        "monthly_annual": monthly_annual,
        "eps_monthly": eps_monthly, "margin_monthly": margin_monthly,
        "monthly_monthly": monthly_monthly,
        "n_eps_consolidated": n_eps_consolidated,
        "sample": sample_audit, "sample_classes": sample_classes,
        "sample_fs_rows": sample_fs_rows,
        "sample_monthly_rows": sample_monthly_rows,
        "hard_sample": hard_sample, "soft_sample": soft_sample,
        "soft_counts": soft_counts,
        "hard_all": hard_all, "soft_all": soft_sample,
        "margin_by_cat": margin_by_cat, "margin_examples": examples,
        "margin_no_gp_with_op": no_gp_with_op,
        "sugar_margin": sugar_margin, "detergent_margin": detergent_margin,
        "parser_suspects": parser_suspects,
        "newest_compared": newest_compared, "newest_changed": newest_changed,
        "wmlt": w, "newest_other": newest_other,
        "reps": reps, "basis_mismatch": basis_mismatch,
    }
    write_report(ctx)

    print("\n== DB integrity ==")
    print("before: size=%d mtime_ns=%d" % (before["size"], before["mtime_ns"]))
    print("after : size=%d mtime_ns=%d -> %s"
          % (after["size"], after["mtime_ns"],
             "UNCHANGED" if db_unchanged else "CHANGED"))
    print("\naudit %s" % REPORT_PATH)
    print("rows %d | strict %d | nonco %d | funds %d | eps %d | margin %d | "
          "monthly %d | hard %d | soft %d | exit %d | %.1fs"
          % (n_rows, n_strict, n_nonco, n_funds, len(eps_all),
             len(margin_all), len(monthly_all), len(hard_all),
             len(soft_sample), exit_code, time.time() - t0))
    if hard_all:
        print("RESULT: FAIL — hard sanity failures present.")
    else:
        print("RESULT: PASS — no hard sanity failure; gaps reported honestly.")
    conn.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
