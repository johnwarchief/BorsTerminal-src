"""دست‌های Playwright + چشمِ Valen: روی تب تکنیکال و تابلو کلیک می‌کند، اسکرین می‌گیرد،
و هر قاب را هم به‌صورت قطعی (DOM) و هم با رأیِ تصویری Valen بررسی می‌کند.

اجرا با پایتونِ محیطِ توسعه (playwright نصب‌شده)، نه محیطِ ریلیز:
    python tools/ui_walkthrough.py --base http://127.0.0.1:5173
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

VAL_PY = Path("E:/bors-ui-qa/venv/Scripts/python.exe")
EVAL = Path(__file__).with_name("valen_eval.py")
SHOTS = Path("E:/bors-ui-qa/shots")

# کنسولِ ویندوز cp1252 است و متنِ فارسیِ گزارش را نمی‌نویسد
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٬", "0123456789,")
ERROR_MARKERS = ("Unexpected Application Error", "An error occurred", "Cannot read", "is not a function")


def fa_num(text: str):
    """اولین عددِ داخل متنِ فارسی → float؛ اگر نبود None."""
    if not text:
        return None
    t = text.translate(PERSIAN_DIGITS).replace("،", ",")
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", t)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


@dataclass
class Step:
    name: str
    actions: list
    question: str = ""
    criteria: dict = field(default_factory=dict)
    # پرسش‌های انتزاعی («رابط سالم است؟») Valen را به تأییدِ همیشه‌بله می‌کشانند؛
    # پرسشِ عینی و کلمه‌ای («پیام خطا دیده می‌شود؟») درست تفکیک می‌کند.
    good: str = "valid"


class Judge:
    """یک پروسهٔ Valen که مدل یک‌بار بارگذاری می‌شود و به‌صورت line-protocol رأی می‌دهد."""

    def __init__(self, enabled: bool):
        self.proc = None
        if not enabled:
            return
        if not VAL_PY.exists():
            print(f"[judge] venv not found at {VAL_PY} — DOM checks only", file=sys.stderr)
            return
        try:
            self.proc = subprocess.Popen(
                [str(VAL_PY), str(EVAL), "--serve"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, encoding="utf-8", bufsize=1,
            )
        except OSError as exc:
            print(f"[judge] spawn failed: {exc} — DOM checks only", file=sys.stderr)

    def ask(self, image: str, question: str, criteria: dict) -> dict | None:
        if not self.proc:
            return None
        req = {"id": time.time_ns(), "image": image, "kind": "choice",
               "question": question, "criteria": criteria}
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            self.proc = None
            return None
        reply = json.loads(line)
        if not reply.get("ok"):
            print(f"[judge] {reply.get('error')}", file=sys.stderr)
            return None
        return reply["answers"].get("ui")

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                self.proc.kill()


def collect_page_state(page) -> dict:
    return page.evaluate(
        """() => {
        const body = document.body.innerText || '';
        const clipped = [];
        for (const el of document.querySelectorAll('th, td, button, span')) {
            if (el.scrollWidth - el.clientWidth > 2 && getComputedStyle(el).overflow !== 'visible') {
                const t = (el.textContent || '').trim().slice(0, 40);
                if (t) clipped.push(t);
                if (clipped.length > 12) break;
            }
        }
        const bad = [];
        for (const el of document.querySelectorAll('td, th, span, div')) {
            const t = (el.textContent || '').trim();
            if (/^(NaN|undefined|null|Infinity|-Infinity)$/.test(t)) {
                bad.push(t + '@' + (el.className || '').toString().slice(0, 30));
                if (bad.length > 8) break;
            }
        }
        return {
            text: body.slice(0, 4000),
            canvases: document.querySelectorAll('canvas').length,
            rows: document.querySelectorAll('[data-testid="tape-row"]').length,
            docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            clipped: clipped,
            rawValues: bad,
        };
    }"""
    )


def run_step(page, errors: list[str], judge: Judge, step: Step, report: list) -> bool:
    mark = len(errors)

    t0 = time.time()
    try:
        for act in step.actions:
            act(page)
    except Exception as exc:  # noqa: BLE001
        report.append({"step": step.name, "status": "action-failed", "detail": str(exc)[:300]})
        print(f" FAIL  {step.name:<38} action error: {str(exc)[:160]}", file=sys.stdout)
        return False

    SHOTS.mkdir(parents=True, exist_ok=True)
    shot = SHOTS / f"{step.name}.png"
    page.screenshot(path=str(shot))
    state = collect_page_state(page)

    problems = []
    hit = next((m for m in ERROR_MARKERS if m in state["text"]), None)
    if hit:
        problems.append(f"error-boundary: {hit}")
    if state["rawValues"]:
        problems.append(f"raw-values: {state['rawValues'][:5]}")
    if state["docOverflowX"] > 2:
        problems.append(f"horizontal-overflow: {state['docOverflowX']}px")
    new_errors = errors[mark:]
    if new_errors:
        problems.append(f"console-errors: {new_errors[:3]}")

    verdict = None
    if step.question and step.criteria:
        verdict = judge.ask(str(shot), step.question, step.criteria)
        if verdict and verdict.get("choice") and verdict["choice"] != step.good:
            problems.append(f"valen: {verdict['choice']} p={verdict.get('probabilities')}")

    ok = not problems
    report.append({
        "step": step.name, "status": "ok" if ok else "BROKEN",
        "seconds": round(time.time() - t0, 1), "shot": str(shot),
        "problems": problems, "valen": verdict,
        "rows": state["rows"], "canvases": state["canvases"],
    })
    print(f"{'  ok  ' if ok else ' FAIL '} {step.name:<38} rows={state['rows']} "
          f"{'| ' + '; '.join(problems) if problems else ''}", file=sys.stdout)
    return ok


# ---------------------------------------------------------------- actions
def goto(page, url, ready: str | None = None):
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    # روترِ hash بی‌بارگذاری جابه‌جا می‌شود؛ تا نشانهٔ آمادگی صبر نمی‌کنیم،
    # اسکرین‌شاتِ مرحلهٔ بعد نیمه‌کاره است.
    if ready:
        page.wait_for_selector(ready, timeout=25000)
    page.wait_for_timeout(600)


def open_indicators(page):
    btn = page.locator('button[title="پنل اندیکاتورها"]')
    btn.first.wait_for(state="visible", timeout=15000)
    btn.first.click()
    page.wait_for_timeout(400)


def toggle_indicator(label: str):
    def act(page):
        box = page.get_by_label(re.compile(label)).first
        box.wait_for(state="attached", timeout=8000)
        box.click()
        page.wait_for_timeout(700)
    return act


def close_indicators(page):
    # همان دکمهٔ toolbar مودال را تبديل می‌کند؛ Escape در این پنل وصل نیست.
    page.locator('button[title="پنل اندیکاتورها"]').first.click()
    page.wait_for_timeout(300)


def click_header(label: str):
    """هدرِ تابلو <th> نیست: دکمهٔ داخل یک ردیفِ grid است؛ نامِ دقیق + فلشِ مرتب‌سازی."""
    def act(page):
        page.get_by_role(
            "button", name=re.compile(rf"^{re.escape(label)}(\s*[↓↑])?$")
        ).first.click()
        page.wait_for_timeout(500)
    return act


READ_COLUMN = """(label) => {
    // سرستونِ تابلو <th> نیست؛ ردیفِ grid چسبانِ بالا است. برای اینکه نوارِ چسبانِ
    // دیگری قاطی نشود، از خودِ کانتینرِ اسکرول به بالا می‌رویم.
    const scroll = document.querySelector('[data-testid="tape-scroll"]');
    const head = scroll && scroll.parentElement ? scroll.parentElement.firstElementChild : null;
    const heads = head ? Array.from(head.querySelectorAll(':scope > button')) : [];
    const idx = heads.findIndex((h) => (h.textContent || '').trim().startsWith(label));
    const glyph = idx >= 0 ? (heads[idx].textContent || '').trim() : '';
    const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]'));
    if (idx < 0 || !rows.length) return { found: false, glyph, cells: [], headerCount: heads.length };
    const cells = rows.map((r) => (r.children[idx] ? r.children[idx].innerText : ''));
    return { found: true, glyph, cells, headerCount: heads.length,
             rowCount: rows.length, cellCount: rows[0].children.length };
}"""


def assert_sorted(label: str):
    """جهت را حدس نمی‌زند: می‌سنجد که ستون واقعاً یکنوا است و کدام جهت دارد."""
    def act(page):
        res = {}
        for _ in range(4):
            res = page.evaluate(READ_COLUMN, label)
            if res["found"] and any(fa_num(c) is not None for c in res["cells"]):
                break
            # اولین خوانش بعد از ناوبری گاهی قبل از نقاشیِ مجازی‌ساز است
            page.wait_for_timeout(600)
        if not res["found"]:
            raise AssertionError(f"column '{label}' not found in {res.get('headerCount')} headers")
        if res["headerCount"] != res["cellCount"]:
            raise AssertionError(
                f"header/row misalignment: {res['headerCount']} headers vs {res['cellCount']} cells")
        nums = [n for n in (fa_num(c) for c in res["cells"]) if n is not None]
        if len(nums) < 5:
            # صعودی، نمادهای بی‌داده را اول می‌گذارد؛ ممکن است چند صد ردیف «-» باشد،
            # پس تا رسیدن به بخشِ عددی اسکرول می‌کنیم.
            for frac in (0.25, 0.5, 0.75):
                page.evaluate(
                    """(f) => { const el = document.querySelector('[data-testid="tape-scroll"]');
                                if (el) el.scrollTop = el.scrollHeight * f; }""", frac)
                page.wait_for_timeout(700)
                res = page.evaluate(READ_COLUMN, label)
                nums = [n for n in (fa_num(c) for c in res["cells"]) if n is not None]
                if len(nums) >= 5:
                    break
        if len(nums) < 5:
            raise AssertionError(f"only {len(nums)} numeric cells in '{label}'")
        desc = all(a >= b for a, b in zip(nums, nums[1:]))
        asc = all(a <= b for a, b in zip(nums, nums[1:]))
        if not (desc or asc):
            breaks = sum(1 for a, b in zip(nums, nums[1:]) if a < b)
            raise AssertionError(
                f"'{label}' is not monotonic ({breaks} ascending steps in {len(nums)} rows): "
                f"{[round(n, 2) for n in nums[:6]]}")
        act.order = "desc" if desc else "asc"
        act.glyph = res["glyph"]
    return act


def open_filter_settings(index: int):
    def act(page):
        gears = page.locator('button[title^="تنظیم آستانه"]')
        gears.nth(index).wait_for(state="visible", timeout=8000)
        gears.nth(index).click()
        page.wait_for_timeout(900)
    return act


def close_modal(page):
    page.locator('[role="dialog"]').get_by_text("✕", exact=True).first.click()
    page.wait_for_timeout(400)
    if page.locator('[role="dialog"]').count():
        raise AssertionError("popover did not close")


def scroll_table(jump: int):
    def act(page):
        page.evaluate(
            "(y) => { const el = document.querySelector('[data-testid=\"tape-scroll\"]');"
            " if (el) { el.scrollTop = y; } }", jump)
        page.wait_for_timeout(250)
    return act


# ---------------------------------------------------------------- steps
def build_steps(base: str) -> list[Step]:
    # این پرسش کالیبره شده: روی صفحهٔ کرش «بله» (۰٫۵۶) و روی دو صفحهٔ سالم
    # «خیر» (۰٫۹۵ و ۰٫۹۱) می‌دهد. پرسش‌های کلی («رابط سالم است؟») همیشه «سالم»
    # می‌گویند و بی‌فایده‌اند.
    ERR_Q = ("آیا روی این صفحه پیام خطا دیده می‌شود؟ "
             "پیام خطا یعنی عبارت انگلیسی «Unexpected Application Error» "
             "یا جملهٔ قرمزِ خطای برنامه.")
    ERR_C = {
        "خیر": "چنین پیامی روی صفحه نیست؛ جدول، چارت و پنل‌ها عادی‌اند.",
        "بله": "پیام خطا یا صفحهٔ کرش روی تصویر دیده می‌شود.",
    }
    good = "خیر"

    steps: list[Step] = []
    tech = f"{base}/#/technical/خودرو"
    market = f"{base}/#/market"

    steps.append(Step("tech-01-open", [lambda p: goto(p, tech, "canvas")], ERR_Q, ERR_C, good))
    steps.append(Step("tech-02-indicator-menu", [open_indicators]))

    for key, label in [("MA", "میانگین متحرک ساده"), ("EMA", "میانگین متحرک نمایی"),
                       ("RSI", "شاخص قدرت نسبی"), ("MACD", "مکدی"), ("BOLL", "باندهای بولینگر")]:
        steps.append(Step(f"tech-03-{key.lower()}", [toggle_indicator(label)], ERR_Q, ERR_C, good))

    steps.append(Step("tech-04-close-menu", [close_indicators]))
    steps.append(Step("tech-05-settings-appearance", [
        lambda p: p.locator('button[title="تنظیمات چارت"]').first.click(),
        lambda p: p.wait_for_selector('[data-testid="chart-settings"]', timeout=10000),
        lambda p: p.locator('[data-testid="settings-tab-appearance"]').first.click(),
        lambda p: p.wait_for_timeout(400),
    ], ERR_Q, ERR_C, good))

    steps.append(Step("board-01-open",
                     [lambda p: goto(p, market, '[data-testid="tape-row"]')], ERR_Q, ERR_C, good))
    steps.append(Step("board-02-sort-volratio", [click_header("نسبت حجم ماه"),
                                                 assert_sorted("نسبت حجم ماه")]))
    steps.append(Step("board-03-sort-volratio-flip", [click_header("نسبت حجم ماه"),
                                                      assert_sorted("نسبت حجم ماه")]))
    steps.append(Step("board-04-sort-lastprice", [click_header("قیمت آخرین"),
                                                  assert_sorted("قیمت آخرین")]))
    steps.append(Step("board-04b-sort-hourly-pattern", [click_header("الگوی ساعت"),
                                                        assert_sorted("الگوی ساعت")]))

    for i, name in enumerate(["clock", "susp", "jet", "roobi", "noqteh"]):
        steps.append(Step(f"board-05-settings-{name}", [open_filter_settings(i)],
                          ERR_Q, ERR_C, good))
        steps.append(Step(f"board-06-close-{name}", [close_modal]))

    steps.append(Step("board-07-scroll-fast",
                      [scroll_table(4000), scroll_table(20000), scroll_table(60000),
                       scroll_table(1500), scroll_table(90000)]))
    steps.append(Step("board-08-after-scroll", [lambda p: p.wait_for_timeout(600)],
                      ERR_Q, ERR_C, good))
    return steps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--pilot", action="store_true",
                    help="پس از شکست، check_stuck را با شرحِ گام‌ها (بی‌کد) صدا بزن")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out", default="E:/bors-ui-qa/ui_walkthrough.json")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed in this interpreter", file=sys.stderr)
        return 2

    judge = Judge(enabled=not args.no_judge)
    report: list[dict] = []
    failed = 0
    steps = build_steps(args.base.rstrip("/"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": args.width, "height": args.height})
        context.add_init_script("try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        page = context.new_page()
        page.set_default_timeout(20000)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        for step in steps:
            if not run_step(page, errors, judge, step, report):
                failed += 1
        context.close()
        browser.close()
    judge.close()

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(report)} steps, {failed} broken — report: {args.out}")

    if args.pilot and failed:
        # داورِ جریانی فقط شرحِ گام‌ها را می‌بیند، نه کد (خط‌مشیِ مالک). خلاصهٔ
        # خطاها آکولادِ repr دارد، پس پیش از ارسال به شکلِ نصِ ساده درمی‌آید.
        def prose(text: str) -> str:
            return re.sub(r"\s+", " ", re.sub(r"[{}<>\[\];:]", " ", text)).strip()[:140]

        lines = [f"{r['step']} — {r['status']} — " + prose("; ".join(r.get("problems") or []))
                 for r in report if r["status"] != "ok"]
        hist = Path(args.out).with_suffix(".failures.txt")
        hist.write_text("\n".join(lines), encoding="utf-8")
        verdict = subprocess.run(
            [str(VAL_PY), str(Path(__file__).with_name("pilot_ctl.py")),
             "stuck", "--history", str(hist)],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        print("pilot check_stuck:", verdict.stdout.strip() or verdict.stderr.strip())

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
