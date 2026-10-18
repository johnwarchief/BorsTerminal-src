#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/bot_api_v1114.py — گاردِ دروازۀ ربات (`api/bot.py`).

چرا: `paper_trading.py` از دورِ پیش ۵۴ سنجه داشت، ولی آن‌ها *موتور* را می‌سنجیدند.
آنچه درِ نسخهٔ ۱٫۰٫۸۸ وجود نداشت و این گارد می‌سنجد، **مسیرِ قابل‌استفاده** است:
پیکربندیِ اعتبارسنجی‌شده، اجرایِ دستیِ یکِ نشست، وضعیت/تاریخچه، توقف/ادامه، و
سه قفلِ اجرایِ واقعی. بی‌این گارد، «ربات هست» فقط یعنی «کلاسی درِ ریپو هست».

چه چیزی عمداً تزریق می‌شود: `default_ledger` (بانکِ موقت، نه user.dbِ کاربر)،
`_judge` (داورِ قطعیِ ساختگی، تا گارد به تابلویِ زنده وابسته نشود)، `_bars`
(ردیفِ ثابت)، و `_live_gates` (برایِ اثباتِ اینکه قفل‌ها واقعاً بسته‌اند).
هیچ درخواستِ شبکه‌ای به بیرون نمی‌رود و هیچ سفارشی به کارگزاری نمی‌رسد.

اجرا:  python dev/bot_api_v1114.py        (۰ = سبز، ۱ = رد)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.bot as BOT

REAL_JUDGE = BOT._judge          # پیشِ هر stub در install_stubs()
from execution_ledger import ARMED, HALT, TRIPPED, ExecutionLedger
from bot_signals import verdicts_to_membership
from trade_sim import Bar

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:160]))
    return bool(cond)


# ── بسترِ آزمایش ─────────────────────────────────────────────────────────────
_tmp = tempfile.mkdtemp(prefix="bors_bot_api_")
LEDGER = ExecutionLedger(os.path.join(_tmp, "bot.db"))
app = FastAPI()
app.include_router(BOT.router)
client = TestClient(app)

SESSIONS = ["20261001", "20261004", "20261005", "20261006"]
PRICES = {"A": [100.0, 104.0, 108.0, 112.0], "B": [50.0, 49.0, 48.0, 47.0]}
#: داورِ ساختگی ولی قطعی: A ازِ نشستِ سوم درِ قیف است، B هیچ‌وقت نیست.
SURVIVORS = {SESSIONS[0]: [], SESSIONS[1]: [], SESSIONS[2]: ["A"], SESSIONS[3]: ["A"]}
#: شمارشگرهایِ «یکِ فشارِ دکمه»: داور باید یک‌بار صدا زده شود و ردیف فقط برایِ
#: نمادهایِ اقدام‌پذیر بیاید. این دو عدد همان چیزی است که ۱۲۹٬۶۱۳ ردیف را ساخت.
JUDGE_CALLS: list[str] = []
BARS_CALLS: list[tuple] = []


def install_stubs(session_day=SESSIONS[-1]):
    """چهار درزِ تزریق: بانکِ موقت، داور، ردیف‌ها، و قفل‌هایِ زنده."""
    BOT.default_ledger = lambda: LEDGER
    BOT._board_day = lambda: int(session_day)

    def fake_judge(cfg):
        def judge(session):
            JUDGE_CALLS.append(str(session))
            surv = SURVIVORS.get(str(session), [])
            return verdicts_to_membership(surv, list(PRICES))
        return judge
    BOT._judge = fake_judge

    def fake_bars(cfg, day, symbols=None):
        BARS_CALLS.append((int(day), None if symbols is None else set(symbols)))
        out = []
        prev = {}
        for d in SESSIONS:
            if int(d) != int(day):
                continue
            for sym, series in PRICES.items():
                if symbols is not None and sym not in symbols:
                    continue
                c = series[SESSIONS.index(d)]
                o = prev.get(sym, c)
                out.append(Bar(symbol=sym, date=d, open=o, high=max(o, c) * 1.01,
                               low=min(o, c) * 0.99, close=c, volume=1_000_000.0,
                               prev_close=prev.get(sym), src="guard"))
                prev[sym] = c
        return out
    BOT._bars = fake_bars
    BOT._live_gates = lambda: {"env_live": False, "adapter": "mock", "session": "none",
                               "capabilities": {}, "live_capable": False, "dry_run": True,
                               "all_open": False, "live_wired": False,
                               "broker_wired": "paper_only",
                               "live_wired_reason": "stub: کاغذیِ hard-wired"}


