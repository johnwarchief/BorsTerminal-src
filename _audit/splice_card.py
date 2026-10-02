"""_audit/splice_card.py — `api/fundamental.py` را از «تک‌منبع» خواندن می‌کند.

دو چیز جایگزین می‌شود:
  ۱) جدولِ طبقه (_FIN_TOKENS … company_profile) → واگرد به `fts_engine.company_profile`
  ۲) `dynamic_annualized_sales` → واگرد به `fts_engine.annualized_sales`
بقیۀ فایل دست‌نخورده می‌ماند (لایه‌هایِ نمایشِ کارت همان کلیدها را می‌گیرند).
"""
import ast
import py_compile

TARGET = "api/fundamental.py"

NEW_PROFILE = '''# ═══════════════════════════════════════════════════════════════════════════
#  طبقۀ شرکت — واگرد به تک‌مرجعِ fts_engine
# ═══════════════════════════════════════════════════════════════════════════
# جدولِ توکن‌ها و «مبنای درآمد» در `fts_engine.company_profile` زندگی می‌کند؛
# این‌جا فقط نامِ دوباره‌سازی‌نشده نگه داشته شده تا `evaluate_v10`، `ind1b`،
# `_growth_breadth` و گاردها (dev/fund_not_applicable_v1028.py و
# dev/test_fts_v10_ladder.py که این نام را صدا می‌زنند) بی‌تغییر کار کنند.
# پیش از این همین جدول دو جا بود و `bulk_scan` (که به `api/` دسترسی ندارد)
# نسخهٔ موتور را نمی‌دید ⇒ طبقۀ مالی/خدماتی در کارت N/A و در اسکرینر «فروش».
company_profile = fts_engine.company_profile
_PROFILE_LABEL = fts_engine._PROFILE_LABEL
_OP_BASIS_KINDS = fts_engine._OP_BASIS_KINDS


'''

NEW_ANNUALIZED = '''def dynamic_annualized_sales(conn, symbol, series=None, ref=None, profile=None,
                             exempt=None) -> dict:
    """لایۀ ۴ کارت — واگرد به `fts_engine.annualized_sales` (تک‌پیاده‌سازی).

    ضریبِ ثابت نیست: ۳ ماه ×۴، ۴ ماه ×۳، ۶ ماه ×۲ … (م = بلندترینِ ماهِ دارایِ
    گزارشِ تجمیعی در آخرین سالِ مالی، نه تقویم). طبقۀ مالی/خدماتی/صندوق/هلدینگ
    «فروش کالا» ندارد ⇒ مبنایش درآمدِ صورتِ مالیِ سالانه، و حکمِ معافیت از
    `fts_engine.ind4_exempt` می‌آید (تک‌مرجعِ کارت و اسکرینر).
    جزئیاتِ قاعده و گیتِ «واحد مشکوک» در docstring خودِ آن تابع است.
    """
    return fts_engine.annualized_sales(conn, symbol, ref=ref, series=series,
                                       profile=profile, exempt=exempt)


'''


def _bounds(tree, names):
    """(شروع، پایان) پیوستۀ تعریف‌ها، شاملِ کامنت‌هایِ چسبیدهٔ بالایِ اولین."""
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    nodes.sort(key=lambda n: n.lineno)
    return nodes


def main():
    src = open(TARGET, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)

    # ۲) dynamic_annualized_sales
    fn = _bounds(tree, {"dynamic_annualized_sales"})[0]
    a_start, a_end = fn.lineno - 1, fn.end_lineno

    # ۱) توکن‌ها + company_profile: از سطرِ _FIN_TOKENS تا پایانِ company_profile
    prof = _bounds(tree, {"company_profile"})[0]
    tok = next(i for i, ln in enumerate(lines) if ln.startswith("_FIN_TOKENS ="))
    # کامنتِ بخشِ بالایِ توکن‌ها (بلوکِ «# ═══ …» + توضیح) را هم بردار
    p_start = tok
    while p_start > 0 and (lines[p_start - 1].startswith("#")
                           or not lines[p_start - 1].strip()):
        p_start -= 1
    p_end = prof.end_lineno

    out = (lines[:p_start] + [NEW_PROFILE]
           + lines[p_end:a_start] + [NEW_ANNUALIZED] + lines[a_end:])
    text = "".join(out)
    open(TARGET, "w", encoding="utf-8", newline="").write(text)
    py_compile.compile(TARGET, doraise=True)
    t2 = ast.parse(text)
    names = [n.name for n in t2.body if isinstance(n, ast.FunctionDef)]
    for w in ("dynamic_annualized_sales", "ind4_valuation", "evaluate_v10"):
        print(("  ✓ " if w in names else "  ✗ ") + w)
    print("  توکن‌هایِ محلیِ طبقه ماند؟",
          sum(1 for n in t2.body if isinstance(n, ast.Assign)
              and getattr(n.targets[0], "id", "").startswith("_FIN_TOKENS")) == 0)
    print("COMPILE OK")


if __name__ == "__main__":
    main()
