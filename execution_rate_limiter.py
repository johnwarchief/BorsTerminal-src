# -*- coding: utf-8 -*-
"""execution_rate_limiter.py — شمارندهٔ نرخِ سفارشِ چندپنجره‌ای با منشأِ صریح.

چرا این ماژول جدا است: سقفِ مجازِ «تعداد اقدام» در کارگزاری هیچ‌گاه به‌صورتِ
یک عددِ قطعیِ سروری اثبات نشده است. پس هر قاعده باید بگوید از کجا آمده و
در سطحِ خودش رفتار کند. سه سطح که با هم قاطی نمی‌شوند:

  • OFFICIAL   — قاعدۀ رسمی/سروری با شاهدِ کافی (مستندِ کارگزاری یا سازمان).
  • CLIENT_CODE — عددی که فقط در کدِ کلاینت/باندلِ SPA دیده شده؛ شاهدِ سرور نیست.
  • MEASURED   — عددی که در یکِ نشستِ واقعی اندازه گرفته شده (با تاریخِ مشاهده).
  • INTERNAL   — سقفِ ایمنیِ خودِ BorsTerminal؛ هرگز به کارگزاری نسبت نمی‌شود.

قواعدِ اجرا:
  ۱) یک اقدام فقط وقتی مجاز است که همهٔ پنجره‌هایِ فعال جا داشته باشند.
  ۲) «تلاش برای ارسال» بودجه مصرف می‌کند، نه فقط «سفارشِ پذیرفته‌شده» — تا وقتی
     شمارشِ سرور معلوم نیست، حالتِ محافظه‌کارانه انتخاب شده؛ این تصمیمِ داخلی است
     و در هر قاعده با `counts` برچسب خورده.
  ۳) پس از شاهدِ throttling (۴۲۹/Retry-After/پیامِ ردِ محدودیت) قفلِ موقت
     می‌خورد؛ قفلِ موقت با اتصالِ دوباره پاک نمی‌شود.
  ۴) هیچ عددی ساخته نمی‌شود: قاعدۀ بی‌منبع واردِ فهرستِ اعمال‌شونده نمی‌شود.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional

# ── سطوحِ قاعده ──────────────────────────────────────────────────────────────
OFFICIAL = "OFFICIAL"
CLIENT_CODE = "CLIENT_CODE"
MEASURED = "MEASURED"
INTERNAL = "INTERNAL"
UNKNOWN = "UNKNOWN"

KINDS = (OFFICIAL, CLIENT_CODE, MEASURED, INTERNAL, UNKNOWN)

#: ترتیبِ اعتبار در گزارش: رسمی بالاتر از اندازه‌گیری‌شده، بالاتر از کدِ کلاینت.
KIND_RANK = {OFFICIAL: 0, MEASURED: 1, CLIENT_CODE: 2, INTERNAL: 3, UNKNOWN: 4}

COUNT_ATTEMPTS = "submission_attempt"
COUNT_ACCEPTED = "accepted_order"

#: رشته‌هایی که در کارگزاری/پیام‌هایِ فارسی نشانهٔ محدودیتِ نرخ‌اند. مشاهده در
#: کدِ کلاینت و رفتارِ صفحه؛ هر تطبیق فقط «شاهد» است نه قانونِ اثبات‌شده.
THROTTLE_MARKERS = (
    "بیش از حد مجاز", "حد مجاز", "سرعت غیرمجاز",
    "too many requests", "rate limit", "throttl", "retry-after",
)


#: کدهایِ OMS که در باندلِ d.easytrader.ir دیده شدند و نشانهٔ محدودیت/ردِ
#: نرخ‌اند. معنایِ هرکدام از باندل است، نه از سندِ سرور؛ بنابراین فقط «توقف»
#: می‌سازند، نه «تلاشِ دوباره». (مشاهده: ۲۰۲۶-۱۰-۲۳، main-XW5OZAYT.js)
OMS_THROTTLE_CODES: dict[str, str] = {
    "2080": "عدم رعایت محدودیت تعداد ارسال سفارش همزمان در ثانیه",
    "13021": "خطای ارسال بیش از 300 میلی ثانیه (معنای دقیق UNVERIFIED)",
    "8040": "احتمال معامله با خود (self-trade)",
    "13001": "احتمال معامله با خود (self-trade)",
    "13002": "احتمال معامله با خود (self-trade)",
    "1003": "خارج از محدودهٔ زمانی مجاز",
    "2022": "خارج از محدودهٔ زمانی مجاز",
    "8018": "خارج از محدودهٔ زمانی مجاز",
}


@dataclass
class RateRule:
    """یک سقفِ زمانی با منشأِ قابلِ استناد.

    `source` و `observed_at` برایِ قاعده‌ای که اعمال می‌شود الزامی‌اند؛ نبودِ
    آن‌ها یعنی قاعده فقط «اطلاع‌رسانی» است و جلویِ اقدام را نمی‌گیرد.
    """
    rule_id: str
    label: str
    kind: str
    max_events: int
    window_s: float
    source: str = ""
    observed_at: str = ""
    confidence: str = "UNVERIFIED"
    counts: str = COUNT_ATTEMPTS
    scope: str = "account"
    enforced: bool = True
    attributed_to_broker: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        self.rule_id = str(self.rule_id or "").strip()
        self.kind = str(self.kind or INTERNAL)
        self.max_events = max(1, int(self.max_events))
        self.window_s = max(0.001, float(self.window_s))
        self.scope = str(self.scope or "account")
        if self.kind not in KINDS:
            raise ValueError("unknown rule kind: %s" % self.kind)

    @property
    def enforceable(self) -> bool:
        """اعمال‌شدنی یعنی: سقف دارد + پنجره دارد + منشأ/تاریخِ مشاهده دارد."""
        return bool(self.enforced and self.source and self.observed_at)

    def public(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id, "label": self.label, "kind": self.kind,
            "max_events": self.max_events, "window_s": self.window_s,
            "source": self.source, "observed_at": self.observed_at,
            "confidence": self.confidence, "counts": self.counts,
            "scope": self.scope, "enforced": bool(self.enforced),
            "enforceable": self.enforceable,
            "attributed_to_broker": bool(self.attributed_to_broker),
            "note": self.note,
        }


@dataclass
class Decision:
    ok: bool
    retry_after_s: float = 0.0
    blocked_by: Optional[str] = None
    reason: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    kind: str = ""
    rule_source: str = ""
    attributed_to_broker: bool = False

    def public(self) -> dict[str, Any]:
        return {"ok": bool(self.ok), "retry_after_s": round(self.retry_after_s, 3),
                "blocked_by": self.blocked_by, "reason": self.reason,
                "counts": dict(self.counts), "kind": self.kind,
                "rule_source": self.rule_source,
                "attributed_to_broker": bool(self.attributed_to_broker)}


@dataclass
class PlanCheck:
    """آیا «N اقدام با فاصلهٔ M میلی‌ثانیه» با سقف‌هایِ فعال جا می‌شود؟"""
    fits: bool
    max_feasible_actions: int
    first_blocking_action: Optional[int]
    blocked_by: Optional[str]
    reasons: list[str] = field(default_factory=list)
    windows: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {"fits": bool(self.fits),
                "max_feasible_actions": self.max_feasible_actions,
                "first_blocking_action": self.first_blocking_action,
                "blocked_by": self.blocked_by, "reasons": list(self.reasons),
                "windows": dict(self.windows)}


# ── قواعدِ پیش‌فرض ───────────────────────────────────────────────────────────
#: قاعدۀ رسمیِ مقرراتی: فاصلۀ زمانیِ حداقل ۳۰۰ میلی‌ثانیه بینِ سفارش‌هایِ ارسالی.
#: منبع: تعهدنامۀ معاملات برخط + پاسخِ مدیرِ نظارتِ سازمانِ بورس (seba.ir،
#: 2023-11-12) و کدِ OMS 13021 در باندل. پس این «انتخابِ داخلی» نیست؛ کفِ اجباری
#: است و بی‌توجه به تنظیمِ کاربر پایین‌تر نمی‌آید.
OFFICIAL_SPACING = RateRule(
    "official_min_spacing", "حداقلِ فاصلۀ زمانی بینِ دو سفارش (مقرراتی)", OFFICIAL,
    1, 0.300,
    source="تعهدنامۀ معاملات برخط + پاسخ مدیر نظارت سازمان بورس (seba.ir, 2023-11-12) "
           "و کد OMS 13021",
    observed_at="2026-10-23", confidence="OFFICIAL_TEXT",
    attributed_to_broker=True,
    note="کفِ اجباری؛ فاصلۀ کاربر در پنل همیشه بالای این نگهداشته می‌شود.")

#: سقف‌هایِ داخلیِ ایمنیِ خودِ برنامه. عددِ کارگزاری نیست و به کارگزاری نسبت
#: داده نمی‌شود؛ کاربر می‌تواند هرکدام را در پنل تنظیم/خاموش کند، ولی هیچ‌وقت
#: بی‌سقف. `attributed_to_broker=False` همین را در هر گزارش تکرار می‌کند.
INTERNAL_DEFAULTS: tuple[RateRule, ...] = (
    OFFICIAL_SPACING,
    RateRule("internal_per_minute", "سقفِ داخلی در هر دقیقه", INTERNAL,
             6, 60.0, source="BorsTerminal internal safety default",
             observed_at="2026-10-23", confidence="INTERNAL_CHOICE",
             note="سقفِ سرور «اعلامی و غیرعمومی» است (ماده ۱۶ دستورالعمل برخط)؛ "
                  "این عددِ خودِ برنامه است، نه کارگزاری."),
    RateRule("internal_per_hour", "سقفِ داخلی در هر ساعت", INTERNAL,
             20, 3600.0, source="BorsTerminal internal safety default",
             observed_at="2026-10-23", confidence="INTERNAL_CHOICE"),
    RateRule("internal_per_session", "سقفِ داخلی در هر اجرایِ AutoClicker", INTERNAL,
             20, 86400.0, source="BorsTerminal internal safety default",
             observed_at="2026-10-23", confidence="INTERNAL_CHOICE",
             note="سقفِ مطلقِ تعدادِ کلیک؛ هرگز بی‌سقف."),
)

#: قاعدۀ فقط-اطلاع‌رسانی: عددی که فقط در کدِ کلاینت دیده شد. تا وقتی شاهدِ سرور
#: ندارد، «اعمال» نمی‌شود؛ در گزارشِ قوانین با منشأ و تاریخِ مشاهده می‌آید.
SPACING_RULE_ID = OFFICIAL_SPACING.rule_id

CLIENT_OBSERVED: tuple[RateRule, ...] = (
    RateRule("client_1000_per_hour", "سقفِ اعلامی در کدِ کلاینت", CLIENT_CODE,
             1000, 3600.0,
             source="باندلِ SPA (d.easytrader.ir, main-XW5OZAYT.js): پیامِ «محدودیت "
                    "1000 سفارش در ساعت» روی HTTP 429، بی‌Retry-After و بی‌کدِ سروری",
             observed_at="2026-10-23", confidence="UNVERIFIED",
             enforced=False, attributed_to_broker=False,
             note="هیچ سندِ رسمی یا کدِ OMS هم‌نام آن را تأیید نمی‌کند؛ قانونِ سرور "
                  "اعلام‌نشده است."),
)


def default_rules() -> list[RateRule]:
    return [RateRule(**{k: getattr(r, k) for k in (
        "rule_id", "label", "kind", "max_events", "window_s", "source",
        "observed_at", "confidence", "counts", "scope", "enforced",
        "attributed_to_broker", "note")}) for r in (INTERNAL_DEFAULTS + CLIENT_OBSERVED)]


def matched_oms_code(body: Any = None) -> Optional[str]:
    """کدِ OMSِ شناخته‌شده در بدنهٔ پاسخ/متنِ خطا؛ فقط از باندل، نه از سندِ سرور."""
    text = str(body if body is not None else "")
    for code in OMS_THROTTLE_CODES:
        if code in text:
            return code
    return None


def looks_like_throttle(status: Optional[int] = None, body: Any = None,
                        headers: Optional[Mapping[str, Any]] = None) -> bool:
    """شاهدِ محدودیت: ۴۲۹، Retry-After، پیامِ فارسیِ ردِ نرخ، یا کدِ OMS."""
    try:
        if status is not None and int(status) == 429:
            return True
    except (TypeError, ValueError):
        pass
    hdrs = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if hdrs.get("retry-after"):
        return True
    low = str(body if body is not None else "").lower()
    if any(m.lower() in low for m in THROTTLE_MARKERS):
        return True
    # متنِ پیامِ OMS (نه عددِ خام) شاهد است؛ عددِ تنها در بدنه با قیمت قاطی می‌شود.
    return any(m.lower() in low for m in OMS_THROTTLE_CODES.values())


class OrderRateLimiter:
    """پنجره‌هایِ لغزانِ چندگانه، مشترک بینِ همهٔ اقدام‌هایِ یک حساب.

    شمارنده‌ها درِ حافظه‌اند و فقط «تلاش‌هایِ همین نشستِ برنامه» را می‌شمارند؛
    شمارشِ سمتِ سرور دیده نمی‌شود، پس این هیچ‌وقت ادعای «مصرفِ سهمیۀ سرور»
    نمی‌کند — ادعایش فقط «سقفِ داخلیِ برنامه» است.
    """

    def __init__(self, *, rules: Optional[Iterable[RateRule]] = None,
                 clock: Callable[[], float] = time.monotonic,
                 respect_client_rules: bool = True) -> None:
        got = list(rules) if rules is not None else default_rules()
        self._rules: dict[str, RateRule] = {}
        for r in got:
            self._rules[r.rule_id] = r
        self._clock = clock
        self._respect_client_rules = bool(respect_client_rules)
        self._events: dict[tuple[str, str], deque] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self._observed: list[dict[str, Any]] = []

    # ---- ساختارِ قواعد ----
    @property
    def rules(self) -> list[RateRule]:
        with self._lock:
            return list(self._rules.values())

    def set_rule(self, rule: RateRule) -> None:
        """جایگزینیِ یک قاعده با همان rule_id؛ برایِ تنظیمِ کاربر در پنل."""
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(str(rule_id), None) is not None

    def _active(self) -> list[RateRule]:
        out = []
        for r in self._rules.values():
            if not r.enforceable:
                continue
            if r.kind == CLIENT_CODE and not self._respect_client_rules:
                continue
            out.append(r)
        return sorted(out, key=lambda x: (KIND_RANK.get(x.kind, 9), x.window_s))

    # ---- شمارش ----
    def _prune(self, key: tuple[str, str], rule: RateRule, now: float) -> deque:
        q = self._events[key]
        while q and now - q[0] >= rule.window_s:
            q.popleft()
        return q

    def usage(self, account: str = "easytrader") -> dict[str, Any]:
        now = self._clock()
        out: dict[str, Any] = {}
        with self._lock:
            for rule in sorted(self._rules.values(),
                               key=lambda x: (KIND_RANK.get(x.kind, 9), x.window_s)):
                q = self._prune((account, rule.rule_id), rule, now)
                out[rule.rule_id] = {
                    "label": rule.label, "kind": rule.kind,
                    "used": len(q), "max_events": rule.max_events,
                    "window_s": rule.window_s,
                    "remaining": max(0, rule.max_events - len(q)),
                    "enforced": bool(rule.enforceable),
                    "attributed_to_broker": bool(rule.attributed_to_broker),
                    "source": rule.source, "observed_at": rule.observed_at,
                    "confidence": rule.confidence,
                }
            blocked = self._blocked_until.get(account, 0.0)
        return {"account": account, "rules": out,
                "blocked_for_s": max(0.0, round(blocked - now, 3)),
                "observed_throttle_evidence": list(self._observed)[-6:]}

    def try_acquire(self, account: str = "easytrader", *,
                    consume: bool = True) -> Decision:
        """بودجه می‌گیرد و درِ همان فراخوانی ثبت می‌کند (اگر مجاز بود)."""
        now = self._clock()
        with self._lock:
            until = self._blocked_until.get(account)
            if until is not None and now < until:
                return Decision(False, round(until - now, 3), "throttle_lockout",
                                "پس از شاهدِ محدودیت، قفلِ موقت فعال است")
            counts: dict[str, int] = {}
            for rule in self._active():
                q = self._prune((account, rule.rule_id), rule, now)
                counts[rule.rule_id] = len(q)
                if len(q) >= rule.max_events:
                    retry = max(0.0, rule.window_s - (now - q[0])) if q else 0.0
                    return Decision(False, round(retry, 3), rule.rule_id,
                                    "%s (%s) پر است" % (rule.label, rule.kind),
                                    counts=counts, kind=rule.kind,
                                    rule_source=rule.source,
                                    attributed_to_broker=bool(
                                        rule.attributed_to_broker))
            if consume:
                for rule in self._active():
                    self._events[(account, rule.rule_id)].append(now)
            return Decision(True, 0.0, None, "", counts=counts)

    def record(self, account: str = "easytrader", *,
               at_mono_s: Optional[float] = None) -> None:
        """ثبتِ دستیِ یک تلاش (مسیرهایی که خودشان acquire نکرده‌اند).

        `at_mono_s` لحظۀ واقعیِ شلیک است، نه لحظۀ پایانِ اقدام؛ وگرنه فاصله از
        «پایانِ اجرایِ قبلی» سنجیده می‌شد و اجراهای کندتر از فاصله، همیشه
        قفلِ کاذب می‌گرفتند (سنجش ۲۰۲۶-۱۰-۲۴: اقدامِ دوم ۷۷ms بعد شمرده شد).
        """
        now = self._clock() if at_mono_s is None else float(at_mono_s)
        with self._lock:
            for rule in self._active():
                self._events[(account, rule.rule_id)].append(now)

    def block_for(self, seconds: float, account: str = "easytrader",
                  *, source: str = "manual") -> None:
        with self._lock:
            until = self._clock() + max(0.0, float(seconds))
            self._blocked_until[account] = max(until,
                                               self._blocked_until.get(account, 0.0))
            self._observed.append({"kind": "lockout", "seconds": round(max(0.0, float(seconds)), 3),
                                   "source": str(source)[:120], "at_mono": round(self._clock(), 3)})

    def observe_response(self, *, status: Optional[int] = None, body: Any = None,
                         headers: Optional[Mapping[str, Any]] = None,
                         account: str = "easytrader",
                         where: str = "") -> Optional[float]:
        """پاسخِ کارگزاری را می‌خواند؛ اگر شاهدِ throttling بود قفلِ موقت می‌زند.

        Retry-After فقط از هدرِ واقعی خوانده می‌شود؛ نبودِ آن یعنی «مدتِ
        نامعلوم» و در نتیجه قفلِ پیش‌فرضِ داخلی می‌خورد (نه عددِ اختراعیِ سرور).
        """
        if not looks_like_throttle(status=status, body=body, headers=headers):
            return None
        secs: Optional[float] = None
        for k, v in {str(x).lower(): y for x, y in (headers or {}).items()}.items():
            if k == "retry-after":
                try:
                    secs = max(0.0, float(str(v).strip()))
                except (TypeError, ValueError):
                    secs = None
        entry = {"kind": "throttle_evidence", "status": status,
                 "retry_after_s": secs, "where": str(where)[:80],
                 "at_mono": round(self._clock(), 3)}
        with self._lock:
            self._observed.append(entry)
        self.block_for(secs if secs is not None else self.backoff_default_s,
                       account, source="throttle-evidence")
        return secs

    @property
    def backoff_default_s(self) -> float:
        """مدتِ قفلِ پیش‌فرض وقتی Retry-After داده نشده — انتخابِ داخلی، نه سروری."""
        return 30.0

    def reset(self, account: str = "easytrader") -> None:
        """پاک‌سازیِ فقط برایِ تست/بازگشاییِ صریح؛ قفلِ توقفِ اضطراری را باز نمی‌کند."""
        with self._lock:
            for key in [k for k in self._events if k[0] == account]:
                self._events[key].clear()
            self._observed.clear()

    # ---- پیش‌نمایشِ برنامه ----
    def check_plan(self, *, actions: int, interval_ms: float,
                   account: str = "easytrader") -> PlanCheck:
        """با سقف‌ها می‌سنجد: آیا N اقدام با فاصلهٔ M جا می‌شود؟

        شمارشِ «مصرف‌شده» هم لحاظ می‌شود: اگر درِ این پنجره بودجه رفته باشد،
        برنامه از همین حالا باید بگوید چند اقدامِ دیگر جا است.
        """
        n = max(0, int(actions))
        step_s = max(0.0, float(interval_ms) / 1000.0)
        now = self._clock()
        reasons: list[str] = []
        windows: dict[str, Any] = {}
        worst_remaining = n
        blocking_rule: Optional[str] = None
        first_blocking: Optional[int] = None
        with self._lock:
            used = {}
            for rule in self._active():
                used[rule.rule_id] = len(self._prune((account, rule.rule_id), rule, now))
            for rule in self._active():
                u0 = used[rule.rule_id]
                # اقدامِ i-ام در زمان now + i*step_s؛ در پنجره‌اش چند اقدام قبلی‌اش جا می‌ماند؟
                capacity = rule.max_events - u0
                feasible = 0
                for i in range(n):
                    t = now + i * step_s
                    in_window = sum(1 for j in range(i)
                                    if t - (now + j * step_s) < rule.window_s)
                    if u0 + in_window + 1 <= rule.max_events:
                        feasible += 1
                    else:
                        break
                windows[rule.rule_id] = {
                    "label": rule.label, "kind": rule.kind, "used": u0,
                    "max_events": rule.max_events, "window_s": rule.window_s,
                    "feasible_from_now": feasible,
                    "initial_capacity": max(0, capacity)}
                if feasible < n:
                    reasons.append("%s (%s): با فاصلهٔ %.3fs فقط %d از %d اقدام در "
                                   "پنجرۀ %ss جا می‌شود"
                                   % (rule.label, rule.kind, step_s, feasible, n,
                                      rule.window_s))
                    if feasible < worst_remaining:
                        worst_remaining = feasible
                        blocking_rule = rule.rule_id
                        first_blocking = feasible + 1
        min_step = 0.0
        for rule in self._active():
            if rule.window_s and rule.max_events == 1:
                min_step = max(min_step, rule.window_s)
        #: فاصلۀ مقرراتی *بینِ دو اقدام* است؛ یک اقدامِ تنها فاصله‌ای ندارد.
        #: سنجش ۲۰۲۶-۱۰-۲۴: اجرایِ تک‌اقدامی با interval=0 به‌غلط «جا نمی‌شود».
        if min_step and n > 1 and step_s < min_step:
            reasons.append("کمینۀ فاصلهٔ اجباری %.3fs است (قاعدهٔ %s)" %
                           (min_step, SPACING_RULE_ID))
            if blocking_rule is None:
                blocking_rule = SPACING_RULE_ID
        return PlanCheck(fits=(not reasons), max_feasible_actions=max(0, worst_remaining),
                         first_blocking_action=first_blocking, blocked_by=blocking_rule,
                         reasons=reasons, windows=windows)

    def public(self, account: str = "easytrader") -> dict[str, Any]:
        return {"rules": [r.public() for r in sorted(
                    self._rules.values(),
                    key=lambda x: (KIND_RANK.get(x.kind, 9), x.window_s))],
                "usage": self.usage(account),
                "respect_client_rules": bool(self._respect_client_rules),
                "unknowns": [
                    "شمارشِ واقعیِ سهمیه در سمتِ سرور دیده نمی‌شود",
                    "واحدِ شمارشِ سرور (تلاش یا سفارشِ پذیرفته‌شده) UNKNOWN است",
                    "سقفِ روزانه/ساعتیِ رسمیِ کارگزاری مستند نشده است",
                ]}


__all__ = ["RateRule", "Decision", "PlanCheck", "OrderRateLimiter",
           "default_rules", "looks_like_throttle", "INTERNAL_DEFAULTS",
           "CLIENT_OBSERVED", "OFFICIAL", "CLIENT_CODE", "MEASURED", "INTERNAL",
           "UNKNOWN", "COUNT_ATTEMPTS", "COUNT_ACCEPTED", "THROTTLE_MARKERS"]
