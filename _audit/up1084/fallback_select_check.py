"""برگشتِ کامل (fallback) برایِ نسخۀ بدونِ پچ — با خودِ latest.jsonِ زنده.

_select_patch درِ api/update تابعِ خالصِ انتخاب است و APP_VERSION را از ماژولِ خود
می‌خواند؛ اینجا همان تابع را برایِ نسخه‌هایِ مختلفِ کلاینت اجرا می‌کنیم تا ثابت
شود «پچِ نامرتبط هرگز انتخاب نمی‌شود» و کلاینتِ بی‌پچ به نصابِ کامل برمی‌گردد.
دادۀ ورودیِ این سنجش همان latest.jsonِ منتشرشده است (بی‌دست‌ساز).
"""
import json
import sys

sys.path.insert(0, ".")
import api.update as U  # noqa: E402

L = json.load(open(r"_audit/up1084/latest.json", encoding="utf-8"))
print("latest.json:", {"version": L.get("version"), "patches": len(L.get("patches") or []),
                       "platforms": list((L.get("platforms") or {}).keys())})
for e in (L.get("patches") or []):
    print("  patch:", json.dumps(e, ensure_ascii=False)[:260])

installer = None
for name, plat in (L.get("platforms") or {}).items():
    if isinstance(plat, dict) and plat.get("url"):
        installer = (name, plat["url"])
        print("  installer:", name, plat["url"][-56:], "sig:", bool(plat.get("signature")))

ok = 0
tot = 0
for ver, want in [("1.0.83", "1.0.83"), ("1.0.82", "1.0.82"), ("1.0.81", "1.0.81"),
                  ("1.0.80", None), ("1.0.79", None), ("1.0.60", None), ("1.0.84", None)]:
    U.APP_VERSION = ver                      # کلاینتِ ساختگی، با مانیفستِ واقعی
    got = U._select_patch(L)
    tot += 1
    if want is None:
        good = got is None
        detail = "به نصابِ کامل برمی‌گردد" if got is None else f"انتخابِ نادرست: {got}"
    else:
        good = bool(got) and str(got.get("from")) == want and got["url"].endswith(
            f"BorsTerminal_Patch_{want}_to_1.0.84.zip") and bool(got.get("signature"))
        detail = (got or {}).get("url", "")[-46:]
    ok += bool(good)
    print(("  ok   " if good else "  FAIL ") + f"کلاینت {ver}: " + detail)

print(f"\n{ok}/{tot} — انتخابِ پچ و برگشتِ کامل با مانیفستِ زنده سنجیده شد")
sys.exit(0 if ok == tot and installer else 1)
