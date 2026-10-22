"""FUNNEL-SIGNATURE v1 — گاردِ کلیدِ دادهٔ کشِ قیف (P2-R2).

بدنهٔ قیف با امضایِ داده (revision/static_rev/session_day + screener cache +
tech context) کش می‌شود. اگر هر یک از این ورودی‌ها عوض شود، کلید باید عوض
شود؛ وگرنه پاسخِ ۳۰۴/کش‌شده دادهٔ کهنه را تأیید می‌کند.

usage: python dev/funnel_signature_v1.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def main():
    import api.funnel as F
    import market_state as MS
    import api.screener as SC

    base = F._data_signature()
    ck("دو فراخوانِ پیاپی همان امضا را می‌دهند", base == F._data_signature(), base)

    orig_rev = MS.revision
    MS.revision = lambda: int(orig_rev()) + 1
    try:
        ck("تغییرِ revision امضا را عوض می‌کند", F._data_signature() != base)
    finally:
        MS.revision = orig_rev

    old_ts = SC._SCREENER_CACHE.get("ts")
    SC._SCREENER_CACHE["ts"] = float(old_ts or 0) + 1.0
    try:
        ck("تغییرِ screener cache امضا را عوض می‌کند", F._data_signature() != base)
    finally:
        SC._SCREENER_CACHE["ts"] = old_ts

    old_tech = F._TECH_CTX.get("ts")
    F._TECH_CTX["ts"] = float(old_tech or 0) + 1.0
    try:
        ck("تغییرِ tech context امضا را عوض می‌کند", F._data_signature() != base)
    finally:
        F._TECH_CTX["ts"] = old_tech

    print("\n%d بررسی، %d سبز، %d سرخ" % (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("FUNNEL-SIGNATURE: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