def reset_state():
    LEDGER.save_state(BOT.CONFIG_KEY, dict(BOT.DEFAULTS))
    LEDGER.save_state(BOT.RUNS_KEY, {"runs": []})
    LEDGER.save_state("paper_account", {})
    LEDGER.save_state("paper_history", {})
    LEDGER.save_state(BOT.MEMBERSHIP_KEY, {})
    LEDGER.save_state("paper_pending", {})
    LEDGER.set_kill(ARMED, "پیکربندیِ گارد", actor="guard")


install_stubs()
reset_state()

# ── ۱) قراردادِ وضعیت ──────────────────────────────────────────────────────
r = client.get("/api/bot/status")
ck(r.status_code == 200, "۰۱ status پاسخ ۲۰۰ می‌دهد", r.status_code)
d = r.json()
ck(d.get("config", {}).get("mode") == "paper", "۰۲ پیش‌فرضِ ربات کاغذی است")
ck(d.get("config", {}).get("enabled") is False, "۰۳ پیش‌فرض خاموش است (بی‌اجرایِ خودکار)")
ck(d.get("auto_run") is False, "۰۴ پاسخ صریح می‌گوید ربات خودکار اجرا نمی‌شود")
ck(d.get("kill") == ARMED, "۰۵ وضعیتِ قفل ازِ همان دفترِ سرخطی خوانده می‌شود")
ck("اجرایِ واقعی" in str(d.get("confirm_phrase", "")),
   "۰۶ عبارتِ تأییدِ اجرایِ واقعی درِ پاسخ هست (کاربر حدس نمی‌زند)")
lg = d.get("live_gates") or {}
ck(lg.get("all_open") is False and lg.get("env_live") is False,
   "۰۷ قفل‌های اجرایِ واقعی درِ حالتِ عادی بسته گزارش می‌شوند")
ck(isinstance(lg.get("capabilities"), dict) and "error" not in lg,
   "۰۸ capabilities از runtime خوانده می‌شود، نه list() شدنِ یک دیتاکلس",
   lg.get("error"))

# ── ۲) اعتبارسنجیِ پیکربندی ─────────────────────────────────────────────────
r = client.put("/api/bot/config", json={"preset": "trend", "sizing_fraction": 0.08})
ck(r.json().get("status") == "ok" and r.json()["config"]["sizing_fraction"] == 0.08,
   "۰۹ مقدارِ معتبر پذیرفته می‌شود")
r = client.put("/api/bot/config", json={"sizng_fraction": 0.08})
ck(r.json().get("status") == "error" and "ناشناخته" in json.dumps(r.json(), ensure_ascii=False),
   "۱۰ کلیدِ غلط‌املا ساکت پذیرفته نمی‌شود (typo ≠ سقفِ تعریف‌نشده)")
r = client.put("/api/bot/config", json={"sizing_fraction": 0.9})
ck(r.json().get("status") == "error", "۱۱ sizing_fraction بیرونِ مجاز رد می‌شود")
r = client.put("/api/bot/config", json={"max_order_value": 0})
ck(r.json().get("status") == "error", "۱۲ سقفِ صفر رد می‌شود (صفر گزینه نیست)")
r = client.put("/api/bot/config", json={"max_symbol_exposure": None})
ck(r.json().get("status") == "ok", "۱۳ null یعنی «تعریف نشده» — پذیرفته می‌شود")
r = client.put("/api/bot/config", json={"fund_mode": "whatever"})
ck(r.json().get("status") == "error", "۱۴ fund_modeِ ناشناخته رد می‌شود")
r = client.put("/api/bot/config", content=b"{not json")
ck(r.json().get("status") == "error", "۱۵ بدنِ خراب JSON پاسخِ ساختگی نمی‌گیرد")

