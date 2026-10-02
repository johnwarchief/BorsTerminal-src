"""_audit/splice_fund.py — بلوکِ جدیدِ fts_engine را از رُخِ AST جایِ‌گزین می‌کند.

فقط `annualized_sales` (و کامنتِ یک‌خطیِ بالایِ آن) با `new_block_fts.txt`
جایگزین می‌شود؛ بقیۀ فایل دست‌نخورده. بعد از جای‌گزینی import و compile می‌شود.
"""
import ast
import py_compile
import sys

TARGET = "fts_engine.py"
BLOCK = "_audit/new_block_fts.txt"

src = open(TARGET, encoding="utf-8").read()
lines = src.splitlines(keepends=True)
tree = ast.parse(src)
fn = next(n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "annualized_sales")
start = fn.lineno - 1
if lines[start - 1].startswith("# ===================="):
    start -= 1                      # کامنتِ بخشِ بالایِ تابع هم جایگزین شود
end = fn.end_lineno

block = open(BLOCK, encoding="utf-8").read().splitlines(keepends=True)
if block[0].startswith("# ==================== شاخص ۴"):
    block = block[1:]               # سطرِ تکراریِ بالایِ فایلِ بلوک

out = "".join(lines[:start]) + "".join(block) + "".join(lines[end:])
open(TARGET, "w", encoding="utf-8", newline="").write(out)
py_compile.compile(TARGET, doraise=True)
tree2 = ast.parse(open(TARGET, encoding="utf-8").read())
names = {n.name for n in tree2.body if isinstance(n, (ast.FunctionDef, ast.Assign))}
for want in ("company_profile", "annualize_rows", "annualized_sales"):
    has = any(isinstance(n, ast.FunctionDef) and n.name == want for n in tree2.body)
    print(("  ✓ " if has else "  ✗ ") + want, "در fts_engine")
dup = [n.name for n in tree2.body if isinstance(n, ast.FunctionDef)]
print("تکراریِ تابع:", {x for x in dup if dup.count(x) > 1} or "ندارد")
print("COMPILE OK")
