# -*- coding: utf-8 -*-
"""execution_ui_state.py — خواندنِ حالتِ فرمِ واقعی و تشخیصِ دکمهٔ درست.

Round 22 این ماژول را می‌سازد چون «یک selector، یک کلیک» برایِ فرمِ واقعیِ
EasyTrader قابلِ اتکا نیست: همان صفحه چند دکمهٔ هم‌نام، نسخهٔ مخفیِ ازقبلِ
فریم‌ورک، و فرمِ بازمانده از نمادِ قبلی دارد. سه اصل:

  ۱) فقط‌خواندنی. هیچ fill/click/change در این مسیر نیست؛ قیمت و تعدادِ
     کاربرِ واقعی فقط خوانده و مقایسه می‌شوند.
  ۲) شمارشِ خامِ selector دلیلِ یکتایی نیست. کاندیداها باید «موجود + نمایان +
     فعال + داخلِ viewport +وابسته به همان فرم» باشند؛ اگر دو تا ماند، مبهم است.
  ۳) هر تصمیم با شاهد برمی‌گردد (متن/aria/path/موقعیت و اندازه) و هر چیزی که دیده
     نمی‌شود UNKNOWN می‌ماند، نه PASS.

خروجیِ `evaluate` رویِ DOMِ واقعی اجرا می‌شود و داوری درِ پایتون انجام می‌شود؛
پس همان داوری با fixture و با Mock قابلِ تست است.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

# نشانه‌هایِ سمت در رابطِ فارسی/انگلیسیِ کارگزاری.
SIDE_TOKENS: dict[str, tuple[str, ...]] = {
    "buy": ("خرید", "buy", "purchase"),
    "sell": ("فروش", "sell"),
}
#: سمتِ مخالفِ هر سمت؛ برایِ اینکه «دکمهٔ فروش» در اجراِ خرید رد شود.
OPPOSITE = {"buy": "sell", "sell": "buy"}

#: عمقِ بیشترین بالابرنده برایِ یافتنِ ظرفِ فرم (جلوگیری از ریشه‌ی کلِ SPA).
_MAX_SCOPE_ANCESTORS = 8


UI_STATE_JS = r"""(opts) => {
  const clean = (s, n) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, n || 140);
  const qall = (sel) => { if (!sel) return []; try { return Array.from(document.querySelectorAll(sel)); } catch (e) { return []; } };
  const rectOf = (el) => { try { return el.getBoundingClientRect(); } catch (e) { return null; } };
  const styleOf = (el) => { try { return getComputedStyle(el); } catch (e) { return null; } };
  const visible = (el) => {
    const r = rectOf(el); const s = styleOf(el);
    if (!r || !s) return false;
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
      && s.display !== 'none' && Number(s.opacity) !== 0 && el.offsetParent !== null;
  };
  const inViewport = (el) => {
    const r = rectOf(el);
    if (!r || !r.width || !r.height) return false;
    const vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    return r.top >= 0 && r.left >= 0 && r.bottom <= vh && r.right <= vw;
  };
  const enabled = (el) => {
    if (el.disabled === true) return false;
    if (el.getAttribute && el.getAttribute('aria-disabled') === 'true') return false;
    if (el.getAttribute && el.getAttribute('aria-hidden') === 'true') return false;
    const s = styleOf(el);
    if (s && (s.pointerEvents === 'none')) return false;
    return true;
  };
  const pathOf = (el) => {
    const parts = []; let cur = el, depth = 0;
    while (cur && cur.tagName && depth < 12) {
      let name = cur.tagName.toLowerCase();
      if (cur.id) { parts.unshift(name + '#' + cur.id); break; }
      const parent = cur.parentElement;
      let idx = 1;
      if (parent) {
        const same = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        idx = Math.max(1, same.indexOf(cur) + 1);
      }
      parts.unshift(name + ':nth(' + idx + ')');
      cur = parent; depth++;
    }
    return parts.join('/');
  };
  const valueOf = (sel) => {
    const nodes = qall(sel);
    if (!nodes.length) return {present: false, count: nodes.length, value: '', text: '',
                               visible: false, readonly: null};
    const el = nodes[0];
    const raw = (el.value !== undefined && el.value !== null && String(el.value) !== '')
      ? String(el.value) : String(el.innerText || el.textContent || '');
    return {present: true, count: nodes.length, value: clean(raw, 60),
            text: clean(el.innerText || el.textContent || '', 60),
            visible: visible(el), readonly: (el.readOnly === true ||
              String(el.getAttribute('readonly') || '') !== ''),
            disabled: el.disabled === true, path: pathOf(el),
            rect: (() => { const r = rectOf(el); return r ? {x: Math.round(r.x), y: Math.round(r.y),
                       w: Math.round(r.width), h: Math.round(r.height)} : null; })()};
  };
  const scopeOf = (btn) => {
    const sel = opts.form_scope_selector || '';
    if (sel) { try { const sc = btn.closest(sel); if (sc) return sc; } catch (e) {} }
    let cur = btn.parentElement, depth = 0;
    const price = qall(opts.price_selector)[0];
    const qty = qall(opts.quantity_selector)[0];
    while (cur && depth < 8) {
      if ((!price || cur.contains(price)) && (!qty || cur.contains(qty))) return cur;
      cur = cur.parentElement; depth++;
    }
    return null;
  };
  const priceEl = qall(opts.price_selector)[0] || null;
  const qtyEl = qall(opts.quantity_selector)[0] || null;
  const candidates = qall(opts.submit_selector).map((el, i) => {
    const scope = scopeOf(el);
    const bound = !!(scope && ((priceEl && scope.contains(priceEl)) ||
                               (qtyEl && scope.contains(qtyEl))));
    const label = clean(el.getAttribute && el.getAttribute('aria-label'), 80);
    const text = clean(el.innerText || el.textContent || '', 80);
    const hay = (label + ' ' + text).toLowerCase();
    const want = String(opts.side || 'buy');
    const against = String(opts.opposite_side || 'sell');
    const wantHit = (opts.want_tokens || []).some(t => hay.indexOf(String(t).toLowerCase()) >= 0);
    const againstHit = (opts.against_tokens || []).some(t => hay.indexOf(String(t).toLowerCase()) >= 0);
    return {index: i, tag: el.tagName.toLowerCase(), text: text, aria: label,
            id: clean(el.id, 60), testid: clean(el.getAttribute('data-testid'), 60),
            cy: clean(el.getAttribute('data-cy'), 60),
            classes: clean(el.className, 120), type: clean(el.getAttribute('type'), 20),
            visible: visible(el), enabled: enabled(el), in_viewport: inViewport(el),
            form_bound: bound, scope_path: scope ? pathOf(scope) : '',
            side_match: wantHit, opposite_side: againstHit,
            path: pathOf(el),
            rect: (() => { const r = rectOf(el); return r ? {x: Math.round(r.x), y: Math.round(r.y),
                       w: Math.round(r.width), h: Math.round(r.height)} : null; })()};
  });
  const tabText = (name) => {
    const hit = Array.from(document.querySelectorAll('button,[role=tab],a'))
      .find(el => clean(el.innerText || el.textContent || '', 40) === name);
    if (!hit) return null;
    const s = styleOf(hit);
    return {present: true, visible: visible(hit),
            active: (hit.getAttribute && (hit.getAttribute('aria-selected') === 'true' ||
                    hit.getAttribute('data-active') === 'true')) ||
                    !!((s && (s.fontWeight === '700' || s.fontWeight === 'bold'))) ||
                    /active|selected/i.test(String(hit.className || ''))};
  };
  return {
    url_path: location.pathname,
    title: clean(document.title, 80),
    ready_state: document.readyState,
    viewport: {w: window.innerWidth || 0, h: window.innerHeight || 0},
    counts: {
      submit_matches: candidates.length,
      buttons_total: document.querySelectorAll('button,[role=button],a').length,
      inputs_total: document.querySelectorAll('input,select,textarea').length,
      forms_total: document.querySelectorAll('form').length,
      price_matches: qall(opts.price_selector).length,
      quantity_matches: qall(opts.quantity_selector).length,
      symbol_matches: qall(opts.symbol_selector).length,
    },
    fields: {
      price: valueOf(opts.price_selector),
      quantity: valueOf(opts.quantity_selector),
      symbol: valueOf(opts.symbol_selector),
      isin: valueOf(opts.isin_selector),
      side: valueOf(opts.side_selector),
    },
    tabs: {normal: tabText('عادی'), algo: tabText('هوشمند'), day: tabText('روز'),
           draft: tabText('پیش‌نویس')},
    submit_candidates: candidates,
    dom_signature: {
      submit_paths: candidates.map(c => c.path),
      submit_labels: candidates.map(c => (c.aria || c.text)).slice(0, 12),
      price_path: priceEl ? pathOf(priceEl) : '',
      quantity_path: qtyEl ? pathOf(qtyEl) : '',
      buttons_total: document.querySelectorAll('button,[role=button],a').length,
    },
  };
}"""


@dataclass
class UIOptions:
    """selectorها + انتظاراتِ کاربر. همه از تنظیماتِ پنل می‌آیند، نه از کد."""
    submit_selector: str = ""
    price_selector: str = ""
    quantity_selector: str = ""
    symbol_selector: str = ""
    isin_selector: str = ""
    side_selector: str = ""
    form_scope_selector: str = ""
    side: str = "buy"
    expected_price: Optional[float] = None
    expected_quantity: Optional[float] = None
    expected_symbol: str = ""
    expected_isin: str = ""
    #: تلورانسِ مقایسه؛ قیمت ریالی عددِ صحیح است ولی فرم ممکن است جداکننده داشته باشد.
    price_tolerance: float = 0.5
    quantity_tolerance: float = 0.0
    require_form_bound: bool = True

    def as_eval_opts(self) -> dict[str, Any]:
        want = list(SIDE_TOKENS.get(self.side, ()))
        against = list(SIDE_TOKENS.get(OPPOSITE.get(self.side, ""), ()))
        return {
            "submit_selector": self.submit_selector,
            "price_selector": self.price_selector,
            "quantity_selector": self.quantity_selector,
            "symbol_selector": self.symbol_selector,
            "isin_selector": self.isin_selector,
            "side_selector": self.side_selector,
            "form_scope_selector": self.form_scope_selector,
            "side": self.side,
            "opposite_side": OPPOSITE.get(self.side, ""),
            "want_tokens": want,
            "against_tokens": against,
        }

    def public(self) -> dict[str, Any]:
        return {"submit_selector": self.submit_selector,
                "price_selector": self.price_selector,
                "quantity_selector": self.quantity_selector,
                "symbol_selector": self.symbol_selector,
                "isin_selector": self.isin_selector,
                "side_selector": self.side_selector,
                "form_scope_selector": self.form_scope_selector,
                "side": self.side, "expected_price": self.expected_price,
                "expected_quantity": self.expected_quantity,
                "expected_symbol": self.expected_symbol,
                "expected_isin": self.expected_isin,
                "require_form_bound": bool(self.require_form_bound)}


@dataclass
class Resolution:
    """داوریِ نهایی: آیا کلیکِ امن رویِ یک دکمهٔ معین ممکن است؟"""
    ok: bool
    verdict: str
    reason: str
    button: Optional[dict[str, Any]] = None
    checks: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {"ok": bool(self.ok), "verdict": self.verdict, "reason": self.reason,
                "button": dict(self.button or {}), "checks": dict(self.checks),
                "reasons": list(self.reasons), "evidence": dict(self.evidence)}


# ── تبدیلِ متنِ فرم به عدد ────────────────────────────────────────────────────
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_amount(raw: Any) -> Optional[float]:
    """هر شکلِ نمایشیِ عدد (هزارگان، رقمِ فارسی، فاصله) → float؛ بی‌حدس."""
    s = str(raw if raw is not None else "").strip()
    if not s:
        return None
    s = s.translate(_DIGIT_MAP)
    for ch in (",", "٬", "،", " ", "\u00a0", "\u202f", "_"):
        s = s.replace(ch, "")
    s = s.replace("﷼", "").replace("ریال", "").replace("تومان", "").strip()
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return " ".join(str(value if value is not None else "").translate(_DIGIT_MAP)
                    .split()).strip().lower()


def field_text(node: Mapping[str, Any]) -> str:
    """مقدارِ خوانده‌شده: اول value (ورودی)، بعد text (عنوانِ فرم)."""
    node = node or {}
    v = str(node.get("value") or "")
    if not v.strip():
        v = str(node.get("text") or "")
    return v


def read_ui_state(driver: Any, opts: UIOptions) -> dict[str, Any]:
    """یک فراخوانیِ فقط‌خواندنی رویِ صفحه؛ هیچ نوشتن/کلیکی انجام نمی‌شود."""
    hooked = getattr(driver, "ui_state", None)
    if callable(hooked):
        return dict(hooked(opts.as_eval_opts()) or {})
    got = driver.evaluate(UI_STATE_JS, opts.as_eval_opts())
    return dict(got or {})


def judge(state: Mapping[str, Any], opts: UIOptions) -> Resolution:
    """داوریِ خالص رویِ خروجیِ read_ui_state؛ قابلِ تست بی‌مرورگر."""
    checks: dict[str, str] = {}
    reasons: list[str] = []
    st = dict(state or {})
    fields = dict(st.get("fields") or {})
    counts = dict(st.get("counts") or {})

    def note(name: str, ok: bool, detail: str = "", unknown: bool = False) -> None:
        checks[name] = "PASS" if ok else ("UNKNOWN" if unknown else "FAIL")
        if not ok and detail:
            reasons.append(detail)

    # ۱) سازۀ فرم
    price_node = dict(fields.get("price") or {})
    qty_node = dict(fields.get("quantity") or {})
    sym_node = dict(fields.get("symbol") or {})
    have_fields = bool(price_node.get("present") and qty_node.get("present"))
    note("form_fields_present", have_fields,
         "فیلدِ قیمت/تعداد در صفحه نیست" if not have_fields else "")
    visible_fields = bool(price_node.get("visible") and qty_node.get("visible"))
    note("form_fields_visible", visible_fields,
         "فیلدهایِ فرم نمایان نیستند" if have_fields and not visible_fields else "",
         unknown=not have_fields)
    unique_fields = (int(counts.get("price_matches") or 0) == 1 and
                     int(counts.get("quantity_matches") or 0) == 1)
    note("form_fields_unique", unique_fields,
         "قیمت/تعداد بیش از یک تطبیق دارد" if not unique_fields else "")

    # ۲) نماد — هر سیگنالِ تنظیم‌شده باید هم‌خوان باشد؛ یکی «درست» با دیگری
    #    «نادرست» یعنی فرم کهنه/دوبخشی است، نه تأییدِ هویت.
    sym_text = _norm(field_text(sym_node))
    want_sym = _norm(opts.expected_symbol)
    want_isin = _norm(opts.expected_isin).upper()
    form_isin = _norm(field_text(fields.get("isin") or {})).upper()
    sym_configured = bool(opts.symbol_selector and want_sym)
    isin_configured = bool(opts.isin_selector and want_isin)
    if not sym_configured and not isin_configured:
        note("symbol_verified", False, "نه نشانهٔ نماد و نه ISIN برایِ مقایسه تنظیم نشده",
             unknown=True)
    else:
        sym_ok: Optional[bool] = None
        isin_ok: Optional[bool] = None
        if sym_configured:
            sym_ok = bool(sym_text and want_sym in sym_text)
        if isin_configured:
            isin_ok = (form_isin == want_isin) if form_isin else None
        contradicted = (sym_ok is False) or (isin_ok is False)
        agreed = (sym_ok is True) or (isin_ok is True)
        note("symbol_verified", bool(agreed and not contradicted),
             "نمادِ فرم (%s) با انتظار (%s) نمی‌خواند" % (sym_text[:40], want_sym[:40])
             if contradicted else
             "هیچ سیگنالِ هویتی خوانا نبود (form symbol=%r isin=%r)"
             % (sym_text[:30], form_isin[:30]))

    # ۳) قیمت و تعدادِ خوانده‌شده (فقط مقایسه، هرگز نوشتن)
    got_price = parse_amount(field_text(price_node))
    got_qty = parse_amount(field_text(qty_node))
    if opts.expected_price is None:
        note("price_matches_expected", False, "قیمتِ موردِ انتظار تنظیم نشده", unknown=True)
    elif got_price is None:
        note("price_matches_expected", False, "قیمتِ فرم خوانا نیست", unknown=True)
    else:
        ok = abs(got_price - float(opts.expected_price)) <= float(opts.price_tolerance)
        note("price_matches_expected", ok,
             "قیمتِ فرم %s با موردِ انتظار %s نمی‌خواند" % (got_price, opts.expected_price))
    if opts.expected_quantity is None:
        note("quantity_matches_expected", False, "تعدادِ موردِ انتظار تنظیم نشده",
             unknown=True)
    elif got_qty is None:
        note("quantity_matches_expected", False, "تعدادِ فرم خوانا نیست", unknown=True)
    else:
        ok = abs(got_qty - float(opts.expected_quantity)) <= float(opts.quantity_tolerance)
        note("quantity_matches_expected", ok,
             "تعدادِ فرم %s با موردِ انتظار %s نمی‌خواند" % (got_qty, opts.expected_quantity))

    # ۴) سمت
    cands = [dict(c) for c in (st.get("submit_candidates") or [])]
    side_node = dict(fields.get("side") or {})
    side_hay = _norm(field_text(side_node))
    tokens = SIDE_TOKENS.get(opts.side, ())
    side_from_field = bool(side_hay and any(t in side_hay for t in tokens))
    side_candidates = [c for c in cands
                       if c.get("side_match") and not c.get("opposite_side")]
    note("side_verified", side_from_field or bool(side_candidates),
         "سمتِ فرم از متنِ دکمه/فیلدِ سمت قابلِ اثبات نیست")

    # ۵) دکمه: نمایان + فعال + داخلِ viewport + وابسته به همان فرم + سمتِ درست
    usable = [c for c in cands
              if c.get("visible") and c.get("enabled") and c.get("in_viewport")
              and c.get("side_match") and not c.get("opposite_side")]
    if opts.require_form_bound:
        bound = [c for c in usable if c.get("form_bound")]
        if bound:
            usable = bound
        else:
            note("button_bound_to_form", False,
                 "هیچ کاندیدایِ دکمه به همان فرمِ قیمت/تعداد وابسته نیست")
    hidden_same_name = [c for c in cands
                        if c.get("side_match") and not c.get("visible")]
    opposite_visible = [c for c in cands
                        if c.get("opposite_side") and c.get("visible") and c.get("enabled")]
    checks["submit_matches"] = str(int(counts.get("submit_matches") or len(cands)))
    checks["submit_usable"] = str(len(usable))
    checks["submit_hidden_same_name"] = str(len(hidden_same_name))
    checks["submit_opposite_visible"] = str(len(opposite_visible))

    verdict = ""
    button: Optional[dict[str, Any]] = None
    if len(usable) > 1:
        verdict = "AMBIGUOUS"
        reasons.append("%d دکمهٔ نمایانِ هم‌شرایط هست؛ انتخاب مبهم است و اقدام نمی‌شود"
                       % len(usable))
    elif len(usable) == 0:
        if opposite_visible:
            verdict = "WRONG_SIDE_ONLY"
            reasons.append("فقط دکمهٔ سمتِ مخالف نمایان/فعال است")
        elif cands:
            verdict = "NO_USABLE_BUTTON"
            reasons.append("%d کاندیدا دیده شد ولی هیچ‌کدام نمایان/فعال/داخلِ viewport "
                           "و وابسته به فرم نبود" % len(cands))
        else:
            verdict = "NO_BUTTON"
            reasons.append("دکمه‌ای با این selector در DOM نیست")
    else:
        # دقیقاً یک کاندیدایِ قابلِ استفاده: داوریِ «دکمه» مستقل از شکستِ چک‌هایِ
        # دیگر است، وگرنه یک قیمتِ نامطابقت را «مبهم» گزارش می‌کردیم.
        verdict = "UNIQUE"
        button = usable[0]

    blocking = [k for k, v in checks.items() if v == "FAIL"]
    unknown = [k for k, v in checks.items() if v == "UNKNOWN"]
    ok = verdict == "UNIQUE" and not blocking and not unknown
    if ok:
        reason = "دکمهٔ یکتا و فرمِ سازگار تأیید شد"
    elif verdict != "UNIQUE":
        reason = reasons[-1] if reasons else verdict
    else:
        reason = ("دکمه یکتا بود ولی پیش‌شرط‌ها ناکافی‌اند: "
                  + ", ".join(blocking + unknown))

    return Resolution(
        ok=ok, verdict=verdict, reason=reason[:300], button=button, checks=checks,
        reasons=reasons,
        evidence={
            "url_path": st.get("url_path"), "title": st.get("title"),
            "ready_state": st.get("ready_state"),
            "viewport": st.get("viewport"), "counts": counts,
            "form_symbol_text": sym_text[:60],
            "form_price": got_price, "form_quantity": got_qty,
            "tabs": st.get("tabs"), "dom_signature": st.get("dom_signature"),
            "candidates": [{k: c.get(k) for k in ("index", "text", "aria", "visible",
                                                  "enabled", "in_viewport", "form_bound",
                                                  "side_match", "opposite_side", "path")}
                           for c in cands][:12],
        })


def signature_changed(before: Optional[Mapping[str, Any]],
                      after: Optional[Mapping[str, Any]]) -> bool:
    """تغییرِ DOM بینِ دو خوانش (نسخهٔ تازهٔ UI یا جابه‌جاییِ فرم)."""
    a = dict(before or {})
    b = dict(after or {})
    if not a or not b:
        return True
    return (list(a.get("submit_paths") or []) != list(b.get("submit_paths") or [])
            or list(a.get("submit_labels") or []) != list(b.get("submit_labels") or [])
            or a.get("price_path") != b.get("price_path")
            or a.get("quantity_path") != b.get("quantity_path")
            or int(a.get("buttons_total") or 0) != int(b.get("buttons_total") or 0))


def same_button(before: Optional[Mapping[str, Any]],
                after: Optional[Mapping[str, Any]]) -> bool:
    """آیا دکمهٔ انتخابی همان عنصرِ قبلی است: path، برچسب، و موقعیت/اندازه."""
    a, b = dict(before or {}), dict(after or {})
    if not a or not b:
        return False
    return (str(a.get("path") or "") == str(b.get("path") or "")
            and str(a.get("aria") or a.get("text") or "") ==
            str(b.get("aria") or b.get("text") or ""))


__all__ = ["UI_STATE_JS", "UIOptions", "Resolution", "read_ui_state", "judge",
           "parse_amount", "signature_changed", "same_button", "SIDE_TOKENS",
           "OPPOSITE", "field_text"]
