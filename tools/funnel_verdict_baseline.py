# tools/funnel_verdict_baseline.py — مبنایِ رأیِ قیف (پیش/پس ازِ ادغامِ System 2)

"""بدنه‌هایِ `/api/funnel` را درون‌فرآیندی ثبت می‌کند تا ادغامِ ساختاریِ قیف
«بی‌جابه‌جاییِ رأی» را باِ عدد اثبات کند، نه باِ نگاهِ کد.

چرا درون‌فرآیندی: بک‌اندِ زنده نشسته رویِ `market.db` می‌نویسد و رأی را باِ
زمانِ اجرا تکان می‌دهد؛ این‌جا فقط `api.funnel._run` خوانده می‌شود.

چرا `start_refresh` جای‌گزین می‌شود: آن تابع رشتهٔ پس‌زمینهٔ `funnel_tech_scan`
را بالا می‌آورد که جدولِ اسکن را درِ همان `market.db` بازنویسی می‌کند. دو اجرایِ
پیش و پس باید رویِ یکِ دادهٔ ثابت مقایسه شوند، پس نوشتنِ پس‌زمینه خاموش می‌ماند.
این جای‌گزینی هیچ رأیِ stage را نمی‌بیند: `pending_symbols` که ازِ خودِ `_run`
می‌آید همچنان ثبت می‌شود، و `stages`/`entries`/`status_matrix`/`exclusions`
از `FE.evaluate` می‌آیند، نه ازِ رشتهٔ پس‌زمینه. این ادعا درِ `selftest` پایین
سنجیده می‌شود، نه فرض.

فرارها ازِ هش: `as_of` (مهرِ زمان)، `cached_for_ms` (سنِ کش)، `timeline`
(خطِ زمانِ نمادها، ۹ مگابایت و بی‌رأی). بدنهٔ `tech_scan` به‌طورِ قطعی
سازش می‌شود تا شمارش‌هایِ رشتهٔ پس‌زمینه درِ مقایسه نیفتند.

فرمان:
    PYTHONIOENCODING=utf-8 python tools/funnel_verdict_baseline.py --label pre
    PYTHONIOENCODING=utf-8 python tools/funnel_verdict_baseline.py --compare pre post

خروجی: `_audit/funnel_verdict_<label>.json` (gitignored) و یکِ جدولِ فارسی رویِ
stdout. هردو اجرایِ `--label` باید SHAهایِ یکسان بدهند؛ هر اختلافی درِ
`--compare` باِ نامِ حالت و فیلدِ.changed گزارش می‌شود.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PRESETS = ("swing", "trend", "hourglass", "tech_first", "custom")
VOLATILE = ("as_of", "cached_for_ms", "timeline", "elapsed_ms", "duration_ms")

# زمینه‌هایِ ثابتی که باید درِ هر دو اجرا یکی باشند؛ اگر اینها تکان بخورند،
# اختلافِ رأی دیگر تقصیرِ ادغام نیست و مقایسه بی‌معنا است.
CONTEXT_TABLES = (
    ("instruments", "count(*)"),
    ("tape_history", "count(*)"),
)


def _cases() -> list[dict]:
    """ماتریسِ حالت‌ها: پنج preset × دو منطق، به‌علاوه زنجیرۀ custom،
    فیلترهایِ تکنیکال، تنظیماتِ مستقلِ استراتژی، حالتِ بنیادی، و خطاهایِ اعتبارسنجی."""
    cases: list[dict] = []

    def add(name: str, **kw):
        cases.append({"name": name, "kw": kw})

    # ۱) پنج preset درِ هر دو منطقِ اشتراک/اجتماع
    for p in PRESETS:
        for logic in ("and", "or"):
            add(f"{p}__{logic}", preset=p, logic=logic)

    # ۲) زنجیرۀ دستی درِ هر دو منطق (چیپ‌هایِ تابلو)
    for i, chain in enumerate(
        (["f_clock", "f_jet", "f_susp"], ["f_roobi", "f_noqteh", "f_smart"], ["f_legal", "f_clock"])
    ):
        for logic in ("and", "or"):
            add(f"custom_chain{i}__{logic}", preset="custom", chain=chain, logic=logic)

    # ۳) زنجیرۀ فیلترِ تکنیکال (جریانِ «تکنیکال اول»)
    for tc in (["t_weekly_up"], ["t_weekly_up", "t_daily_up"],
               ["t_setup_jet", "t_risk_divergence"], ["t_hourglass_accelerate"]):
        for logic in ("and", "or"):
            add("tech_" + "_".join(t.replace("t_", "") for t in tc) + f"__{logic}",
                preset="tech_first", tech_chain=tc, logic=logic)

    # ۴) تنظیماتِ مستقلِ همین استراتژی (رأیِ مالک ۱۴-۰۷-۲۷)
    for st in ({"weekly_mode": "require_up"},
               {"weekly_mode": "reject_down", "daily_mode": "require_up"},
               {"daily_mode": "require_up", "clock_delta_pct": "2"},
               {"clock_delta_pct": "2"}):
        add("set_" + "_".join(f"{k}={v}" for k, v in sorted(st.items())),
            preset="tech_first", settings=st, tech_chain=["t_weekly_up"])

    # ۵) حالتِ بنیادی و suffix
    for fm in ("hard", "standard", "exception"):
        add(f"fund_{fm}__trend", preset="trend", fund_mode=fm)
    add("keep_suffix__swing", preset="swing", drop_suffix=False)
    add("keep_suffix__trend", preset="trend", drop_suffix=False)

    # ۶) پارامتر و استثنایِ دست‌ساز (مسیرِ params/exceptions درِ کلیدِ کش)
    add("params__custom", preset="custom", chain=["f_clock", "f_jet"],
        params={"f_jet": {"min": 3}}, exceptions={"f_susp": ["خودرو"]})

    # ۷) خطاهایِ اعتبارسنجی — متنِ خطا هم رأیِ محصول است
    add("err_unknown_preset", preset="nope")
    add("err_unknown_logic", preset="swing", logic="xor")
    add("err_unknown_tech", preset="tech_first", tech_chain=["t_not_real"])
    add("err_unknown_setting_key", preset="tech_first", settings={"weekly_mode2": "off"})
    add("err_unknown_setting_value", preset="tech_first", settings={"weekly_mode": "maybe"})
    add("err_unknown_fund_mode", preset="trend", fund_mode="soft")
    return cases


def _freeze_tech_scan(payload: dict) -> None:
    """شمارش‌هایِ رشتهٔ پس‌زمینه را بی‌معنا نمی‌گذاریم: فقط ثابت می‌شوند."""
    ts = payload.get("tech_scan")
    if isinstance(ts, dict):
        keep = {"pending_symbols": ts.get("pending_symbols")}
        payload["tech_scan"] = keep


def _canonical(payload) -> str:
    if isinstance(payload, dict):
        clean = {k: v for k, v in payload.items() if k not in VOLATILE}
        if "tech_scan" in clean:
            _freeze_tech_scan(clean)
        return json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _digest(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]


def _counts(payload) -> dict:
    """چند عددِ خواندنی برایِ جدولِ گزارشِ انسانی (هش همه‌چیز را می‌گیرد)."""
    if not isinstance(payload, dict):
        return {}
    out: dict[str, object] = {"status": payload.get("status")}
    uni = payload.get("universe") or {}
    for k in ("board", "screened", "market", "joined", "excluded", "duplicate_rows"):
        if k in uni:
            out[f"uni.{k}"] = uni.get(k)
    stages = payload.get("stages") or {}
    for sname, svals in sorted(stages.items()):
        if isinstance(svals, dict):
            for f in ("pass", "reject", "pending", "unavailable"):
                if f in svals:
                    out[f"{sname}.{f}"] = svals.get(f)
    entries = payload.get("entries") or {}
    for sname, lst in sorted(entries.items()):
        if isinstance(lst, list):
            out[f"entries.{sname}"] = len(lst)
    ex = payload.get("exclusions")
    if isinstance(ex, list):
        out["exclusions"] = len(ex)
    if isinstance(payload.get("message"), str):
        out["message"] = payload.get("message")
    return out


def _context_fingerprint() -> dict:
    fp = {}
    try:
        from bors_config import DB_PATH
    except Exception as e:  # noqa: BLE001
        return {"db": "unavailable: " + str(e)[:80]}
    if not os.path.exists(DB_PATH):
        return {"db": "missing"}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        for table, expr in CONTEXT_TABLES:
            try:
                fp[table] = conn.execute(f"select {expr} from {table}").fetchone()[0]
            except Exception as e:  # noqa: BLE001
                fp[table] = "err:" + str(e)[:60]
    finally:
        conn.close()
    return fp


def capture(label: str, out_dir: str) -> int:
    import api.funnel as F
    import funnel_tech_scan as SCAN

    calls = []

    def stub_start_refresh(symbols):
        syms = list(symbols)
        calls.append(len(syms))
        return {"running": False, "queued": 0, "done": 0, "failed": 0,
                "in_flight": 0, "error": None, "stubbed": True}

    SCAN.start_refresh = stub_start_refresh  # type: ignore[attr-defined]

    import funnel_tech_scan as _S  # همان ماژول، برایِ اطمینان ازِ جای‌گزینی
    assert getattr(_S, "start_refresh") is stub_start_refresh, "جای‌گزینیِ refresh نشست"

    ctx = _context_fingerprint()
    doc = {
        "label": label,
        "git_sha": subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip(),
        "context": ctx,
        "cases": [],
    }
    print(f"[verdict] مبنایِ زمینه: " + json.dumps(ctx, ensure_ascii=False))

    for case in _cases():
        kw = dict(case["kw"])
        kw.setdefault("preset", "trend")
        try:
            payload = F._run(kw.pop("preset"), list(kw.pop("chain", [])),
                             kw.pop("fund_mode", "standard"),
                             kw.pop("params", {}), kw.pop("exceptions", {}),
                             full=True, drop_suffix=kw.pop("drop_suffix", True),
                             logic=kw.pop("logic", "and"),
                             tech_chain=list(kw.pop("tech_chain", [])),
                             settings=kw.pop("settings", {}))
        except Exception as e:  # noqa: BLE001 — خرابیِ خودِ مسیرِ رأی باید ثبت شود
            payload = {"status": "raised", "message": f"{type(e).__name__}: {e}"}
        doc["cases"].append({
            "name": case["name"],
            "request": {k: v for k, v in case["kw"].items()},
            "digest": _digest(payload),
            "counts": _counts(payload),
            "body": json.loads(_canonical(payload)) if isinstance(payload, dict) else payload,
        })
        print(f"[verdict] {case['name']}: {doc['cases'][-1]['digest']} "
              f"status={payload.get('status') if isinstance(payload, dict) else '?'}")

    path = os.path.join(out_dir, f"funnel_verdict_{label}.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
    n = len(doc["cases"])
    print(f"[verdict] {n} حالت در {path} (refreshِ پس‌زمینه: {len(calls)} فراخوانی، "
          f"{sum(calls)} نمادِ صف‌شده ثبت شد)")
    return 0


def _load(out_dir: str, label: str) -> dict:
    p = os.path.join(out_dir, f"funnel_verdict_{label}.json")
    if not os.path.exists(p):
        raise SystemExit(f"[verdict] فایلِ مبنایِ «{label}» نیست: {p} — اول --label بگیر")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _diff_fields(a, b, prefix="") -> list[str]:
    if a == b:
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _diff_fields(a.get(k), b.get(k), prefix + "/" + str(k))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [prefix + f" (len {len(a)}→{len(b)})"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff_fields(x, y, prefix + f"[{i}]")
        return out
    return [prefix + f" ({str(a)[:40]}→{str(b)[:40]})"]


def compare(out_dir: str, a_label: str, b_label: str) -> int:
    A, B = _load(out_dir, a_label), _load(out_dir, b_label)
    if A["context"] != B["context"]:
        print("[verdict] هشدار: زمینۀ دو اجرا یکی نیست — مقایسه بی‌اعتبار است.")
        print("  " + a_label + ": " + json.dumps(A["context"], ensure_ascii=False))
        print("  " + b_label + ": " + json.dumps(B["context"], ensure_ascii=False))
    aa = {c["name"]: c for c in A["cases"]}
    bb = {c["name"]: c for c in B["cases"]}
    only_a, only_b = sorted(set(aa) - set(bb)), sorted(set(bb) - set(aa))
    moved, same = [], 0
    for name in sorted(set(aa) & set(bb)):
        if aa[name]["digest"] == bb[name]["digest"]:
            same += 1
            continue
        fields = _diff_fields(aa[name]["body"], bb[name]["body"])
        moved.append((name, aa[name]["digest"], bb[name]["digest"], fields))

    print("\n═══ تطبیقِ بدنهٔ قیف: " + a_label + " در برابرِ " + b_label + " ═══\n")
    print(f"حالت‌هایِ یکسان: {same} | جابه‌جا: {len(moved)} | "
          f"فقط درِ «{a_label}»: {len(only_a)} | فقط درِ «{b_label}»: {len(only_b)}")
    for name, d1, d2, fields in moved:
        print(f"\n── {name}: {d1} → {d2}")
        for f in fields[:20]:
            print("   " + f)
        if len(fields) > 20:
            print(f"   … و {len(fields) - 20} فیلدِ دیگر")
    for name in only_a:
        print(f"\n── غایب درِ {b_label}: {name}")
    for name in only_b:
        print(f"\n── تازه درِ {b_label}: {name}")
    if moved or only_a or only_b:
        print("\nنتیجه: جابه‌جاییِ رأی دیده شد — هر سطر باید توضیحِ طرح‌دار داشته باشد.")
        return 1
    print("\nنتیجه: بدنه‌ها بیت‌به‌بیت یکسان‌اند (بی‌شمارۀ زمان و خطِ زمان).")
    return 0


def selftest(out_dir: str) -> int:
    """ثابت می‌کند سنجشورِ جای‌گزینیِ `start_refresh` رأیِ stage را نمی‌بیند:
    یکِ حالت باِ refreshِ واقعی (پس ازِ پشتیبان‌گیریِ market.db) اجرا می‌شود و
    بدنه‌اش باِ همان حالت درِ مبنایِ جای‌گزین‌شده مقایسه می‌گردد."""
    print("[selftest] این حالتِ خاموش‌کنندهٔ رشتهٔ پس‌زمینه را می‌سنجد.")
    print("[selftest] بازار باز نیست و نوشتنِ اسکن درِ market.db ریسک دارد؛ "
          "برایِ اجرایِ کامل، market.db را کپی کنید و BORS_VERDICT_SELFTEST=1 بگذارید.")
    if os.environ.get("BORS_VERDICT_SELFTEST") != "1":
        return 0
    import api.funnel as F
    payload_stubbed = F._run("swing", [], "standard", {}, {}, full=True)
    d_stub = _digest(payload_stubbed)
    print(f"[selftest] باِ جای‌گزینی: {d_stub}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="مبنایِ رأیِ قیف")
    ap.add_argument("--label", help="یکِ اجرا ثبت می‌کند (pre یا post)")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit"))
    args = ap.parse_args()
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    out_dir = args.out
    if args.compare:
        return compare(out_dir, *args.compare)
    if args.selftest:
        return selftest(out_dir)
    if not args.label:
        raise SystemExit("[verdict] یا --label یا --compare یا --selftest")
    return capture(out_dir=out_dir, label=args.label)


if __name__ == "__main__":
    raise SystemExit(main())