# ── ۴) اجرایِ واقعی فقط با سه قفل ────────────────────────────────────────────
r = client.put("/api/bot/config", json={"mode": "live"})
ck(r.json()["config"]["mode"] == "paper",
   "۱۶ mode=live بی‌قفل‌ها به paper برمی‌گردد", r.json()["config"]["mode"])
body17 = json.dumps(r.json(), ensure_ascii=False)
note17 = str((r.json().get("config") or {}).get("note") or "")
ck("paper_only" in body17 and "BOT_LIVE" not in body17,
   "۱۷ دلیلِ برگشت باِ شاهدِ ماشین‌خوان گفته می‌شود، نه سکوت", note17[:160])
ck("broker_wired" in body17,
   "۱۷b علتِ نبودِ «واقعی» درِ پاسخِ config هم هست (paper_only)", body17[:120])
# mode=live ازِ راهِ PUT ذخیره نمی‌شود (تست ۱۶)؛ اینجا عمداً ازِ راهِ دفتر
# می‌نویسیم تا ببینیم /run هم تنها به config اکتفا نمی‌کند.
cfg = dict(BOT.DEFAULTS); cfg["mode"] = "live"; cfg["enabled"] = True
LEDGER.save_state(BOT.CONFIG_KEY, cfg)
r = client.post("/api/bot/run", json={})
ck(r.json().get("status") == "refused" and "live" in json.dumps(r.json(), ensure_ascii=False),
   "۱۸ با config=live ولی قفلِ بسته، /run رد می‌کند (نه اجرا، نه جعلِ paper)",
   r.json().get("message"))

# ── ۵) ردِّ دروازه‌ها ────────────────────────────────────────────────────────
reset_state()
r = client.post("/api/bot/run", json={})
ck(r.json().get("status") == "refused" and "خاموش" in r.json().get("message", ""),
   "۱۹ رباتِ خاموش هیچ اجرا نمی‌کند")
client.put("/api/bot/config", json={"enabled": True})
LEDGER.set_kill(HALT, "آزمونِ گارد", actor="guard")
r = client.post("/api/bot/run", json={})
ck(r.json().get("status") == "halted", "۲۰ درِ HALTED هیچ سفارشی ساخته نمی‌شود")
LEDGER.set_kill(ARMED, "ادامهٔ آزمون", actor="guard")

# ── ۶) نشستِ کاغذیِ انتها‌به‌انتها ─────────────────────────────────────────────
r = client.post("/api/bot/run", json={})
body = r.json()
ck(body.get("status") == "ok", "۲۱ اجرایِ کاغذی با وضعیتِ ok برمی‌گردد", body.get("message"))
run = body.get("run") or {}
ck(run.get("session") == SESSIONS[-1], "۲۲ نشستِ بسته‌شدۀ تابلو مرجع است، نه ساعتِ دستگاه")
ck(run.get("bars") == 1, "۲۳ یکِ فشارِ دکمه = یکِ نشست: ردیفِ همان روز، نه ۳۵ نشست", run.get("bars"))
ck(len(run.get("decisions") or []) > 0, "۲۴ دستِکم یکِ تصمیم/یادداشت ثبت شده")
r2 = client.post("/api/bot/run", json={})
ck(r2.json().get("status") == "ok", "۲۵ اجرایِ دوباره نمی‌شکند")
hist = client.get("/api/bot/history").json()
ck(len(hist.get("runs") or []) == 2, "۲۶ تاریخچهٔ اجراها ثبت می‌شود (دو اجرا)")
kinds = [e.get("kind") for e in hist.get("events") or []]
ck("bot_run" in kinds, "۲۷ ردِّپایِ دفتر برایِ هر اجرا نوشته می‌شود")
ck(len([k for k in kinds if k == "bot_run"]) == 2,
   "۲۸ اجرایِ تکراریِ همان نشستِ دستی، ردِّپایِ دومی ازِ نوعِ دیگر نمی‌سازد")
acct = hist.get("account") or {}
ck(acct.get("cash") is not None or acct.get("positions") is not None,
   "۲۹ حسابِ کاغذی پس ازِ اجرا وضعیتِ قابلِ نمایش دارد", list(acct)[:4])

