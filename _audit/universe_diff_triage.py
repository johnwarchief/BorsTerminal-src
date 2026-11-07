#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/universe_diff_triage.py — هر نمادِ DIFFS از ممیزیِ کلِ مجموعه، با علتِ شمارش‌شده.

مأموریت (بندِ ۲٫۴): «صفر بودنِ اختلاف‌ها فقط وقتی قابل‌اعلام است که واقعاً تمامِ
مجموعهٔ قابل‌مقایسه بررسی شده باشد» — پس این فایل همان اختلاف‌ها را از manifest و
daftarِ UNRESOLVED می‌خواند و به تفکیکِ علت نشان می‌دهد. هیچ عددی اینجا تایپ نشده؛
همه از CSVِ همان اجرا می‌آید.
"""
import collections
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "_audit", "SYMBOL-AUDIT-MANIFEST.csv")
UNRES = os.path.join(ROOT, "_audit", "SYMBOL-AUDIT-UNRESOLVED.csv")


def load(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    rows = load(MANIFEST)
    un = load(UNRES)
    by_status = collections.Counter(r["status"] for r in rows)
    print("manifest rows: %d" % len(rows))
    for k, v in by_status.most_common():
        print("  %-20s %d" % (k, v))

    diffs = [r for r in rows if r["status"] == "DIFFS"]
    fields = ("close_diff", "open_diff", "volume_diff", "widen_unexplained",
              "invariant_violations", "bad_numbers", "dup_dates", "order_mixed",
              "extra_in_served", "missing_unexpected", "factor_invalid",
              "unexpected_factor_jumps", "factor_value_mismatch", "raw_path_mutated")
    print("\nDIFFS symbols: %d" % len(diffs))
    tot = {f: sum(int(r[f] or 0) for r in diffs) for f in fields}
    for f, n in sorted(tot.items(), key=lambda kv: -kv[1]):
        if n:
            syms = sum(1 for r in diffs if int(r[f] or 0) > 0)
            print("  %-24s %8d  (روی %d نماد)" % (f, n, syms))

    cause_kinds = collections.Counter()
    for r in diffs:
        for part in (r["cause"] or "").split(";"):
            if part:
                cause_kinds[part.split("=")[0]] += 1
    print("\nعلت‌ها (تعدادِ نماد با آن علت):")
    for k, v in cause_kinds.most_common():
        print("  %-24s %d" % (k, v))

    print("\nنمونۀِ پنج نمادِ first-by-close_diff:")
    for r in sorted(diffs, key=lambda x: -int(x["close_diff"] or 0))[:5]:
        print("  %-16s %-10s close=%s max_abs=%s max_rel=%s basis=%s events=%s cov=%s"
              % (r["symbol"], r["ins_code"], r["close_diff"], r["max_abs_close_diff"],
                 r["max_rel_close_diff"], r["basis_applied"], r["adj_events"],
                 r["candles_before_coverage"]))

    codes = {r["ins_code"] for r in diffs}
    kinds = collections.Counter((u["field"], u["status"]) for u in un if u["ins_code"] in codes)
    print("\nردیف‌هایِ daftarِ اختلاف درِ نمادهایِ DIFFS:")
    for (fld, st), n in kinds.most_common(20):
        print("  %-22s %-11s %8d" % (fld, st, n))

    sample = [u for u in un if u["ins_code"] in codes and u["status"] == "UNRESOLVED"]
    print("\nنمونۀِ هفت ردیفِ حل‌نشده:")
    for u in sample[:7]:
        print("  %s | %s | %s | src=%s ours=%s | abs=%s rel=%s"
              % (u["symbol"], u["date"], u["field"], u["source_value"], u["ours"],
                 u["abs_diff"], u["rel_diff"]))
    print("\ncause هایِ حل‌نشده:")
    cc = collections.Counter(u["cause"] for u in sample)
    for k, v in cc.most_common(10):
        print("  %6d  %s" % (v, k[:110]))

    print("\nپوششِ تعدیل درِ کلِ مجموعه:")
    ev = sum(1 for r in rows if int(r["adj_events"] or 0) > 0)
    cov = sum(1 for r in rows if int(r["candles_before_coverage"] or 0) > 0)
    fa = sum(1 for r in rows if r["functional_available"] == "yes")
    cc2 = sum(1 for r in rows if r["chain_complete"] == "True")
    print("  نماد با رویدادِ تعدیل ............ %d" % ev)
    print("  نماد با کندلِ پیشِ پوششِ دفتر .... %d" % cov)
    print("  زنجیرۀِ کامل ..................... %d" % cc2)
    print("  تعدیلِ عملکردی اثبات‌شده ......... %d" % fa)
    src = collections.Counter(r["adjust_source"] for r in rows)
    print("  منبعِ داوری:")
    for k, v in src.most_common():
        print("    %-32s %d" % (k or "-", v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
