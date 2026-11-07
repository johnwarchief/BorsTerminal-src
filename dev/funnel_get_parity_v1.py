"""FUNNEL-GET-PARITY v1 — گاردِ برابریِ GETِ شرطی با POST (P2-R2).

رابط برایِ پاسخِ ۳۰۴ِ صفر‌بایت، قیف را با GET (همان پارامترها در query) می‌خواند.
این گارد ثابت می‌کند بدنهٔ GET با بدنهٔ POST برایِ همان ورودی یکی است — با
پارامترهایِ ساده و با `exceptions`/`strategy_settings` (که پیش‌تر فقط در POST
بودند). `as_of` و `cached_for_ms` نوسانی‌اند و مقایسه نمی‌شوند؛ هیچ داوری یا
فیلدِ دیگری مستثنی نیست.

خواندنی؛ بدونِ market.db ⇒ SKIP.

usage: python dev/funnel_get_parity_v1.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

VOLATILE = ("as_of", "cached_for_ms")


class Req:
    def __init__(self):
        self.headers = {}
        self.method = "GET"


def _stable(obj):
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def _json(resp):
    return json.loads(bytes(resp.body).decode("utf-8"))


def main():
    if not os.path.exists("market.db"):
        print("SKIP: market.db نیست")
        return 0
    import api.funnel as F

    checks = []

    def ck(label, ok, detail=""):
        checks.append(bool(ok))
        print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))

    def compare(label, get_kwargs, post_call):
        g = _json(F.get_funnel(Req(), **get_kwargs))
        p = _json(post_call())
        ck(label, _stable(g) == _stable(p),
           "get=%s post=%s status=%s/%s" %
           (g.get("status"), p.get("status"), g.get("as_of"), p.get("as_of")))

    base_get = dict(preset="trend", chain="", fund_mode="standard", drop_suffix=True,
                    logic="and", tech_chain="", exceptions="{}",
                    strategy_settings="{}", params="{}")
    compare("GET ساده == POST ساده", base_get,
            lambda: F._funnel_http(Req(), "trend", [], "standard", {}, {}))

    exc = {"فولاد": ["I1"]}
    stg = {"clock_delta_pct": "2"}
    get2 = dict(base_get, exceptions=json.dumps(exc, ensure_ascii=False),
                strategy_settings=json.dumps(stg, ensure_ascii=False))
    compare("GET با exceptions/strategy_settings == POST", get2,
            lambda: F._funnel_http(Req(), "trend", [], "standard", {}, exc, settings=stg))

    print("\n%d بررسی، %d سبز، %d سرخ" % (len(checks), sum(checks), len(checks) - sum(checks)))
    print("FUNNEL-GET-PARITY: " + ("PASS" if all(checks) else "FAIL"))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