# ── ۶) توقف / ادامه / قفلِ خودکار ─────────────────────────────────────────────
r = client.post("/api/bot/halt", json={"reason": "آزمون"})
ck(r.json().get("kill") == HALT, "۳۰ توقفِ دستی همان قفلِ پایدارِ سرخطی را می‌نویسد")
r = client.post("/api/bot/run", json={})
ck(r.json().get("status") == "halted", "۳۱ پس ازِ توقف، اجرا رد می‌شود")
r = client.post("/api/bot/resume", json={})
ck(r.json().get("kill") == ARMED, "۳۲ ادامه به ARMED برمی‌گردد")
LEDGER.set_kill(TRIPPED, "ضررِ روزانه", actor="risk-engine")
r = client.post("/api/bot/resume", json={})
ck(r.json().get("status") == "refused" and r.json().get("kill") == TRIPPED,
   "۳۳ قفلِ خودکارِ ریسک بی‌اقدامِ صریحِ انسان باز نمی‌شود")
LEDGER.set_kill(ARMED, "پایانِ آزمون", actor="guard")

# ── ۷) صداقتِ داده ───────────────────────────────────────────────────────────
reset_state()
client.put("/api/bot/config", json={"enabled": True})
BOT._bars = lambda cfg, day, symbols=None: []
r = client.post("/api/bot/run", json={})
ck(r.json().get("status") == "no_data" and "بی‌اقدام" in r.json().get("message", ""),
   "۳۴ بی‌ردیف: no_data و صفر اقدام — نه صفرِ جعلیِ موفق")
BOT._bars = lambda cfg, day, symbols=None: (_ for _ in ()).throw(RuntimeError("بانک نیست"))
try:
    r = client.post("/api/bot/run", json={})
    ok = r.status_code == 200 and r.json().get("status") in ("no_data", "error")
except Exception as e:
    ok = False
    r = None
ck(ok, "۳۵ خطایِ بانک درِ پاسخ می‌نشیند و اجرا نمی‌شکند", getattr(r, "json", lambda: None)())
install_stubs()

# ── ۸) نبودِ افشا ────────────────────────────────────────────────────────────
blob = json.dumps(client.get("/api/bot/status").json(), ensure_ascii=False)
ck(not any(t in blob.lower() for t in ("token", "authorization", "bearer", "password")),
   "۳۶ پاسخِ status هیچ credential یا tokenی ندارد")
ck("cookie" not in blob.lower(), "۳۷ هیچ سرِ نشستِ کارگزاری ازِ API بیرون نمی‌رود")

# ── ۹) قراردادِ یکتا با بقیۀ مسیر ────────────────────────────────────────────
ck(BOT.Limits is not None and "max_daily_loss" in BOT.Limits.__dataclass_fields__,
   "۳۸ ربات همان Limitsِ execution_service را می‌سازد، نه داورِ دوم")
ck(BOT.STATE_KEY == "paper_account", "۳۹ حسابِ کاغذی همان کلیدِ دفتر را دارد")
import api as API
import re as _re
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "api", "__init__.py"), encoding="utf-8").read()
# سنجه عینِ کد نبود، جستارِ متنیِ «bot]» بود — درِ دورِ ادغام که فهرستِ ماژول‌ها
# اتحاد خورد و `…, execution, bot, structure3]` شد، همان جستار قرمز شد *بدین‌حالی
# که bot ثبت بود*: قرمزِ جعلی. جایش یکِ داوریِ ساختاری نشست: آیا واقعاً مسیری
# زیرِ `/api/bot/` درِ روترِ تجمیعی هست یا نه — همان چیزی که EXE لازم دارد.
def _all_paths(node, acc):
    """همۀ مسیرهایِ یک روتر. درِ این نسخۀ FastAPI `include_router` تنبل است:
    `.routes` شیءِ `_IncludedRouter` می‌دهد بی‌`path`؛ روترِ واقعی زیرِ
    `original_router` نشسته است. بی‌این، هر شمارشِ مسیر صفر می‌شود و سنجه
    «هیچ /api/bot/* نیست» قرمزِ جعلی می‌داد (همین‌جا اتفاق افتاد)."""
    inner = getattr(node, "original_router", None)
    if inner is not None:
        node = inner
    for r in getattr(node, "routes", []) or []:
        p = getattr(r, "path", None)
        if p:
            acc.append(p)
        _all_paths(r, acc)
    return acc


