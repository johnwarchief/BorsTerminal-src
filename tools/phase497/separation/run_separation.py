# tools/phase497/separation/run_separation.py
"""Task 6 orchestrator: full build + measured validation of the separated data layer.

Builds OUT_DIR/shared_metadata.db and OUT_DIR/technical.db from the READ-ONLY
Rahavard archive (reference_all.db + bars_*.jsonl + universe.json + corrections
pack), runs ALL FIVE validation gates against the real reference
(structural_only=False), and writes small evidence artifacts to _audit/phase49-7/.

Controller rulings applied here:
  12 — reference before/after stat verification (size + mtime epoch of
       reference_all.db, universe.json, pack factors.jsonl must be UNCHANGED;
       reference_all.db size must remain 14612127744).
  13 — Persian summary (separation_summary_fa.md) with ALL digits
       script-generated from artifacts via str.maketrans; identifiers/SQL ASCII.
(Ruling 11 — batched inserts + bulk PRAGMAs + per-file progress — lives in
build_technical.build_candles.)

Usage:
  python -m tools.phase497.separation.run_separation             # full build
  python -m tools.phase497.separation.run_separation --summary-only
"""
import os, json, re, sqlite3, sys, time
from . import paths, build_shared, build_technical, validate_separation as V

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
AUDIT_DIR = os.path.join(_ROOT, "_audit", "phase49-7")
REF_SIZE_EXPECTED = 14612127744  # Ruling 12: measured reference_all.db size (bytes)

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(x):
    """Ruling 13: every numeric digit in the Persian summary is script-generated."""
    return str(x).translate(_FA_DIGITS)


def _stat(path):
    st = os.stat(path)
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


def reference_stats():
    """Ruling 12: size + mtime epoch of every READ-ONLY archive input."""
    return {
        "reference_all.db": _stat(paths.REF_DB),
        "universe.json": _stat(paths.UNIVERSE),
        "pack_factors.jsonl": _stat(os.path.join(paths.PACK, "factors.jsonl")),
    }


def verify_reference_unchanged(before, after):
    """Return a list of problems (empty == read-only compliance proven)."""
    problems = []
    for name in before:
        if before[name] != after[name]:
            problems.append(f"{name}: before={before[name]} after={after[name]}")
    for label, snap in (("before", before), ("after", after)):
        sz = snap["reference_all.db"]["size"]
        if sz != REF_SIZE_EXPECTED:
            problems.append(f"reference_all.db {label} size={sz} != expected {REF_SIZE_EXPECTED}")
    return problems


def adjustment_coverage(tech):
    """Measured adjustment-coverage limitations (Task 4 findings) from technical.db."""
    c = sqlite3.connect(tech)
    cov = {
        "events": c.execute("SELECT COUNT(*) FROM adjustment_event").fetchone()[0],
        "factors": c.execute("SELECT COUNT(*) FROM adjustment_factor").fetchone()[0],
        "null_asset_id": c.execute("SELECT COUNT(*) FROM adjustment_event WHERE asset_id IS NULL").fetchone()[0],
        "keyless_events": c.execute(
            "SELECT COUNT(*) FROM adjustment_event WHERE asset_id IS NULL AND (ins_code IS NULL OR ins_code='')").fetchone()[0],
    }
    c.close()
    return cov


def _evidence_num(pattern, text):
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"evidence pattern {pattern!r} not found in {text!r}")
    return m.group(1)


