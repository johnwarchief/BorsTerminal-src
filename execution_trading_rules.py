# -*- coding: utf-8 -*-
"""execution_trading_rules.py — پیش‌نگاشتِ قواعدِ سفارش‌گذاری، با منشأِ هر قاعده.

بند ۷ مأموریت: هیچ قاعدۀ بی‌منبع واردِ داوری نمی‌شود و هیچ چک فقط به‌خاطرِ
«همیشه PASS» سبز نمی‌ماند. هر قاعده یکی از این‌هاست:

  OFFICIAL   — مصوبه/دستورالعمل/سندِ کارگزاری با متنِ قابلِ استناد
  BROKER_DOC — صفحۀ راهنمایِ خودِ کارگزاری (رفتارِ سامانه، نه قانونِ سازمان)
  CLIENT_CODE — فقط در کدِ کلاینت/باندل دیده شده؛ شاهدِ سرور نیست
  INTERNAL   — انتخابِ ایمنیِ خودِ BorsTerminal
  UNKNOWN    — هنوز اثبات نشده؛ در گزارش همین نام می‌آید

و هر چک فقط وقتی PASS است که دادهٔ واقعی، تازه، و با منبعِ مشخص داشته باشد؛
نبودِ داده یعنی UNKNOWN با دلیل، نه ردِ خاموش و نه سبزِ نمایشی.

مهم‌ترین یافتِ این Round (باید در رابط دیده شود، نه فقط در لاگ): الحاقیۀ
معاملات الگوریتمیِ قراردادِ برخط، «ثبت سفارش با الگوریتم در زمانِ پیش‌گشایش یا
گشایشِ نمادها» را مجاز نمی‌داند. پس زمانِ هدفِ داخلِ این پنجره بی‌اقرارِ صریحِ
کاربر مسدود است. متنِ این بند از الگویِ کانون/یک کارگزاری است؛ نسخۀ امضاشدۀ
مفید در دسترس نبود — این حدِ اطمینان هم در گزارش می‌آید.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

OFFICIAL = "OFFICIAL"
BROKER_DOC = "BROKER_DOC"
CLIENT_CODE = "CLIENT_CODE"
INTERNAL = "INTERNAL"
UNKNOWN = "UNKNOWN"

#: پنجرۀ پذیرش و ساعات معاملۀ بازار اول (منبع: راهنمای مفید + کد OMS 1003/2022/8018).
ACCEPT_OPEN = "08:45"
CONTINUOUS_OPEN = "09:00"
CONTINUOUS_CLOSE = "12:30"

#: الحاقیۀ معاملات الگوریتمی — متنِ صریح دربارۀ پیش‌گشایش/گشایش.
ALGORITHMIC_CLAUSE = (
    "طبق مقررات بازار سرمایه، با استفاده از الگوریتم، ثبت سفارش‌های دوبخشی یا "
    "ثبت سفارش در زمان‌های پیش‌گشایش یا زمان‌های گشایش نمادها مجاز نیست.")

RULES: dict[str, dict[str, str]] = {
    "min_spacing_300ms": {
        "kind": OFFICIAL,
        "statement": "حداقل فاصله زمانی ۳۰۰ میلی‌ثانیه بین سفارش‌های ارسالی رعایت شود.",
        "source": "تعهدنامۀ خدمات معاملاتی برخط (کانون کارگزاران) + پاسخ مدیر نظارت "
                  "سازمان بورس، seba.ir 2023-11-12؛ و کد OMS 13021 «ارسال بیش از "
                  "۳۰۰ میلی ثانیه»",
        "observed_at": "2026-10-23",
        "confidence": "HIGH",
        "how": "کفِ اجباری در rate limiter و در اعتبارسنجیِ فاصلۀ پنل",
    },
    "oms_per_second_cap": {
        "kind": CLIENT_CODE,
        "statement": "«امکان ارسال سفارش به دلیل عدم رعایت محدودیت تعداد ارسال "
                     "سفارش همزمان در ثانیه وجود ندارد» (کد 2080).",
        "source": "باندلِ SPA d.easytrader.ir (main-XW5OZAYT.js)",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM",
        "how": "شاهدِ رد → توقفِ اجرا + قفلِ موقت؛ عددِ سقفِ ثانیه منتشر نشده ⇒ UNKNOWN",
    },
    "client_1000_per_hour": {
        "kind": CLIENT_CODE,
        "statement": "«محدودیت ۱۰۰۰ سفارش در ساعت» روی HTTP 429.",
        "source": "همان باندل، داخل createOrder(); بدون Retry-After و بدون کدِ سروریِ هم‌نام",
        "observed_at": "2026-10-23",
        "confidence": "UNVERIFIED",
        "how": "فقط اطلاع‌رسانی؛ قانونِ سرور اعلام‌نشده و اعمال نمی‌شود",
    },
    "order_count_caps": {
        "kind": OFFICIAL,
        "statement": "سقف‌های حداکثر/حداقل ثبت سفارش وجود دارد ولی «اعلامی توسط "
                     "سازمان یا بورس» و غیرعمومی است (مواد ۱۶/۲۸/۲۹/۳۰).",
        "source": "دستورالعمل اجرایی معاملات برخط، پیوست بند ۶ صورتجلسۀ ۵۹۰ (۹۸/۰۶/۰۶) "
                  "و قرارداد خدمات برخط کانون",
        "observed_at": "2026-10-23",
        "confidence": "HIGH_FOR_EXISTENCE_LOW_FOR_NUMBER",
        "how": "سقفِ BorsTerminal = لایۀ INTERNAL با برچسبِ «سقف ایمنی داخلی»",
    },
    "price_tick": {
        "kind": OFFICIAL,
        "statement": "زیر ۵۰۰۰ ریال گام ۱ ریال؛ ۵۰۰۰ ریال و بالاتر گام ۱۰ ریال.",
        "source": "قواعد گام قیمت (مصوب ۱۴۰۰) + کد OMS 2014 «قیمت سفارش باید مضربی "
                  "از ۱۰ باشد» در باندل",
        "observed_at": "2026-10-23",
        "confidence": "HIGH",
        "how": "چکِ تقسیمِ قیمت بر گام پیش از هر کلیک",
    },
    "price_band": {
        "kind": OFFICIAL,
        "statement": "دامنۀ نوسان فعلی سهام عادی ۳٪± است و قیمت سفارش خرید/فروش "
                     "نمی‌تواند از ۵۰٪ دامنه نسبت به قیمت آخرین معامله فراتر رود؛ "
                     "اگر در روز معاملاتی انجام نشده باشد این محدودیت اعمال نمی‌شود.",
        "source": "راهنمای مفید (learning.emofid.com/general-rules-for-placing-orders/) "
                  "+ اعلام رئیس سازمان بورس دربارۀ دامنۀ ۳٪ (۱۴۰۵) + کد OMS 8036/8037",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM",
        "how": "با allowed_min/allowed_max محلی و آخرینِ معامله مقایسه می‌شود؛ دادهٔ "
               "کهنه ⇒ UNKNOWN",
    },
    "order_size_thresholds": {
        "kind": OFFICIAL,
        "statement": "آستانۀ حجم خرید بر حسب قیمت: <۵۰۰ تومان→۴۰۰هزار، ۵۰۰–۱۰۰۰→۲۰۰هزار، "
                     "۱۰۰۰–۱۰۰۰۰→۱۰۰هزار، >۱۰۰۰۰→۵۰هزار سهم؛ کمینۀ ارزش خرید ۵۰۰٬۰۰۰ تومان.",
        "source": "راهنمای مفید + کد OMS 6004/8045 (در باندل دو مقدار ۱M و ۵M ریال دیده "
                  "شده؛ پاسخ رسمی کارگزاری ۵۰۰هزار تومان + کارمزد)",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM_CONFLICTING",
        "how": "عدد قابل‌تنظیم است و در تعارض، برچسبِ OWNER_RULING_REQUIRED می‌خورد",
    },
    "trading_window": {
        "kind": BROKER_DOC,
        "statement": "پذیرش سفارش ۰۸:۴۵ تا ۱۲:۳۰؛ پیش‌گشایش ۰۸:۴۵–۰۹:۰۰ و پیوسته "
                     "۰۹:۰۰–۱۲:۳۰؛ شنبه تا چهارشنبه.",
        "source": "راهنمای مفید (trading-hours، ۲۰۲۶-۰۹-۲۹) + کد OMS 1003/2022/8018 "
                  "«خارج از محدوده زمانی مجاز»",
        "observed_at": "2026-10-23",
        "confidence": "HIGH",
        "how": "درگاهِ زمانیِ زمانِ هدف؛ سفارش پیش از ۰۸:۴۵ در این OMS رد می‌شود (نه صف)",
    },
    "algorithmic_preopen": {
        "kind": OFFICIAL,
        "statement": ALGORITHMIC_CLAUSE,
        "source": "الحاقیۀ معاملات الگوریتمی به قرارداد برخط (پیوست، بند ۵) — نسخۀ "
                  "منتشرشادۀ کانون/یک کارگزاری؛ نسخۀ امضاشدۀ مفید در دسترس نبود",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM_TEXT_HIGH_INTENT",
        "how": "زمانِ هدفِ داخلِ پیش‌گشایش/گشایش بی‌اقرارِ صریحِ کاربر ⇒ BLOCKED",
    },
    "high_frequency_block": {
        "kind": BROKER_DOC,
        "statement": "«اگر با روشی به غیر از استفاده متعارف … اقدام به ارسال سفارش‌ها "
                     "با فرکانس بالا نماید، دسترسی فرد بلافاصله قطع گردیده».",
        "source": "رویه معاملات برخط — راهنمای مفید (procedure-of-online-trading، بند ۶)",
        "observed_at": "2026-10-23",
        "confidence": "HIGH",
        "how": "سقفِ داخلی + لاگِ قابلِ استناد؛ رابط هیچ «سرخطی تضمینی» وعده نمی‌دهد",
    },
    "self_trade": {
        "kind": CLIENT_CODE,
        "statement": "«امکان ارسال سفارشاتی که احتمال معامله با خود را دارند وجود ندارد» "
                     "(کد 8040/13001/13002).",
        "source": "باندلِ SPA d.easytrader.ir",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM",
        "how": "پیش از کلیک: اگر روی همان نماد سفارشِ مخالفِ هم‌قیمت باز باشد ⇒ رد",
    },
    "one_order_per_side": {
        "kind": BROKER_DOC,
        "statement": "در سفارش هوشمند: «امکان ثبت بیش از یک سفارش به طور همزمان در یک "
                     "سمت (خرید یا فروش) بر روی یک نماد وجود ندارد».",
        "source": "راهنمای مفید (how-to-place-a-smart-order-in-easytrader)",
        "observed_at": "2026-10-23",
        "confidence": "MEDIUM_SCOPE_UNKNOWN",
        "how": "هشدارِ «تکرارِ سفارشِ یکسان» در پیش‌نمایش؛ شمولش بر سفارش عادی "
               "UNVERIFIED است ⇒ ادعای رد/پذیرش نمی‌کند",
    },
    "queue_priority": {
        "kind": OFFICIAL,
        "statement": "کارگزار مکلف است سفارش را با رعایت ترتیب زمانی دریافت بلافاصله "
                     "ارسال کند؛ اولویت بر حسب نوع سفارش است. دانه‌بندی زمانی صف و هیچ "
                     "سندِ «ارسال سریع‌تر = جای بهتر» منتشر نشده است.",
        "source": "مادۀ ۵ دستورالعمل معاملۀ برخط؛ مواد ۹ و ۱۴ دستورالعمل انجام معاملات "
                  "(nibb.ir)",
        "observed_at": "2026-10-23",
        "confidence": "HIGH_FOR_PRINCIPLE_UNKNOWN_FOR_GRANULARITY",
        "how": "رابط هیچ جایگاه صفی را تضمین یا ادعا نمی‌کند",
    },
    "response_not_success": {
        "kind": OFFICIAL,
        "statement": "سفارشِ ناقضِ مقررات نباید ارسال شود و پیامِ عدمِ پذیرش با دلیل "
                     "داده می‌شود (مادۀ ۱۸)؛ HTTP 200 به‌تنهایی پذیرش نیست.",
        "source": "دستورالعمل اجرایی معاملات برخط + رفتارِ مشاهده‌شده (WAF با 200 و HTML)",
        "observed_at": "2026-10-23",
        "confidence": "HIGH",
        "how": "پذیرش فقط با بدنهٔ ساختارمند/کدپیگیری؛ HTML یا نبودِ شاهد ⇒ UNKNOWN",
    },
}


def rule_of(rule_id: str) -> dict[str, str]:
    got = dict(RULES.get(str(rule_id)) or {})
    got.setdefault("rule_id", str(rule_id))
    got["rule_id"] = str(rule_id)
    return got


# ── جدول گام قیمت ────────────────────────────────────────────────────────────
def price_tick_for(price: Optional[float]) -> Optional[float]:
    """گام قیمت از جدولِ رسمی؛ بی‌قیمت ⇒ None (نه حدس)."""
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return 1.0 if p < 5000.0 else 10.0


def size_threshold_shares(price_rial: Optional[float]) -> Optional[float]:
    """آستانۀ حجم خرید بر حسب برچسبِ قیمتی؛ تعارضِ منبع ⇒ برچسب در گزارش."""
    if price_rial is None or float(price_rial) <= 0:
        return None
    toman = float(price_rial) / 10.0
    if toman < 500:
        return 400_000.0
    if toman < 1000:
        return 200_000.0
    if toman < 10_000:
        return 100_000.0
    return 50_000.0


MIN_BUY_VALUE_TOMAN = 500_000.0


def session_window(at_ms: int, *, tz: Optional[timezone] = None) -> tuple[str, str]:
    """(وضعیت روز, پنجره) از روی ساعتِ تهرانِ محلیِ همان لحظه."""
    use = tz or timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")
    try:
        local = datetime.fromtimestamp(int(at_ms) / 1000.0, use)
    except (OSError, OverflowError, ValueError):
        return "unknown", "UNKNOWN"
    if local.weekday() in (3, 4):
        day = "closed"
    elif local.weekday() == 5:
        day = "saturday-trading"
    else:
        day = "trading-day"
    hm = local.hour * 60 + local.minute
    if hm < 8 * 60 + 45:
        win = "BEFORE_ACCEPTANCE"
    elif hm < 9 * 60:
        win = "PRE_OPEN"
    elif hm < 12 * 60 + 30:
        win = "CONTINUOUS"
    else:
        win = "AFTER_CLOSE"
    return day, win


# ── چک‌ها ────────────────────────────────────────────────────────────────────
@dataclass
class Check:
    id: str
    label: str
    status: str                 # PASS | FAIL | UNKNOWN | WARN | BLOCKED
    detail: str = ""
    rule_id: str = ""
    source: str = ""
    confidence: str = ""
    owner_ruling_required: bool = False

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _mk(cid: str, label: str, status: str, detail: str, rule_id: str,
        *, owner: bool = False) -> Check:
    r = rule_of(rule_id)
    return Check(cid, label, status, detail[:300], rule_id, r.get("source", ""),
                 r.get("confidence", ""), owner)


@dataclass
class PreflightReport:
    ok_for_arm: bool
    checks: list[Check] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def add(self, chk: Check) -> None:
        self.checks.append(chk)
        if chk.status in ("FAIL", "BLOCKED"):
            self.blockers.append("%s: %s" % (chk.label, chk.detail))
        elif chk.status == "WARN":
            self.warnings.append("%s: %s" % (chk.label, chk.detail))
        elif chk.status == "UNKNOWN":
            self.unknowns.append("%s: %s" % (chk.label, chk.detail))

    def public(self) -> dict[str, Any]:
        return {"ok_for_arm": bool(self.ok_for_arm),
                "checks": [c.public() for c in self.checks],
                "blockers": list(self.blockers), "warnings": list(self.warnings),
                "unknowns": list(self.unknowns), "facts": dict(self.facts),
                "rule_sources": {c.rule_id: rule_of(c.rule_id) for c in self.checks
                                 if c.rule_id}}


def run_preflight(*, symbol: str = "", isin: str = "", side: str = "buy",
                  price: Optional[float] = None, quantity: Optional[float] = None,
                  total_actions: int = 1, interval_ms: Optional[float] = None,
                  target_at_ms: Optional[int] = None,
                  facts: Optional[Mapping[str, Any]] = None,
                  acknowledge_preopen: bool = False,
                  max_data_age_s: float = 300.0,
                  now_ms: Optional[int] = None) -> PreflightReport:
    """پیش‌نگاشتِ کامل. هیچ چکی بی‌دادهٔ تازه PASS نمی‌شود.

    `facts` کلیدهایِ این‌ها را می‌پذیرد (هر کدام می‌تواند None باشد):
    last_price, allowed_min, allowed_max, data_as_of_ms, data_source,
    calendar_open, band_fresh_only, open_orders (فهرستِ سفارش‌هایِ باز),
    buying_power_ok, max_order_shares, min_order_value_toman.
    """
    f = dict(facts or {})
    at = int(now_ms if now_ms is not None else datetime.now().timestamp() * 1000)
    rep = PreflightReport(ok_for_arm=False)
    rep.facts = {"symbol": symbol, "isin": isin, "side": side, "price": price,
                 "quantity": quantity, "total_actions": total_actions,
                 "interval_ms": interval_ms, "target_at_ms": target_at_ms,
                 "checked_at_ms": at, "data_source": f.get("data_source") or "none"}
    # ۱) گام قیمت
    tick = price_tick_for(price)
    if tick is None:
        rep.add(_mk("price_tick", "گام قیمت", "UNKNOWN",
                    "قیمت برای محاسبۀ گام موجود نیست", "price_tick"))
    elif price is not None and abs(float(price) / tick - round(float(price) / tick)) > 1e-9:
        rep.add(_mk("price_tick", "گام قیمت", "FAIL",
                    "قیمت %s مضربی از گام %s نیست" % (price, tick), "price_tick"))
    else:
        rep.add(_mk("price_tick", "گام قیمت", "PASS",
                    "مضربی از گام %s ریال" % tick, "price_tick"))
    # ۲) محدودهٔ قیمت مجاز (فقط با دادهٔ تازه)
    last = f.get("last_price")
    lo, hi = f.get("allowed_min"), f.get("allowed_max")
    as_of = f.get("data_as_of_ms")
    if lo is None or hi is None:
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز", "UNKNOWN",
                    "allowed_min/allowed_max از منبع محلی خوانده نشد", "price_band"))
    elif as_of is None:
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز", "UNKNOWN",
                    "زمانِ دادهٔ بازه معلوم نیست؛ تازگی قابل اثبات نیست", "price_band"))
    elif (at - int(as_of)) / 1000.0 > float(max_data_age_s):
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز", "UNKNOWN",
                    "دادهٔ بازه کهنه است (سِن %ss از سقف %ss بیشتر)"
                    % (int((at - int(as_of)) / 1000.0), int(max_data_age_s)), "price_band"))
    elif price is None:
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز", "UNKNOWN",
                    "قیمت مورد انتظار تنظیم نشده", "price_band"))
    elif not (float(lo) <= float(price) <= float(hi)):
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز", "FAIL",
                    "قیمت %s خارج از [%s, %s] است" % (price, lo, hi), "price_band"))
    else:
        extra = ""
        if last and side == "buy" and float(price) > float(last) * 1.015 + 1e-9:
            extra = (" | بیش از ۵۰٪ دامنه روی آخرینِ معامله (%s) — در بازارِ عادی "
                     "ممکن است رد شود" % last)
        elif last and side == "sell" and float(price) < float(last) * 0.985 - 1e-9:
            extra = " | کمتر از ۵۰٪ دامنه روی آخرینِ معامله (%s)" % last
        rep.add(_mk("price_band", "محدودۀ قیمت مجاز",
                    "WARN" if extra else "PASS",
                    "قیمت داخل [%s, %s] است%s" % (lo, hi, extra), "price_band"))
    # ۳) سقف حجم / کمینۀ ارزش
    thr = f.get("max_order_shares") or size_threshold_shares(price)
    value_toman = None
    if price is not None and quantity is not None:
        value_toman = float(price) * float(quantity) / 10.0
    if quantity is None:
        rep.add(_mk("order_size", "سقف حجم و کمینۀ ارزش", "UNKNOWN",
                    "تعدادِ سفارش تنظیم نشده", "order_size_thresholds"))
    elif thr is not None and float(quantity) > float(thr):
        rep.add(_mk("order_size", "سقف حجم و کمینۀ ارزش", "FAIL",
                    "حجم %s از آستانۀ %s سهم بیشتر است" % (quantity, thr),
                    "order_size_thresholds"))
    elif value_toman is not None and value_toman < MIN_BUY_VALUE_TOMAN:
        rep.add(_mk("order_size", "سقف حجم و کمینۀ ارزش", "FAIL",
                    "ارزش %s تومان از کمینۀ %s تومان کمتر است"
                    % (round(value_toman), int(MIN_BUY_VALUE_TOMAN)),
                    "order_size_thresholds", owner=True))
    else:
        rep.add(_mk("order_size", "سقف حجم و کمینۀ ارزش",
                    "WARN" if f.get("max_order_shares") is None else "PASS",
                    "با آستانۀ %s سهم و کمینۀ ارزش می‌خواند؛ عددِ آستانه در منبع "
                    "مختلف است (۱M/۵M ریال) و قابل تنظیم نگه داشته شده" % thr,
                    "order_size_thresholds", owner=True))
    # ۴) توان خرید / موجودی قابل فروش
    bp = f.get("buying_power_ok")
    if bp is None:
        rep.add(_mk("buying_power", "توان خرید / موجودی قابل فروش", "UNKNOWN",
                    "منبعِ قابلِ اتکا برای حساب خوانده نشد (capabilities.balances "
                    "هنوز اثبات نشده)", "order_count_caps"))
    elif bp is False:
        rep.add(_mk("buying_power", "توان خرید / موجودی قابل فروش", "FAIL",
                    "منبع می‌گوید کفایت ندارد", "order_count_caps"))
    else:
        rep.add(_mk("buying_power", "توان خرید / موجودی قابل فروش", "PASS",
                    "از منبعِ خوانده‌شده تأیید شد", "order_count_caps"))
    # ۵) ساعت و تقویم
    day, win = session_window(target_at_ms if target_at_ms is not None else at)
    cal = f.get("calendar_open")
    if win in ("BEFORE_ACCEPTANCE", "AFTER_CLOSE"):
        rep.add(_mk("trading_window", "ساعات مجاز معامله", "FAIL",
                    "زمانِ هدف در پنجرۀ %s است؛ این OMS سفارش را رد می‌کند (نه صف)" % win,
                    "trading_window"))
    elif win == "UNKNOWN":
        rep.add(_mk("trading_window", "ساعات مجاز معامله", "UNKNOWN",
                    "ساعتِ هدف قابل تبدیل به تهران نبود", "trading_window"))
    else:
        rep.add(_mk("trading_window", "ساعات مجاز معامله", "PASS",
                    "پنجرۀ %s (روز: %s)" % (win, day), "trading_window"))
    if cal is None:
        rep.add(_mk("calendar", "تقویم معاملاتی آن روز", "UNKNOWN",
                    "باز/بسته بودنِ روزِ هدف از تقویمِ محلی اثبات نشده (مناسبتِ تعطیل "
                    "در دسترس نیست)", "trading_window"))
    elif cal is False:
        rep.add(_mk("calendar", "تقویم معاملاتی آن روز", "FAIL",
                    "روزِ هدف بسته است", "trading_window"))
    else:
        rep.add(_mk("calendar", "تقویم معاملاتی آن روز", "PASS",
                    "تقویم محلی آن روز را باز می‌داند", "trading_window"))
    # ۶) درگاهِ الگوریتمیِ پیش‌گشایش/گشایش — بندِ قرارداد
    if win == "PRE_OPEN" or (win == "CONTINUOUS" and target_at_ms is not None
                             and _within_first_minute_of_open(target_at_ms)):
        if acknowledge_preopen:
            rep.add(_mk("algorithmic_timing", "محدودیت الگوریتم در پیش‌گشایش/گشایش",
                        "WARN",
                        "کاربر با متنِ الحاقیه اقرار کرده است: «%s» — مسئولیت با "
                        "کاربر و بی‌تضمینِ نتیجه" % ALGORITHMIC_CLAUSE,
                        "algorithmic_preopen", owner=True))
        else:
            rep.add(_mk("algorithmic_timing", "محدودیت الگوریتم در پیش‌گشایش/گشایش",
                        "BLOCKED",
                        "زمانِ هدف در %s است و الحاقیۀ معاملات الگوریتمی ثبتِ "
                        "الگوریتمی سفارش در پیش‌گشایش/گشایش را مجاز نمی‌داند؛ برای "
                        "ادامه باید در پنل صریحاً اقرار شود" % win,
                        "algorithmic_preopen", owner=True))
    else:
        rep.add(_mk("algorithmic_timing", "محدودیت الگوریتم در پیش‌گشایش/گشایش",
                    "PASS", "زمانِ هدف در پنجرۀ ممنوع نیست", "algorithmic_preopen"))
    # ۷) فاصلۀ زمانی (مقرراتی)
    if interval_ms is None:
        rep.add(_mk("min_spacing", "حداقل فاصلۀ زمانی", "UNKNOWN",
                    "فاصله تنظیم نشده", "min_spacing_300ms"))
    elif float(interval_ms) < 300.0:
        rep.add(_mk("min_spacing", "حداقل فاصلۀ زمانی", "FAIL",
                    "فاصلۀ %sms از کفِ مقرراتی ۳۰۰ms کمتر است" % interval_ms,
                    "min_spacing_300ms"))
    else:
        rep.add(_mk("min_spacing", "حداقل فاصلۀ زمانی", "PASS",
                    "فاصلۀ %sms بالای کفِ ۳۰۰ms" % interval_ms, "min_spacing_300ms"))
    # ۸) تکرارِ سفارشِ یکسان / self-trade
    opens = [dict(o) for o in (f.get("open_orders") or []) if isinstance(o, Mapping)]
    if not opens and f.get("open_orders") is None:
        rep.add(_mk("open_orders", "سفارش‌های بازِ هم‌جهت", "UNKNOWN",
                    "فهرستِ سفارش‌های باز خوانده نشد؛ نه رد تأیید می‌شود نه پذیرش",
                    "one_order_per_side"))
    else:
        same = [o for o in opens if str(o.get("side", "")).lower() == str(side).lower()
                and _same_instrument(o, symbol, isin)]
        opposite = [o for o in opens
                    if str(o.get("side", "")).lower() != str(side).lower()
                    and _same_instrument(o, symbol, isin)
                    and price is not None and abs(float(o.get("price") or 0) - float(price)) < 1e-9]
        if opposite:
            rep.add(_mk("open_orders", "سفارش‌های بازِ هم‌جهت", "FAIL",
                        "سفارشِ مخالفِ هم‌قیمت باز است (احتمال معاملۀ با خود؛ "
                        "کد 8040/13001/13002)", "self_trade"))
        elif same and int(total_actions or 1) > 1:
            rep.add(_mk("open_orders", "سفارش‌های بازِ هم‌جهت", "WARN",
                        "%d سفارش هم‌جهتِ باز روی همین نماد هست؛ در «سفارش هوشمند» "
                        "بیش از یکی مجاز نیست و شمولش بر سفارش عادی اثبات نشده"
                        % len(same), "one_order_per_side", owner=True))
        else:
            rep.add(_mk("open_orders", "سفارش‌های بازِ هم‌جهت", "PASS",
                        "تعارضِ هم‌قیمتِ مخالف دیده نشد", "one_order_per_side"))
    # ۹) سقف تعدادِ اقدام
    if int(total_actions or 1) > 20:
        rep.add(_mk("action_ceiling", "سقف تعداد اقدام", "FAIL",
                    "تعدادِ خواستۀ %s از سقفِ ایمنیِ داخلیِ برنامه (۲۰) بیشتر است؛ "
                    "این عددِ خودِ برنامه است، نه کارگزاری" % total_actions,
                    "order_count_caps"))
    else:
        rep.add(_mk("action_ceiling", "سقف تعداد اقدام", "PASS",
                    "حداکثر %d سفارشِ بالقوه در این اجرا" % int(total_actions or 1),
                    "order_count_caps"))
    #: «۲۰۰ ≠ موفقیت» یک چکِ پیش‌نگاشت نیست (همیشه سبز می‌ماند)؛ قاعدۀ
    #: تفسیرِ نتیجه است و درِ جدولِ قوانینِ همان درخواست گزارش می‌شود.
    rep.ok_for_arm = not rep.blockers
    return rep


def _same_instrument(order: Mapping[str, Any], symbol: str, isin: str) -> bool:
    sym = str(order.get("symbol") or order.get("symbolName") or "").strip().lower()
    iso = str(order.get("isin") or order.get("symbolIsin") or "").strip().upper()
    return bool((sym and sym == str(symbol or "").strip().lower())
                or (iso and iso == str(isin or "").strip().upper()))


def _within_first_minute_of_open(at_ms: int) -> bool:
    tz = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")
    try:
        local = datetime.fromtimestamp(int(at_ms) / 1000.0, tz)
    except (OSError, OverflowError, ValueError):
        return False
    return local.hour == 9 and local.minute == 0


__all__ = ["RULES", "rule_of", "Check", "PreflightReport", "run_preflight",
           "price_tick_for", "size_threshold_shares", "session_window",
           "ALGORITHMIC_CLAUSE", "ACCEPT_OPEN", "CONTINUOUS_OPEN",
           "CONTINUOUS_CLOSE", "MIN_BUY_VALUE_TOMAN",
           "OFFICIAL", "BROKER_DOC", "CLIENT_CODE", "INTERNAL", "UNKNOWN"]
