# -*- coding: utf-8 -*-
"""round19_ui_check — live UI proof of the Round 19 queue monitor (real backend)."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5212"


def main() -> int:
    checks = []

    def ck(cond, label, detail=""):
        checks.append(bool(cond))
        print(("ok   " if cond else "FAIL ") + label +
              ("" if cond else "  -> " + str(detail)[:260]))

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1366, "height": 768}, locale="fa-IR")
        ctx.add_init_script(
            "try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(1500)
        pg.evaluate("location.hash = '#/autoclicker'")
        pg.wait_for_selector("[data-testid='autoclicker-page']", timeout=20000)
        pg.click("[data-testid='autoclicker-path-api']")
        pg.wait_for_selector("[data-testid='autoclicker-queue-monitor']", timeout=15000)
        if "--blocked-only" in sys.argv:
            # پس از بسته‌شدنِ پنجرهٔ مالک: فقط حالتِ صادقانهٔ «بی‌دسترسی».
            pg.wait_for_function(
                "() => { const el = document.querySelector("
                "'[data-testid=\\'autoclicker-queue-empty\\']');"
                " return el && el.textContent.includes('دسترسی به حساب'); }",
                timeout=30000)
            supported = pg.get_by_test_id("autoclicker-queue-supported").inner_text()
            why = pg.get_by_test_id("autoclicker-queue-empty").inner_text()
            source = pg.get_by_test_id("autoclicker-queue-source").inner_text()
            closed = pg.get_by_test_id("autoclicker-mofid-live-closed").inner_text()
            rank_rows = pg.locator("[data-testid^='autoclicker-queue-rank-']").count()
            ck("در دسترس نیست" in supported,
               "حالتِ بی‌دسترسی صریح است", supported)
            ck("دسترسی به حساب" in why,
               "علتِ نبودِ داده از سرور است", why)
            ck("۱۰" in source, "نرخِ پایش ۱۰ ثانیه است", source)
            ck(rank_rows == 0, "هیچ رتبهٔ ساختگی نیست", rank_rows)
            ck("live_ready=false" in closed, "live_ready=false در UI است", closed)
            ck(not errs, "بدونِ خطای runtime", errs[:2])
            qsec = pg.get_by_test_id("autoclicker-queue-monitor")
            qsec.scroll_into_view_if_needed()
            pg.wait_for_timeout(300)
            qsec.screenshot(
                path=r"C:/Users/PCMOD/Desktop/_bors-sarkhati-minfix/_audit/round19_queue_blocked.png")
            ctx.close()
            b.close()
            print("\n%d checks, %d failed" % (len(checks), checks.count(False)))
            print("ROUND19 UI BLOCKED " + ("OK" if all(checks) else "FAILED"))
            return 0 if all(checks) else 1
        pg.click("[data-testid='autoclicker-mofid-verify']")
        pg.wait_for_selector("[data-testid='autoclicker-mofid-account-readiness']",
                             timeout=60000)
        # polling هر ۱۰ ثانیه است؛ تا رسیدنِ منبعِ آداپتور صبر می‌کنیم.
        pg.wait_for_function(
            "() => { const el = document.querySelector("
            "'[data-testid=\\'autoclicker-queue-source\\']');"
            " return el && el.textContent.includes('adapter:mofid'); }",
            timeout=30000)

        supported = pg.get_by_test_id("autoclicker-queue-supported").inner_text()
        claim = pg.get_by_test_id("autoclicker-queue-claim").inner_text()
        empty = pg.get_by_test_id("autoclicker-queue-empty").inner_text()
        source = pg.get_by_test_id("autoclicker-queue-source").inner_text()
        closed = pg.get_by_test_id("autoclicker-mofid-live-closed").inner_text()
        rank_rows = pg.locator("[data-testid^='autoclicker-queue-rank-']").count()
        queue_rows = pg.locator("[data-testid^='autoclicker-queue-row-']").count()

        ck("در دسترس نیست" in supported,
           "بدونِ قرارداد جایگاه، وضعیت صریح است", supported)
        ck("رتبهٔ اول" in claim and "۰" in claim,
           "UI می‌گوید ۰ رتبهٔ اول نیست", claim)
        ck("سفارشِ واقعیِ قابل‌پایشی نیست" in empty,
           "نبودِ سفارش با علت نمایش داده می‌شود", empty)
        ck("adapter:mofid" in source and "۱۰" in source,
           "منبع/نرخِ پایش از پاسخِ سرور است", source)
        ck(queue_rows == 0 and rank_rows == 0,
           "هیچ ردیف/رتبهٔ ساختگی ساخته نشده", (queue_rows, rank_rows))
        ck("live_ready=false" in closed,
           "live_ready=false در UI است", closed)
        ck(not errs, "بدونِ خطای runtime", errs[:2])
        qsec = pg.get_by_test_id("autoclicker-queue-monitor")
        qsec.scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        qsec.screenshot(
            path=r"C:/Users/PCMOD/Desktop/_bors-sarkhati-minfix/_audit/round19_queue_section.png")
        pg.screenshot(
            path=r"C:/Users/PCMOD/Desktop/_bors-sarkhati-minfix/_audit/round19_ui_live.png",
            full_page=True)
        ctx.close()
        b.close()
    print("\n%d checks, %d failed" % (len(checks), checks.count(False)))
    print("ROUND19 UI " + ("OK" if all(checks) else "FAILED"))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