def emit_summary_fa(rep, tech, out_path):
    """Ruling 13: Persian summary from separation_validation.json + technical.db.

    ALL digits are extracted from the measured artifacts and converted with
    str.maketrans (never hand-typed). Gate names / SQL identifiers stay ASCII.
    """
    gates = ["integrity", "no_placeholder", "no_dup_t", "alias_reproduction", "row_reconciliation"]
    ph = _evidence_num(r"t=0 rows=(\d+)", rep["no_placeholder"]["evidence"])
    dup = _evidence_num(r"dup-t groups=(\d+)", rep["no_dup_t"]["evidence"])
    common = _evidence_num(r"\((\d+) bars\)", rep["alias_reproduction"]["evidence"])
    sample_asset = _evidence_num(r"on (\d+) \(", rep["alias_reproduction"]["evidence"])
    m = re.search(r"technical=(\d+) ref_distinct_no_t0=(\d+)", rep["row_reconciliation"]["evidence"])
    if not m:
        raise ValueError(f"row_reconciliation evidence unparseable: {rep['row_reconciliation']['evidence']!r}")
    tech_rows, ref_distinct = m.group(1), m.group(2)
    cov = adjustment_coverage(tech)

    L = []
    L.append("# خلاصه جداسازی لایه داده فنی (Phase 4.9.7 — Task 6)")
    L.append("")
    L.append("تولید خودکار از `separation_validation.json` و `technical.db`؛ همه ارقام با اسکریپت "
             "از شواهد اندازه‌گیری‌شده ساخته شده‌اند (تبدیل ارقام با `str.maketrans`). "
             "شناسه‌ها و SQL به ASCII باقی مانده‌اند.")
    L.append("")
    L.append(f"## حکم دروازه‌های اعتبارسنجی ({_fa(len(gates))} دروازه)")
    L.append("")
    L.append("| دروازه | حکم | شاهد اندازه‌گیری‌شده |")
    L.append("|---|---|---|")
    for g in gates:
        verdict = "قبول" if rep[g]["pass"] else "رد"
        L.append(f"| {g} | {verdict} | {rep[g]['evidence']} |")
    L.append("")
    all_verdict = "قبول" if rep["all_pass"] else "رد"
    L.append(f"**all_pass = {rep['all_pass']}** (همه دروازه‌ها: {all_verdict})")
    L.append("")
    L.append("## شواهد اندازه‌گیری‌شده")
    L.append("")
    L.append(f"- شمار ردیف‌های جدول candle در technical.db: {_fa(tech_rows)}")
    L.append(f"- شمار کلیدهای یکتای مرجع (بدون t=0 و بدون aliasهای real_close/type5): {_fa(ref_distinct)}")
    L.append(f"- کندل‌های مشترک نمونه alias (asset_id={_fa(sample_asset)}، real_close==last و type0==type5): {_fa(common)}")
    L.append(f"- ردیف‌های placeholder با t=0: {_fa(ph)}")
    L.append(f"- گروه‌های تکراری dup-t: {_fa(dup)}")
    L.append("")
    L.append("## پوشش تعدیلات — محدودیت‌های کشف‌شده (Task 4)")
    L.append("")
    L.append(f"- رویدادهای تعدیل (adjustment_event): {_fa(cov['events'])}")
    L.append(f"- ضریب‌های تعدیل (adjustment_factor): {_fa(cov['factors'])}")
    L.append(f"- رویدادهای بدون asset_id (NULL): {_fa(cov['null_asset_id'])}")
    L.append(f"- رویدادهای بدون کلید دارایی (ins_code تهی یا غایب): {_fa(cov['keyless_events'])}")
    L.append("")
    L.append(f"این {_fa(cov['keyless_events'])} رویداد بدون کلید، از طریق symbol فارسی در pack و "
             "جدول id_crosswalk در shared_metadata.db قابل بازیابی هستند؛ schema بدون تغییر باقی مانده است.")
    ref_path = os.path.join(AUDIT_DIR, "reference_unchanged.json")
    if os.path.exists(ref_path):
        with open(ref_path, encoding="utf-8") as f:
            rr = json.load(f)
        L.append("")
        L.append("## انطباق فقط-خواندنی (Ruling 12)")
        L.append("")
        b, a = rr["before"]["reference_all.db"], rr["after"]["reference_all.db"]
        L.append(f"- reference_all.db پیش از ساخت: size={_fa(b['size'])} mtime={_fa(b['mtime'])}")
        L.append(f"- reference_all.db پس از ساخت: size={_fa(a['size'])} mtime={_fa(a['mtime'])}")
        unchanged_verdict = "تأیید (بدون تغییر)" if rr["unchanged"] else "رد (تغییر detected)"
        L.append(f"- نتیجه: {unchanged_verdict}")
    L.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return out_path


def main():
    os.makedirs(paths.OUT_DIR, exist_ok=True)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    shared = os.path.join(paths.OUT_DIR, "shared_metadata.db")
    tech = os.path.join(paths.OUT_DIR, "technical.db")

    # Ruling 12: before-stat of every read-only archive input.
    before = reference_stats()
    print("REFERENCE_BEFORE " + json.dumps(before, sort_keys=True), flush=True)

    t0 = time.time(); build_shared.build_all(shared)
    print(f"shared built {time.time()-t0:.1f}s", flush=True)
    t0 = time.time(); build_technical.build_candles(tech)
    print(f"candles built {time.time()-t0:.1f}s", flush=True)
    t0 = time.time(); build_technical.build_adjustments(tech)
    print(f"adjustments built {time.time()-t0:.1f}s", flush=True)

    t0 = time.time(); rep = V.validate(shared, tech)  # structural_only=False -> all 5 gates vs real reference
    print(f"validation done {time.time()-t0:.1f}s", flush=True)
    for g, v in rep.items():
        if isinstance(v, dict):
            print(f"GATE {g}: pass={v['pass']} evidence={v['evidence']}", flush=True)

    out = os.path.join(AUDIT_DIR, "separation_validation.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)

    # Ruling 12: after-stat + ASSERT equality (measured read-only compliance).
    after = reference_stats()
    problems = verify_reference_unchanged(before, after)
    ref_rep = {"before": before, "after": after, "unchanged": not problems, "problems": problems}
    with open(os.path.join(AUDIT_DIR, "reference_unchanged.json"), "w", encoding="utf-8") as f:
        json.dump(ref_rep, f, ensure_ascii=False, indent=1)
    print("REFERENCE_AFTER " + json.dumps(after, sort_keys=True), flush=True)
    print("REFERENCE_UNCHANGED", not problems, flush=True)

    # Ruling 13: Persian summary with script-generated digits.
    summary = emit_summary_fa(rep, tech, os.path.join(AUDIT_DIR, "separation_summary_fa.md"))
    print("SUMMARY_FA " + summary, flush=True)

    print("ALL_PASS", rep["all_pass"], flush=True)
    if problems:
        print("STOP: reference archive changed - read-only violation:", problems, flush=True)
        raise SystemExit(2)
    if not rep["all_pass"]:
        print("STOP: gate failure - investigate measured evidence (no fudge)", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    if "--summary-only" in sys.argv:
        with open(os.path.join(AUDIT_DIR, "separation_validation.json"), encoding="utf-8") as f:
            rep = json.load(f)
        emit_summary_fa(rep, os.path.join(paths.OUT_DIR, "technical.db"),
                        os.path.join(AUDIT_DIR, "separation_summary_fa.md"))
        print("SUMMARY_FA regenerated", flush=True)
    else:
        main()