#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_round22_v1172 — Round 22: اتوکلیکرِ واقعی، با شمارش و توقفِ قابلِ اثبات.

هیچ شبکه‌ای به کارگزاری، هیچ مرورگرِ واقعی (نگاشتِ DOM در
`autoclicker_round22_browser_v1173.py` سنجیده می‌شود). اینجا رفتارِ لایه‌ها
سنجیده می‌شود: داوریِ UI، شمارشِ پایدار، نرخ، زمان‌بندی/ timezone، توقفِ اضطراری
و منشأِ قوانین.

پنج ادعا که اگر بشکنند این گارد باید قرمز شود:
  ۱) بدونِ کلیکِ بی‌دلیل: هیچ مسیری فرمِ واقعی را پر/تغییر نمی‌دهد.
  ۲) هیچ‌وقت بیشتر از تعدادِ تنظیم‌شده کلیک نمی‌شود، حتی با تیک‌هایِ مکرر.
  ۳) نتیجهٔ مبهم/قطعِ نشست/دکمهٔ مبهم → توقف، نه تلاشِ دوباره.
  ۴) restart هیچ اقدامی را خودکار اجرا نمی‌کند.
  ۵) هیچ عددِ «تأییدشده» از خودِ برنامه نمی‌آید: هر قاعده منبع/تاریخ دارد.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:320])


import execution_autoclick_run as RUN                        # noqa: E402
import execution_autoclick_scheduler as SCH                   # noqa: E402
import execution_autoclick_executor as EX                     # noqa: E402
import execution_browser as EB                                # noqa: E402
import execution_rate_limiter as RL                           # noqa: E402
import execution_trading_rules as TR                          # noqa: E402
import execution_ui_state as UIS                              # noqa: E402


# ── ساختِ حالتِ صفحه، همان شکلی که JS برمی‌گرداند ─────────────────────────────
def cand(index=0, *, text="ارسال خرید", aria="ارسال خرید", visible=True, enabled=True,
         in_viewport=True, form_bound=True, side="buy"):
    want = list(UIS.SIDE_TOKENS.get(side, ()))
    against = list(UIS.SIDE_TOKENS.get(UIS.OPPOSITE.get(side, ""), ()))
    hay = (aria + " " + text).lower()
    return {"index": index, "tag": "button", "text": text, "aria": aria, "id": "",
            "testid": "", "cy": "", "classes": "order-btn", "type": "submit",
            "visible": visible, "enabled": enabled, "in_viewport": in_viewport,
            "form_bound": form_bound,
            "side_match": any(t.lower() in hay for t in want),
            "opposite_side": any(t.lower() in hay for t in against),
            "path": "body/form/div[%d]/button" % index,
            "rect": {"x": 10, "y": 200 + index * 40, "w": 90, "h": 32}}


def page_state(*, symbol="داروند", price="11010", quantity="100", side_text="خرید",
               isin="IRO1DRVN0001", cands=None, price_present=True, qty_present=True,
               price_visible=True, symbol_visible=True, counts=None):
    cands = cands if cands is not None else [cand()]
    base_counts = {"submit_matches": len(cands), "buttons_total": len(cands) + 3,
                   "inputs_total": 4, "forms_total": 1,
                   "price_matches": 1 if price_present else 0,
                   "quantity_matches": 1 if qty_present else 0,
                   "symbol_matches": 1}
    if counts:
        base_counts.update(counts)
    return {
        "url_path": "/order", "title": "EasyTrader", "ready_state": "complete",
        "viewport": {"w": 1366, "h": 900}, "counts": base_counts,
        "fields": {
            "price": {"present": price_present, "count": base_counts["price_matches"],
                      "value": price, "text": "", "visible": price_visible,
                      "readonly": False, "disabled": False, "path": "body/input#price"},
            "quantity": {"present": qty_present, "count": base_counts["quantity_matches"],
                         "value": quantity, "text": "", "visible": True,
                         "readonly": False, "disabled": False,
                         "path": "body/input#quantity"},
            "symbol": {"present": True, "count": 1, "value": "", "text": symbol,
                       "visible": symbol_visible, "readonly": None, "disabled": False,
                       "path": "body/header#sym"},
            "isin": {"present": True, "count": 1, "value": isin, "text": "",
                     "visible": True, "readonly": None, "disabled": False,
                     "path": "body#isin"},
            "side": {"present": True, "count": 1, "value": "", "text": side_text,
                     "visible": True, "readonly": None, "disabled": False,
                     "path": "body#side"},
        },
        "tabs": {"normal": {"present": True, "visible": True, "active": True},
                 "algo": {"present": True, "visible": True, "active": False},
                 "day": {"present": True, "visible": True, "active": True},
                 "draft": {"present": True, "visible": True, "active": False}},
        "submit_candidates": cands,
        "dom_signature": {"submit_paths": [c["path"] for c in cands],
                          "submit_labels": [c["aria"] for c in cands],
                          "price_path": "body/input#price",
                          "quantity_path": "body/input#quantity",
                          "buttons_total": base_counts["buttons_total"]},
    }


UI = UIS.UIOptions(submit_selector="button[aria-label='ارسال خرید']",
                   price_selector="#price", quantity_selector="#quantity",
                   symbol_selector="[data-cy='order-form-header-symbol-name']",
                   isin_selector="#isin", side_selector="#side",
                   side="buy", expected_price=11010.0, expected_quantity=100.0,
                   expected_symbol="داروند", expected_isin="IRO1DRVN0001")


def fresh_run(*, claim=True, at_ms=None, **kw):
    st = store_tmp()
    rec = mkrun(st, **kw)
    if claim:
        at = int(at_ms if at_ms is not None else rec.config.planned_first_at_ms() + 10)
        act = st.claim_next(rec.run_id, at_ms=at, token="test") or rec.actions[0]
    else:
        act = rec.actions[0]
    return st, st.get(rec.run_id), act


def driver_for(state, *, alive=True, url="https://d.easytrader.ir/order", **kw):
    d = EB.MockBrowserDriver(**kw)
    d.order_url = "http://mock.local/core/api/v2/order"
    d.ui_fixture = state
    d.url_value = url
    d.start()
    d._mock_alive = alive
    d.is_alive = lambda: bool(d._mock_alive)          # type: ignore[assignment]
    d.url = lambda: str(d.url_value)                  # type: ignore[assignment]
    return d


