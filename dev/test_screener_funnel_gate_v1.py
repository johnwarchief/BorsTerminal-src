# dev/test_screener_funnel_gate_v1.py — بند ۷.۱: اسکرینر بقایایِ قیف را می‌خواند
"""رأیِ مالک (1405-07-20): `api/screener` نباید اسکنِ مستقلِ بنیادی‌اولِ کلِ بازار
باشد و نباید راهی برای دورزدنِ قیف بدهد. این گارد همان را می‌بندد:

    funnel_candidate ⇒ tape=pass ∧ technical=pass ∧ fundamental=pass
    technical=pass   ⇒ tape=pass                  (تکنیکال فقط ورودیِ عبورکرده را می‌بیند)
    بی‌قیف (خطا/unavailable) ⇒ هیچ کاندیدی نیست   («نداریم» جای «قبول» را نمی‌گیرد)
    سنجیده‌نشده (pending/unavailable/not_required) ⇒ کاندید نیست، و «رد» هم نیست

و دروازۀِ `symbols=` فقط کم می‌کند: هیچ پارامتری کاندیدِ بی‌عبور از قیف نمی‌سازد.
بخشِ آخر رویِ بانکِ محلی و موتورِ واقعی اجرا می‌شود؛ بی‌بانک ⇒ SKIP.
"""
import inspect
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import funnel_engine as FE                       # noqa: E402
from api.screener import (_apply_funnel_gate,    # noqa: E402
                          _funnel_gate, _only_symbols, get_screener)

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def matrix(**cells):
    """status_matrixِ ساختگی با همان شکلِ خودِ موتور: {symbol: {stage: {status}}}"""
    out = {}
    for sym, (t, x, f) in cells.items():
        out[sym] = {"tape": {"status": t, "human_reason": "ت"},
                    "technical": {"status": x, "human_reason": "ایست"},
                    "fundamental": {"status": f, "human_reason": "ب"},
                    "handover": {"status": f, "human_reason": "خ"}}
    return out


ROWS = [{"symbol": s, "score": 4} for s in
        ("allpass", "taperej", "techunmeasured", "techpending", "fundrej",
         "notonboard", "vetoed", "asmvetoed")]


def gate_applied(m):
    return {"state": "applied", "matrix": m,
            "block": {"state": "applied", "preset": "trend", "chain": []}}


M = matrix(
    allpass=(FE.PASS, FE.PASS, FE.PASS),
    taperej=(FE.REJECT, FE.NOT_REQUIRED, FE.NOT_REQUIRED),
    techunmeasured=(FE.PASS, FE.UNAVAILABLE, FE.NOT_REQUIRED),
    techpending=(FE.PASS, FE.PENDING, FE.NOT_REQUIRED),
    fundrej=(FE.PASS, FE.PASS, FE.REJECT),
    vetoed=(FE.PASS, FE.PASS, FE.PASS),
    asmvetoed=(FE.PASS, FE.PASS, FE.PASS),
)
rows_in = [dict(r) for r in ROWS]
rows_in[6]["weekly_veto"] = True
rows_in[7]["assembly_veto"] = True
out = {r["symbol"]: r for r in _apply_funnel_gate(rows_in, gate_applied(M))}

ck("هر سه گام pass ⇒ کاندید", out["allpass"]["funnel_candidate"] is True, out["allpass"])
ck("ردِ تابلوخوانی ⇒ کاندید نیست (و تکنیکال اصلاً اجرا نشده)",
   out["taperej"]["funnel_candidate"] is False
   and out["taperej"]["technical_status"] == FE.NOT_REQUIRED, out["taperej"])
ck("تکنیکالِ سنجیده‌نشده ⇒ کاندید نیست، «رد» هم نیست",
   out["techunmeasured"]["funnel_candidate"] is False
   and out["techunmeasured"]["technical_status"] == FE.UNAVAILABLE, out["techunmeasured"])
ck("تکنیکالِ در انتظار ⇒ کاندید نیست (cold-start رأیِ منفی نمی‌سازد)",
   out["techpending"]["funnel_candidate"] is False
   and out["techpending"]["technical_status"] == FE.PENDING, out["techpending"])
ck("ردِ بنیادی ⇒ کاندید نیست", out["fundrej"]["funnel_candidate"] is False, out["fundrej"])
ck("وتوی هفتگی کاندید را می‌شکند حتی با سه pass",
   out["vetoed"]["funnel_candidate"] is False, out["vetoed"])
ck("وتوی مجمع هم همین‌طور (زمان‌بندیِ ورود، نه ضعفِ بنیادی)",
   out["asmvetoed"]["funnel_candidate"] is False, out["asmvetoed"])
ck("ردیفی که در جامعۀِ تابلویِ امروز نیست ⇒ not_in_board، نه pass و نه reject",
   out["notonboard"]["gate_state"] == "not_in_board"
   and out["notonboard"]["funnel_candidate"] is False, out["notonboard"])
ck("علتِ ردِ تکنیکال از خودِ قیف منتقل می‌شود (ردپا بی‌حدسِ رابط)",
   out["taperej"].get("technical_reason") == "ایست", out["taperej"])

# ── بی‌قیف ⇒ هیچ کاندیدی ─────────────────────────────────────────────────────
for st in ("error", "unavailable"):
    g = {"state": st, "matrix": {}, "block": {"state": st, "message": "x"}}
    ann = _apply_funnel_gate([dict(r) for r in ROWS], g)
    ck(f"قیفِ {st} ⇒ صفر کاندید و gate_state اعلام می‌کند",
       all(r["funnel_candidate"] is False for r in ann)
       and all(r["gate_state"] == st for r in ann),
       [(r["symbol"], r["gate_state"]) for r in ann][:2])

