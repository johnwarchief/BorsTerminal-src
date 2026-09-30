# -*- coding: utf-8 -*-
"""سازندۀ `docs/AGENT-INDEX.md` — نقشۀ کد برایِ ایجنت.

چرا: هر ایجنت که تازه واردِ مخزن می‌شود امروز با grep/claw سراسری زمینۀ خودش را
پُر می‌کند (و هزینه‌اش توکن است، نه ثانیه). این فایل یک نقشۀ فشرده و
ماشین‌تولید می‌دهد: هر اندپوینت با خطِ خودش، هر اسلایسِ فرانت با ورودی‌هایش،
هر گاردِ dev با توصیفِ خودش. `dev/code_index_guard_v1065.py` بی‌تازگیِ آن را
قرمز می‌کند، پس هیچ‌وقت نقشۀ دروغ تحویلِ ایجنت نمی‌شود.

    python tools/build_agent_index.py            # نوشتن docs/AGENT-INDEX.md
    python tools/build_agent_index.py --check    # بی‌نوشت؛ rc=1 یعنی کهنه
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "AGENT-INDEX.md"

ROUTES_RE = re.compile(
    r'@router\.(get|post|put|delete)\(\s*"([^"]+)"'
)
BACKEND_ENGINES = (
    "fts_engine.py", "tape_flags.py", "mstat_engine.py", "codal_fetcher.py",
    "bors_config.py", "app.py", "bors_entry.py",
)
FRONT_GROUPS = ("features", "widgets", "shared", "app")
SKIP_DIRS = {"node_modules", "dist", "__tests__", "vendor"}


def _defs(path: Path):
    """(نام، خط) هر تابع/متدِ سطح‌بالا یا کلاس — با ast، نه regex."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            out.append(("%s (class)" % node.name, node.lineno))
    return out


def backend_section() -> list[str]:
    lines = ["## بک‌اند (FastAPI) — اندپوینت و خطِ آن", ""]
    api_dir = ROOT / "api"
    files = sorted(p for p in api_dir.glob("*.py"))
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        routes = [(m.group(1).upper(), m.group(2), text[:m.start()].count("\n") + 1)
                  for m in ROUTES_RE.finditer(text)]
        names = [n for n, _ in _defs(p)]
        lines.append("### `api/%s` — %d تابع، %d اندپوینت" % (p.name, len(names), len(routes)))
        for method, path, ln in routes:
            lines.append("- `%s %s` → `api/%s:%d`" % (method, path, p.name, ln))
        if not routes and names:
            head = ", ".join("`%s`" % n for n in names[:12])
            more = " …" if len(names) > 12 else ""
            lines.append("- (بدونِ router) توابع: %s%s" % (head, more))
        lines.append("")
    lines.append("## موتورهایِ پشتِ اسکرینر/تابلو")
    lines.append("")
    lines.append("| فایل | تابع‌هایِ کلیدی |")
    lines.append("| --- | --- |")
    for name in BACKEND_ENGINES:
        p = ROOT / name
        if not p.exists():
            continue
        names = [n for n, _ in _defs(p)]
        head = ", ".join("`%s`" % n for n in names[:6])
        more = " (+%d)" % (len(names) - 6) if len(names) > 6 else ""
        lines.append("| `%s` | %s%s |" % (name, head or "—", more))
    lines.append("")
    return lines


def frontend_section() -> list[str]:
    lines = ["## فرانت (React + FSD) — ورودیِ هر برش", ""]
    src = ROOT / "frontend" / "src"
    for group in FRONT_GROUPS:
        gdir = src / group
        if not gdir.is_dir():
            continue
        lines.append("### `%s/`" % group)
        lines.append("")
        for slice_dir in sorted(p for p in gdir.iterdir() if p.is_dir()):
            files = [p for p in slice_dir.rglob("*.ts*")
                     if p.is_file() and not any(s in p.parts for s in SKIP_DIRS)
                     and ".spec." not in p.name]
            if not files:
                continue
            tests = sorted(p.name for p in slice_dir.rglob("*.spec.tsx")
                           if ".spec." in p.name)
            entry = [f for f in files if f.name in ("index.ts", "index.tsx")]
            picks = sorted(f for f in files if f.name.startswith("use"))[:4]
            comps = sorted(f for f in files if f.name.endswith("Page.tsx")
                           or f.name.endswith("Table.tsx") or f.name.endswith("Panel.tsx"))[:3]
            shown = (entry + picks + comps)[:6]
            if not shown:
                shown = sorted(files)[:4]
            rels = ", ".join("`%s`" % f.relative_to(src).as_posix() for f in shown)
            extra = " (+%d فایل)" % (len(files) - len(shown)) if len(files) > len(shown) else ""
            lines.append("- **%s** — %d فایل: %s%s" % (
                slice_dir.relative_to(src).as_posix(), len(files), rels, extra))
            if tests:
                lines.append("  - تست: %s" % ", ".join("`%s`" % t for t in tests[:3]))
        lines.append("")
    routes = ROOT / "frontend" / "src" / "app"
    rfile = routes / "routes.tsx"
    if rfile.exists():
        text = rfile.read_text(encoding="utf-8", errors="replace")
        paths = sorted(set(re.findall(r"path\s*:\s*[\"']([^\"']+)[\"']", text)))
        lines.append("### مسیرهایِ روتر (`app/routes.tsx`)")
        lines.append("")
        lines.append("- " + ", ".join("`%s`" % p for p in paths) if paths else "- (چیزی یافت نشد)")
        lines.append("")
    return lines


