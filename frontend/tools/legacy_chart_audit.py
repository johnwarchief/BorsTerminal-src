# tools/legacy_chart_audit.py -- پیش ازِ حذف، ثابت کن کدام فایل واقعاً ازِ
# دسترسِ اپلیکیشنِ زنده بیرون است. «مرده» یعنی تنها واردکننده‌هایش یا خودِ
# محلةِ مرده باشند یا فایل‌هایِ تستِ همان محله.
#
# چرا اسکریپت و نه چشم: هشت فایلِ تست این محله را می‌سازند و اگر یکی از آن‌ها
# ازِ صفحه‌ایِ زنده صدا می‌زد، حذفِ بی‌صدا یعنی کرشِ کاربر.
import re
import sys
from pathlib import Path

SRC = Path("src").resolve()

CANDIDATES = [
    "features/technical/components/KLineChartWrapper.tsx",
    "features/technical/components/LwChartWrapper.tsx",
    "features/technical/components/SplitChartView.tsx",
    "features/technical/components/DrawingToolbar.tsx",
    "features/technical/components/ToolPropertiesPanel.tsx",
    "features/technical/components/FtsToolbar.tsx",
    "features/technical/components/FtsBottomStrip.tsx",
    "features/technical/lib/lwChart.ts",
    "features/technical/lib/chartTypes.ts",
    "features/technical/lib/compare.ts",
    "features/technical/lib/compareSeries.ts",
    "features/technical/lib/compareIndicator.ts",
]
ABS = {c: (SRC / c) for c in CANDIDATES}
TARGETS = {}
for c, p in ABS.items():
    TARGETS[p] = c
    TARGETS[p.with_suffix("")] = c          # import بدون پسوند

IMP = re.compile(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""")
ALIAS = {"@features": SRC / "features", "@shared": SRC / "shared",
         "@app": SRC / "app", "@widgets": SRC / "widgets", "@contracts": SRC / "contracts"}

files = sorted(p for p in SRC.rglob("*.ts*") if p.is_file())
importers = {c: set() for c in CANDIDATES}

for p in files:
    me = p.relative_to(SRC).as_posix()
    for spec in IMP.findall(p.read_text(encoding="utf-8", errors="replace")):
        resolved = None
        if spec.startswith("."):
            resolved = (p.parent / spec).resolve()
        else:
            for pre, root in ALIAS.items():
                if spec == pre or spec.startswith(pre + "/"):
                    resolved = (root / spec[len(pre):].lstrip("/")).resolve()
        if resolved is None:
            continue
        tgt = TARGETS.get(resolved) or TARGETS.get(Path(str(resolved) + ".tsx")) or TARGETS.get(Path(str(resolved) + ".ts"))
        if tgt and tgt != me:
            importers[tgt].add(me)

bad = 0
for c in CANDIDATES:
    imps = sorted(importers[c])
    dead = [i for i in imps if i in set(CANDIDATES)]
    tests = [i for i in imps if i.startswith("__tests__/")]
    live = [i for i in imps if i not in dead and i not in tests]
    verdict = "DEAD" if not live else "LIVE-USED"
    if live:
        bad += 1
    print("%-9s %-58s importers=%d" % (verdict, c, len(imps)))
    for i in imps:
        tag = "dead" if i in dead else ("test" if i in tests else "LIVE")
        print("            [%4s] %s" % (tag, i))
print("\nفایل‌هایی که هنوز مصرف‌کنندۀِ زنده دارند:", bad)
sys.exit(0)