def ctx_for(driver, *, dry_run=True, wall=None, **kw):
    extra = {"wall_ms": wall} if wall is not None else {}
    return lambda: EX.ExecutorContext(driver=driver, ui=UI, dry_run=dry_run,
                                      **extra, **kw)


def store_tmp() -> RUN.AutoClickRunStore:
    return RUN.AutoClickRunStore(os.path.join(tempfile.mkdtemp(), "ac22.db"))


def mkrun(st, *, n=2, iv=800, target="2026-10-24T09:05:00", dry=True, **kw) -> RUN.RunRecord:
    cfg = RUN.RunConfig(symbol=kw.pop("symbol", "داروند"), isin="IRO1DRVN0001",
                        side=kw.pop("side", "buy"), expected_price=kw.pop("price", 11010.0),
                        expected_quantity=kw.pop("qty", 100.0), target_at=target,
                        mode="repeat" if n > 1 else "single", total_actions=n,
                        interval_ms=iv, dry_run=dry, prewarm_ms=kw.pop("prewarm_ms", 0),
                        **kw)
    rec = st.create(cfg)
    st.arm(rec.run_id, validation={"ok_for_arm": True}, ok_for_arm=True)
    st.start(rec.run_id)
    return st.get(rec.run_id)


class FakeClock:
    def __init__(self, ms: int) -> None:
        self.ms = int(ms)

    def wall(self) -> int:
        return self.ms

    def advance(self, delta: int) -> None:
        self.ms += int(delta)

    def mono(self) -> float:
        return self.ms / 1000.0


# ── ۱) داوریِ UI: فقط دکمهٔ نمایان/فعال/داخلِ viewport/همان فرم، یک‌تا ────────
def part_ui_judge() -> None:
    good = UIS.judge(page_state(), UI)
    ck(good.ok and good.verdict == "UNIQUE", "داوری: دکمهٔ یکتایِ نمایان PASS می‌شود",
       good.reasons)
    two = UIS.judge(page_state(cands=[cand(0), cand(1)]), UI)
    ck(not two.ok and two.verdict == "AMBIGUOUS", "داوری: دو دکمهٔ نمایان = مبهم، اقدام نه",
       two.verdict)
    hidden = UIS.judge(page_state(cands=[cand(0, visible=False), cand(1)]), UI)
    ck(hidden.ok and hidden.button and int(hidden.button["index"]) == 1,
       "داوری: نسخهٔ hidden هم‌نام نادیده گرفته می‌شود")
    offscreen = UIS.judge(page_state(cands=[cand(0, in_viewport=False), cand(1)]), UI)
    ck(offscreen.ok and int(offscreen.button["index"] or 0) == 1,
       "داوری: خارج از viewport کلیک نمی‌شود")
    disabled = UIS.judge(page_state(cands=[cand(0, enabled=False)]), UI)
    ck(not disabled.ok and disabled.verdict == "NO_USABLE_BUTTON",
       "داوری: دکمهٔ غیرفعال مردود است", disabled.verdict)
    other_form = UIS.judge(page_state(cands=[cand(0, form_bound=False), cand(1)]), UI)
    ck(other_form.ok and int(other_form.button["index"] or 0) == 1,
       "داوری: دکمهٔ بی‌ربط به همان فرم رد می‌شود")
    sell_only = UIS.judge(page_state(cands=[cand(0, text="ارسال فروش", aria="ارسال فروش")],
                                     side_text="فروش"), UI)
    ck(not sell_only.ok and sell_only.verdict == "WRONG_SIDE_ONLY",
       "داوری: خرید با دکمهٔ فروش انجام نمی‌شود", sell_only.verdict)
    wrong_symbol = UIS.judge(page_state(symbol="اطلس"), UI)
    ck(not wrong_symbol.ok and wrong_symbol.checks.get("symbol_verified") == "FAIL",
       "داوری: هدرِ نمادِ دیگر مردود است، حتی اگر ISIN هم‌خوان بماند")
    only_isin = UIS.judge(page_state(symbol=""), UIS.UIOptions(
        **{**__import__("dataclasses").asdict(UI), "symbol_selector": ""}))
    ck(only_isin.ok, "داوری: تنظیمِ فقط-ISIN هم هویت را تأیید می‌کند", only_isin.reasons)
    stale_isin = UIS.judge(page_state(symbol="", isin=""), UIS.UIOptions(
        **{**__import__("dataclasses").asdict(UI), "symbol_selector": ""}))
    ck(not stale_isin.ok and stale_isin.checks.get("symbol_verified") == "FAIL",
       "داوری: ISINِ خالی تأییدِ هویت نیست")
    wrong_price = UIS.judge(page_state(price="10990"), UI)
    ck(not wrong_price.ok and wrong_price.checks.get("price_matches_expected") == "FAIL",
       "داوری: قیمتِ فرم با موردِ انتظار نمی‌خواند")
    wrong_qty = UIS.judge(page_state(quantity="99"), UI)
    ck(not wrong_qty.ok and wrong_qty.checks.get("quantity_matches_expected") == "FAIL",
       "داوری: تعدادِ فرم با موردِ انتظار نمی‌خواند")
    noisiny = UIS.judge(page_state(counts={"price_matches": 2}), UI)
    ck(not noisiny.ok, "داوری: دو تطبیقِ فیلد قیمت = فرمِ نامعتبر")
    # عددِ فارسی/هزارگان در فرم واقعی
    fa = UIS.judge(page_state(price="۱۱٬۰۱۰", quantity="۱۰۰"), UI)
    ck(fa.ok, "داوری: رقمِ فارسی و جداکنندهٔ هزارگان در فرم خوانده می‌شود", fa.reasons)