def guards_section() -> list[str]:
    """توصیفِ هر سوئیت از خودِ SUITES در run_all_tests.py — منبعِ واحد."""
    lines = ["## گاردهایِ dev (توصیف از `dev/run_all_tests.py`)", ""]
    text = (ROOT / "dev" / "run_all_tests.py").read_text(encoding="utf-8", errors="replace")
    pairs = re.findall(r"\(\s*'([^']*\.py(?:\s+--\w+)?)'\s*,\s*\n?\s*'([^']+)'", text)
    pairs += re.findall(r"\(\s*'([^']*\.py(?:\s+--\w+)?)'\s*,\s*'([^']+)'\s*\)", text)
    seen = set()
    rows = []
    for path, desc in pairs:
        if path in seen:
            continue
        seen.add(path)
        rows.append((path, desc))
    if rows:
        lines.append("| سوئیت | چه چیزی را نگه می‌دارد |")
        lines.append("| --- | --- |")
        for path, desc in sorted(rows):
            lines.append("| `%s` | %s |" % (path, desc))
    else:
        lines.append("- (SUITES خالی خوانده نشد — `run_all_tests.py` را ببینید)")
    lines.append("")
    return lines


def pointer_section() -> list[str]:
    return [
        "## از نشانه تا فایل (کجا را بگردم؟)",
        "",
        "| نشانه در رابط | فایل/خطِ مرجع |",
        "| --- | --- |",
        "| ستون «الگو» و پنج پرچمِ تابلو | `tape_flags.py` (فرمول) + `frontend/src/features/market` (نمایش) + `dev/tape_filters_v1034.py` (برابری با سایت) |",
        "| ستونِ بنیادی/امتیاز/«سنجیده نشد» | `api/screener.py` (بیرون از کش) + `fts_engine.py` (`ind3_na`/`ind4_na`) + `frontend/src/features/fundamental/ui/FtsScreenTable.tsx` |",
        "| قیفِ چهارمرحله‌ای و پیچ‌هایش | `frontend/src/features/master/ui/FtsFunnelStages.tsx` + `frontend/src/features/master/lib/ftsFunnel.ts` + استور `useFunnelPrefsStore` |",
        "| برچسبِ مجمع/افزایش سرمایه و وتوی مجمع | `api/chart.py` (`upcoming_assemblies`، `ASSEMBLY_NEAR_DAYS`) + `api/screener.py` (`_apply_assembly_veto`) + `frontend/src/features/fundamental/lib/assemblyEvent.ts` + `dev/assembly_veto_v1064.py` |",
        "| درخت استراتژی و «جریان مسیر» | `frontend/src/features/master/components/ObsidianStrategyGraph.tsx` (`COMET_T`/`cubicAt` در ~۱۰۱۰) + `frontend/src/index.css` (`fts-comet`، `data-tree-flow-running`) |",
        "| کندل/چارت و موتورِ دوم FFC | `frontend/src/features/technical/engine/registry.ts` + `engine/ffc/FastFinancialChartsEngine.ts`؛ `KLineChartWrapper.tsx` مستقیم klinecharts را می‌زند |",
        "| دельتای آپدیت و امضا | `scripts/build_all.py` → `scripts/make_patch.py` → `scripts/publish_github_release.py`؛ `api/update.py` + `bors_minisign.py` |",
        "| هر اندپوینت | `dev/db_contract_v11.py` (قراردادِ کش/اسکیمای همان مسیر) |",
        "",
        "**قیدهایِ شکست‌پذیر** (توضیحِ کامل در `AGENTS.md` و `skills/`): `numpy==2.0.2` پین؛"
        " packaging رویِ onedir؛ `market.db.lzma` کنارِ EXE؛ هر `api/*.py`ِ تازه در"
        " `hiddenimports`؛ ارقامِ فارسی با `toFaDigits`/`_fa()` و `PYTHONIOENCODING=utf-8`;"
        " کلاسِ `.num` هرگز روی `<td>`؛ «بی‌داده وتو نیست».",
        "",
    ]


def build() -> str:
    head = [
        "# نقشۀ کد برایِ ایجنت (ماشین‌تولید)",
        "",
        "<!-- generated by tools/build_agent_index.py — دستِ دستی ویرایشش نکن؛ بی‌تازگی‌اش را dev/code_index_guard_v1065.py قرمز می‌کند -->",
        "",
        "این فایل تنها یک چیز را می‌فروشد: ایجنتِ تازه وارد، به‌جایِ grep سراسری،"
        " بداند هر مفهوم در کدام فایل است. جزئیاتِ روش‌شناسی در `docs/FTS_SPEC.md` و"
        " رأی‌هایِ مالک در `docs/fts-notes/OWNER_RULINGS.md` است.",
        "",
    ]
    parts = head + backend_section() + frontend_section() + guards_section() + pointer_section()
    parts.append("---")
    parts.append("")
    parts.append("بازتولید: `python tools/build_agent_index.py` — سپس گارد: "
                 "`python dev/code_index_guard_v1065.py`")
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    check = "--check" in sys.argv
    text = build()
    if check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("AGENT-INDEX STALE: docs/AGENT-INDEX.md با سورسِ فعلی نمی‌خواند")
            print("بازتولید کنید: python tools/build_agent_index.py")
            return 1
        print("AGENT-INDEX OK")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("AGENT-INDEX WRITTEN %s — %d سطر، %d بایت" % (
        OUT.relative_to(ROOT).as_posix(), text.count("\n") + 1, len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
