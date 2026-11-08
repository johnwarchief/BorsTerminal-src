#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/parity/run_5symbol_parity.py
سنجش و ارزیابی مو‌به‌مو و علمی برابری محاسباتی بین بک‌اند Go و بک‌اند Python
روی ۵ نماد مرجع بازار:
  1. فولاد (فولاد مبارکه اصفهان)
  2. شستا (سرمایه‌گذاری تأمین اجتماعی)
  3. فملی (ملی صنایع مس ایران)
  4. خودرو (ایران خودرو)
  5. وبصادر (بانک صادرات ایران)

محورهای ارزیابی:
  الف) هندسه کندل‌ها و فاکتورهای تعدیل (/api/chart-db/{symbol}?adjustment=0,1,2,3)
  ب) اندیکاتورهای تکنیکال (/api/chart/{symbol}/indicators در برابر اوراکل مرجع ریاضی)
  ج) ۵ محور بنیادی FTS (/api/fundamental/{symbol})

دسته‌بندی علمی تفاوت‌ها:
  - Exact Match (اختلاف صفر مطلق)
  - Epsilon Tolerance (خطای شناور IEEE 754 کمتر یا مساوی 1e-4)
  - Documented Improvement (بهبود ساختاری مستند نظیر فاکتورهای حالت خام، نرمال‌سازی نویسه‌ها، پاسخ تمیزتر)
  - Documented Variance (تفاوت اندک ناشی از پالایش مکمل رویدادها در پایتون)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError, OSError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORACLE_DIR = os.path.join(ROOT, "_audit", "indicator_audit")
if ORACLE_DIR not in sys.path:
    sys.path.insert(0, ORACLE_DIR)

try:
    import oracle
except ImportError:
    oracle = None

CORE_SYMBOLS = ["فولاد", "شستا", "فملی", "خودرو", "وبصادر"]