# ── ۲) executor: کلیکِ واقعی با گاردِ dry-run و بی‌نوشتنِ فرم ─────────────────
def part_executor() -> None:
    st, rec, act = fresh_run(n=1)
    d = driver_for(page_state())
    ex = EX.AutoClickExecutor(ctx_for(d))
    out = ex(rec, act, SCH.FireHooks(rec.run_id, 0, st, threading.Event()))
    ck(out["state"] == "DRY_RUN", "dry-run: کلیک شد و درخواستِ سفارش درِ مرورگر abort شد",
       (out["state"], out["reason"]))
    ck(d.order_endpoint_hits == 0 and d.blocked_writes,
       "dry-run: هیچ POSTی به کارگزاری نرسید", (d.order_endpoint_hits, len(d.blocked_writes)))
    ck(d.click_count == 1, "dry-run: دقیقاً یک کلیک", d.click_count)
    fills = [e for e in d.events if e.get("kind") == "fill"]
    ck(not fills, "هیچ فیلدی در فرمِ واقعی پر/تغییر داده نشد", fills)
    ck(out["metrics"]["click_to_request_ms"] is not None,
       "تلمتری: فاصلۀ کلیک→درخواست جدا ثبت شد", out["metrics"])
    ck(out["evidence"]["form"]["price"] == 11010.0,
       "شاهد: قیمتِ خوانده‌شده از فرم درِ لاگ است", out["evidence"]["form"])
    ck(out["telemetry"]["latencies"]["target_error_ms"] is not None,
       "تلمتری: خطایِ زمانِ هدف (wall) ثبت شد", out["telemetry"]["latencies"])

    def once(driver, **ctxkw):
        s2, r2, a2 = fresh_run(n=2)
        return EX.AutoClickExecutor(ctx_for(driver, **ctxkw))(
            r2, a2, SCH.FireHooks(r2.run_id, 0, s2, threading.Event()))

    d2 = driver_for(page_state(cands=[cand(0), cand(1)]))
    out2 = once(d2)
    ck(out2["state"] == "AMBIGUOUS" and d2.click_count == 0,
       "داوریِ مبهم → صفر کلیک", (out2["state"], d2.click_count))
    ck(out2["fired"] is False, "اقدامِ مردود «شلیک‌شده» شمارش نمی‌شود")

    d3 = driver_for(page_state(), url="https://login.emofid.com/Login")
    s3, r3, a3 = fresh_run(n=2)
    out3 = EX.AutoClickExecutor(ctx_for(d3, session_ok=lambda: (False, "LOGIN_REQUIRED")))(
        r3, a3, SCH.FireHooks(r3.run_id, 0, s3, threading.Event()))
    ck(out3["state"] == "SESSION_LOST" and d3.click_count == 0,
       "ورودِ تأییدنشده → توقف پیش از کلیک", out3["state"])
    out3b = once(d3)
    ck(out3b["state"] == "SESSION_LOST", "میزبانِ ناخواسته (login.emofid.com) مردود است",
       out3b["state"])

    d4 = driver_for(page_state(), alive=False)
    out4 = once(d4)
    ck(out4["state"] == "BROWSER_LOST" and d4.click_count == 0,
       "مرورگر قطع‌شده → BROWSER_LOST بی‌کلیک", out4["state"])

    d5 = driver_for(page_state())
    ex5 = EX.AutoClickExecutor(ctx_for(d5))
    warm = ex5.run_warm()
    ck(warm["ok"], "warm: ارزیابیِ پیش از هدف موفق ثبت شد", warm)
    d5.ui_fixture = page_state(cands=[cand(0, text="ارسال فروش", aria="ارسال فروش")])
    s5, r5, a5 = fresh_run(n=2)
    out5 = ex5(r5, a5, SCH.FireHooks(r5.run_id, 0, s5, threading.Event()))
    ck(out5["state"] in ("MISMATCH", "WRONG_SIDE_ONLY", "AMBIGUOUS") and d5.click_count == 0,
       "DOM تغییر کرده → کلیک نمی‌شود", (out5["state"], d5.click_count))

    d6 = driver_for(page_state())
    d6.request_method = "GET"          # هیچ نوشتنی ساخته نمی‌شود
    out6 = once(d6)
    ck(out6["state"] == "NOT_SENT" and out6["stop_run"] is True,
       "کلیک بی‌درخواستِ سفارش → NOT_SENT، نه تلاشِ دوباره", out6["state"])

    d7 = driver_for(page_state())
    out7 = once(d7)
    d7b = driver_for(page_state())

    def escape_during_click():
        # گارد باز است ولی نوشتن رها شده (تقلیدِ شکستِ route.abort در Chromium)
        d7b.escaped_writes.append({"classification": "order"})
        d7b.blocked_writes.clear()
        d7b.writes_escaped = True

    d7b.before_click = escape_during_click
    out7b = once(d7b)
    ck(out7["state"] == "DRY_RUN", "حالتِ عادیِ dry-run سبز است", out7["state"])
    ck(out7b["state"] == "UNKNOWN" and out7b["stop_run"],
       "عبورِ نوشتن از گارد → UNKNOWN با ادعایِ نامعلوم", out7b["state"])

    def accept(payload):
        return {"status": 200, "body": {"isSuccessful": True, "id": "BR-77"}}

    d8 = driver_for(page_state(), on_submit=accept)
    out8 = once(d8, dry_run=False)
    ck(out8["state"] == "ACCEPTED" and out8["evidence"].get("broker_order_id") == "BR-77",
       "live: پذیرش فقط از بدنهٔ ساختارمند", (out8["state"], out8.get("reason")))

    def wafy(payload):
        return {"status": 200, "body": "<html><title>WAF</title></html>"}

    d9 = driver_for(page_state(), on_submit=wafy)
    out9 = once(d9, dry_run=False)
    ck(out9["state"] == "UNKNOWN" and out9["stop_run"] is True,
       "live: HTML/WAF با ۲۰۰ → UNKNOWN و توقف", out9["state"])

    def rejected(payload):
        return {"status": 200, "body": {"isSuccessful": False,
                                        "omsError": [{"code": "2080"}],
                                        "message": "عدم رعایت محدودیت تعداد ارسال "
                                                   "سفارش همزمان در ثانیه"}}

    d10 = driver_for(page_state(), on_submit=rejected)
    out10 = once(d10, dry_run=False)
    ck(out10["state"] == "REJECTED" and out10["stop_run"] is True,
       "live: کدِ OMSِ محدودیتِ نرخ → رد + توقفِ اجرا",
       (out10["state"], out10["stop_run"]))

    def rate429(payload):
        return {"status": 429, "body": {"message": "خطا، محدودیت 1000 سفارش در ساعت"}}

    d11 = driver_for(page_state(), on_submit=rate429)
    out11 = once(d11, dry_run=False)
    ck(out11["state"] == "REJECTED" and out11["stop_run"] is True and
       out11["evidence"].get("http_status") == 429,
       "live: ۴۲۹ → رد + توقف (نه ارسالِ دوباره)",
       (out11["state"], out11["evidence"].get("http_status")))


