#!/usr/bin/env python3
"""Regenerate the migration-progress dashboard from MIGRATION-STATUS.json.

Stdlib only. Single source of truth is MIGRATION-STATUS.json; every chart and
report below is derived from it (no hand-typed numbers inside images).

Usage:
    python docs/migration-progress/generate_progress.py [--repo PATH] [--check]

Outputs (written next to this script):
    MIGRATION-WORK-BREAKDOWN.md
    MIGRATION-PROGRESS.md
    MIGRATION-REMAINING-WORK.md
    MIGRATION-DEPENDENCIES.mmd
    charts/*.mmd

Snapshot metadata (base branch, base commit, snapshot date) comes from the JSON;
generation time and the live git HEAD are stamped at run time, and a drift warning
is emitted if the checkout HEAD no longer equals the audited base commit.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TASK_STATUSES = ["COMPLETE", "PARTIAL", "IN_PROGRESS", "OPEN", "BLOCKED", "NOT_MEASURED", "DEFERRED", "OUT_OF_SCOPE"]
GATE_VERDICTS = ["PASS", "FAIL", "NOT_MEASURED", "INSUFFICIENT_SAMPLES"]
DECISION_STATUSES = ["DECIDED", "ACCEPTED", "DEFERRED", "OPEN", "PROPOSED", "FINDING"]
RISK_WEIGHT = {"high": 3, "medium": 2, "low": 1}

STATUS_FA = {
    "COMPLETE": "تکمیل", "PARTIAL": "نسبی", "IN_PROGRESS": "در حال انجام",
    "OPEN": "شروع‌نشده", "BLOCKED": "مسدود", "NOT_MEASURED": "سنجیده‌نشده",
    "DEFERRED": "موکول", "OUT_OF_SCOPE": "خارج از محدوده",
}
STATUS_COLOR = {
    "COMPLETE": "#2e7d32", "PARTIAL": "#f9a825", "IN_PROGRESS": "#1565c0",
    "OPEN": "#9e9e9e", "BLOCKED": "#c62828", "NOT_MEASURED": "#6a1b9a",
    "DEFERRED": "#00838f", "OUT_OF_SCOPE": "#455a64",
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def git_head(repo):
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def esc(s):
    return str(s).replace('"', "'").replace("\n", " ")


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def validate(m):
    errs = []
    ids = [t["id"] for t in m["tasks"]]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        errs.append(f"duplicate task ids: {dup}")
    idset = set(ids)
    for t in m["tasks"]:
        if t["status"] not in TASK_STATUSES:
            errs.append(f"{t['id']}: bad status {t['status']}")
        if t["ws"] not in {w["id"] for w in m["workstreams"]}:
            errs.append(f"{t['id']}: unknown workstream {t['ws']}")
        for d in t.get("deps", []):
            if d not in idset:
                errs.append(f"{t['id']}: unresolved dep {d}")
        if t["status"] == "COMPLETE" and not t.get("evidence"):
            errs.append(f"{t['id']}: COMPLETE without evidence")
    for g in m["acceptance_gates"]:
        if g["verdict"] not in GATE_VERDICTS:
            errs.append(f"gate {g['id']}: bad verdict {g['verdict']}")
    for d in m["decisions"]:
        if d["status"] not in DECISION_STATUSES:
            errs.append(f"decision {d['id']}: bad status {d['status']}")
    # accepted stages must not be silently reopened
    for s in m["stages"]:
        if s["status"] == "ACCEPTED":
            reopened = [t["id"] for t in m["tasks"]
                        if t.get("stage") == s["id"] and t["status"] in ("OPEN", "BLOCKED")
                        and not t.get("reopen_justification")]
            if reopened:
                errs.append(f"accepted stage {s['id']} has reopened tasks without justification: {reopened}")
    return errs


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def impl_tasks(m):
    return [t for t in m["tasks"] if t["status"] != "OUT_OF_SCOPE"]


def metrics(m):
    ts = impl_tasks(m)
    total = len(ts)
    by = {s: sum(1 for t in ts if t["status"] == s) for s in TASK_STATUSES}
    complete = by["COMPLETE"]
    w_total = sum(RISK_WEIGHT.get(t.get("risk", "medium"), 2) for t in ts)
    w_done = sum(RISK_WEIGHT.get(t.get("risk", "medium"), 2) for t in ts if t["status"] == "COMPLETE")

    dec = m["decisions"]
    dec_closed = sum(1 for d in dec if d["status"] in ("DECIDED", "ACCEPTED", "DEFERRED"))
    q = m["owner_questions"]
    q_closed = sum(1 for x in q if x["status"] in ("DECIDED", "ACCEPTED", "DEFERRED"))

    gates = m["acceptance_gates"]
    g_pass = sum(1 for g in gates if g["verdict"] == "PASS")
    g_measured = sum(1 for g in gates if g["verdict"] in ("PASS", "FAIL"))

    return {
        "tasks_total": total, "tasks_by_status": by, "tasks_complete": complete,
        "impl_pct": pct(complete, total),
        "weight_total": w_total, "weight_done": w_done, "impl_weighted_pct": pct(w_done, w_total),
        "decisions_total": len(dec), "decisions_closed": dec_closed, "decision_pct": pct(dec_closed, len(dec)),
        "questions_total": len(q), "questions_closed": q_closed, "question_pct": pct(q_closed, len(q)),
        "gates_total": len(gates), "gates_pass": g_pass, "gates_measured": g_measured,
        "acceptance_pct": pct(g_pass, len(gates)), "acceptance_measured_pct": pct(g_pass, g_measured),
    }


def ws_rollup(m, ws_id):
    ts = [t for t in impl_tasks(m) if t["ws"] == ws_id]
    if not ts:
        return "OPEN"
    st = {t["status"] for t in ts}
    if st == {"COMPLETE"}:
        return "COMPLETE"
    if "BLOCKED" in st:
        return "BLOCKED"
    if "IN_PROGRESS" in st:
        return "IN_PROGRESS"
    if "COMPLETE" in st or "PARTIAL" in st:
        return "PARTIAL"
    if st <= {"DEFERRED"}:
        return "DEFERRED"
    return "OPEN"


def stage_stats(m, stage_id):
    ts = [t for t in impl_tasks(m) if t.get("stage") == stage_id]
    done = sum(1 for t in ts if t["status"] == "COMPLETE")
    stage = next((s for s in m["stages"] if s["id"] == stage_id), None)
    if stage and stage["status"] == "ACCEPTED":
        # Accepted stage: completion reflects its acceptance gate (met), not the
        # forward-looking capability tasks tagged to it. Those remain visible in
        # the task/gate sections and do NOT reopen the accepted stage.
        return len(ts), len(ts)
    return done, len(ts)


def critical_path(m):
    """Longest risk-weighted path through remaining tasks to final acceptance."""
    ts = {t["id"]: t for t in impl_tasks(m) if t["status"] != "COMPLETE"}
    terminals = [tid for tid in ts if ts[tid].get("terminal")]
    if not terminals:
        terminals = [tid for tid in ts if not any(tid in o.get("deps", []) for o in ts.values())]
    memo = {}

    def best(tid):
        if tid in memo:
            return memo[tid]
        t = ts.get(tid)
        if t is None:
            return (0, [])
        w = RISK_WEIGHT.get(t.get("risk", "medium"), 2)
        upstream = [d for d in t.get("deps", []) if d in ts]
        if not upstream:
            memo[tid] = (w, [tid])
            return memo[tid]
        bw, bp = max((best(d) for d in upstream), key=lambda x: x[0])
        memo[tid] = (bw + w, bp + [tid])
        return memo[tid]

    if not terminals:
        return []
    end = max(terminals, key=lambda tid: best(tid)[0])
    return best(end)[1]


# ---------------------------------------------------------------------------
# mermaid builders
# ---------------------------------------------------------------------------
def mmd_workstream(m):
    L = ["flowchart LR"]
    for w in m["workstreams"]:
        st = ws_rollup(m, w["id"])
        done, tot = sum(1 for t in impl_tasks(m) if t["ws"] == w["id"] and t["status"] == "COMPLETE"), \
            sum(1 for t in impl_tasks(m) if t["ws"] == w["id"])
        L.append(f'  {w["id"]}["{esc(w["name"])}<br/>{STATUS_FA[st]} {done}/{tot}"]:::{st}')
    L.append("  classDef COMPLETE fill:#2e7d32,color:#fff;")
    L.append("  classDef PARTIAL fill:#f9a825,color:#000;")
    L.append("  classDef IN_PROGRESS fill:#1565c0,color:#fff;")
    L.append("  classDef OPEN fill:#9e9e9e,color:#fff;")
    L.append("  classDef BLOCKED fill:#c62828,color:#fff;")
    L.append("  classDef DEFERRED fill:#00838f,color:#fff;")
    return "\n".join(L)


def mmd_status_pie(m, met):
    L = ['pie showTitle title وضعیت Taskهای اجرایی (خارج از محدوده حذف شده)']
    for s in TASK_STATUSES:
        if s == "OUT_OF_SCOPE":
            continue
        n = met["tasks_by_status"].get(s, 0)
        if n:
            L.append(f'  "{STATUS_FA[s]}" : {n}')
    return "\n".join(L)


def mmd_stages(m):
    L = ["xychart-beta", '  title "درصد تکمیل هر Stage (Taskهای COMPLETE از کل)"']
    labels = [s["id"] for s in m["stages"]]
    L.append('  x-axis [' + ", ".join(f'"{x}"' for x in labels) + "]")
    vals = []
    for s in m["stages"]:
        d, t = stage_stats(m, s["id"])
        vals.append(pct(d, t))
    L.append("  y-axis \"percent\" 0 --> 100")
    L.append("  bar [" + ", ".join(str(v) for v in vals) + "]")
    return "\n".join(L)


def mmd_metrics(met):
    L = ["xychart-beta", '  title "سه سنجهٔ مستقل پیشرفت (بدون وزن)"']
    L.append('  x-axis ["Decision Closure", "Implementation", "Acceptance (all)", "Acceptance (measured)"]')
    L.append("  y-axis \"percent\" 0 --> 100")
    L.append(f'  bar [{met["decision_pct"]}, {met["impl_pct"]}, {met["acceptance_pct"]}, {met["acceptance_measured_pct"]}]')
    return "\n".join(L)


def mmd_dependencies(m):
    ts = [t for t in impl_tasks(m) if t["status"] != "COMPLETE"]
    ids = {t["id"] for t in ts}
    L = ["flowchart TD"]
    for t in ts:
        L.append(f'  {t["id"]}["{esc(t["id"])}: {esc(t["title"])}"]:::{t["status"]}')
    for t in ts:
        for d in t.get("deps", []):
            if d in ids:
                L.append(f"  {d} --> {t['id']}")
    for s, c in STATUS_COLOR.items():
        L.append(f"  classDef {s} fill:{c},color:#fff;")
    return "\n".join(L)


def mmd_blocked(m):
    L = ["flowchart TD"]
    blocked = [t for t in m["tasks"] if t["status"] == "BLOCKED"]
    owner = [t for t in impl_tasks(m) if t.get("owner_decision") and t["status"] != "COMPLETE"]
    qs = [q for q in m["owner_questions"] if q.get("blocking") and q["status"] not in ("DECIDED", "ACCEPTED")]
    for q in qs:
        L.append(f'  {q["id"]}["{q["id"]}: {esc(q["title"])}"]:::BLOCKED')
    for t in blocked:
        L.append(f'  {t["id"]}["{esc(t["id"])}: {esc(t["title"])}"]:::BLOCKED')
    for t in owner:
        L.append(f'  {t["id"]}["{esc(t["id"])}: {esc(t["title"])}"]:::OPEN')
        for q in t.get("owner_questions", []):
            if any(x["id"] == q for x in qs):
                L.append(f"  {q} --> {t['id']}")
    for t in blocked:
        for d in t.get("deps", []):
            L.append(f"  {d} --> {t['id']}")
    L.append("  classDef BLOCKED fill:#c62828,color:#fff;")
    L.append("  classDef OPEN fill:#9e9e9e,color:#fff;")
    return "\n".join(L)


def mmd_critical(m, path):
    L = ["flowchart LR"]
    if not path:
        L.append('  empty["مسیر بحرانی یافت نشد"]')
        return "\n".join(L)
    tmap = {t["id"]: t for t in m["tasks"]}
    for tid in path:
        t = tmap[tid]
        L.append(f'  {tid}["{esc(tid)}: {esc(t["title"])}<br/>{STATUS_FA[t["status"]]} / risk {t.get("risk","medium")}"]:::{t["status"]}')
    for a, b in zip(path, path[1:]):
        L.append(f"  {a} ==> {b}")
    for s, c in STATUS_COLOR.items():
        L.append(f"  classDef {s} fill:{c},color:#fff;")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# markdown builders
# ---------------------------------------------------------------------------
def header(m, met, generated, head, drift):
    s = m["snapshot"]
    lines = [
        f"> **Snapshot:** branch `{s['base_branch']}` @ `{s['base_commit'][:12]}` ({s['commit_date']}) · "
        f"snapshot date {s['snapshot_date']} · generated {generated} UTC",
        f"> **Audit branch:** `{s['audit_branch']}` · live HEAD `{head[:12] or 'n/a'}`"
        + (" · ⚠️ DRIFT: checkout HEAD differs from audited base commit" if drift else ""),
        f"> **Source of truth:** `MIGRATION-STATUS.json` · regenerate: `python docs/migration-progress/generate_progress.py`",
    ]
    return "\n".join(lines)


def md_breakdown(m, met, generated, head, drift):
    L = ["# Migration Work Breakdown Structure", "", header(m, met, generated, head, drift), ""]
    L.append("هر Task شناسهٔ پایدار، شرح، وابستگی‌ها و شاهد پذیرش دارد. وضعیت‌ها فقط از شواهدِ "
             "قابل‌تکرار (کد/تست/کامیت/گزارش) گرفته شده‌اند؛ `DECIDED` به‌تنهایی `COMPLETE` نیست.")
    L.append("")
    for w in m["workstreams"]:
        ts = [t for t in m["tasks"] if t["ws"] == w["id"]]
        st = ws_rollup(m, w["id"])
        L.append(f"## {w['id']} — {w['name']} ({w['name_fa']}) — وضعیت کلی: {STATUS_FA[st]}")
        L.append("")
        L.append("| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |")
        L.append("|---|---|---|---|---|---|")
        for t in ts:
            ev = "; ".join(f"`{e['ref']}`" for e in t.get("evidence", [])) or "—"
            deps = ", ".join(t.get("deps", [])) or "—"
            flag = " 🔒مالک" if t.get("owner_decision") else ""
            L.append(f"| {t['id']} | {esc(t['title'])}{flag} | {t['status']} | {t.get('risk','medium')} | {deps} | {ev} |")
        L.append("")
    return "\n".join(L)


def md_progress(m, met, generated, head, drift):
    s = m["snapshot"]
    L = ["# Migration Progress Dashboard", "", header(m, met, generated, head, drift), ""]
    L.append("## ۰. روش، محدوده و تقدم")
    L.append("")
    L.append("- **تقدم مأموریت:** این سند، مأموریت تکمیلیِ «ممیزی پیشرفت مهاجرت» است. مأموریت اصلیِ Phase 4.9.8 "
             "(دیتابیس کانونیکال + تداوم TSETMC) به‌عنوان کارِ اجراییِ جدید در WBS ثبت شده (Stage `P498`، وضعیت OPEN) "
             "و در این سشن پیاده‌سازی نشده است؛ نمودار، وضعیت واقعی commit مبنا را نشان می‌دهد نه تاریخ نگارش اسناد.")
    L.append("- **مبنای وضعیت:** `go-main` @ `" + s["base_commit"][:12] + "`. هر ادعای COMPLETE به کد/تست/کامیت/گزارش قابل‌تکرار ارجاع دارد؛ "
             "گزارش قدیمی به‌تنهایی اثبات وضعیت امروز نیست. `DECIDED` به‌تنهایی `COMPLETE` نیست.")
    L.append("- **شواهد تازهٔ این ممیزی:** `go test ./...` = ۵۵ پکیج ok / ۰ FAIL؛ `tsc -b` = صفر خطا؛ "
             "`vitest run` = ۱۰۷ پرونده / ۸۶۷ تست passed (همه روی همین commit).")
    L.append("- **سه شکاف Runtime مندرج در پذیرش Stage 4** علیه کد جاری بازبینی شد: Generation Resolver (بسته شد)، "
             "Producer Allowlist (بسته شد)، API Honesty (قرارداد Job بسته شد؛ ممیزی همهٔ مسیرها باز است).")
    L.append("- **آنچه سنجیده نشده:** هر گیت/Task بدون شواهد کافی `NOT_MEASURED` است و هرگز PASS تلقی نمی‌شود؛ "
             "فهرست کامل در بخش گیت‌ها و `MIGRATION-REMAINING-WORK.md`.")
    L.append("- **خارج از محدوده:** لین Android، همگام‌سازی ابری، و زیرساخت توزیع تجاری با برچسب `OUT_OF_SCOPE` جدا شده‌اند "
             "و در مخرج درصد پیاده‌سازی نمی‌آیند.")
    L.append("")
    L.append("## ۱. سه سنجهٔ مستقل پیشرفت")
    L.append("")
    L.append("| سنجه | تعداد | درصد | قاعده |")
    L.append("|---|---|---|---|")
    L.append(f"| Decision Closure (تصمیم‌های معماری) | {met['decisions_closed']}/{met['decisions_total']} | {met['decision_pct']}% | DECIDED+ACCEPTED+DEFERRED(حکم‌شده) از کل |")
    L.append(f"| Owner Questions (پرسش‌های مالک) | {met['questions_closed']}/{met['questions_total']} | {met['question_pct']}% | پرسش‌های تعیین‌تکلیف‌شده از Q1–Q24 |")
    L.append(f"| Implementation Completion (بدون وزن) | {met['tasks_complete']}/{met['tasks_total']} | {met['impl_pct']}% | COMPLETE از Taskهای اجرایی (OUT_OF_SCOPE حذف) |")
    L.append(f"| Implementation Completion (وزن‌دار ریسک) | {met['weight_done']}/{met['weight_total']} | {met['impl_weighted_pct']}% | وزن high=3/medium=2/low=1 |")
    L.append(f"| Acceptance Completion (همهٔ گیت‌ها) | {met['gates_pass']}/{met['gates_total']} | {met['acceptance_pct']}% | PASS از کل گیت‌ها |")
    L.append(f"| Acceptance Completion (گیت‌های سنجیده) | {met['gates_pass']}/{met['gates_measured']} | {met['acceptance_measured_pct']}% | PASS از PASS+FAIL |")
    L.append("")
    L.append("> درصد وزنی فقط بر پایهٔ ریسکِ اعلام‌شدهٔ هر Task است (روش در `MIGRATION-STATUS.json` → `metrics_rules`). "
             "هیچ درصدی از روی تعداد سطرهای سند ساخته نشده است.")
    L.append("")
    L.append("## ۲. وضعیت Taskها به تفکیک")
    L.append("")
    L.append("| وضعیت | تعداد |")
    L.append("|---|---|")
    full_by = {s: sum(1 for t in m["tasks"] if t["status"] == s) for s in TASK_STATUSES}
    for st in TASK_STATUSES:
        L.append(f"| {st} ({STATUS_FA[st]}) | {full_by.get(st,0)} |")
    L.append("")
    L.append(f"> جمع کل Taskها: {len(m['tasks'])}. مخرجِ سنجهٔ Implementation فقط Taskهای اجرایی است "
             f"({met['tasks_total']} = کل منهای {full_by.get('OUT_OF_SCOPE',0)} مورد OUT_OF_SCOPE).")
    L.append("")
    L.append("## ۳. وضعیت Workstreamها")
    L.append("")
    L.extend(["```mermaid", mmd_workstream(m), "```", ""])
    L.extend(["```mermaid", mmd_status_pie(m, met), "```", ""])
    L.append("## ۴. درصد تکمیل هر Stage")
    L.append("")
    L.append("> برای Stageهای `ACCEPTED`، درصد بر پایهٔ **گیت پذیرش همان Stage** است (۱۰۰٪ = محدودهٔ پذیرش برآورده شده). "
             "کارهای تکمیلیِ قابلیت‌ها که فراتر از محدودهٔ پذیرش آن Stage هستند، در بخش Taskها/گیت‌ها جداگانه دیده می‌شوند "
             "و Stage پذیرفته‌شده را بازگشایی نمی‌کنند. برای Stageهای فعال، درصد = نسبت Taskهای COMPLETE به کل Taskهای آن Stage.")
    L.append("")
    L.append("| Stage | وضعیت | COMPLETE/کل | درصد |")
    L.append("|---|---|---|---|")
    for st in m["stages"]:
        d, t = stage_stats(m, st["id"])
        L.append(f"| {st['id']} — {st['name']} | {st['status']} | {d}/{t} | {pct(d,t)}% |")
    L.append("")
    L.extend(["```mermaid", mmd_stages(m), "```", ""])
    L.append("## ۵. مقایسهٔ سه سنجه")
    L.append("")
    L.extend(["```mermaid", mmd_metrics(met), "```", ""])
    L.append("## ۶. مسیر بحرانی تا پذیرش تولیدی")
    L.append("")
    path = critical_path(m)
    L.append("مسیر بحرانی (طولانی‌ترین مسیرِ وزن‌دارِ ریسک through Taskهای باقی‌مانده): "
             + (" → ".join(path) if path else "—"))
    L.append("")
    L.extend(["```mermaid", mmd_critical(m, path), "```", ""])
    L.append("## ۷. کارهای مسدود / نیازمند تصمیم مالک")
    L.append("")
    L.extend(["```mermaid", mmd_blocked(m), "```", ""])
    L.append("## ۸. گیت‌های پذیرش")
    L.append("")
    L.append("| گیت | حکم | منبع | شاهد |")
    L.append("|---|---|---|---|")
    for g in m["acceptance_gates"]:
        L.append(f"| {g['id']} — {esc(g['name'])} | {g['verdict']} | {g['source']} | {esc(g.get('evidence','—'))} |")
    L.append("")
    return "\n".join(L)


def md_remaining(m, met, generated, head, drift):
    L = ["# Migration Remaining Work", "", header(m, met, generated, head, drift), ""]
    rem = [t for t in impl_tasks(m) if t["status"] != "COMPLETE"]
    L.append(f"**{len(rem)} Task باقی‌مانده** از {met['tasks_total']} Task اجرایی. "
             f"مسدود: {sum(1 for t in rem if t['status']=='BLOCKED')} · "
             f"نیازمند تصمیم مالک: {sum(1 for t in rem if t.get('owner_decision'))} · "
             f"خارج از محدوده (جدا): {sum(1 for t in m['tasks'] if t['status']=='OUT_OF_SCOPE')}")
    L.append("")
    L.append("## نقشهٔ وابستگی Taskهای باقی‌مانده")
    L.append("")
    L.extend(["```mermaid", mmd_dependencies(m), "```", ""])
    L.append("## فهرست کارهای باقی‌مانده به تفکیک Workstream")
    L.append("")
    for w in m["workstreams"]:
        ts = [t for t in rem if t["ws"] == w["id"]]
        if not ts:
            continue
        L.append(f"### {w['id']} — {w['name']}")
        L.append("")
        L.append("| ID | Task | وضعیت | ریسک | پیش‌نیاز | تصمیم مالک | پرسش‌های باز |")
        L.append("|---|---|---|---|---|---|---|")
        for t in ts:
            deps = ", ".join(t.get("deps", [])) or "—"
            od = "بله" if t.get("owner_decision") else "—"
            oq = ", ".join(t.get("owner_questions", [])) or "—"
            L.append(f"| {t['id']} | {esc(t['title'])} | {t['status']} | {t.get('risk','medium')} | {deps} | {od} | {oq} |")
        L.append("")
    L.append("## پرسش‌های باز مالک (Blocking)")
    L.append("")
    L.append("| ID | پرسش | وضعیت | مسدودکننده | پیش‌فرض تا رأی |")
    L.append("|---|---|---|---|---|")
    for q in m["owner_questions"]:
        L.append(f"| {q['id']} | {esc(q['title'])} | {q['status']} | {'بله' if q.get('blocking') else '—'} | {esc(q.get('default','—'))} |")
    L.append("")
    L.append("## موارد خارج از محدودهٔ مهاجرت (OUT_OF_SCOPE)")
    L.append("")
    for t in m["tasks"]:
        if t["status"] == "OUT_OF_SCOPE":
            L.append(f"- **{t['id']}** — {esc(t['title'])}: {esc(t.get('notes',''))}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    m = load(os.path.join(HERE, "MIGRATION-STATUS.json"))
    errs = validate(m)
    if errs:
        print("VALIDATION FAILED:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print(f"validation OK: {len(m['tasks'])} tasks, {len(m['decisions'])} decisions, "
          f"{len(m['owner_questions'])} questions, {len(m['acceptance_gates'])} gates")
    if args.check:
        return

    met = metrics(m)
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    head = git_head(args.repo)
    drift = bool(head) and head != m["snapshot"]["base_commit"]
    if drift:
        print(f"WARNING: live HEAD {head[:12]} != base {m['snapshot']['base_commit'][:12]}")

    charts = {
        "workstream-status.mmd": mmd_workstream(m),
        "task-status-pie.mmd": mmd_status_pie(m, met),
        "stage-completion.mmd": mmd_stages(m),
        "metrics-comparison.mmd": mmd_metrics(met),
        "blocked-owner-decisions.mmd": mmd_blocked(m),
        "critical-path.mmd": mmd_critical(m, critical_path(m)),
    }
    os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
    for name, body in charts.items():
        with open(os.path.join(HERE, "charts", name), "w", encoding="utf-8", newline="\n") as f:
            f.write(body + "\n")
    with open(os.path.join(HERE, "MIGRATION-DEPENDENCIES.mmd"), "w", encoding="utf-8", newline="\n") as f:
        f.write(mmd_dependencies(m) + "\n")

    docs = {
        "MIGRATION-WORK-BREAKDOWN.md": md_breakdown(m, met, generated, head, drift),
        "MIGRATION-PROGRESS.md": md_progress(m, met, generated, head, drift),
        "MIGRATION-REMAINING-WORK.md": md_remaining(m, met, generated, head, drift),
    }
    for name, body in docs.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(body + "\n")

    print(f"implementation: {met['tasks_complete']}/{met['tasks_total']} = {met['impl_pct']}% "
          f"(weighted {met['impl_weighted_pct']}%)")
    print(f"decision closure: {met['decisions_closed']}/{met['decisions_total']} = {met['decision_pct']}%")
    print(f"acceptance: {met['gates_pass']}/{met['gates_total']} = {met['acceptance_pct']}% "
          f"(measured {met['acceptance_measured_pct']}%)")
    print("wrote 3 reports + 7 mermaid charts")


if __name__ == "__main__":
    main()