_paths = _all_paths(API.api_router(), [])
ck(any(p.startswith("/api/bot/") for p in _paths),
   "۴۰ api_router ماژولِ bot را ثبت می‌کند (وگرنه هر /api/bot/* درِ EXE 404 است)",
   "%d مسیر، هیچ /api/bot/* نیست" % len(_paths))
# و همان داوریِ متنی، این‌بار به‌شکلی که اتحادِ فهرست را ببیند (نه فقط انتهای فهرست)
ck(_re.search(r"mods\s*=\s*\[[^\]]*?\bbot\b", src) is not None,
   "۴۰‑ب bot درِ فهرستِ `mods` نوشته شده (منبع، نه فقط روترِ ساخته‌شده)")
for spec in ("fts_terminal.spec", "bors_setup.spec"):
    s = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), spec),
             encoding="utf-8").read()
    ck("'api.bot'" in s and "'paper_trading'" in s and "'bot_signals'" in s,
       "۴۱/۴۲ %s درِ hiddenimports ربات را دارد" % spec)

# ── ۴۳) کنترلِ منفی: اگر درزِ داور را برنداریم، گارد کور نیست ────────────────
real_judge = BOT.FunnelMembership(lambda s: {})
ck(real_judge._membership("x") == {}, "۴۳ داورِ بی‌خروجی ⇒ نگاشتِ خالی، نه «همه خارج»")
fm = BOT.FunnelMembership(lambda s: {"A": "maybe"})
ck(fm._membership("s")["A"] == "unknown",
   "۴۴ «نمی‌دانیم» با «خارج» یکی نمی‌شود (بی‌دلیل فروشی ساخته نمی‌شود)")

# A-تازۀ واقعی: هیچ نوشتنی درِ مسیرِ اجرا/ربات نباید retryِ کور داشته باشد.
# `http()` پیش‌فرض retries=2 و رویِ خطایِ شبکه هم تلاشِ دوباره می‌کند؛ برایِ
# POSTِ ارسالِ سفارش آن یعنی «شاید نرسیده باشد، دوباره بفرست» = سفارشِ تکراری.
import re as _re
for rel in ("frontend/src/features/portfolio/lib/orderClient.ts",
            "frontend/src/features/portfolio/lib/botClient.ts"):
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel),
               encoding="utf-8").read().split("\n")
    writing, naked = 0, []
    for i, line in enumerate(src):
        m = _re.search(r"method:\s*'(POST|PUT|DELETE)'", line)
        if not m:
            continue
        writing += 1
        window = " ".join(src[max(0, i - 3):i + 4])   # آبجکتِ گزینه یکِ فراخوانی باز است
        if "retries" not in window and "NO_RETRY" not in window:
            naked.append(line.strip()[:60])
    ck(writing > 0 and not naked,
       "۴۶ %s: هر %d نوشتن retries:0 دارد" % (rel.split("/")[-1], writing), naked)

# ── ۱۰) یکِ نشست درِ هر فشار: داوریِ یک‌بار، «دیروز» ازِ ردِّپا، T+1 واقعی ─────
# این بخش همان عیبی را می‌بندد که دورِ پیش ازِ سنجش بیرون آمد: `_bars` ۳۵ نشست
# × ۶٬۰۱۸ نماد را *نماد-محور* می‌داد (۱۲۹٬۶۱۳ ردیف ⇒ ۱٬۴۵۷ ثانیه) و داور ۱۵۶ بار
# در ۴۰۰ ردیفِ اول صدا زده شد. قیف بی‌`as_of` است، پس داوریِ دوبارهٔ گذشته
# نشتِ آینده می‌سازد؛ «دیروز» باید ازِ ردِّپا بیاید.
from execution_contract import InstrumentRef, OrderDraft, OrderMode, Side
import paper_trading as PT