# ── ۳) شمارش/سقف/ادامه درِ زمان‌بند ──────────────────────────────────────────
def part_scheduler_counts() -> None:
    st = store_tmp()
    rec = mkrun(st, n=3, iv=800)
    clk = FakeClock(rec.config.planned_first_at_ms())
    d = driver_for(page_state())
    ex = EX.AutoClickExecutor(ctx_for(d))
    rn = SCH.AutoClickRunRunner(st, executor=ex, wall_ms=clk.wall, clock=clk.mono,
                                spin_ms=0.0)
    for _ in range(12):
        clk.advance(500)
        rn.tick()
    got = st.get(rec.run_id)
    ck(d.click_count == 3 and got.fired_actions == 3,
       "سه اقدامِ تنظیم‌شده = سه کلیک، نه بیشتر", (d.click_count, got.fired_actions))
    ck(got.state == RUN.COMPLETED, "پس از سقفِ تعداد، اجرا COMPLETED می‌شود", got.state)
    for _ in range(8):
        clk.advance(500)
        rn.tick()
    ck(st.get(rec.run_id).fired_actions == 3 and d.click_count == 3,
       "تیک‌هایِ اضافی پس از سقف، کلیکِ تازه نمی‌سازد",
       (st.get(rec.run_id).fired_actions, d.click_count))

    # دو زمان‌بند هم‌زمان رویِ یک اجرا → هر اقدام فقط یک بار شلیک می‌شود
    st2 = store_tmp()
    rec2 = mkrun(st2, n=2, iv=20000)
    clk2 = FakeClock(rec2.config.planned_first_at_ms())
    d2 = driver_for(page_state())
    ex2 = EX.AutoClickExecutor(ctx_for(d2))
    r_a = SCH.AutoClickRunRunner(st2, executor=ex2, wall_ms=clk2.wall, clock=clk2.mono,
                                spin_ms=0.0)
    r_b = SCH.AutoClickRunRunner(st2, executor=ex2, wall_ms=clk2.wall, clock=clk2.mono,
                                spin_ms=0.0)
    clk2.advance(900)
    a = r_a.tick()
    b = r_b.tick()
    ck(d2.click_count == 1, "دو حلقه رویِ یک ردیف = یک کلیک (claimِ یک‌برنده)",
       (d2.click_count, a.public(), b.public()))
    ck(b.action_idx is None or b.outcome.get("state") != "DRY_RUN",
       "برندهٔ دوم اقدامِ تکراری نساخت")

    # نتیجهٔ UNKNOWN ادامه نمی‌دهد
    st3 = store_tmp()
    rec3 = mkrun(st3, n=4, iv=800)
    clk3 = FakeClock(rec3.config.planned_first_at_ms())
    calls = []

    def unknown_exec(run, action, hooks):
        calls.append(action.idx)
        hooks.mark_fired(clk3.wall())
        return {"state": "UNKNOWN", "fired": True, "reason": "پاسخ مبهم", "stop_run": True}

    SCH.AutoClickRunRunner(st3, executor=unknown_exec, wall_ms=clk3.wall, clock=clk3.mono,
                           spin_ms=0.0)
    r3 = SCH.AutoClickRunRunner(st3, executor=unknown_exec, wall_ms=clk3.wall,
                                clock=clk3.mono, spin_ms=0.0)
    for _ in range(6):
        clk3.advance(900)
        r3.tick()
    got3 = st3.get(rec3.run_id)
    ck(calls == [0] and got3.state == RUN.NEEDS_REVIEW,
       "UNKNOWN → صفرِ تلاشِ دوباره و وضعیتِ NEEDS_REVIEW", (calls, got3.state))
    ck([a.state for a in got3.actions].count(RUN.A_CANCELLED) == 3,
       "ردیف‌هایِ مانده لغو شدند", [a.state for a in got3.actions])

    # REJECTEDِ قطعی (بی‌شاهدِ نرخ) اجازهٔ ادامه می‌دهد — بند ۶
    ck(SCH.allows_continuation("REJECTED", {"stop_run": False}) is True,
       "ردِ قطعیِ غیرنرخ با تأییدِ چندباره = ادامه مجاز")
    ck(SCH.allows_continuation("REJECTED", {"stop_run": True}) is False,
       "شاهدِ نرخ حتی با ردِ قطعی ادامه نمی‌دهد")

    # توقفِ اضطراری در میانهٔ برنامه
    st4 = store_tmp()
    rec4 = mkrun(st4, n=5, iv=1000)
    clk4 = FakeClock(rec4.config.planned_first_at_ms())
    d4 = driver_for(page_state())
    r4b = SCH.AutoClickRunRunner(st4, executor=EX.AutoClickExecutor(ctx_for(d4)),
                                 wall_ms=clk4.wall, clock=clk4.mono, spin_ms=0.0)
    clk4.advance(1100)
    r4b.tick()
    stopped = r4b.stop(reason="مالک زد")
    for _ in range(5):
        clk4.advance(1100)
        r4b.tick()
    got4 = st4.get(rec4.run_id)
    ck(d4.click_count == 1 and got4.state == RUN.STOPPED,
       "توقفِ اضطراری: کلیک‌ها در یک می‌ماند و اجرا STOPPED می‌شود",
       (d4.click_count, got4.state, stopped))
    ck([a.state for a in got4.actions].count(RUN.A_CANCELLED) == 4,
       "چهار اقدامِ مانده لغو شدند", [a.state for a in got4.actions])
    # شروعِ دوبارهٔ کنترل‌شده بی‌اجرایِ خودکار
    st4.reset_for_restart(rec4.run_id)
    ck(st4.get(rec4.run_id).state == RUN.VALIDATED and d4.click_count == 1,
       "reset فقط VALIDATED می‌کند و خودش کلیک نمی‌سازد",
       (st4.get(rec4.run_id).state, d4.click_count))

    # از دست رفتنِ هدف: catch-up نمی‌شود
    st5 = store_tmp()
    rec5 = mkrun(st5, n=2, iv=800)
    clk5 = FakeClock(rec5.config.planned_last_at_ms() + 60_000)
    d5 = driver_for(page_state())
    r5 = SCH.AutoClickRunRunner(st5, executor=EX.AutoClickExecutor(ctx_for(d5)),
                                wall_ms=clk5.wall, clock=clk5.mono, spin_ms=0.0)
    rep5 = r5.tick()
    ck(rep5.transition == RUN.MISSED_TARGET and d5.click_count == 0,
       "گذشتنِ هدف → MISSED_TARGET بی‌کلیکِ جبرانی", (rep5.transition, d5.click_count))

    # kill switch از بیرون
    st6 = store_tmp()
    rec6 = mkrun(st6, n=3, iv=800)
    clk6 = FakeClock(rec6.config.planned_first_at_ms())
    d6 = driver_for(page_state())
    flag = {"halted": False}
    r6 = SCH.AutoClickRunRunner(st6, executor=EX.AutoClickExecutor(ctx_for(d6)),
                                wall_ms=clk6.wall, clock=clk6.mono, spin_ms=0.0,
                                halt_check=lambda: (flag["halted"], "کلیدِ توقف"))
    clk6.advance(900)
    r6.tick()
    flag["halted"] = True
    clk6.advance(900)
    rep6 = r6.tick()
    ck(rep6.transition == RUN.NEEDS_REVIEW and st6.get(rec6.run_id).state == RUN.NEEDS_REVIEW,
       "کلیدِ توقفِ اضطراریِ سراسری اجرا را می‌بندد", rep6.transition)
    broken = SCH.AutoClickRunRunner(st6, executor=EX.AutoClickExecutor(ctx_for(d6)),
                                     halt_check=lambda: (_ for _ in ()).throw(RuntimeError()))
    ck(broken._halted()[0] is True, "خرابیِ بررسیِ توقف = متوقف‌باش، نه ادامه")

    # نرخ: ردِ پیش از کلیک
    st7 = store_tmp()
    rec7 = mkrun(st7, n=2, iv=800)
    clk7 = FakeClock(rec7.config.planned_first_at_ms())
    d7 = driver_for(page_state())
    lim = RL.OrderRateLimiter(clock=clk7.mono)
    lim.block_for(10.0, "easytrader", source="throttle-evidence")
    r7 = SCH.AutoClickRunRunner(st7, executor=EX.AutoClickExecutor(ctx_for(d7)),
                                limiter=lim, wall_ms=clk7.wall, clock=clk7.mono, spin_ms=0.0)
    clk7.advance(900)
    rep7 = r7.tick()
    ck(rep7.transition == RUN.BLOCKED and d7.click_count == 0,
       "قفلِ نرخ پیش از کلیک → BLOCKED و صفر کلیک", (rep7.transition, d7.click_count))
    st8 = store_tmp()
    rec8 = mkrun(st8, n=4, iv=800)
    clk8 = FakeClock(rec8.config.planned_first_at_ms())
    d8 = driver_for(page_state())
    lim8 = RL.OrderRateLimiter(clock=clk8.mono)
    r8 = SCH.AutoClickRunRunner(st8, executor=EX.AutoClickExecutor(
        ctx_for(d8, wall=clk8.wall)), limiter=lim8, wall_ms=clk8.wall, clock=clk8.mono,
        spin_ms=0.0)
    for _ in range(14):
        clk8.advance(200)          # حلقۀ سریع‌تر از کفِ مقرراتی
        r8.tick()
    fires = sorted(a.fired_at_ms for a in st8.get(rec8.run_id).actions
                   if a.fired_at_ms)
    deltas = [b - a for a, b in zip(fires, fires[1:])]
    ck(fires and all(dl >= 300 for dl in deltas),
       "هیچ دو شلیکی به هم نزدیک‌تر از کفِ مقرراتیِ ۳۰۰ms نمی‌افتند",
       (fires, deltas, d8.click_count))
    # بودجه فقط با شلیک خرج می‌شود
    lim9 = RL.OrderRateLimiter(clock=lambda: 0.0)
    before = lim9.usage()["rules"]["internal_per_minute"]["used"]
    lim9.try_acquire(consume=False)
    ck(lim9.usage()["rules"]["internal_per_minute"]["used"] == before,
       "پیش‌چکِ بی‌مصرف، بودجه نمی‌خورد")


