# -*- coding: utf-8 -*-
"""round18_ui_check — live UI proof of Round 18 readiness fields (real backend)."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5212"


def main() -> int:
    checks = []

    def ck(cond, label, detail=""):
        checks.append(bool(cond))
        print(("ok   " if cond else "FAIL ") + label +
              ("" if cond else "  -> " + str(detail)[:220]))

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
        pg.wait_for_selector("[data-testid='autoclicker-mofid-verify']", timeout=15000)
        pg.click("[data-testid='autoclicker-mofid-verify']")
        pg.wait_for_selector("[data-testid='autoclicker-mofid-account-readiness']",
                             timeout=60000)
        bp = pg.get_by_test_id("autoclicker-mofid-bp").inner_text()
        readiness = pg.get_by_test_id("autoclicker-mofid-account-readiness").inner_text()
        fresh = pg.get_by_test_id("autoclicker-mofid-freshness").inner_text()
        closed = pg.get_by_test_id("autoclicker-mofid-live-closed").inner_text()
        ck("IRR" in bp and "VERIFIED" in bp, "واحد/دقت در UI نمایش داده می‌شود", bp)
        ck("ناقص" in readiness and "sellable:UNVERIFIED" in readiness,
           "گیتِ ناقص و sellable تأییدنشده دیده می‌شود", readiness)
        ck("LOCAL_FETCH_ONLY" in fresh and "اندازه‌گیری‌نشده" in fresh,
           "تازگی/read-back صادقانه نمایش داده می‌شوند", fresh)
        ck("live_ready=false" in closed, "live_ready=false در UI است", closed)
        ck(not errs, "بدونِ خطای runtime", errs[:2])
        pg.screenshot(path=r"C:/Users/PCMOD/Desktop/_bors-sarkhati-minfix/_audit/round18_ui_live.png",
                      full_page=True)
        ctx.close()
        b.close()
    print("\n%d checks, %d failed" % (len(checks), checks.count(False)))
    print("ROUND18 UI " + ("OK" if all(checks) else "FAILED"))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
