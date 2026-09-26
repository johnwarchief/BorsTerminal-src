"""چشمِ تصویری رویِ تب «بنیادی»: جدول، کارتِ نماد، پنل‌های جزئیات، کشوی تنظیمات و
تمِ روشن — در دو رزولوشن. هر قاب هم با DOM سنجیده می‌شود هم با Valen (یک مدل،
سرویسِ خطی، نه بارگذاریِ مجدد به‌ازایِ هر شات).

    python tools/capture_fund_visual.py --base http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

VAL_PY = Path("E:/bors-ui-qa/venv/Scripts/python.exe")
EVAL = Path(__file__).with_name("valen_eval.py")
SHOTS = Path("E:/bors-ui-qa/shots")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Valen با پرسشِ انتزاعی («آیا زیباست؟») رویِ صفحهٔ خراب هم «بله» می‌داد؛ پرسش باید
# عینیِ دوتایی باشد تا رأی‌اش قابل‌اتکا باشد.
RTL_Q = ("این تصویر یک رابط راست‌به‌چپ فارسی است. آیا متن یا کنترلِ شکسته‌ای می‌بینی: "
         "متنی که از کادرش بیرون زده، تکه‌ای که روی دیگری افتاده، یا بخشی که جهتِ "
         "چپ‌به‌راست گرفته است؟")
NUM_Q = ("آیا در این تصویر عددِ بی‌معنی یا خطایی می‌بینی: صفر درصد به‌عنوان آستانه، "
         "عبارت NaN یا undefined، یا ستونی که کامل خالی است؟")

CLIP_JS = """
() => {
  const bad = [];
  for (const el of document.querySelectorAll('span,div,button,td,th,h3,p')) {
    const cs = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 3 && el.clientWidth > 12
        && (el.textContent||'').trim().length > 2 && cs.overflow !== 'visible') {
      bad.push(((el.textContent||'').trim().slice(0,34)) + ' [' + cs.direction + '/' + cs.textAlign + ']');
    }
  }
  return [...new Set(bad)].slice(0,14);
}
"""

PROBLEM_JS = """
() => {
  const txt = document.body.innerText || '';
  return {
    error_boundary: /Unexpected Application Error|Something went wrong|An error occurred/i.test(txt),
    nan_undefined: [...new Set(txt.match(/NaN|undefined|\\[object Object\\]/g) || [])].slice(0,6),
    latin_words: (txt.match(/[A-Za-z]{4,}(?: [A-Za-z]{2,}){2,}/g) || []).slice(0,5),
    latin_digits: [...new Set((txt.match(/(?<![\\d.,%])\\d{2,}(?![\\d.,%])/g) || []))].slice(0,8),
    overflow_x: document.documentElement.scrollWidth > window.innerWidth + 2,
    dir: document.documentElement.dir || '(none)',
  };
}
"""


class Valen:
    """سرویسِ خطیِ valen_eval --serve؛ مدل یک بار بارگذاری می‌شود."""

    def __init__(self, enabled: bool):
        self.proc = None
        if not enabled:
            return
        self.proc = subprocess.Popen(
            [str(VAL_PY), str(EVAL), "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, errors="replace",
        )

    def ask(self, image: Path, question: str, yes: str, no: str) -> dict:
        if not self.proc:
            return {}
        req = {"image": str(image), "kind": "choice", "question": question,
               "criteria": {yes: yes, no: no}}
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            return {"error": (line or "")[:200]}
        if not resp.get("ok"):
            return {"error": resp.get("error")}
        return (resp.get("answers") or {}).get("ui") or {}

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
            self.proc.wait(timeout=30)


def login(pg, base: str):
    pg.goto(base + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=re.compile("ورود")).first.click()
    pg.wait_for_function("() => document.querySelectorAll('tbody tr').length > 5", timeout=120000)
    pg.wait_for_timeout(2500)


def capture(pg, name: str, vlm: Valen, results: list, ask_num: bool = True):
    SHOTS.mkdir(parents=True, exist_ok=True)
    shot = SHOTS / f"{name}.png"
    pg.screenshot(path=str(shot), full_page=False)
    dom = pg.evaluate(PROBLEM_JS)
    clipped = pg.evaluate(CLIP_JS)
    rec: dict = {"step": name, "shot": str(shot), "dom": dom, "clipped": clipped}
    rec["rtl"] = vlm.ask(shot, RTL_Q, "بله", "خیر")
    if ask_num:
        rec["nums"] = vlm.ask(shot, NUM_Q, "بله", "خیر")
    results.append(rec)

    hits = [k for k, v in dom.items() if v and k != "dir"] + (["clipped"] if clipped else [])
    pr = (rec["rtl"].get("probabilities") or {}).get("بله", 0)
    pn = (rec.get("nums", {}).get("probabilities") or {}).get("بله", 0)
    mark = "!! " if hits or pr > 0.5 else "   "
    print(f"{mark}{name:26s} rtl_بله={pr:.2f} num_بله={pn:.2f} " +
          (",".join(hits) if hits else ""), flush=True)
    for c in clipped[:4]:
        print(f"      بریده: {c}", flush=True)


def run(base: str, width: int, height: int, vlm: Valen, tag: str) -> list:
    results: list = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": height})
        login(pg, base)

        capture(pg, f"{tag}-table-top", vlm, results)
        sc = pg.locator('[data-testid="fts-screen-scroll"]').first
        sc.evaluate("(el) => el.scrollBy({top: 1500})")
        pg.wait_for_timeout(1000)
        capture(pg, f"{tag}-table-mid", vlm, results)
        sc.evaluate("(el) => el.scrollBy({top: -1500})")
        pg.wait_for_timeout(700)

        #排序ِ ستونِ امتیاز تا ردیف‌هایِ پایینِ نردبان هم دیده شوند
        try:
            pg.get_by_role("button", name=re.compile("امتیاز")).first.click()
            pg.wait_for_timeout(1200)
            capture(pg, f"{tag}-table-sorted-score", vlm, results, ask_num=False)
        except Exception:  # noqa: BLE001
            pass

        pg.locator('[data-testid="fts-screen-row"]').first.click()
        pg.wait_for_timeout(3500)
        capture(pg, f"{tag}-card", vlm, results)

        # پنل‌های جزئیات: دقیقاً دکمه‌های پنج‌گانهٔ کارت. «div.grid button» گام‌های
        # استراتژی را هم می‌گیرد و کاربر را به تب دیگری می‌برد.
        for d in ["1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry"]:
            btn = pg.locator(f'button[data-testid="fts-card-cell-{d}"]')
            if btn.count() == 0:
                print(f"   drill {d}: دکمه پیدا نشد", flush=True)
                continue
            try:
                btn.first.click(timeout=5000)
            except Exception as e:  # noqa: BLE001
                print(f"   drill {d} skipped:", str(e)[:90], flush=True)
                continue
            pg.wait_for_timeout(1800)
            capture(pg, f"{tag}-drill-{d}", vlm, results)
            # همان دکمه پنل را می‌بندد (onDrill همان کلید را null می‌کند)
            try:
                btn.first.click(timeout=4000)
            except Exception:  # noqa: BLE001
                pass
            pg.wait_for_timeout(900)

        try:
            pg.locator('[data-testid="fts-settings-btn"]').first.click(timeout=5000)
            pg.wait_for_timeout(1600)
            capture(pg, f"{tag}-settings-drawer", vlm, results)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(600)
        except Exception as e:  # noqa: BLE001
            print("   drawer skipped:", str(e)[:110], flush=True)

        try:
            pg.locator('button[title*="تم"]').first.click(timeout=4000)
            pg.wait_for_timeout(1600)
            capture(pg, f"{tag}-light-table", vlm, results, ask_num=False)
            pg.locator('[data-testid="fts-screen-row"]').first.click()
            pg.wait_for_timeout(2600)
            capture(pg, f"{tag}-light-card", vlm, results, ask_num=False)
        except Exception as e:  # noqa: BLE001
            print("   theme skipped:", str(e)[:110], flush=True)

        b.close()
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default="E:/bors-ui-qa/fund_visual.json")
    args = ap.parse_args()

    vlm = Valen(not args.no_judge)
    allr: list = []
    try:
        for w, h, tag in [(1920, 1080, "fv1920"), (1366, 768, "fv1366")]:
            print(f"\n=== {w}x{h} ===", flush=True)
            allr += run(args.base, w, h, vlm, tag)
    finally:
        vlm.close()

    Path(args.out).write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")

    bad = [r["step"] for r in allr
           if any(v for k, v in r["dom"].items() if k != "dir")
           or r["clipped"]
           or (r.get("rtl", {}).get("probabilities") or {}).get("بله", 0) > 0.5
           or (r.get("nums", {}).get("probabilities") or {}).get("بله", 0) > 0.5]
    print(f"\n{len(allr)} قاب | {'OK' if not bad else 'موارد: ' + ', '.join(bad)} — {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