# ── `watchlist`ِ بنیادی دست‌نخورده است (سازگاریِ مصرف‌کننده‌ها) ───────────────
wl = _apply_funnel_gate([{"symbol": "allpass", "watchlist": True}], gate_applied(M))
ck("پرچمِ قیف جای `watchlist`ِ اسکرینر را نمی‌گیرد (کارتِ قدیمی نمی‌شکند)",
   wl[0]["watchlist"] is True and wl[0]["funnel_candidate"] is True, wl[0])

# ── دروازۀِ symbols: فقط کم می‌کند ───────────────────────────────────────────
kept, asked = _only_symbols([{"symbol": "شپنا"}, {"symbol": "فولاد"}], ["شپنا"])
ck("symbols= فقط مجموعه را کم می‌کند", len(kept) == 1 and kept[0]["symbol"] == "شپنا"
   and asked == 1, kept)
kept2, asked2 = _only_symbols([{"symbol": "شپنا"}], ["شپنا", "ناموجود"])
ck("symbols= نمادِ ناشناخته اضافه نمی‌کند", len(kept2) == 1 and asked2 == 2, kept2)
kept3, asked3 = _only_symbols([{"symbol": "شپنا"}, {"symbol": "فولاد"}], [])
ck("symbols= خالی = بی‌فیلتر (همان همۀِ ردیف‌ها)", len(kept3) == 2 and asked3 == 0, kept3)
# نوشتارِ عربی/فارسی یکی است، نه دو نماد
kept4, _ = _only_symbols([{"symbol": "كيان"}], ["کیان"])
ck("normalizationِ نماد درِ دروازه هم کار می‌کند", len(kept4) == 1, kept4)

# ── دروازۀِ دورزدن وجود ندارد ────────────────────────────────────────────────
sig = inspect.signature(get_screener)
ck("هیچ پارامترِ «بی‌قیف»/«skip» درِ route نیست",
   not any(k.lower() in ("skip_funnel", "no_gate", "bypass", "ignore_funnel", "all")
           for k in sig.parameters), list(sig.parameters))
ck("پارامترها فقط preset/chain/symbols‌اند (همان سه)",
   set(sig.parameters) == {"symbols", "preset", "chain"}, list(sig.parameters))
src = io.open(os.path.join(ROOT, "api", "screener.py"), encoding="utf-8").read()
ck("پرچمِ قیف بیرونِ کشِ ۱۲ساعته حساب می‌شود (مثلِ وتوی مجمع)",
   src.index("def _screener_cached()") > src.index("def _apply_funnel_gate(")
   and "fresh[\"data\"] = _apply_funnel_gate(_apply_assembly_veto(rows), gate)" in src)
ck("منبعِ پرچم، status_matrixِ خودِ قیف است (نه کسرِ دوم)",
   "payload.get(\"status_matrix\")" in src and "FE.PASS" in src)

# ── رویِ بانک و موتورِ واقعی ─────────────────────────────────────────────────
if not os.path.exists(os.path.join(ROOT, "market.db")):
    ck("مقابلهٔ واقعی با market.db", None)
else:
    # قیفِ واقعی به اسنپ‌شاتِ تابلو نیاز دارد؛ درِ این پروسۀِ تنها همان را
    # خودمان گرم می‌کنیم (همان مسیری که `/api/market` می‌رود، بی‌شبکه).
    try:
        import api.market as _MK
        _MK.warm_market_cache()
    except Exception as e:
        print("  (گرم‌کردنِ تابلو نشد:", type(e).__name__, e, ")")
    try:
        gate = _funnel_gate("trend", [])
    except Exception as e:
        gate = {"state": "exception", "block": {"state": "exception"}, "matrix": {}}
        print("  (قیفِ واقعی نرسید:", e, ")")
    if gate.get("state") != "applied":
        ck("قیفِ واقعی ساخته شد (تابلو/اسکرینر درِ بانک هست)", None)
    else:
        rows = [{"symbol": s} for s in list(gate["matrix"])[:400]]
        ann = _apply_funnel_gate(rows, gate)
        cand = [r for r in ann if r["funnel_candidate"]]
        tech_pass = {r["symbol"] for r in ann if r["technical_status"] == FE.PASS}
        tape_pass = {r["symbol"] for r in ann if r["tape_status"] == FE.PASS}
        ck("واقعی: کاندید ⊆ بقایایِ تکنیکال", all(r["symbol"] in tech_pass for r in cand),
           [r["symbol"] for r in cand if r["symbol"] not in tech_pass][:5])
        ck("واقعی: بقایایِ تکنیکال ⊆ بقایایِ تابلوخوانی", tech_pass <= tape_pass,
           list(tech_pass - tape_pass)[:5])
        ck("واقعی: شمارشِ گام‌ها از خودِ پاسخ خواندنی است",
           all(k in (gate["block"].get("stages") or {})
               for k in ("tape", "technical", "fundamental", "handover")),
           list((gate["block"].get("stages") or {})))
        chain = gate["block"].get("chain") or []
        ck("واقعی: preset/chainِ به‌کاررفته اعلام می‌شود",
           bool(gate["block"].get("preset")) and isinstance(chain, list), gate["block"].get("preset"))

print("─" * 72)
print(f"نتیجۀِ گاردِ قیفِ اسکرینر: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