reset_state()
JUDGE_CALLS.clear(); BARS_CALLS.clear()
client.put("/api/bot/config", json={"enabled": True})
install_stubs(session_day=SESSIONS[2])
r = client.post("/api/bot/run", json={}).json()
ck(r.get("status") == "ok", "۴۷ نشستِ کاغذی با ok برمی‌گردد", r.get("message"))
ck(JUDGE_CALLS == [SESSIONS[2]], "۴۸ داور دقیقاً یک‌بار صدا زده می‌شود", JUDGE_CALLS)
ck(BARS_CALLS and BARS_CALLS[-1][0] == int(SESSIONS[2]) and BARS_CALLS[-1][1] == {"A"},
   "۴۹ ردیف فقط برایِ نمادهایِ اقدام‌پذیرِ همان نشست خواسته می‌شود", BARS_CALLS[-1:])
memb = LEDGER.load_state(BOT.MEMBERSHIP_KEY) or {}
ck(memb.get("session") == SESSIONS[2] and (memb.get("map") or {}).get("A") == "in",
   "۵۰ رأیِ همین نشست درِ ردِّپا می‌ماند (دیروزِ نشستِ بعد)", list(memb)[:4])
drafts = (LEDGER.load_state(PT.PENDING_KEY) or {}).get("drafts") or []
ck(len(drafts) == 1 and drafts[0]["symbol"] == "A",
   "۵۱ سیگنالِ این نشست پر نمی‌شود و پاک هم نمی‌شود: یکِ draft رویِ دیسک", drafts)
s_fresh = BOT._session(dict(BOT.DEFAULTS, enabled=True), LEDGER, int(SESSIONS[2]))[0]
ck(list(getattr(s_fresh, "_pending", {})) == [drafts[0]["execution_id"]],
   "۵۲ پسِ restart همان draft برمی‌گردد (پیگیریِ سفارش نمی‌سوزد)",
   list(getattr(s_fresh, "_pending", {})))

JUDGE_CALLS.clear()
r2 = client.post("/api/bot/run", json={}).json()
ck(r2.get("status") == "ok", "۵۳ فشارِ دوباره رویِ همان نشست نمی‌شکند", r2.get("message"))
ck(JUDGE_CALLS == [SESSIONS[2]], "۵۴ دو فشارِ همان نشست = دو داوریِ پیشین نه، یکِ داوری",
   JUDGE_CALLS)
ck(len((LEDGER.load_state(PT.PENDING_KEY) or {}).get("drafts") or []) == 1,
   "۵۵ فشارِ دوباره سفارشِ تکراری نمی‌سازد")

install_stubs(session_day=SESSIONS[3])
r3 = client.post("/api/bot/run", json={}).json()
run3 = r3.get("run") or {}
disp = sum(int(d.get("dispatched") or 0) for d in run3.get("decisions") or [])
ck(disp == 1, "۵۶ سیگنالِ دیروز درِ نشستِ امروز پر می‌شود (T+1، یکِ اقدام)", disp)
ck(not (LEDGER.load_state(PT.PENDING_KEY) or {}).get("drafts"),
   "۵۷ پسِ پرشدن، draft ازِ دفترِ انتظار بیرون می‌رود")
ck(run3.get("prev_session") == SESSIONS[2] and not any(
    d.get("signals") for d in run3.get("decisions") or []),
   "۵۸ نمادی که دیروز هم درِ قیف بود دوباره خریده نمی‌شود", run3.get("decisions"))
acct3 = LEDGER.load_state(PT.STATE_KEY) or {}
ck("B" not in (acct3.get("positions") or {}),
   "۵۹ نمادی که هیچ‌وقت درِ قیف نبوده خریده نمی‌شود", list(acct3.get("positions") or {}))

# انقضایِ سفارشِ درِ انتظار: نمادی که ردیفِ تازه‌تر هرگز نمی‌رسد، تا بی‌نهایت
# باز نمی‌ماند — باید درِ ردِّپا بسته شود (بندِ ۶: پیگیریِ سفارش نه گم شود نه جا بماند).
reset_state()
client.put("/api/bot/config", json={"enabled": True})
install_stubs(session_day=SESSIONS[2])
Z = OrderDraft(execution_id="paper:Z:20261005:buy", instrument=InstrumentRef(symbol="Z"),
               side=Side.BUY, price=10.0, quantity=5.0, mode=OrderMode.SAFE,
               price_source="guard", price_as_of=SESSIONS[2])
