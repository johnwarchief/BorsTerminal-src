# -*- coding: utf-8 -*-
"""dev/funnel_engine_v1.py — گاردِ داورِ canonicalِ قیف (۲۲ بندِ مأموریت)

همۀ «انتظار»ها بیرونِ موتور و با دستِ خودِ این فایل نوشته شده‌اند: ردیف‌هایِ
ساختگیِ مشخص می‌سازم و عددِ درست را از قبل می‌دانم. اگر موتور انتظار را عوض
کند، این گارد قرمز می‌شود — نه سبزِ دروغین.

اجرا:  python dev/funnel_engine_v1.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import funnel_engine as FE  # noqa: E402
import funnel_registry as REG  # noqa: E402

FAILED: list[str] = []


def ck(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


def board(sym: str, **flags) -> dict:
    r: dict = {"symbol": sym, "name": sym}
    for f in REG.filter_ids():
        r[f] = flags.get(f, False)
    return r


def screen(sym: str, **over) -> dict:
    r: dict = {
        "symbol": sym, "score": 0, "primary_score": 0, "i1_pass": None, "i2_pass": None,
        "i3_pass": None, "i4_pass": None, "i5_pass": None, "tech_trend_w": None,
        "tech_trend_d": None, "tech_matrix_decision": None, "assembly_veto": False,
    }
    r.update(over)
    return r


UP = dict(tech_trend_w="up", tech_trend_d="up", tech_matrix_decision="PERMITTED")
W_DOWN = dict(tech_trend_w="down", tech_trend_d="up", tech_matrix_decision="REJECT")
W_RANGE = dict(tech_trend_w="range", tech_trend_d="up", tech_matrix_decision="REJECT")
OK_FUND = dict(i1_pass=1, i2_pass=1, i3_pass=1, i4_pass=1, i5_pass=1, score=5, primary_score=3)


# ── Custom: اشتراکِ ترتیبی ────────────────────────────────────────────────
B = [board("الف", f_susp=True, f_noqteh=True), board("ب", f_susp=True, f_noqteh=False),
     board("پ", f_susp=False, f_noqteh=True), board("ت", f_susp=False, f_noqteh=False)]
S = [screen("الف", **UP, **OK_FUND), screen("ب", **UP, **OK_FUND),
     screen("پ", **UP, **OK_FUND), screen("ت", **UP, **OK_FUND)]

o = FE.evaluate(B, S, preset="custom", custom_chain=["f_susp", "f_noqteh"])
t1, t2 = o["stages"]["tape"]["steps"][0], o["stages"]["tape"]["steps"][1]
ck(t1["input_count"] == 4 and t1["matched_count"] == 2 and t1["removed_count"] == 2,
   "۱) F1 رویِ جامعۀ کامل: ۴ → ۲ (حجم مشکوک)")
ck(t2["input_count"] == 2 and t2["matched_count"] == 1,
   "۱) F2 فقط رویِ بازماندۀ F1: ۲ → ۱ (نقطه‌زنی)")
ck([e["symbol"] for e in o["handover"]] == ["الف"], "۱) خروجیِ نهایی فقط «الف» است")

o2 = FE.evaluate(B, S, preset="custom", custom_chain=["f_noqteh", "f_susp"])
s2 = o2["stages"]["tape"]["steps"]
ck([s["filter_id"] for s in s2] == ["f_noqteh", "f_susp"], "۲) ترتیبِ زنجیره عیناً ثبت می‌شود")
ck(s2[0]["input_count"] == 4 and s2[0]["matched_count"] == 2 and s2[1]["input_count"] == 2,
   "۲) شمارشِ مرحلهٔ دوم به ترتیبِ تازه بسته است، نه به ترتیبِ قبلی")

o3 = FE.evaluate(B, S, preset="custom", custom_chain=["f_susp", "f_jet"])
ck(o3["stages"]["tape"]["steps"][1]["matched_count"] == 0,
   "۳) OR نشت نکرده: «جت» هیچ‌کدام از حجم‌مشکوک‌ها را رد می‌کند و مجموع تهی می‌شود")
ck(len(o3["handover"]) == 0, "۳) با منطقِ OR این تست باید قرمز شود (۲ نماد می‌آمد)")

ck(set(REG.filter_ids()) == {"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh",
                             "f_smart", "f_legal"},
   "۴) رجیستری هر هفت فیلترِ docs/*.txt را بیرون می‌گذارد")
o4 = FE.evaluate(B, S, preset="custom", custom_chain=["f_smart"])
ck(o4["stages"]["tape"]["steps"][0]["label"] == "ورود پول هوشمند",
   "۴) فیلترِ پولِ هوشمند از چیپِ تابلو به زنجیرۀ قیف رسیده")

import json  # noqa: E402
chain_a = ["f_susp", "f_noqteh", "f_smart"]
run1 = FE.evaluate(B, S, preset="custom", custom_chain=chain_a, as_of=1)
run2 = FE.evaluate(B, S, preset="custom", custom_chain=chain_a, as_of=1)
pinned = json.dumps({k: run1[k] for k in ("stages", "trace", "handover", "chain")},
                    ensure_ascii=False, sort_keys=True)
pinned2 = json.dumps({k: run2[k] for k in ("stages", "trace", "handover", "chain")},
                     ensure_ascii=False, sort_keys=True)
ck(pinned == pinned2, "۵) یک ورودیِ یکسان ⇒ trace، شمارش‌ها و تحویل بایت‌به‌بایت یکی")
ck(run1["ruleset_version"] == REG.RULESET_VERSION and run1["engine_version"] == FE.ENGINE_VERSION,
   "۵) هر پاسخ با engine_version و ruleset_versionِ همان روز مهر شده")
ck(all(st["source_ref"].startswith("docs/") and st["formula_version"] for st in run1["stages"]["tape"]["steps"]),
   "۵) هر مرحله منبع و نسخۀ فرمولش را درِ trace دارد")

o5 = FE.evaluate([board("الف", f_clock=True)], [screen("الف", **UP, **OK_FUND)],
                 preset="custom", custom_chain=["f_clock"],
                 params={"f_clock": {"vol_mult": 3.0, "min_trades": 30}})
ck(o5["stages"]["tape"]["steps"][0]["parameter_set"] == {"vol_mult": 3.0, "min_trades": 30},
   "۶) parameter_setِ کاربر درِ trace همان مرحله می‌نشیند (کاننیکال عوض نمی‌شود)")

# ── تکنیکال: هفتگی اول ────────────────────────────────────────────────────
def tech_of(rows, sc):
    return FE.evaluate(rows, sc, preset="custom", custom_chain=[]).stages if False else \
        FE.evaluate(rows, sc, preset="custom", custom_chain=[])


d_down = FE.evaluate([board("x"), board("y")],
                     [screen("x", **W_DOWN, **OK_FUND), screen("y", **W_RANGE, **OK_FUND)],
                     preset="custom", custom_chain=[])
ck(d_down["stages"]["technical"]["counts"][FE.REJECT] == 2,
   "۷ و ۸) هفتگی نزولی و هفتگی خنثی هر دو رد")

d_branch = FE.evaluate([board("u", f_susp=True), board("v", f_susp=True), board("w", f_susp=True)],
                       [screen("u", tech_trend_w="up", tech_trend_d="up", tech_matrix_decision="PERMITTED", **OK_FUND),
                        screen("v", tech_trend_w="up", tech_trend_d="down", tech_matrix_decision="PERMITTED", **OK_FUND),
                        screen("w", tech_trend_w="up", tech_trend_d="range", tech_matrix_decision="PERMITTED", **OK_FUND)],
                       preset="custom", custom_chain=["f_susp"])
br = {t["symbol"]: t["branch"] for t in d_branch["trace"]["technical"]}
ck(br["u"] == "جت / پولبک" and br["v"] == "فیبوناچی / CHoCH"
   and br["w"] == "کف دوقلو / آخرین ساختار حمایت-مقاومت",
   "۹، ۱۰ و ۱) شاخه‌هایِ روزانه بعد از صعودیِ هفتگی درست‌اند")

d_veto = FE.evaluate([board("z", f_susp=True)],
                     [screen("z", tech_trend_w="down", tech_trend_d="up", tech_matrix_decision="REJECT",
                             tech_jet=1, tech_choch_bull=1, tech_points=5, **OK_FUND)],
                     preset="custom", custom_chain=["f_susp"])
ck(not d_veto["handover"], "۱۲) جت + CHoCH + امتیازِ پنج، وتوی هفتگی را نمی‌شکنند")

# ── بنیادی: سه حالت ───────────────────────────────────────────────────────
def fund(symbols_rows, mode, exc=None):
    rows, sc = symbols_rows
    return FE.evaluate(rows, sc, preset="custom", custom_chain=[], fund_mode=mode,
                       exceptions=exc)


one_i3_bad = ([board("a")], [screen("a", **UP, i1_pass=1, i2_pass=1, i3_pass=0,
                                    i4_pass=1, i5_pass=1, score=4, primary_score=2)])
std = fund(one_i3_bad, "standard")
ck(not std["handover"], "۱۳) standard: I3 رد ⇒ نماد رد (حتی با I4/I5 کامل)")
hard = fund(one_i3_bad, "hard")
ck(not hard["handover"], "۱۴) hard: همان رد")
one_i4_bad = ([board("a")], [screen("a", **UP, i1_pass=1, i2_pass=1, i3_pass=1,
                                    i4_pass=0, i5_pass=1, score=4, primary_score=3)])
ck(bool(fund(one_i4_bad, "standard")["handover"]), "۱۴) hard: I4 رد ⇒ درِ standard قبول، درِ hard رد")
ck(not fund(one_i4_bad, "hard")["handover"], "۱۴) hard: I4 رد ⇒ رد")

missing = ([board("a")], [screen("a", **UP, i1_pass=None, i2_pass=1, i3_pass=1,
                                 i4_pass=1, i5_pass=1, score=4, primary_score=2)])
ms = fund(missing, "standard")
ck(ms["stages"]["fundamental"]["counts"][FE.PENDING] == 1 and not ms["handover"],
   "۱۵) بی‌دادهٔ بلاکر = PENDING، نه pass و نه reject")

exc = fund(one_i3_bad, "exception", {"a": ["I3"]})
ent = exc["handover"]
ck(len(ent) == 1 and ent[0]["exception"] and ent[0]["exceptions"] == ["I3"],
   "۱۶) استثنایِ صریح برچسب دارد و درِ trace می‌ماند")
ck(exc["trace"]["fundamental"][0]["canonical"] == FE.REJECT
   and exc["trace"]["fundamental"][0]["effective"] == FE.PASS,
   "۱۸) canonical و effective جدا نگه داشته شده‌اند")
ck(not fund(one_i3_bad, "exception", {"a": ["I1"]})["handover"],
   "۱۹) استثنایِ اشتباه (I1 درحالی‌که I3 رد است) کمکی نمی‌کند")
ck(not fund(one_i4_bad, "exception", {"a": ["I4"]})["stages"]["fundamental"]["counts"][FE.REJECT],
   "۱۷) I4/I5 درِ standard جبران‌کنندهٔ بلاکر نیستند و ردی تولید نمی‌کنند")

# ── تحویل ─────────────────────────────────────────────────────────────────
mix = ([board("الف", f_susp=True), board("ب", f_susp=True), board("پ", f_susp=True)],
       [screen("الف", **UP, i1_pass=1, i2_pass=1, i3_pass=1, i4_pass=0, i5_pass=0, score=3, primary_score=3),
        screen("ب", **UP, i1_pass=1, i2_pass=1, i3_pass=1, i4_pass=1, i5_pass=1, score=5, primary_score=3,
               tech_points=2),
        screen("پ", **UP, i1_pass=1, i2_pass=1, i3_pass=1, i4_pass=1, i5_pass=0, score=4, primary_score=3)])
hx = FE.evaluate(*mix, preset="custom", custom_chain=["f_susp"])
ck([e["symbol"] for e in hx["handover"]] == ["ب", "پ", "الف"],
   "۱۹ و ۲۱) بهترین‌ها اول: حکم ⇒ بی‌استثنا ⇒ امتیازِ بنیادی ⇒ شاهدِ تکنیکال ⇒ رتبۀ بک‌اند")
ck(all(e["display_rank"] == i for i, e in enumerate(hx["handover"], 1)),
   "۲۱) رتبۀ نمایشی پیوسته و بازتولیدشدنی است")
ck(hx["stages"]["tape"]["steps"][0]["input_count"] == 3 and len(hx["handover"]) == 3,
   "۲۰) هیچ سقفی درِ موتور نیست: هر سه ورودی، هر سه خروجی")
big = ([board(f"s{i}", f_susp=True) for i in range(1200)],
       [screen(f"s{i}", **UP, **OK_FUND) for i in range(1200)])
bx = FE.evaluate(big[0], big[1], preset="custom", custom_chain=["f_susp"])
ck(len(bx["handover"]) == 1200, "۲۰) ۱۲۰۰ نماد ورودی ⇒ ۱۲۰۰ نماد درِ تحویل (بی‌slice)")
src = open(os.path.join(REPO, "funnel_engine.py"), encoding="utf-8").read()
ck(".slice(" not in src and "[:60]" not in src and "[:50]" not in src,
   "۲۰) درِ متنِ موتور هم هیچ برشِ ثابتی نیست")
ck(hx["handover"][0]["why"] and all("code" in w for w in hx["handover"][0]["why"]),
   "۲۲) هر ردیفِ تحویل دلیلِ رمزگذاری‌شده (reason_code) دارد")

# ── نمایِ آمادهٔ رندر (خط ۵، ۶، ۷ و ۲۶ مأموریت) ────────────────────────────
V = FE.evaluate(B, S, preset="custom", custom_chain=["f_susp", "f_noqteh"])
tape_syms = {e["symbol"] for e in V["entries"]["tape"] if e["status"]["tape"] == "pass"}
tech_syms = {e["symbol"] for e in V["entries"]["technical"]}
fund_syms = {e["symbol"] for e in V["entries"]["fundamental"]}
ck(tech_syms <= tape_syms and fund_syms <= tech_syms,
   "۲۳) survivors هر گام زیرمجموعۀ گامِ قبلی است (Y ⊆ X) — درِ همان پاسخِ API")
tl = V["timeline"]["ب"]
ck([t["stage"] for t in tl] == ["universe", "tape:f_susp", "tape:f_noqteh"],
   "۲۴) خطِ زمانِ نمادِ ردشده درِ همان فیلتر می‌ایستد و ادامه نمی‌یابد")
ck(all(t.get("reason_code") and t.get("human_reason") and "input_count" in t for t in tl),
   "۲۴) هر گامِ trace دلیلِ رمزگذاری‌شده + شمارۀ ورودی/خروجی دارد")
ck(tl[-1]["source"].startswith("docs/") and "formula_version" in tl[-1],
   "۲۴) منبع و نسخۀ فرمولِ همان فیلتر درِ trace هست، نه فقط نامِ مرحله")
ck(all("source_ref" in st and st["parameter_set"] for st in V["stages"]["tape"]["steps"]),
   "۲۵) هر مرحلۀ زنجیره parameter_set و source_ref خودش را درِ پاسخ دارد")
row = V["entries"]["tape"][0]
for k in ("symbol", "name", "sector", "last", "change_pct", "vol_ratio", "patterns",
          "status", "why", "score", "weekly", "daily", "branch", "inds", "as_of"):
    if k not in row:
        ck(False, f"۲۶) ردیفِ نمایشی ستونِ {k} را ندارد")
        break
else:
    ck(True, "۲۶) ردیفِ نمایشی هر ستونی که جدول می‌خواهد را از API می‌گیرد (بدون join فرانت)")

print()
if FAILED:
    print(f"funnel_engine guard: {len(FAILED)} FAILED")
    sys.exit(1)
print(f"funnel_engine guard OK — {26} بندِ مأموریت")