# ── ۴) timezone / پیکربندی / restart ────────────────────────────────────────
def part_time_and_config() -> None:
    epoch = RUN.parse_tehran_wall("2026-10-24T09:00:00")
    # ۰۹:۰۰ تهران = ۰۵:۳۰ UTC (ثابتِ +۳:۳۰، بدونِ DST)
    import datetime as dt
    as_utc = dt.datetime.fromtimestamp(epoch / 1000.0, dt.timezone.utc)
    ck(as_utc.isoformat().startswith("2026-10-24T05:30:00"),
       "تبدیلِ تهران به UTC درست است (بدونِ DST)", as_utc.isoformat())
    fa = RUN.parse_tehran_wall("۱۴۰۵-۰۸-۰۲T۰۹:۰۰:۰۰".replace("۱۴۰۵-۰۸-۰۲", "2026-10-24"))
    ck(fa == epoch, "رقمِ فارسی در ورودیِ زمان پذیرفته و یکسان تبدیل می‌شود", (fa, epoch))
    for bad in ("", "09:00", "2026-13-45T09:00"):
        try:
            RUN.parse_tehran_wall(bad)
            ck(False, "زمانِ نامعتبر مردود است: %r" % bad)
        except RUN.RunError:
            ck(True, "زمانِ نامعتبر مردود: %r" % bad[:12])
    cfg = RUN.RunConfig(symbol="داروند", side="buy", expected_price=11010, expected_quantity=100,
                        target_at="2026-10-24T09:00:00", mode="repeat", total_actions=4,
                        interval_ms=750)
    pv = cfg.normalized().preview()
    ck(pv["max_orders_possible"] == 4 and pv["total_shares_possible"] == 400 and
       pv["max_gross_value_rial"] == 4_404_000.0,
       "پیش‌نمایش: حداکثرِ سفارش/سهم/ارزشِ ناخالص محاسبه می‌شود", pv)
    ck("مستقل" in pv["warning"] or "سفارش" in pv["warning"],
       "پیش‌نمایش صریح می‌گوید هر کلیک می‌تواند سفارشِ مستقل بسازد", pv["warning"])
    # فاصله و تعداد از کد نمی‌آیند، از تنظیمات می‌آیند
    alt = RUN.RunConfig(**{**__import__("dataclasses").asdict(cfg), "total_actions": 7,
                           "interval_ms": 1200}).normalized()
    ck(alt.total_actions == 7 and alt.interval_ms == 1200 and
       len([alt.planned_action_at_ms(i) for i in range(7)]) == 7 and
       alt.planned_action_at_ms(6) - alt.planned_action_at_ms(0) == 7200,
       "تعداد/فاصله ورودیِ واقعی‌اند و زمان‌ها را جابه‌جا می‌کنند",
       (alt.total_actions, alt.interval_ms))
    # پیکربندیِ بی‌سقف و زیرِ کف مردود است
    for bad_kwargs, why in (({"mode": "repeat", "total_actions": 999, "interval_ms": 800},
                             "تعدادِ بی‌سقف"),
                            ({"mode": "repeat", "total_actions": 2, "interval_ms": 50},
                             "فاصلۀ زیر کف مقرراتی")):
        try:
            RUN.RunConfig(**{**__import__("dataclasses").asdict(cfg), **bad_kwargs}).normalized()
            ck(False, "%s مردود نیست" % why)
        except RUN.RunError as e:
            ck(True, "%s مردود: %s" % (why, e.code))
    # ذخیره/بازخوانیِ اجرا: تنظیمات با بازشدنِ دوباره عوض نمی‌شوند
    st = store_tmp()
    rec = mkrun(st, n=3, iv=800)
    again = st.get(rec.run_id)
    ck(again.config.total_actions == rec.config.total_actions and
       again.config.interval_ms == rec.config.interval_ms and
       again.config.expected_price == rec.config.expected_price,
       "تنظیمات بعدِ بازشدنِ دوباره یکسان می‌ماند",
       (again.config.total_actions, again.config.interval_ms))
    # restart → NEEDS_REVIEW و بی‌هیچ اقدامِ خودکار
    st.arm(rec.run_id, validation={"ok": True}, ok_for_arm=True)
    st.start(rec.run_id)
    d = driver_for(page_state())
    clk = FakeClock(rec.config.planned_first_at_ms())
    r = SCH.AutoClickRunRunner(st, executor=EX.AutoClickExecutor(ctx_for(d)),
                               wall_ms=clk.wall, clock=clk.mono, spin_ms=0.0)
    rec_store2 = st.recover()
    ck(rec_store2["restored"] >= 1 and st.get(rec.run_id).state == RUN.NEEDS_REVIEW,
       "recover بعدِ restart اجرا را NEEDS_REVIEW می‌کند", rec_store2)
    r.tick()
    ck(d.click_count == 0, "بعدِ restart هیچ اقدامی خودکار اجرا نمی‌شود", d.click_count)
    # تأییدِ اجرایِ زنده بی‌عبارتِ صریح ممکن نیست
    try:
        st.set_confirmation(rec.run_id, live=True, dry_run=False, phrase="اشتباه")
        ck(False, "عبارتِ نادرست نباید تأییدِ زنده بسازد")
    except RUN.RunError as e:
        ck(e.code == "CONFIRMATION_PHRASE", "تأییدِ زنده بی‌عبارتِ درست مردود: %s" % e.code)
    st.set_confirmation(rec.run_id, live=True, dry_run=False, phrase=RUN.LIVE_PHRASE)
    st.set_state(rec.run_id, RUN.ARMED, reason="arm")
    ck(st.start(rec.run_id).state == RUN.RUNNING,
       "با تأییدِ صریحِ مالک، اجرایِ زنده قابلِ شروع است")