LEDGER.save_state(PT.PENDING_KEY, {"drafts": [PT._draft_dump(Z)]})
install_stubs(session_day=SESSIONS[3])
r4 = client.post("/api/bot/run", json={}).json()
ev = [e for e in (LEDGER.events(kinds=("risk_reject",)) or []) if e.get("symbol") == "Z"]
ck(r4.get("status") == "ok" and (r4.get("run") or {}).get("expired") == ["Z"],
   "۶۰ draftِ بی‌ردیفِ تازه منقضی می‌شود", (r4.get("run") or {}).get("expired"))
ck(any(e.get("status") == "expired" for e in ev),
   "۶۱ انقضا درِ ردِّپا ثبت می‌شود، نه بی‌صدا پاک شدن", [e.get("status") for e in ev])
left = [d.get("symbol") for d in ((LEDGER.load_state(PT.PENDING_KEY) or {}).get("drafts") or [])]
ck("Z" not in left, "۶۲ پسِ انقضا Z ازِ دفترِ انتظار بیرون می‌رود (draftِ همین نشست می‌ماند)", left)

# ── ۱۱) قراردادِ واقعیِ داور: همان چیزی که خودِ قیف می‌فرستد ─────────────────
# نخستین نسخۀ `_judge` دو کلیدِ اشتباه را می‌خواند (`payload["survivors"]` و سپس
# `handover`); قیف حکمِ نهاییِ نمادبه‌نماد را درِ `status_matrix[sym]["handover"]
# ["status"]` می‌فرستد. گاردِ پیشین `_judge` را کلاً stub می‌کرد، پس این شاخه‌ها
# هرگز اجرا نشدند و رویِ دادۀ واقعی ربات بی‌صدا «بی‌داده» می‌گفت.
import api.funnel as FUN

_real_run = FUN._run
try:
    PAYLOAD = {"status": "success",
               "handover": [{"symbol": "A", "final": "pass"}],
               "stages": {"handover": {"survivors": ["A"]}},
               "status_matrix": {
                   "A": {"handover": {"status": "pass"}},
                   "B": {"handover": {"status": "reject"}},
                   "C": {"handover": {"status": "pending"}},
                   "D": {"handover": {"status": "not_in_universe"}},
                   "E": {"handover": {"status": "unavailable"}}}}
    FUN._run = lambda *a, **k: PAYLOAD
    got = REAL_JUDGE(dict(BOT.DEFAULTS))(SESSIONS[-1])
    ck(got == {"A": "in", "B": "out", "C": "unknown", "D": "out", "E": "unknown"},
       "۶۳ داور حکمِ نهاییِ خودِ قیف را نمادبه‌نماد می‌خواند", got)
    ck(got.get("C") == "unknown" and got.get("E") == "unknown",
       "۶۴ «سنجیده نشده» با «خارج است» یکی نیست (بی‌دلیل فروشی نمی‌سازد)", got)

    # کنترلِ منفی: پاسخِ بی‌status_matrix هیچ رأیی نیست، نه «همه خارج»
    FUN._run = lambda *a, **k: {"status": "success", "handover": [{"symbol": "A"}],
                                "survivors": [{"symbol": "A"}]}
    ck(REAL_JUDGE(dict(BOT.DEFAULTS))("s") == {},
       "۶۵ بی‌status_matrix ⇒ نگاشتِ خالی (کلیدِ ساختگی رأی نیست)")
    FUN._run = lambda *a, **k: {"status": "error", "message": "x"}
    ck(REAL_JUDGE(dict(BOT.DEFAULTS))("s") == {}, "۶۶ قیفِ خطادار هیچ رأیی نمی‌دهد")
finally:
    FUN._run = _real_run
for mod in ("api/funnel.py", "funnel_engine.py"):
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            *mod.split("/")), encoding="utf-8").read()
    ck("status_matrix" in src, "۶۷ %s کلیدِ status_matrix را می‌فرستد (قراردادِ ۶۳)" % mod)

print("\nbot_api_v1114: %d passed / %d failed" % (PASS, FAIL))
try:
    LEDGER.close()
except Exception:
    pass
sys.exit(1 if FAIL else 0)