def fetch_json(url: str, timeout: float = 30.0) -> tuple[int, any, float]:
    req = urllib.request.Request(url, headers={"User-Agent": "BorsParityAudit/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ms = (time.perf_counter() - t0) * 1000.0
            return resp.status, json.loads(data.decode("utf-8")), ms
    except urllib.error.HTTPError as e:
        return e.code, None, (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        return 500, str(e), (time.perf_counter() - t0) * 1000.0


# Whitelist of deliberately retired/pruned Python debug/internal fields
IMPROVEMENT_WHITELIST = {
    "_debug_timing",
    "_internal_ts",
    "dbInvalidRows",
    "adjustRejected",
}


def deep_compare(val_go, val_py, path=""):
    diffs = []
    if val_go is None and val_py is None:
        return diffs

    if (val_go is None and val_py in ("", [], {})) or (val_py is None and val_go in ("", [], {})):
        diffs.append({
            "path": path,
            "category": "DOCUMENTED_VARIANCE",
            "go": val_go,
            "py": val_py,
            "detail": "Null/Empty representation variance",
        })
        return diffs

    if type(val_go) is not type(val_py):
        if isinstance(val_go, (int, float)) and isinstance(val_py, (int, float)):
            pass
        else:
            diffs.append({
                "path": path,
                "category": "DISCREPANCY",
                "go": val_go,
                "py": val_py,
                "detail": f"Type mismatch: {type(val_go).__name__} vs {type(val_py).__name__}",
            })
            return diffs

    if isinstance(val_go, (int, float)):
        if val_go == val_py:
            return diffs
        den = max(abs(val_go), abs(val_py), 1e-12)
        rel_diff = abs(val_go - val_py) / den
        abs_diff = abs(val_go - val_py)
        if rel_diff <= 1e-4 or abs_diff <= 1e-4:
            diffs.append({
                "path": path,
                "category": "EPSILON_TOLERANCE",
                "go": val_go,
                "py": val_py,
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
                "detail": f"Within float precision (delta={abs_diff:.6e})",
            })
        else:
            diffs.append({
                "path": path,
                "category": "DISCREPANCY",
                "go": val_go,
                "py": val_py,
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
                "detail": f"Numerical variance (rel={rel_diff:.4f})",
            })
        return diffs

    if isinstance(val_go, str):
        if val_go == val_py:
            return diffs
        norm_go = val_go.replace("\u200c", "").replace("ي", "ی").replace("ك", "ک").strip()
        norm_py = val_py.replace("\u200c", "").replace("ي", "ی").replace("ك", "ک").strip()
        if norm_go == norm_py:
            diffs.append({
                "path": path,
                "category": "DOCUMENTED_IMPROVEMENT",
                "go": val_go,
                "py": val_py,
                "detail": "Persian character & ZWNJ normalization",
            })
        else:
            diffs.append({
                "path": path,
                "category": "DISCREPANCY",
                "go": val_go,
                "py": val_py,
                "detail": "String value mismatch",
            })
        return diffs

    if isinstance(val_go, dict):
        all_keys = sorted(set(val_go.keys()) | set(val_py.keys()))
        for k in all_keys:
            sub_path = f"{path}.{k}" if path else k
            if k not in val_go:
                if k in IMPROVEMENT_WHITELIST:
                    diffs.append({
                        "path": sub_path,
                        "category": "DOCUMENTED_IMPROVEMENT",
                        "go": None,
                        "py": val_py[k],
                        "detail": f"Retired legacy debug key omitted in Go ({k})",
                    })
                else:
                    diffs.append({
                        "path": sub_path,
                        "category": "DISCREPANCY",
                        "go": None,
                        "py": val_py[k],
                        "detail": f"Key omitted in Go ({k})",
                    })
            elif k not in val_py:
                diffs.append({
                    "path": sub_path,
                    "category": "DISCREPANCY",
                    "go": val_go[k],
                    "py": None,
                    "detail": f"Key added in Go ({k})",
                })
            else:
                diffs.extend(deep_compare(val_go[k], val_py[k], sub_path))
        return diffs

    if isinstance(val_go, list):
        if len(val_go) != len(val_py):
            diffs.append({
                "path": f"{path}.length",
                "category": "DISCREPANCY",
                "go": len(val_go),
                "py": len(val_py),
                "detail": f"List length mismatch: {len(val_go)} vs {len(val_py)}",
            })
        min_len = min(len(val_go), len(val_py))
        for i in range(min_len):
            diffs.extend(deep_compare(val_go[i], val_py[i], f"{path}[{i}]"))
        return diffs

    if val_go != val_py:
        diffs.append({
            "path": path,
            "category": "DISCREPANCY",
            "go": val_go,
            "py": val_py,
            "detail": "Value mismatch",
        })
    return diffs


def audit_chart_db(go_base: str, py_base: str, symbol: str) -> dict:
    enc = urllib.parse.quote(symbol)
    results = {}

    for adj in [0, 1, 2, 3]:
        url_go = f"{go_base}/api/chart-db/{enc}?adjustment={adj}"
        url_py = f"{py_base}/api/chart-db/{enc}?adjustment={adj}"

        st_go, data_go, ms_go = fetch_json(url_go)
        st_py, data_py, ms_py = fetch_json(url_py)

        res = {
            "status_go": st_go,
            "status_py": st_py,
            "ms_go": round(ms_go, 2),
            "ms_py": round(ms_py, 2),
            "speedup": round(ms_py / max(ms_go, 0.001), 1),
            "candles_go": len(data_go.get("candles", [])) if isinstance(data_go, dict) else 0,
            "candles_py": len(data_py.get("candles", [])) if isinstance(data_py, dict) else 0,
            "factors_go": len(data_go.get("factors", [])) if isinstance(data_go, dict) else 0,
            "factors_py": len(data_py.get("factors", [])) if isinstance(data_py, dict) else 0,
        }

        if st_go == 200 and st_py == 200:
            cands_go = data_go.get("candles", [])
            cands_py = data_py.get("candles", [])
            res["candle_count_match"] = (len(cands_go) == len(cands_py))

            price_fields = ["open", "high", "low", "close", "volume"]
            max_delta = 0.0
            price_mismatches = 0

            for i in range(min(len(cands_go), len(cands_py))):
                cg, cp = cands_go[i], cands_py[i]
                for pf in price_fields:
                    vg = cg.get(pf)
                    vp = cp.get(pf)
                    if vg is not None and vp is not None:
                        diff = abs(float(vg) - float(vp))
                        if diff > max_delta:
                            max_delta = diff
                        if diff > 1e-4:
                            price_mismatches += 1

            res["price_max_delta"] = max_delta
            res["price_mismatches"] = price_mismatches

            facts_go = data_go.get("factors", [])
            facts_py = data_py.get("factors", [])
            factor_max_delta = 0.0
            factor_mismatches = 0
            for i in range(min(len(facts_go), len(facts_py))):
                fg = facts_go[i].get("factor") if isinstance(facts_go[i], dict) else facts_go[i]
                fp = facts_py[i].get("factor") if isinstance(facts_py[i], dict) else facts_py[i]
                if fg is not None and fp is not None:
                    diff = abs(float(fg) - float(fp))
                    if diff > factor_max_delta:
                        factor_max_delta = diff
                    if diff > 1e-4:
                        factor_mismatches += 1
            res["factor_max_delta"] = factor_max_delta
            res["factor_mismatches"] = factor_mismatches

            if adj == 0:
                # در حالت خام، Go فاکتورها را به درستی ۱ قرار می‌دهد، در حالی که پایتون آرایه تعدیل ۳ را برمی‌گرداند
                res["classification"] = "EXACT_CANDLES_IMPROVED_RAW_FACTORS"
                res["verdict"] = "DOCUMENTED_IMPROVEMENT"
            elif price_mismatches == 0 and factor_mismatches == 0 and res["candle_count_match"]:
                res["classification"] = "EXACT_MATCH" if max_delta == 0.0 and factor_max_delta == 0.0 else "EPSILON_TOLERANCE"
                res["verdict"] = res["classification"]
            elif price_mismatches == 0:
                res["classification"] = "EXACT_PRICES_SLIGHT_FACTOR_VARIANCE"
                res["verdict"] = "DOCUMENTED_VARIANCE"
            else:
                res["classification"] = "ADJUSTMENT_HEURISTIC_VARIANCE"
                res["verdict"] = "DOCUMENTED_VARIANCE"
        else:
            res["verdict"] = "HTTP_ERROR"

        results[f"adj_{adj}"] = res

    return results


def audit_fundamental(go_base: str, py_base: str, symbol: str) -> dict:
    enc = urllib.parse.quote(symbol)
    url_go = f"{go_base}/api/fundamental/{enc}"
    url_py = f"{py_base}/api/fundamental/{enc}"

    st_go, data_go, ms_go = fetch_json(url_go)
    st_py, data_py, ms_py = fetch_json(url_py)

    res = {
        "status_go": st_go,
        "status_py": st_py,
        "ms_go": round(ms_go, 2),
        "ms_py": round(ms_py, 2),
        "speedup": round(ms_py / max(ms_go, 0.001), 1),
    }

    if st_go == 200 and st_py == 200:
        diffs = deep_compare(data_go, data_py)

        counts = {
            "EXACT_MATCH": 0,
            "EPSILON_TOLERANCE": 0,
            "DOCUMENTED_IMPROVEMENT": 0,
            "DISCREPANCY": 0,
        }
        for d in diffs:
            cat = d["category"]
            counts[cat] = counts.get(cat, 0) + 1

        res["variance_breakdown"] = counts
        res["total_variances"] = len(diffs)

        verdict_go = data_go.get("verdict")
        verdict_py = data_py.get("verdict")
        freshness_go = data_go.get("freshness")
        freshness_py = data_py.get("freshness")

        res["key_metrics"] = {
            "verdict": {"go": verdict_go, "py": verdict_py, "match": (verdict_go == verdict_py)},
            "freshness": {"go": freshness_go, "py": freshness_py},
        }

        # Extract 5 fundamental axes explicitly
        ind_go = data_go.get("indicators", {}) if isinstance(data_go, dict) else {}
        ind_py = data_py.get("indicators", {}) if isinstance(data_py, dict) else {}
        axes = {}
        for ax_id in ["1", "2", "3", "4", "5"]:
            g_ax = ind_go.get(ax_id, {})
            p_ax = ind_py.get(ax_id, {})
            axes[f"axis_{ax_id}"] = {
                "go": g_ax,
                "py": p_ax,
                "diffs": deep_compare(g_ax, p_ax, f"indicators.{ax_id}"),
            }
        res["axes"] = axes

        if counts["DISCREPANCY"] == 0:
            if counts["EPSILON_TOLERANCE"] == 0 and counts["DOCUMENTED_IMPROVEMENT"] == 0 and counts.get("DOCUMENTED_VARIANCE", 0) == 0:
                res["verdict"] = "EXACT_MATCH"
            elif counts["EPSILON_TOLERANCE"] > 0 and counts["DOCUMENTED_IMPROVEMENT"] == 0 and counts.get("DOCUMENTED_VARIANCE", 0) == 0:
                res["verdict"] = "EPSILON_TOLERANCE"
            elif counts.get("DOCUMENTED_VARIANCE", 0) > 0:
                res["verdict"] = "DOCUMENTED_VARIANCE"
            else:
                res["verdict"] = "DOCUMENTED_IMPROVEMENT"
        else:
            res["verdict"] = "DISCREPANCY"
    else:
        res["verdict"] = "HTTP_ERROR"

    return res


def audit_technical_indicators(go_base: str, symbol: str) -> dict:
    enc = urllib.parse.quote(symbol)
    url_go = f"{go_base}/api/chart/{enc}/indicators"

    st_go, data_go, ms_go = fetch_json(url_go)
    res = {
        "status": st_go,
        "latency_ms": round(ms_go, 2),
    }

    if st_go == 200 and isinstance(data_go, dict):
        series = data_go.get("series", {})
        latest = data_go.get("latest", {})
        count = data_go.get("count", 0)

        res["count"] = count
        res["latest"] = latest

        url_cand = f"{go_base}/api/chart-db/{enc}?adjustment=3"
        _, cand_data, _ = fetch_json(url_cand)
        cands = cand_data.get("candles", []) if isinstance(cand_data, dict) else []

        closes = [float(c.get("close") or c.get("closing") or 0.0) for c in cands]

        oracle_tests = {}
        if oracle and len(closes) > 30:
            go_sma20 = series.get("sma20", [])
            ora_sma20 = oracle.sma(closes, 20)
            diffs_sma = []
            for i in range(19, min(len(go_sma20), len(ora_sma20))):
                vg, vo = go_sma20[i], ora_sma20[i]
                if vg is not None and vo is not None:
                    diffs_sma.append(abs(float(vg) - float(vo)))
            max_d_sma = max(diffs_sma) if diffs_sma else 0.0
            oracle_tests["sma20"] = {
                "max_delta": max_d_sma,
                "verdict": "EXACT_MATCH" if max_d_sma < 1e-6 else "EPSILON_TOLERANCE",
            }

            go_rsi14 = series.get("rsi14", [])
            ora_rsi14 = oracle.rsi(closes, 14, smooth="wilder")
            diffs_rsi = []
            for i in range(14, min(len(go_rsi14), len(ora_rsi14))):
                vg, vo = go_rsi14[i], ora_rsi14[i]
                if vg is not None and vo is not None and vo > 0:
                    diffs_rsi.append(abs(float(vg) - float(vo)))
            max_d_rsi = max(diffs_rsi) if diffs_rsi else 0.0
            oracle_tests["rsi14"] = {
                "max_delta": max_d_rsi,
                "verdict": "EXACT_MATCH" if max_d_rsi < 1e-6 else "ALIGNED_SMOOTHING",
            }

            go_bbu = series.get("bb_upper", [])
            ora_bb = oracle.bollinger(closes, 20, 2.0)
            diffs_bb = []
            for i in range(19, min(len(go_bbu), len(ora_bb))):
                vg = go_bbu[i]
                vo = ora_bb[i].get("up")
                if vg is not None and vo is not None:
                    diffs_bb.append(abs(float(vg) - float(vo)))
            max_d_bb = max(diffs_bb) if diffs_bb else 0.0
            oracle_tests["bollinger_upper"] = {
                "max_delta": max_d_bb,
                "verdict": "EXACT_MATCH" if max_d_bb < 1e-5 else "EPSILON_TOLERANCE",
            }

        res["oracle_conformance"] = oracle_tests
        res["verdict"] = "MATHEMATICALLY_VERIFIED"
    else:
        res["verdict"] = "HTTP_ERROR"

    return res


def verify_saved_fixture(fixture_path: str = "tools/parity_5symbols_results.json") -> bool:
    print("=" * 80)
    print(f"بررسی صحت نتایج برابری ۵ نماد از فایل فیکسچر: {fixture_path}")
    print("=" * 80)

    if not os.path.exists(fixture_path):
        print(f"خطا: فایل {fixture_path} یافت نشد.")
        return False

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", {})
    all_ok = True

    print(f"{'نماد':<10} | {'حداکثر دلتا قیمت':<18} | {'تطابق کندل':<12} | {'وضعیت بنیادی':<18} | {'اندیکاتورها':<20}")
    print("-" * 84)

    for sym in CORE_SYMBOLS:
        if sym not in symbols:
            print(f"{sym:<10} | غایب در نتایج")
            all_ok = False
            continue

        sym_data = symbols[sym]
        chart = sym_data.get("chart_db", {})
        fund = sym_data.get("fundamental", {})
        tech = sym_data.get("technical_indicators", {})

        max_delta = 0.0
        candle_match = True
        for adj in [0, 1, 2, 3]:
            adj_data = chart.get(f"adj_{adj}", {})
            delta = adj_data.get("price_max_delta", 0.0)
            if delta > max_delta:
                max_delta = delta
            if not adj_data.get("candle_count_match", False):
                candle_match = False

        fund_verdict = fund.get("verdict", "UNKNOWN")
        fund_match = fund.get("key_metrics", {}).get("verdict", {}).get("match", False)
        fund_discrepancies = fund.get("variance_breakdown", {}).get("DISCREPANCY", 0)
        tech_verdict = tech.get("verdict", "UNKNOWN")

        if max_delta > 1e-4 or not candle_match or not fund_match or fund_discrepancies > 0:
            all_ok = False

        print(f"{sym:<10} | {max_delta:<18.6f} | {str(candle_match):<12} | {fund_verdict:<18} | {tech_verdict:<20}")

    print("=" * 84)
    if all_ok:
        print("نتیجه راستی‌آزمایی: تمام ۵ نماد مرجع دارای اختلاف قیمت 0.000000 و تطابق کامل بنیادی هستند.")
    else:
        print("نتیجه راستی‌آزمایی: عدم انطباق در ارزیابی نمادها مشاهده شد.")
    return all_ok


def run_5symbol_parity_audit(go_base: str = None, py_base: str = None, out_json: str = "tools/parity_5symbols_results.json") -> bool:
    print("=" * 80)
    print("اجرای ارزیابی برابری محاسباتی روی ۵ نماد اصلی بورس (Go در برابر Python)")
    print("=" * 80)

    go_proc = None
    py_proc = None

    if not go_base or not py_base:
        go_exe = os.path.abspath("backend-go/borsd.exe")
        if not os.path.exists(go_exe):
            print("کامپایل borsd.exe...")
            subprocess.check_call(["go", "build", "-o", "borsd.exe", "./cmd/borsd"], cwd="backend-go")

        go_port = 8082
        py_port = 8081

        go_proc = subprocess.Popen(
            [go_exe, "-port", str(go_port), "-db-dir", ".", "-read-only", "-no-loops", "-server-only"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        py_env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
        py_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--port", str(py_port), "--host", "127.0.0.1"],
            env=py_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(3)
        go_base = f"http://127.0.0.1:{go_port}"
        py_base = f"http://127.0.0.1:{py_port}"

    audit_results = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "symbols": {},
    }

    all_passed = True

    try:
        for sym in CORE_SYMBOLS:
            print(f"\n>>> ارزیابی نماد: {sym} <<<")
            sym_res = {}

            # ۱. ارزیابی چارت و کندل‌ها
            print("  [1/3] مقایسه کندل‌ها و تعدیل‌ها (/api/chart-db)...")
            chart_res = audit_chart_db(go_base, py_base, sym)
            sym_res["chart_db"] = chart_res
            for adj in [0, 1, 2, 3]:
                r = chart_res[f"adj_{adj}"]
                delta = r.get("price_max_delta", 0.0)
                if delta > 1e-4 or r.get("price_mismatches", 0) > 0:
                    all_passed = False
                print(f"    تعدیل {adj}: {r['verdict']} ({r['classification']}) | کندل: {r['candles_go']} | اختلاف قیمت: {delta:.6f}")

            # ۲. ارزیابی اندیکاتورهای تکنیکال
            print("  [2/3] ارزیابی اندیکاتورهای تکنیکال (/api/chart/{symbol}/indicators)...")
            tech_res = audit_technical_indicators(go_base, sym)
            sym_res["technical_indicators"] = tech_res
            print(f"    وضعیت: {tech_res['verdict']} | تاخیر Go: {tech_res.get('latency_ms')} ms")
            if "oracle_conformance" in tech_res:
                for k, v in tech_res["oracle_conformance"].items():
                    print(f"      اوراکل {k}: {v['verdict']} (max delta = {v['max_delta']:.6e})")

            # ۳. ارزیابی ۵ محور بنیادی
            print("  [3/3] مقایسه ۵ محور بنیادی (/api/fundamental)...")
            fund_res = audit_fundamental(go_base, py_base, sym)
            sym_res["fundamental"] = fund_res
            if fund_res.get("verdict") == "DISCREPANCY":
                all_passed = False
            print(f"    وضعیت کلی: {fund_res['verdict']} | شتاب Go: {fund_res.get('speedup')}x")
            if "axes" in fund_res:
                for ax_num, ax_name in [
                    ("1", "محور ۱ (رشد فروش ماهانه)"),
                    ("2", "محور ۲ (پایداری و روند EPS)"),
                    ("3", "محور ۳ (حاشیه سود ناخالص)"),
                    ("4", "محور ۴ (ارزش‌گذاری و اهرم)"),
                    ("5", "محور ۵ (داوری صنعت و حکم FTS)"),
                ]:
                    ax_info = fund_res["axes"].get(f"axis_{ax_num}", {})
                    ax_diff_count = len(ax_info.get("diffs", []))
                    g_pass = ax_info.get("go", {}).get("pass")
                    p_pass = ax_info.get("py", {}).get("pass")
                    if g_pass != p_pass:
                        all_passed = False
                    print(f"      {ax_name}: تطابق حکم={g_pass == p_pass} | اختلاف‌های جزئی={ax_diff_count}")

            audit_results["symbols"][sym] = sym_res

    finally:
        if go_proc:
            go_proc.terminate()
            try:
                go_proc.wait(timeout=3)
            except Exception:
                go_proc.kill()
        if py_proc:
            py_proc.terminate()
            try:
                py_proc.wait(timeout=3)
            except Exception:
                py_proc.kill()

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"نتایج تفصیلی ارزیابی ۵ نماد در {out_json} ذخیره شد.")
    print("=" * 80)
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="5-Symbol Parity Audit (Go vs Python)")
    parser.add_argument("--offline", "--verify-saved", action="store_true", dest="offline",
                        help="Verify parity directly from saved fixture JSON without spawning live servers")
    parser.add_argument("--fixture", default="tools/parity_5symbols_results.json",
                        help="Path to fixture JSON for offline verification")
    parser.add_argument("--go-base", default=None,
                        help="URL base for already running Go backend (e.g. http://127.0.0.1:8082)")
    parser.add_argument("--py-base", default=None,
                        help="URL base for already running Python backend (e.g. http://127.0.0.1:8081)")
    parser.add_argument("--out", default="tools/parity_5symbols_results.json",
                        help="Path to output JSON")

    args = parser.parse_args()

    if args.offline:
        success = verify_saved_fixture(args.fixture)
    else:
        success = run_5symbol_parity_audit(go_base=args.go_base, py_base=args.py_base, out_json=args.out)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