# ── ۵) قوانینِ کارگزاری: منشأ، نه اختراع ─────────────────────────────────────
def part_rules() -> None:
    ids = set(TR.RULES)
    st = store_tmp()
    now = RUN.parse_tehran_wall("2026-10-24T08:00:00")
    facts = {"last_price": 10160.0, "allowed_min": 9580.0, "allowed_max": 11010.0,
             "data_as_of_ms": now, "data_source": "market.db:market_watch",
             "calendar_open": True, "open_orders": []}
    cont = RUN.parse_tehran_wall("2026-10-24T09:05:00")
    rep = TR.run_preflight(symbol="داروند", isin="IRO1DRVN0001", side="buy",
                           price=10800.0, quantity=1000.0, total_actions=3,
                           interval_ms=800.0, target_at_ms=cont, facts=facts, now_ms=now)
    ck(rep.ok_for_arm is True, "پیش‌نگاشتِ کامل با دادهٔ تازه سبز است", rep.blockers)
    ck(all(c.rule_id in ids for c in rep.checks),
       "همۀ چک‌ها به یک قاعدۀ ثبت‌شده برمی‌گردند", [c.rule_id for c in rep.checks])
    ck(all((c.source and c.confidence) for c in rep.checks),
       "هر چک منبع و سطح اطمینان دارد",
       [c.public() for c in rep.checks if not (c.source and c.confidence)][:3])
    missing = TR.run_preflight(symbol="داروند", side="buy", price=10800.0, quantity=1000.0,
                               total_actions=1, interval_ms=800.0, target_at_ms=cont,
                               facts={}, now_ms=now)
    by = {c.id: c.status for c in missing.checks}
    ck(by.get("price_band") == "UNKNOWN" and by.get("buying_power") == "UNKNOWN"
       and by.get("calendar") == "UNKNOWN" and by.get("open_orders") == "UNKNOWN",
       "نبودِ داده = UNKNOWN، نه PASS و نه ردِ خاموش", by)
    stale = dict(facts)
    stale["data_as_of_ms"] = now - 900_000
    stale_rep = TR.run_preflight(symbol="داروند", side="buy", price=10800.0,
                                 quantity=1000.0, total_actions=1, interval_ms=800.0,
                                 target_at_ms=cont, facts=stale, now_ms=now)
    ck({c.id: c.status for c in stale_rep.checks}.get("price_band") == "UNKNOWN",
       "دادهٔ کهنه بازه را PASS نمی‌کند")
    off_tick = TR.run_preflight(symbol="داروند", side="buy", price=10805.0, quantity=1000.0,
                                total_actions=1, interval_ms=800.0, target_at_ms=cont,
                                facts=facts, now_ms=now)
    ck({c.id: c.status for c in off_tick.checks}.get("price_tick") == "FAIL",
       "قیمتِ غیرمضربِ گام مردود است")
    below = TR.run_preflight(symbol="داروند", side="buy", price=9000.0, quantity=1000.0,
                             total_actions=1, interval_ms=800.0, target_at_ms=cont,
                             facts=facts, now_ms=now)
    ck({c.id: c.status for c in below.checks}.get("price_band") == "FAIL",
       "قیمتِ زیرِ مجاز مردود است")
    pre = RUN.parse_tehran_wall("2026-10-24T08:50:00")
    policy = TR.run_preflight(symbol="داروند", side="buy", price=10800.0, quantity=1000.0,
                              total_actions=1, interval_ms=800.0, target_at_ms=pre,
                              facts=facts, now_ms=now)
    stt = {c.id: c.status for c in policy.checks}
    ck(stt.get("algorithmic_timing") == "BLOCKED" and policy.ok_for_arm is False,
       "هدف در پیش‌گشایش بی‌اقرار مسدود است (بندِ الحاقیۀ الگوریتم)", stt)
    acked = TR.run_preflight(symbol="داروند", side="buy", price=10800.0, quantity=1000.0,
                             total_actions=1, interval_ms=800.0, target_at_ms=pre,
                             facts=facts, acknowledge_preopen=True, now_ms=now)
    ck({c.id: c.status for c in acked.checks}.get("algorithmic_timing") == "WARN",
       "با اقرارِ صریحِ کاربر فقط هشدار می‌ماند (تصمیم با مالک)")
    ck(any(c.owner_ruling_required for c in policy.checks),
       "چک‌هایِ مبتنی بر تعریفِ متنِ قراردادی برچسبِ «نیازمندِ نظرِ مالک» دارند")
    selftrade = dict(facts)
    selftrade["open_orders"] = [{"side": "sell", "symbol": "داروند", "price": 10800.0}]
    stt2 = {c.id: c.status for c in TR.run_preflight(
        symbol="داروند", side="buy", price=10800.0, quantity=1000.0, total_actions=1,
        interval_ms=800.0, target_at_ms=cont, facts=selftrade, now_ms=now).checks}
    ck(stt2.get("open_orders") == "FAIL", "سفارشِ مخالفِ هم‌قیمت (self-trade) مردود است")
    early = TR.run_preflight(symbol="داروند", side="buy", price=10800.0, quantity=1000.0,
                             total_actions=1, interval_ms=800.0,
                             target_at_ms=RUN.parse_tehran_wall("2026-10-24T08:30:00"),
                             facts=facts, now_ms=now)
    ck({c.id: c.status for c in early.checks}.get("trading_window") == "FAIL",
       "قبل از ۰۸:۴۵ مردود است (این OMS رد می‌کند نه صف)")
    tiny = TR.run_preflight(symbol="داروند", side="buy", price=10800.0, quantity=100.0,
                            total_actions=1, interval_ms=800.0, target_at_ms=cont,
                            facts=facts, now_ms=now)
    ck({c.id: c.status for c in tiny.checks}.get("order_size") == "FAIL" and
       any(c.owner_ruling_required for c in tiny.checks if c.id == "order_size"),
       "ارزشِ زیرِ کمینه مردود است و تعارضِ منبع برچسبِ نظرِ مالک دارد")
    # سقف‌ها: داخلی به کارگزاری نسبت داده نمی‌شود؛ کلاینت اعمال نمی‌شود
    lim = RL.OrderRateLimiter()
    kinds = {r.rule_id: r.kind for r in lim.rules}
    ck(kinds.get("official_min_spacing") == RL.OFFICIAL and
       lim.rules[[r.rule_id for r in lim.rules].index("official_min_spacing")].attributed_to_broker,
       "کفِ ۳۰۰ms با برچسبِ رسمی/سروری")
    internal = [r for r in lim.rules if r.kind == RL.INTERNAL]
    ck(internal and all(not r.attributed_to_broker for r in internal),
       "سقف‌هایِ داخلی هرگز به کارگزاری نسبت داده نمی‌شوند")
    client = [r for r in lim.rules if r.kind == RL.CLIENT_CODE]
    ck(client and all(not r.enforceable for r in client),
       "«۱۰۰۰ در ساعت» فقط کدِ کلاینت است و اعمال نمی‌شود",
       [r.public() for r in client])
    ck([r.rule_id for r in lim.rules if r.enforceable] and
       not any(r.source == "" for r in lim.rules if r.enforceable),
       "هیچ قاعدۀ اعمال‌شونده‌ای بی‌منبع نیست")
    # شمارشِ اقدام‌ها در پنجره‌ها
    clk = FakeClock(0)
    l2 = RL.OrderRateLimiter(clock=clk.mono)
    oks = 0
    for _ in range(10):
        clk.advance(200)
        if l2.try_acquire().ok:
            oks += 1
    ck(oks <= 6, "سقفِ داخلیِ دقیقه حتی با فاصلۀ ۲۰۰ms از ۶ عبور نمی‌کند", oks)
    plan = l2.check_plan(actions=8, interval_ms=400)
    ck(plan.fits is False and plan.blocked_by and plan.reasons,
       "پیش‌نمایشِ برنامه می‌گوید چند اقدام جا می‌شود", plan.public())
    dec = l2.observe_response(status=429, headers={"Retry-After": "9"}, where="guard")
    ck(dec == 9.0 and l2.try_acquire().ok is False,
       "Retry-Afterِ واقعی به قفلِ موقت تبدیل می‌شود", (dec, l2.try_acquire().public()))
    unknown_backoff = RL.OrderRateLimiter()
    got = unknown_backoff.observe_response(status=429, body="too many requests")
    ck(got is None and unknown_backoff.usage()["blocked_for_s"] > 0,
       "بی‌Retry-After: قفلِ پیش‌فرضِ داخلی، با برچسبِ داخلی نه عددِ سرور",
       (got, unknown_backoff.usage()["blocked_for_s"]))
    text = RL.looks_like_throttle(status=200, body='{"m":"عدم رعایت محدودیت تعداد ارسال '
                                                  'سفارش همزمان در ثانیه"}')
    ck(text is True, "متنِ OMSِ محدودیتِ نرخ حتی با ۲۰۰ شاهد است")
    pub = RL.OrderRateLimiter().public()
    ck(len(pub["unknowns"]) >= 3, "ناشناخته‌ها در گزارشِ قوانین صریح می‌آیند",
       pub["unknowns"])


