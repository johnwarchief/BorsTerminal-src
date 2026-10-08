# -*- coding: utf-8 -*-
"""dev/funnel_engine_v1.py — گاردِ داورِ canonicalِ قیف (۳۸ بندِ مأموریت)

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

# ── قانونِ جامع: تک‌تکِ نمادها وضعیتِ صریح دارند (§8 و §10) ────────────────
U = [board(f"n{i}", f_susp=(i % 3 == 0), f_noqteh=(i % 4 == 0)) for i in range(40)]
SC = [screen(f"n{i}", **(UP if i % 5 else W_DOWN), **OK_FUND) for i in range(40)]
M = FE.evaluate(U, SC, preset="custom", custom_chain=["f_susp", "f_noqteh"])
uni = M["universe"]["joined"]
ck(uni == 40, "۲۷) جامعۀ ورودی شمرده و درِ پاسخ است")
for stage in ("tape", "technical", "fundamental", "handover"):
    tot = sum(M["coverage"][stage].values())
    ck(tot == uni, f"۲۸) {stage}: جمعِ وضعیت‌ها = جامعۀ ورودی ({tot} = {uni})")
ck(set(M["status_matrix"]) == {f"n{i}" for i in range(40)},
   "۲۹) هیچ نمادی از matrix بیرون نیفتاده (بی‌سایلنت‌دراپ)")
DUP = [board("تکراری", f_susp=True), board("تکراری", f_susp=True), board("دیگر", f_susp=True)]
DP = FE.evaluate(DUP, [screen("تکراری", **UP, **OK_FUND), screen("دیگر", **UP, **OK_FUND)],
                 preset="custom", custom_chain=["f_susp"])
ck(DP["universe"]["board"] == 3 and DP["universe"]["joined"] == 2
   and DP["universe"]["duplicate_rows"] == 1,
   "۳۵) ردیفِ هم‌نام دوم نماد شمرده نمی‌شود و صریح گزارش می‌شود")
ck(len(DP["status_matrix"]) == DP["universe"]["joined"]
   == sum(DP["coverage"]["handover"].values()),
   "۳۵) matrix، جامعۀ یکتا و جمعِ وضعیت‌ها هر سه یک عدد")
bad = [s for s, row in M["status_matrix"].items()
       if any(c["status"] not in FE.STATUSES or not c.get("reason_code") for c in row.values())]
ck(not bad, "۳۰) هر خانۀ matrix وضعیتِ معتبر + reason_code دارد")
rej = sorted(s for s, row in M["status_matrix"].items() if row["tape"]["status"] == FE.REJECT)
ck(rej and all(M["status_matrix"][s]["technical"]["status"] == FE.NOT_REQUIRED for s in rej),
   "۳۱) ردشدۀ تابلو درِ تکنیکال NOT_REQUIRED است، نه «سنجیده نشده»")
ck(all(M["status_matrix"][s]["technical"]["reason_code"] == "NOT_REQUIRED_AFTER_TAPE_REJECT"
       for s in rej), "۳۱) علتِ اجرا‌نشدن هم درِ trace ثبت می‌شود")
ck(all(M["status_matrix"][s]["fundamental"]["status"] == FE.NOT_REQUIRED for s in rej),
   "۳۱) بنیادی هم برای همان نماد NOT_REQUIRED است، نه حذف")
# نمادی که ردیفِ اسکرینر ندارد: تکنیکال UNAVAILABLE (نه سنجیده‌نشِ مبهم) و
# بنیادی NOT_REQUIRED با علت؛ تحویل هم UNAVAILABLE می‌گوید، نه حذفِ نماد.
no_screen = [board("بی‌کدال", f_susp=True), board("باکدال", f_susp=True),
             screen("باکدال", **UP, **OK_FUND)]
NS = FE.evaluate(no_screen, [screen("باکدال", **UP, **OK_FUND)],
                 preset="custom", custom_chain=["f_susp"])
row_ns = NS["status_matrix"]["بی‌کدال"]
ck(row_ns["technical"]["status"] == FE.UNAVAILABLE
   and row_ns["technical"]["reason_code"] == "TECH_UNMEASURED",
   "۳۲) نمادِ بی‌ردیفِ اسکرینر: تکنیکال UNAVAILABLE با کد، نه سنجیده‌نشِ مبهم")
ck(row_ns["fundamental"]["status"] == FE.NOT_REQUIRED
   and row_ns["fundamental"]["reason_code"].startswith("NOT_REQUIRED_AFTER"),
   "۳۲) بنیادیِ آن نماد NOT_REQUIRED است با علت، نه غایب")
ck(row_ns["handover"]["status"] == FE.UNAVAILABLE
   and row_ns["handover"]["reason_code"] == "NO_FINAL_SOURCE",
   "۳۲) تحویل هم وضعیت دارد: بی‌منبع، نه گم‌شده")
# بلاکرِ بی‌داده ⇒ PENDING با کدِ هر شاخص (نه pass، نه reject)
miss = FE.evaluate([board("کم‌گزارش", f_susp=True)],
                   [screen("کم‌گزارش", **UP, i1_pass=None, i2_pass=1, i3_pass=1,
                           i4_pass=1, i5_pass=1, score=4, primary_score=2)],
                   preset="custom", custom_chain=["f_susp"])
mr = miss["status_matrix"]["کم‌گزارش"]
ck(mr["fundamental"]["status"] == FE.PENDING
   and mr["fundamental"]["reason_code"] == "FUND_I1_MISSING",
   "۳۳) I1 بی‌گزارش = PENDING با کدِ FUND_I1_MISSING")
ck(mr["handover"]["status"] == FE.PENDING,
   "۳۳) تحویل هم همان انتظار را می‌گوید، نماد ناپدید نمی‌شود")
ck(all(isinstance(M["status_matrix"][s]["handover"].get("display_rank"), int)
       for s, row in M["status_matrix"].items() if row["handover"]["status"] == FE.PASS),
   "۳۴) رتبۀ نمایشی برایِ هر پذیرفته‌شده ثبت شده")

# -- ۳۶) پیمانِ HTTP: همان جامعیت باید از سیم هم عبور کند
# پاسخِ فهرست عمداً بی‌`timeline` است (خطِ زمانِ ۵٫۸ هزار نماد نیمی از پاسخ بود
# و جدولِ فهرست هرگز همه‌اش را نمی‌خواند). دو چیز نباید با این برش برود:
# `status_matrix` (حکمِ هر نماد درِ هر گام) و `coverage` (جمعِ پنج وضعیت).
import api.funnel as FA
STRIPPED = FA._strip(M)
ck("timeline" not in STRIPPED,
   "۳۶) خطِ زمانِ همهٔ نمادها از پاسخِ فهرست بیرون است، نه از داوری")
ck("status_matrix" in STRIPPED and "coverage" in STRIPPED,
   "۳۶) برشِ پاسخ، matrix و coverage را دست نمی‌زند")
_FIVE = ("pass", "reject", "pending", "unavailable", "not_required")
ck(all(sum(STRIPPED["coverage"][g].get(s, 0) for s in _FIVE) == STRIPPED["universe"]["joined"]
       for g in ("tape", "technical", "fundamental", "handover")),
   "۳۶) جمعِ پنج وضعیت درِ هر گام == جامعۀ ورودی، رویِ سیمِ HTTP هم")
ck(len(STRIPPED["status_matrix"]) == STRIPPED["universe"]["joined"],
   "۳۶) یک سطرِ وضعیت برایِ هر نمادِ universe درِ پاسخ هست")
ck(all(set(cell) >= {"status", "reason_code", "human_reason"}
       for row in STRIPPED["status_matrix"].values() for cell in row.values()),
   "۳۶) هر سلولِ پاسخ حکم + کدِ دلیل + متنِ دلیل دارد")
# -- ۳۷) تکنیکال از داوریِ کلِ جوامع خوانده می‌شود، نه از پنجاه ردیفِ اسکرینر
# `api/screener.py` فقط `watchlist_max` ردیفِ اول را غنی می‌کند؛ اگر قیف همان
# را منبعِ رأیِ تکنیکال می‌گذاشت، رسیدگانِ پنجاه‌ویکم هیچ‌وقت داوری نمی‌شدند.
# اینجا موتور `tech_scan` (ردیف‌هایِ `funnel_tech_scan`) و `tech_sigs` (امضایِ
# داده) می‌گیرد و سه حالت را از هم جدا می‌کند: رأیِ ساخته‌شده / در انتظارِ
# اسکن / بی‌سابقهٔ قیمتی.
BS = [board("بی‌تحلیل", f_susp=True), board("درصف", f_susp=True), board("بی‌سابقه", f_susp=True)]
BSR = [screen("بی‌تحلیل"), screen("درصف"), screen("بی‌سابقه")]
g_scan = FE.evaluate(BS, BSR, preset="custom", custom_chain=["f_susp"],
                     tech_scan={"بی‌تحلیل": {"tech_trend_w": "up", "tech_trend_d": "down",
                                               "tech_matrix_decision": "PERMITTED"}},
                     tech_sigs={"بی‌تحلیل": "1405-07-16|128", "درصف": "1405-07-16|94"})
M1 = g_scan["status_matrix"]["بی‌تحلیل"]["technical"]
ck(M1["status"] == FE.PASS and M1["reason_code"] == "WEEKLY_TREND_UP",
   "۳۷) رسیدۀ پنجاه‌ویکم از ردیفِ اسکن داوری می‌گیرد (نه از سقفِ اسکرینر)")
ck(g_scan["status_matrix"]["بی‌تحلیل"]["technical"]["human_reason"],
   "۳۷) دلیلِ همان رأی هم درِ پاسخ است")
M2 = g_scan["status_matrix"]["درصف"]["technical"]
ck(M2["status"] == FE.PENDING and M2["reason_code"] == "TECH_SCAN_PENDING",
   "۳۷) سابقه دارد و اسکن نرسیده ⇒ PENDING با کد، نه «سنجیده نشده» و نه حذف")
ck(g_scan["status_matrix"]["درصف"]["fundamental"]["status"] == FE.NOT_REQUIRED,
   "۳۷) گامِ بعد از توقفِ گامِ قبل خبردار است، نه بی‌حکم")
M3 = g_scan["status_matrix"]["بی‌سابقه"]["technical"]
ck(M3["status"] == FE.UNAVAILABLE and M3["reason_code"] == "TECH_NO_HISTORY",
   "۳۷) هیچ سابقۀ قیمتی = UNAVAILABLE با کدِ خودش (تلاشِ بی‌حاصل نیست، نشدنی است)")
_FIVE2 = ("pass", "reject", "pending", "unavailable", "not_required")
ck(all(sum(g_scan["coverage"][s].get(x, 0) for x in _FIVE2) == 3
       for s in ("tape", "technical", "fundamental", "handover")),
   "۳۷) با سه حالتِ تازه هم جمعِ وضعیت‌ها == جامعۀ ورودی")

# -- ۳۸) جامعۀ تابلو ≠ جامعۀ غربالگری (رأیِ مالک ۱۴۰۵-۰۷-۱۶، بندِ ۱۴ و ۱۵)
# چهار نمادِ همۀ فیلتر را دارند؛ سه تا از آنها به سه علتِ *متفاوت* از جامعۀ
# غربالگری بیرون‌اند. ملاک، وضعیتِ رسمیِ بازار است — نه عددِ اختراعی.
U4 = [board("سالم", f_susp=True),
     {**board("متوقف", f_susp=True), "stop_state": "تعلیق شده"},
     {**board("کهنه", f_susp=True), "is_live": False},
     {**board("ممنوع", f_susp=True), "st_code": "IS", "st_title": "ممنوع-متوقف"}]
U4S = [screen("سالم", **UP, **OK_FUND), screen("متوقف", **UP, **OK_FUND),
       screen("کهنه", **UP, **OK_FUND), screen("ممنوع", **UP, **OK_FUND)]
u4 = FE.evaluate(U4, U4S, preset="custom", custom_chain=["f_susp"])
ck(u4["universe"]["market"] == 4 and u4["universe"]["screening"] == 1
   and u4["universe"]["excluded"] == 3,
   "۳۸) X=۴ نمادِ تابلو، Y=۱ جامعۀ غربالگری، Z=۳ خارج — هر سه جدا شمرده می‌شوند")
ck(u4["universe"]["market"] == u4["universe"]["screening"] + u4["universe"]["excluded"],
   "۳۸) X = Y + Z درِ خودِ پاسخ")
ck([e["symbol"] for e in u4["entries"]["tape"]] == ["سالم"],
   "۳۸) خارج‌ها درِ جدولِ گام نمی‌نشینند (رأیِ مالک: جدول را شلوغ نکن)")
ck(all(u4["status_matrix"]["کهنه"][g]["status"] == FE.NOT_IN_UNIVERSE
       for g in ("tape", "technical", "fundamental", "handover")),
   "۳۸) خارج از جامعه درِ هر چهار گام همان وضعیت است — نه reject و نه pending")
ck({e["symbol"]: e["reason_code"] for e in u4["exclusions"]}
   == {"متوقف": "STOPPED", "کهنه": "NOT_LIVE_SESSION", "ممنوع": "FORBIDDEN_STATE"},
   "۳۸) علتِ خروجِ تک‌تکِ خارج‌ها ثبت می‌شود (هیچ‌کس بی‌علت حذف نمی‌شود)")
ck(u4["universe"]["exclusion_labels"].get("STOPPED")
   and set(u4["universe"]["exclusion_labels"]) == set(u4["universe"]["exclusion_counts"]),
   "۳۸) واژۀ فارسیِ هر علت از خودِ موتور می‌آید، نه از رابط")

# -- ۳۹) «زنده» ≠ «امروز معامله داشت» (رأیِ صریحِ مالک، بندِ ۱۴)
V2 = [{**board("بی‌معامله", f_susp=True), "is_live": True, "q_tot_tran": 0},
      {**board("پرحجم_ممنوع", f_susp=True), "is_live": True, "q_tot_tran": 9_999_999,
       "st_code": "I", "st_title": "ممنوع"}]
v2 = FE.evaluate(V2, [screen("بی‌معامله"), screen("پرحجم_ممنوع")],
                 preset="custom", custom_chain=["f_susp"])
ck(v2["universe"]["screening"] == 1
   and [e["symbol"] for e in v2["exclusions"]] == ["پرحجم_ممنوع"],
   "۳۹) حجمِ امروز نمادی را داخل جامعه نمی‌کند؛ وضعیتِ ممنوع بیرونش می‌اندازد")
ck(v2["status_matrix"]["بی‌معامله"]["tape"]["status"] == FE.PASS,
   "۳۹) نمادِ بی‌معاملۀ امروز درِ جامعۀ غربالگری می‌ماند و حکم می‌گیرد")

# -- ۴۰) silent drop ممنوع، دو سو (بندِ ۱۶: «هیچ نمادی نباید بی‌حکم بماند»)
_SIX = ("pass", "reject", "pending", "unavailable", "not_required", FE.NOT_IN_UNIVERSE)
ck(all(sum(u4["coverage"][g].values()) == 4 for g in ("tape", "technical",
       "fundamental", "handover")),
   "۴۰) جمعِ شش وضعیت درِ هر گام == جامعۀ تابلو (X)")
ck(all(sum(u4["coverage"][g].get(s, 0) for s in _SIX if s != FE.NOT_IN_UNIVERSE) == 1
       for g in ("tape", "technical", "fundamental", "handover")),
   "۴۰) جمعِ پنج وضعیتِ گام == جامعۀ غربالگری (Y) — هیچ نمادِ واجدِ شرایط بی‌حکم نیست")
ck(len(u4["status_matrix"]) == 4, "۴۰) سطرِ وضعیت برایِ هر چهار نماد هست، خارج‌ها هم")

# -- ۴۱) جامعۀ غربالگری پویا است: نه عددِ ثابت، نه سقفِ واچ‌لیست
_SRC = open("funnel_engine.py", encoding="utf-8").read()
ck("2273" not in _SRC and "3991" not in _SRC,
   "۴۱) هیچ شمارۀ جامعۀ ثابتی (۲۲۷۳ / ۳۹۹۱) درِ موتور ننوشته شده")
BIG = [board(f"ن{i:03d}", f_susp=True) for i in range(121)]
BIGS = [screen(f"ن{i:03d}") for i in range(121)]
big = FE.evaluate(BIG, BIGS, preset="custom", custom_chain=["f_susp"])
ck(big["universe"]["screening"] == 121 and len(big["status_matrix"]) == 121
   and len(big["entries"]["tape"]) == 121,
   "۴۱) ۱۲۱ نماد ورودی ⇒ ۱۲۱ نماد درِ غربالگری؛ ظرفیتِ واچ‌لیست (۶۰) هیچ‌جا جامعۀ "
   "غربالگری را کوتاه نمی‌کند")
u5 = FE.evaluate(U4 + [board("افزون", f_susp=True)], U4S + [screen("افزون")],
                 preset="custom", custom_chain=["f_susp"])
ck(u5["universe"]["screening"] == u4["universe"]["screening"] + 1,
   "۴۱) Y با خودِ داده تغییر می‌کند، نه با عددی درِ کد")

print()
if FAILED:
    print(f"funnel_engine guard: {len(FAILED)} FAILED")
    sys.exit(1)
print(f"funnel_engine guard OK — {42} بندِ مأموریت")