# ── ۶) حلقۀ اطمینان: هیچ‌چیز بی‌دلیل کلیک نمی‌کند ───────────────────────────
def part_invariants() -> None:
    # الف) قیمت در لحظۀ هدف پاک شده → فوراً توقف، بی‌کلیک
    st = store_tmp()
    rec = mkrun(st, n=5, iv=800)
    clk = FakeClock(rec.config.planned_first_at_ms())
    d = driver_for(page_state())
    d.ui_fixture = page_state(price="0")
    ex = EX.AutoClickExecutor(ctx_for(d, wall=clk.wall))
    r = SCH.AutoClickRunRunner(st, executor=ex, wall_ms=clk.wall, clock=clk.mono,
                               spin_ms=0.0)
    clk.advance(900)
    rep = r.tick()
    ck(d.click_count == 0 and rep.outcome.get("state") == "MISMATCH",
       "قیمتِ پاک‌شده در لحظۀ هدف → کلیک نه", (d.click_count, rep.outcome.get("state")))
    ck(st.get(rec.run_id).state == RUN.NEEDS_REVIEW and
       [a.state for a in st.get(rec.run_id).actions].count(RUN.A_CANCELLED) == 4,
       "قیمت/تعداد نامعتبر → فوراً توقف و لغوِ ردیف‌هایِ مانده (بند ۶-۴)",
       (st.get(rec.run_id).state,
        [a.state for a in st.get(rec.run_id).actions]))
    # ادامه بی‌اجازۀ کاربر ساخته نمی‌شود
    for _ in range(3):
        clk.advance(900)
        r.tick()
    ck(d.click_count == 0, "پس از توقف، حلقه خودکار از نو کلیک نمی‌سازد", d.click_count)

    # ب) شروعِ دوبارۀ کنترل‌شده: plan حفظ می‌شود، فقط با reset + arm + start
    st.reset_for_restart(rec.run_id)
    st.arm(rec.run_id, validation={"ok_for_arm": True}, ok_for_arm=True)
    st.start(rec.run_id)
    d.ui_fixture = page_state()
    for _ in range(12):
        clk.advance(500)
        r.tick()
    got = st.get(rec.run_id)
    ck(d.click_count == 5 and [a.state for a in got.actions].count(RUN.A_DONE) == 5,
       "شروعِ دوبارۀ کنترل‌شده هر پنج اقدام را اجرا می‌کند",
       (d.click_count, [(a.idx, a.state) for a in got.actions]))
    ck(got.state == RUN.COMPLETED, "اجرا پس از تکمیلِ سقف COMPLETED می‌شود", got.state)
    deltas = [b - a for a, b in zip([a.fired_at_ms for a in got.actions if a.fired_at_ms],
                                  [a.fired_at_ms for a in got.actions if a.fired_at_ms][1:])]
    ck(deltas and all(dl >= 300 for dl in deltas),
       "فاصلۀ واقعیِ شلیک‌ها از کفِ مقرراتی ۳۰۰ms کمتر نیست", deltas)

    # ج) صفحه از مسیرِ سفارش برود → توقفِ آنی، بی‌کلیکِ آن دور
    st2 = store_tmp()
    rec2 = mkrun(st2, n=3, iv=800)
    clk2 = FakeClock(rec2.config.planned_first_at_ms())
    d2 = driver_for(page_state())
    r2 = SCH.AutoClickRunRunner(st2, executor=EX.AutoClickExecutor(
        ctx_for(d2, wall=clk2.wall)), wall_ms=clk2.wall, clock=clk2.mono, spin_ms=0.0)
    clk2.advance(900)
    r2.tick()
    before = d2.click_count
    d2.url_value = "https://d.easytrader.ir/orders"     # رفتن به صفحهٔ سفارشات
    clk2.advance(900)
    rep2 = r2.tick()
    ck(rep2.outcome.get("state") in ("PAGE_CHANGED", "SESSION_LOST") and
       d2.click_count == before,
       "رفتنِ صفحه از مسیرِ سفارش → توقفِ آنی بی‌کلیک",
       (rep2.outcome.get("state"), d2.click_count, before))
    ck(st2.get(rec2.run_id).state in (RUN.NEEDS_REVIEW, RUN.BLOCKED),
       "ناوبریِ ناخواسته اجرا را در وضعیتِ بازبینی می‌گذارد", st2.get(rec2.run_id).state)

    # د) ردیفِ مردود شلیک حساب نمی‌شود و فرصتِ همان ردیف از دست نمی‌رود
    st3 = store_tmp()
    rec3 = mkrun(st3, n=2, iv=800)
    clk3 = FakeClock(rec3.config.planned_first_at_ms())
    d3 = driver_for(page_state(cands=[cand(0), cand(1)]))
    r3 = SCH.AutoClickRunRunner(st3, executor=EX.AutoClickExecutor(
        ctx_for(d3, wall=clk3.wall)), wall_ms=clk3.wall, clock=clk3.mono, spin_ms=0.0)
    clk3.advance(900)
    r3.tick()
    ck(d3.click_count == 0 and st3.get(rec3.run_id).actions[0].state == RUN.A_BLOCKED,
       "اقدامِ مردودِ دکمهٔ مبهم BLOCKED ثبت می‌شود، نه شلیک",
       st3.get(rec3.run_id).actions[0].state)


def main() -> int:
    part_ui_judge()
    part_executor()
    part_scheduler_counts()
    part_time_and_config()
    part_rules()
    part_invariants()
    print("\n%d pass / %d fail" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
