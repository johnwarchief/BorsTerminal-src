# -*- coding: utf-8 -*-
"""execution_easytrader.py — آداپتورِ EasyTrader/Orbis-MTS برایِ سرخطی (مرحلۀ ۳).

مرجعِ طراحی: `docs/trading/EASYTRADER-OSS-RESEARCH-MATRIX.md` (پنج مخزن، با commit و
شاهدِ file:line) و `docs/trading/EASYTRADER-ADAPTER-HANDOFF.md` §۳ (هشت قفلِ طراحی)
و §۴-الف/ب. رأیِ مالک در ۱۴۰۵-۰۷-۲۴: سکوی هدف **EasyTrader/Orbis-MTS** است، نه
Mofid Online-Plus/Titan. دو پروتکلِ جدا با دو مدلِ احراز — پس هیچ ثابتی از این فایل
با آن سکو share نمی‌شود و شکلِ سیم فقط درِ همین فایل می‌نشیند.

چه چیزی این آداپتور *نیست*:

• درِ construction هیچ سوکتی باز نمی‌شود. ترافیک **تزریقی** است (`transport=`)؛
  نبودِ ترافیک یعنی `RefusingTransport` و `capabilities()` هم «هیچ» را اعلام
  می‌کند، نه «صفر مجاز». پس «بی‌نشست» از «آماده» درِ همان پاسخِ status جدا
  خوانده می‌شود، نه از متنِ ثابتِ رابط.
• هیچ retryی ندارد — نه درِ خود، نه درِ `HTTPAdapter`ِ زیرِ آن (`max_retries=0`).
  هر تلاشِ دوباره‌ای که سرنوشتِ تلاشِ اول را نمی‌داند می‌تواند سفارشِ دومِ *واقعی*
  بسازد؛ سه از پنج مخزن دقیقاً همین را می‌کنند (۲۵/۱۵/۴۰ کلیک، `batch_repeat`،
  retryِ ۴۰۸/۵xx).
• هیچ secret نمی‌نویسد. token فقط درِ حافظه است (`_Secret` با `repr` بی‌مقدار) و
  هرچه واردِ لاگ می‌شود از `redact()` خودِ قرارداد می‌گذرد.
• هیچ‌جا «۲xx = پذیرش» نیست. تفسیرِ پاسخ **یک** پیاده‌سازی دارد:
  `interpret_easytrader_response` — و آن هم `isSuccessful` را می‌خواند، نه
  «id داشت» (شاهدِ مخزن ۲: `id` درِ پاسخِ **ردشده** هم می‌آید).

چه چیزی *فرضیه* است: هر مسیر، هر نامِ کلید و هر عددِ enum درِ بلوکِ `WIRE_*` زیر.
منبعشان همان پنج مخزن است و هیچ‌کدام علیه کارگزاریِ امروز تأیید نشده — برایِ همین
`WIRE_HYPOTHESIS = True` است و `/api/execution/status` همان را اعلام می‌کند. تا
روزِ اولین نشستِ مجاز (D1، دستِ مالک) هیچ ادعایِ «پشتیبانیِ واقعی» نوشته نمی‌شود.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, InstrumentRef, OrderDraft, OrderMode, OrderState,
    QueueSnapshot, Resolution, SessionState, SessionStatus, Side, redact,
)

ADAPTER_NAME = "easytrader"

#: تا پیش ازِ دیدنِ یکِ پاسخِ واقعی درِ نشستِ مالک، هر ثابتِ سیم «فرضیه» است.
#: این پرچم درِ `GET /api/execution/status` هم اعلام می‌شود؛ UI چیزی را که
#: فرضیه است «تأییدشده» نشان نمی‌دهد.
WIRE_HYPOTHESIS = True


# ── ۱) ثابت‌هایِ سیم — تنها جایِ نگهداریِ شکلِ پروتکل ────────────────────────
#: میزبان. شاهد: `m-fazel/Sarkhati@c7c9487 src/easy_trader.rs:17`.
WIRE_BASE_URL = "https://api-mts.orbis.easytrader.ir"
#: ثبتِ سفارش. شاهد: `RezaMahdaviiDev/mofid@72a2e8c src/brokerages/easy/api/order.ts:119-132`.
WIRE_PATH_ORDER_CREATE = "/core/api/v2/order"
#: فهرستِ سفارش‌ها — درِ مرجع hardcode است و از Settings رد نمی‌شود
#: (`order.ts:222`). این همان یکۀ reconcile است: تنها چیزی که ابهامِ timeout را
#: تعیین تکلیف می‌کند.
WIRE_PATH_ORDER_LIST = "/core/api/order"
#: جایِ صف. شاهد: `order.ts:291-301` — `actionType=get` و شناسه درِ
#: سرِطلبِ `order-id`، نه درِ path/query.
WIRE_PATH_QUEUE = "/ms/api/MarketSheet/order-place"
#: کاندیدایِ ساعتِ فقط‌خواندنی (ماتریس §۲: `easy/api/account/server-time`).
#: آزموده نشده؛ بی‌پاسخ یعنی «ساعتِ کارگزاری در دسترس نیست»، نه «ساعتِ ما درست است».
WIRE_PATH_SERVER_TIME = "/core/api/account/server-time"

#: بدنۀ سفارش درِ این سکو درهم‌پیچ است: همه‌چیز زیرِ کلیدِ `order`
#: (`Sarkhati src/easy_trader.rs:62-80`). بدنۀِ تختِ Online-Plus/Titan عمداً
#: اینجا نمی‌آید؛ آن پروتکلِ دیگری است.
WIRE_ENVELOPE_KEY = "order"
WIRE_SIDE_BUY = 0        #: `order.ts:13-25` — جهت **عددی** است، نه رشته
WIRE_SIDE_SELL = 1
WIRE_VALIDITY_TYPE = 0
WIRE_ORDER_MODEL_TYPE = 1
WIRE_ORDER_FROM = 34      #: معنایش درِ هیچ مرجعی مستند نیست — ماتریس §۲، UNVERIFIED
WIRE_COMMISSION = 0.0012  #: دامنه/واحدش تأیید نشده — همان‌جا UNVERIFIED

WIRE_KEY_ISIN = "symbolIsin"        #: شناسۀ سفارش ISIN است، نه ins_code
WIRE_KEY_SYMBOL = "symbolName"
WIRE_KEY_PRICE = "price"
WIRE_KEY_QUANTITY = "quantity"
WIRE_KEY_SIDE = "side"
WIRE_KEY_CREATED = "createDateTime"
WIRE_KEY_ID = "id"
WIRE_KEY_SUCCESS = "isSuccessful"
WIRE_KEY_MESSAGE = "message"
WIRE_KEY_OMS_ERROR = "omsError"
WIRE_KEY_ORDERS = "orders"
WIRE_KEY_STATE = "orderStateStr"
WIRE_KEY_EXECUTED = "executedQuantity"
WIRE_HEADER_ORDER_ID = "order-id"

#: `createDateTime` ساعتِ **کلاینت** است و قالبش همان چیزی که مرورگرِ مرجع با
#: `toLocaleString('en-US')` می‌ساخت. این فقط یک برچسبِ زمانِ محلی درِ بدنۀ
#: ارسالی است — نه هویتِ سفارش و نه مدرکِ چیزی؛ تطبیقِ reconcile رویِ
#: ISIN/جهت/قیمت/حجم انجام می‌شود، نه رویِ این رشته.
#: (`strftime` با flagهایِ `-` رویِ ویندوز کار نمی‌کند، پس دستی ساخته می‌شود.)


def client_clock_label(epoch_s: float | None = None) -> str:
    """`M/D/YYYY, h:mm:ss AM/PM` — قالبِ ارسالیِ مرجع، بی‌strftimeِ غیرقابلِ‌حمل."""
    dt = datetime.fromtimestamp(epoch_s if epoch_s is not None else time.time())
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return "%d/%d/%d, %d:%02d:%02d %s" % (dt.month, dt.day, dt.year,
                                          hour, dt.minute, dt.second, ampm)


# ── ۲) ترافیکِ تزریقی ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WireResponse:
    """خام‌ترین چیزی که از کارگزاری می‌رسد: کد، سرها و متنِ بدنۀ خوانا.

    تفسیرِ این سه‌تایی جایِ دیگری جزِ `interpret_easytrader_response` انجام
    نمی‌شود — دو تفسیرِ موازی یعنی دو رأیِ متفاوت برایِ یکِ پاسخ.
    """
    status: int
    headers: Mapping[str, str]
    body: str


class TransportRefused(RuntimeError):
    """ترافیکِ زنده‌ای وصل نیست؛ هیچ درخواستی ساخته نشد."""


class TransportTimeout(RuntimeError):
    """درخواست رفت و پاسخ ندیدیم ⇒ نتیجه نامعلوم. *هرگز* retry نیست."""


class TransportNetwork(RuntimeError):
    """DNS/TLS/اتصال — مثلِ timeout: نامعلوم، و بی‌ارسالِ دوباره."""


class Transport:
    """لاکۀِ ترافیک. آداپتور فقط ازِ این می‌پرسد، پس هر آزمون بی‌شبکه سنجیدنی است."""
    name = "abstract"
    #: False یعنی «این ترافیک هیچ‌جا نمی‌رود» — آداپتور capabilities را «هیچ»
    #: اعلام می‌کند تا UI وضعیتِ واقعی را ببیند نه «Connected»ِ ظاهری.
    is_live = False

    def request(self, *, method: str, url: str, headers: Mapping[str, str],
                payload: Any = None, timeout_s: float = 7.0) -> WireResponse:
        raise NotImplementedError


class RefusingTransport(Transport):
    """پیش‌فرضِ امنِ این فایل.

    چرا ساختِ آداپتور باید ممکن باشد بی‌آنکه چیزی بیرون برود: `api/execution.py`
    درِ import اجرا می‌شود (درِ بیلدِ منجمد هم همین‌طور). اگر construction شبکه
    بزند، هر اجرایِ آفلاینِ تست یک درخواستِ واقعی به کارگزاریِ نشناخته می‌فرستد.
    """
    name = "refusing"
    is_live = False

    def request(self, **_kw) -> WireResponse:
        raise TransportRefused("ترافیکِ زنده وصل نیست (live_enabled=false)")


class RequestsTransport(Transport):
    """ترافیکِ واقعی رویِ `requests` — تنها وابستگیِ موجودِ لازم (درِ requirements.txt).

    سه قفل که این کلاس می‌گذارد و هیچ‌کدام لوکس نیست:

    • `max_retries=0`: urllib3 با retryِ خودش رویِ ۵xx/اتصال دوباره می‌فرستد؛ درِ
      درِ `/order` یعنی سفارشِ تکراریِ واقعی. مرجع‌ها این لایه را نمی‌بینند.
    • `allow_redirects=False`: یکِ 3xx رویِ POST یعنی «همان بدن را به جایِ دیگری
      بفرست» — ما آن را «نامعلوم» می‌خوانیم، نه «بازارسالِ بی‌ضرر».
    • `verify=True`: مرجعِ TypeScript اعتبارِ گواهی را خاموش می‌کرد
      (`core/browser.ts:50` — `ignoreHTTPSErrors: true`). اینجا خاموش‌کردنِ
      بررسیِ TLS هیچ مسیری ندارد.
    """
    name = "requests"
    is_live = True

    def __init__(self, *, session=None, verify: bool = True,
                 connect_timeout_s: float = 5.0) -> None:
        import requests
        from requests.adapters import HTTPAdapter

        self._s = session or requests.Session()
        self._verify = bool(verify)
        for scheme in ("https://", "http://"):
            self._s.mount(scheme, HTTPAdapter(pool_connections=4, pool_maxsize=4,
                                              max_retries=0))
        self._connect_timeout_s = float(connect_timeout_s)

    def request(self, *, method: str, url: str, headers: Mapping[str, str],
                payload: Any = None, timeout_s: float = 7.0) -> WireResponse:
        import requests
        try:
            r = self._s.request(method, url, json=payload, headers=dict(headers),
                                timeout=(self._connect_timeout_s, float(timeout_s)),
                                verify=self._verify, allow_redirects=False)
        except requests.Timeout as e:
            raise TransportTimeout(str(e)) from None
        except requests.RequestException as e:
            raise TransportNetwork(str(e)) from None
        return WireResponse(int(r.status_code), dict(r.headers), r.text or "")


# ── ۳) تفسیرِ پاسخ — یگانه مالکِ معنایِ سیم (قفل‌های ۱ و ۳) ──────────────────
@dataclass(frozen=True)
class WireVerdict:
    """نتیجهٔ داوری رویِ یکِ پاسخِ خام. `accepted=None` یعنی هنوز نمی‌دانیم."""
    accepted: bool | None
    error: ErrorCode | None
    state: OrderState
    broker_order_id: str | None
    message: str
    oms_errors: tuple[Mapping[str, str], ...]
    http_status: int
    ambiguous: bool
    detail: str = ""
    retry_after_ms: int | None = None

    @property
    def is_unknown_result(self) -> bool:
        return self.accepted is None


def _envelope(body: Any) -> tuple[Mapping[str, Any] | None, Any | None]:
    """(پاکتِ dict، فهرستِ ردیف) — یا (None, None) اگر قالبِ انتظار نبود.

    بدنه‌هایِ HTML (صفحۀِ ورودِ مجدد، فایروال، صفحه‌ای که ۲۰۰ می‌دهد ولی JSON
    نیست) اینجا همان «قالبِ ناشناخته» می‌شوند، نه «موفق».
    """
    if isinstance(body, Mapping):
        return body, None
    if isinstance(body, list):
        return None, body
    if isinstance(body, str):
        s = body.strip()
        if not s:
            return None, None
        try:
            got = json.loads(s)
        except (ValueError, TypeError):
            return None, None
        if isinstance(got, Mapping):
            return got, None
        if isinstance(got, list):
            return None, got
    return None, None


def _flag(env: Mapping[str, Any]) -> bool | None:
    """`isSuccessful` با سه مقدار: True/False/None. نبودش **False نیست** — نامعلوم است.

    مرجعِ TypeScript این را `isSuccessful !== false` می‌خواند، یعنی نبودش را
    «موفق» می‌شمرد. ما رویِ سکویی که قرار است پولِ واقعی ببرد، سکوتِ پاسخ را
    پذیرش نمی‌خوانیم؛ تعیینِ تکلیفش به `reconcile` از فهرستِ سفارش‌ها می‌ماند.
    """
    for k, v in env.items():
        if str(k).lower() != WIRE_KEY_SUCCESS.lower():
            continue
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            t = v.strip().lower()
            if t in ("1", "true", "yes", "ok"):
                return True
            if t in ("0", "false", "no"):
                return False
        return None
    return None


def _pick(env: Mapping[str, Any] | None, key: str) -> Any:
    """مقدارِ کلید، بی‌حساسیت به بزرگی/کوچکیِ حروف (سرِطلبِ JSON تضمینی ندارد)."""
    if not env:
        return None
    want = key.lower()
    for k, v in env.items():
        if str(k).lower() == want:
            return v
    return None


def _pick_any(env: Mapping[str, Any] | None, *keys: str) -> Any:
    for k in keys:
        v = _pick(env, k)
        if v is not None and v != "":
            return v
    return None


def _oms_errors(env: Mapping[str, Any] | None) -> tuple[Mapping[str, str], ...]:
    raw = _pick(env, WIRE_KEY_OMS_ERROR)
    if raw is None:
        return ()
    items = raw if isinstance(raw, list) else [raw]
    out: list[Mapping[str, str]] = []
    for it in items:
        if isinstance(it, Mapping):
            out.append({str(k): ("" if v is None else str(v)) for k, v in it.items()})
        elif it is not None:
            out.append({"error": str(it)})
    return tuple(out)


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _order_rows(resp: WireResponse) -> list[Mapping[str, Any]]:
    """ردیف‌هایِ سفارش از پاکت یا بدنۀِ تختِ فهرست."""
    env, rows = _envelope(resp.body)
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, Mapping)]
    if env is None:
        return []
    got = _pick(env, WIRE_KEY_ORDERS)
    if isinstance(got, list):
        return [r for r in got if isinstance(r, Mapping)]
    # بعضی پاکت‌ها خودِ یکِ سفارش‌اند؛ فقط وقتی بپذیریم که کلیدهایِ سفارش را
    # داشته باشند، نه هر dictِ دیگری.
    if _pick_any(env, WIRE_KEY_ID, WIRE_KEY_ISIN) is not None:
        return [env]
    return []


#: واژۀ وضعیتِ سفارش درِ این سکو مستند نشده (`orderStateStr` مبهم است؛ ماتریس §۲).
#: این جدول فقط معادل‌هایِ ASCIIِ خوانا را می‌بلعد و هر چیزِ دیگری UNKNOWN می‌ماند؛
#: متنِ خام همیشه درِ ردِّپا می‌نشیند. تعبیرِ «پر شد/رسید» از رویِ نبودِ داده
#: ممنوع است.
_STATE_WORDS: dict[str, OrderState] = {
    "pending": OrderState.PENDING, "waiting": OrderState.PENDING,
    "queued": OrderState.PENDING, "new": OrderState.PENDING,
    "open": OrderState.OPEN, "active": OrderState.OPEN,
    "partial": OrderState.PARTIAL, "partially": OrderState.PARTIAL,
    "filled": OrderState.FILLED, "executed": OrderState.FILLED,
    "complete": OrderState.FILLED, "done": OrderState.FILLED,
    "cancelled": OrderState.CANCELLED, "canceled": OrderState.CANCELLED,
    "rejected": OrderState.REJECTED, "invalid": OrderState.REJECTED,
}


def map_order_state(raw: Any, *, quantity: float | None = None,
                    executed: float | None = None) -> OrderState:
    """وضعیتِ سفارش از متنِ سرور — و اگر متنِ سرور چیزی نگفت، از عددِ پرشده.

    `executedQuantity` در برابر `quantity` تنها شاهدِ عددیِ موجود است (ماتریس §۲:
    «executedQuantity در برابر quantity به‌عنوانِ نشانهٔ اجرای جزئی»). بی‌آن‌ها
    UNKNOWN می‌مانیم، نه PENDINGِ آرایشی.
    """
    txt = _text(raw)
    if txt:
        hit = _STATE_WORDS.get(txt.lower())
        if hit is not None:
            return hit
    if quantity is not None and quantity > 0 and executed is not None:
        if executed >= quantity:
            return OrderState.FILLED
        if executed > 0:
            return OrderState.PARTIAL
    return OrderState.UNKNOWN


def _retry_after_ms(resp_headers: Mapping[str, str]) -> int | None:
    for h in ("retry-after", "Retry-After", "RETRY-AFTER"):
        v = resp_headers.get(h) if isinstance(resp_headers, Mapping) else None
        if v:
            try:
                return int(float(str(v).strip()) * 1000)
            except (ValueError, TypeError):
                return None
    return None


#: نگاشتِ کدِ OMS ← ErrorCodeِ خودی. مقادیرِ سمتِ چپ ازِ مخزنِ مرجع خوانده شده
#: (`INVALID_PRICE` درِ پیشوندِ `message` و درِ `omsError.code` — ماتریس §۲) و
#: دامنةِ کاملشان تأیید نشده، پس هر کدِ ناآشنا به `BROKER_REJECTED` می‌رسد:
#: «رد شد و نمی‌دانیم چرا» صادق‌تر ازِ حدسِ «قیمتِ بد بود» است.
_OMS_CODE_MAP = {
    "INVALID_PRICE": ErrorCode.INVALID_PRICE,
    "PRICE": ErrorCode.INVALID_PRICE,
    "OUT_OF_RANGE": ErrorCode.INVALID_PRICE,
    "INVALID_QUANTITY": ErrorCode.INVALID_QUANTITY,
    "QUANTITY": ErrorCode.INVALID_QUANTITY,
    "Q_MIN": ErrorCode.INVALID_QUANTITY,
    "AUTH_FAILED": ErrorCode.AUTH_FAILED,
    "SESSION_EXPIRED": ErrorCode.SESSION_EXPIRED,
    "NOT_ORDERABLE": ErrorCode.NOT_ORDERABLE,
}


def _oms_error_code(errs: tuple[Mapping[str, str], ...],
                    msg: str | None) -> ErrorCode:
    """یک کدِ عملیاتی ازِ پاکتِ OMS — و اگر نبود، ازِ خودِ HTTP."""
    for e in errs:
        for k in ("code", "name"):
            hit = _OMS_CODE_MAP.get(str(e.get(k, "")).strip().upper())
            if hit is not None:
                return hit
    if msg:
        head = msg.split("::")[0].strip().upper()
        hit = _OMS_CODE_MAP.get(head)
        if hit is not None:
            return hit
    return ErrorCode.BROKER_REJECTED


def interpret_easytrader_response(status: int, body: Any, *,
                                  where: str = "order",
                                  headers: Mapping[str, str] | None = None) -> WireVerdict:
    """یگانه ترجمۀ «پاسخِ HTTP کارگزاری» ← «معنایِ عملیاتی».

    قواعد، عیناً قفل‌هایِ §۳ دست‌نویسِ تحویل (و هر سطرِ زیر با شاهد از ماتریس):

      ۴۰۱                → SESSION_EXPIRED — نشست باطل شد، بی‌retry، بی‌ارسالِ دوباره
      ۴۰۳                → AUTH_FAILED     — از اول اجازه‌ای نبود، پایانی
      ۴۰۰/۴۰۴/۴۰۵/۴۲۲/۴xx → BROKER_REJECTED — پایانی؛ پیام و کدِ OMS منتقل می‌شود
      ۴۲۹                → RATE_LIMITED     — پایانی + Retry-After (درِ پنج مخزن نبود)
      ۴۰۸                → TIMEOUT          — نامعلوم؛ فقط reconcile
      ۵xx                → NETWORK_ERROR    — نامعلوم؛ سرور شاید پذیرفته باشد
      ۳xx                → UNKNOWN_RESULT   — رویِ POST بازارسالِ بدن را نمی‌پذیریم
      ۲xx و flag=true و بی omsError → پذیرش، و status از متنِ پاسخ
      ۲xx و flag=false              → رد، **حتی با `id`** (spec مرجع :107-120)
      ۲xx و flag نباشد              → UNKNOWN_RESULT — سکوتِ پاسخ پذیرش نیست
      ۲xx و بدنۀ غیرقابل‌خواندن     → UNKNOWN_RESULT — HTML/صفحۀِ ورودِ مجدد
    """
    code = int(status)
    hdrs = headers or {}
    env, _rows = _envelope(body)
    msg = _text(_pick(env, WIRE_KEY_MESSAGE)) if env else None
    errs = _oms_errors(env)
    oid = _text(_pick_any(env, WIRE_KEY_ID, "orderId")) if env else None
    head = (msg or "")[:180]
    after = _retry_after_ms(hdrs)

    if code == 401:
        return WireVerdict(False, ErrorCode.SESSION_EXPIRED, OrderState.UNKNOWN, None,
                           head, errs, code, False, "http 401: نشست باطل شد", after)
    if code == 403:
        return WireVerdict(False, ErrorCode.AUTH_FAILED, OrderState.UNKNOWN, None,
                           head, errs, code, False, "http 403: اجازه‌ای نبود", after)
    if code == 429:
        return WireVerdict(False, ErrorCode.RATE_LIMITED, OrderState.UNKNOWN, None,
                           head, errs, code, False, "http 429: محدودیتِ نرخ", after)
    if code == 408:
        return WireVerdict(None, ErrorCode.TIMEOUT, OrderState.UNKNOWN, None, head, errs,
                           code, True, "http 408: مهلتِ سرور — نتیجه نامعلوم", after)
    if code >= 500:
        return WireVerdict(None, ErrorCode.NETWORK_ERROR, OrderState.UNKNOWN, None,
                           head, errs, code, True,
                           "http %d: سرور پاسخِ معنادار نداد — نتیجه نامعلوم" % code, after)
    if 300 <= code < 400:
        return WireVerdict(None, ErrorCode.UNKNOWN_RESULT, OrderState.UNKNOWN, None,
                           head, errs, code, True,
                           "http %d: بازارسال — رویِ سفارش قبول نمی‌کنیم" % code, after)
    if 400 <= code < 500:
        return WireVerdict(False, _oms_error_code(errs, msg),
                           OrderState.REJECTED, None,
                           head, errs, code, False, "http %d: ردِ پایانی" % code, after)
    if not (200 <= code < 300):
        return WireVerdict(None, ErrorCode.UNKNOWN_RESULT, OrderState.UNKNOWN, None,
                           head, errs, code, True, "http %d: کدِ بی‌معنا" % code, after)

    # ۲xx — و همین‌جا است که «۲xx هیچ حکمی نیست» اجرا می‌شود.
    if env is None:
        return WireVerdict(None, ErrorCode.UNKNOWN_RESULT, OrderState.UNKNOWN, None,
                           head, errs, code, True,
                           "%s: پاسخِ ۲xx بی‌قالبِ قابلِ خواندن" % where, after)
    flag = _flag(env)
    qty = _num(_pick(env, WIRE_KEY_QUANTITY))
    executed = _num(_pick(env, WIRE_KEY_EXECUTED))
    state = map_order_state(_pick_any(env, WIRE_KEY_STATE), quantity=qty,
                            executed=executed)
    if flag is None:
        return WireVerdict(None, ErrorCode.UNKNOWN_RESULT, state, oid, head, errs,
                           code, True,
                           "%s: `isSuccessful` درِ پاسخ نبود — پذیرش ادعا نمی‌شود" % where,
                           after)
    if flag is False or errs:
        # ردشده ممکن است `id` داشته باشد؛ آن id «سفارشِ زنده» نیست و نگه نمی‌ماند.
        return WireVerdict(False, _oms_error_code(errs, msg),
                           OrderState.REJECTED, None,
                           head, errs, code, False, "%s: ردِ OMS" % where, after)
    return WireVerdict(True, None, state, oid, head, errs, code, False,
                       "%s: پذیرفته شد" % where, after)


# ── ۴) بدنۀِ سفارش — یگانه جایِ ساختِ payload ───────────────────────────────
def easytrader_payload(draft: OrderDraft) -> dict[str, Any]:
    """مدلِ داخلی ← بدنۀِ `{"order":{…}}`.

    هیچ مقداری اینجا حدس نمی‌شود: ISIN از `InstrumentRef` می‌آید و نبودش یعنی
    `submit_order` هرگز تا اینجا نمی‌رسد (`orderable()` جلوی‌اش را می‌گیرد).
    """
    inner = {
        WIRE_KEY_ISIN: draft.instrument.isin,
        WIRE_KEY_SYMBOL: draft.instrument.symbol,
        WIRE_KEY_PRICE: draft.price,
        WIRE_KEY_QUANTITY: draft.quantity,
        WIRE_KEY_SIDE: WIRE_SIDE_BUY if draft.side is Side.BUY else WIRE_SIDE_SELL,
        "validityType": WIRE_VALIDITY_TYPE,
        "orderModelType": WIRE_ORDER_MODEL_TYPE,
        "orderFrom": WIRE_ORDER_FROM,
        "commission": WIRE_COMMISSION,
        WIRE_KEY_CREATED: client_clock_label(),
    }
    return {WIRE_ENVELOPE_KEY: inner}


def _code_from_reason(reason: str) -> ErrorCode:
    head = reason.split(":")[-1].upper()
    mapping = {"INVALID_PRICE": ErrorCode.INVALID_PRICE,
               "INVALID_QUANTITY": ErrorCode.INVALID_QUANTITY,
               "INVALID_EXECUTION_ID": ErrorCode.INVALID_EXECUTION_ID,
               "PLACE": ErrorCode.UNSUPPORTED}
    return mapping.get(head, ErrorCode.NOT_ORDERABLE)


#: تواناییِ اعلامیِ این پروتکل از رویِ پنج مخزن. `cancel` درِ هیچ مرجعی پیاده نشده
#: بود و `balances` هیچ‌جا دیده نشد ⇒ صریح False، تا «بی‌داده» از «صفر» جدا بماند
#: (§۱۶ و §۱۸ دستورِ کار).
PROTOCOL_CAPS = Capabilities(place=True, list_orders=True, order_state=True,
                             queue_position=True, cancel=False, best_bid_ask=False,
                             balances=False)
NO_CAPS = Capabilities(place=False, list_orders=False, order_state=False,
                       queue_position=False, cancel=False, best_bid_ask=False,
                       balances=False)


@dataclass(frozen=True)
class Timeouts:
    """timeoutِ صریح رویِ هر عملیات — مرجع‌ها بی‌timeout بودند (`easy_trader.rs:112`)."""
    order_post_s: float = 7.0
    read_s: float = 7.0
    probe_s: float = 4.0


@dataclass
class _Intent:
    """آنچه *قصدِ* ارسال داشتیم، پیش ازِ دیدنِ پاسخ.

    چرا پیش ازِ POST ثبت می‌شود: اگر ack گم شود، تنها راهِ فهمیدنِ «سفارش ساخته
    شد یا نه» تطبیقِ همین قصد با فهرستِ سرور است. بعدِ timeout از پاسخِ ما چیزی
    نمی‌ماند، پس این تنها شاهدِ باقی‌مانده است.
    """
    execution_id: str
    isin: str | None
    symbol: str
    side: int
    price: float | None
    quantity: float | None
    dispatched_at: float
    mode: OrderMode = OrderMode.SAFE
    ack_lost: bool = False
    broker_order_id: str | None = None
    reported_ambiguous: bool = False
    attempts: int = 0

    def matches(self, isin: str | None, side: float | None, price: float | None,
                quantity: float | None) -> bool:
        """تطبیقِ سختِ قصد با ردیفِ سرور — بی‌«نزدیک‌ترین»."""
        if (self.isin or None) != (isin or None):
            return False
        if side is None or float(self.side) != float(side):
            return False
        if self.price is None or price is None or abs(float(self.price) - float(price)) > 1e-9:
            return False
        if self.quantity is None or quantity is None:
            return False
        return abs(float(self.quantity) - float(quantity)) < 1e-9


class _Secret:
    """نگهدارندهٔ token درِ حافظه، با `repr` بی‌مقدار.

    چرا این‌قدر محافظه‌کار: پنج مخزنِ مرجع credential را یا درِ JSONِ صفحه‌اختی
    یا درِ لاگ یا درِ تاریخچۀ git می‌ریختند (شاملِ یکِ HARِ ۵٫۳MB کامیت‌شده و
    رمزهایِ کامیت‌شده درِ `web_scraping.py@b3f8eab`). هر `repr()`/لاگِ تصادفیِ
    این شیء نباید token را بیرون بدهد.
    """
    __slots__ = ("_value",)

    def __init__(self, value: Any = None) -> None:
        self._value = (str(value).strip() if value else None) or None

    def __bool__(self) -> bool:
        return self._value is not None

    def expose(self) -> str | None:
        return self._value

    def __repr__(self) -> str:
        return "<redacted>"

    def __str__(self) -> str:
        return "<redacted>"


class EasyTraderAdapter(BrokerAdapter):
    """آداپتورِ EasyTrader/Orbis-MTS، با ترافیکِ تزریقی و بی‌هیچ ادعایِ تأیید."""
    name = ADAPTER_NAME

    def __init__(self, *, transport: Transport | None = None,
                 token: Any = None, base_url: str | None = None,
                 instruments: Iterable[InstrumentRef] = (),
                 capabilities: Capabilities | None = None,
                 timeouts: Timeouts | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._transport = transport or RefusingTransport()
        self._token = token if isinstance(token, _Secret) else _Secret(token)
        self.base_url = (base_url or WIRE_BASE_URL).rstrip("/")
        self._caps_override = capabilities
        self.timeouts = timeouts or Timeouts()
        self._clock = clock
        self._by_symbol: dict[str, InstrumentRef] = {i.symbol: i for i in instruments}
        #: وضعیتِ نشست **کشی** است: `GET /api/execution/status` هرگز نباید یکِ
        #: درخواستِ بیرونی بزند. تازه‌اش فقط `authenticate()`/`probe()` می‌کند.
        self._session = SessionStatus(
            SessionState.UNKNOWN if self._token else SessionState.DISCONNECTED)
        self._intents: dict[str, _Intent] = {}
        #: ردیف‌هایی که به یکِ قصدِ محلی وصل شدند — تا یکِ ردیفِ سرور دو بار
        #: «پیدا شد» گزارش نشود.
        self._claimed_rows: dict[str, str] = {}
        #: آنچه از فهرستِ سرور *دیده‌ایم*، به‌علاوهٔ پذیرش‌هایِ قطعیِ خودِ ما.
        #: درِ حالتِ timeout چیزی اینجا نیست — و همین تفاوتِ ما با بدل است.
        self.server_orders: dict[str, ExecutionRecord] = {}
        self.queue_by_order: dict[str, QueueSnapshot] = {}
        #: فقطِ برچسبِ عملیات، نه بدن و نه سر — برایِ اثباتِ «چیزی بیرون نرفت».
        self.wire_calls: list[str] = []
        #: ردِّپایِ ترافیک، همه از `redact()` گذشته.
        self.redacted_log: list[dict] = []
        self.last_verdict: WireVerdict | None = None

    # ---- هویت و وضعیت -----------------------------------------------------
    def __repr__(self) -> str:
        return "<EasyTraderAdapter live=%s transport=%s session=%s>" % (
            self.live, self._transport.name, self._session.state.value)

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def live(self) -> bool:
        """هم ترافیک وصل باشد و هم tokenِ مالک باشد. یکی نبود ⇒ «هیچ»."""
        return bool(getattr(self._transport, "is_live", False)) and bool(self._token)

    def set_token(self, value: Any) -> None:
        """token را درِ حافظه می‌گذارد؛ هیچ‌جا نوشته/لاگ نمی‌شود و `repr` ندارد."""
        self._token = _Secret(value)
        self._session = SessionStatus(SessionState.UNKNOWN if self._token
                                      else SessionState.DISCONNECTED,
                                      checked_at=self._iso())

    def has_token(self) -> bool:
        """فقط «هست یا نیست» — مقدار هیچ‌مسیری بیرون نمی‌رود."""
        return bool(self._token)

    def clear_token(self) -> None:
        self._token = _Secret(None)
        self._session = SessionStatus(SessionState.DISCONNECTED, checked_at=self._iso())

    def capabilities(self) -> Capabilities:
        if self._caps_override is not None:
            return self._caps_override
        return PROTOCOL_CAPS if self.live else NO_CAPS

    def session_status(self) -> SessionStatus:
        return self._session

    def set_session(self, status: SessionStatus) -> None:
        self._session = status

    # ---- ۵) ترافیک ---------------------------------------------------------
    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        tok = self._token.expose() or ""
        # نرمال‌سازیِ bearer یک‌بار درِ لبه (الگویِ پذیرفته‌شده از مخزن ۱)
        auth = ""
        if tok:
            auth = tok if tok.lower().startswith(("bearer ", "basic ")) else "Bearer " + tok
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if auth:
            h["Authorization"] = auth
        if extra:
            h.update({str(k): str(v) for k, v in extra.items()})
        return h

    def _log_exchange(self, entry: Mapping[str, Any]) -> None:
        self.redacted_log.append(dict(redact(entry)))
        if len(self.redacted_log) > 200:
            del self.redacted_log[:-200]

    def _call(self, method: str, path: str, *, tag: str, timeout_s: float,
              payload: Any = None, headers: Mapping[str, str] | None = None) -> WireResponse:
        self.wire_calls.append("%s:%s" % (tag, method))
        if not self.live:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "اتصالِ زنده وصل نیست — هیچ درخواستی ساخته نشد")
        url = self.base_url + path
        hdrs = self._headers(headers)
        t0 = time.monotonic()
        try:
            resp = self._transport.request(method=method, url=url, headers=hdrs,
                                           payload=payload, timeout_s=timeout_s)
        except TransportRefused:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "ترافیکِ زنده وصل نیست — هیچ درخواستی ساخته نشد") from None
        except TransportTimeout as e:
            self._log_exchange({"tag": tag, "method": method, "url": url,
                                "error": "timeout",
                                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1)})
            raise BrokerError(ErrorCode.TIMEOUT,
                              "%s: پاسخ نیامد — نتیجه نامعلوم؛ ارسالِ دوباره ممنوع" % tag) from None
        except TransportNetwork as e:
            raise BrokerError(ErrorCode.NETWORK_ERROR,
                              "%s: خطایِ شبکه/اتصال — نتیجه نامعلوم" % tag) from None
        self._log_exchange({"tag": tag, "method": method, "url": url,
                            "status": resp.status,
                            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
                            "authorization": hdrs.get("Authorization"),
                            "body_head": (resp.body or "")[:120]})
        return resp

    # ---- ۶) نشست -----------------------------------------------------------
    def authenticate(self) -> SessionStatus:
        """کم‌خطرترین پرسیدنی که وجودِ نشستِ معتبر را ثابت می‌کند: فهرستِ سفارش‌ها.

        درِ `/order` برایِ آزمونِ اتصال صدا زده نمی‌شود (قفلِ ۷: هیچ سفارشی به‌عنوانِ
        ping — کاری که مخزن ۱ و ۲ می‌کردند). ۴۰۱ و ۴۰۳ دو حالتِ *جدا* می‌گیرند.
        """
        self.wire_calls.append("authenticate")
        if not self.live:
            self._session = SessionStatus(SessionState.DISCONNECTED,
                                          checked_at=self._iso())
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "نشستِ زنده ممکن نیست: transport یا token نیست")
        try:
            resp = self._call("GET", WIRE_PATH_ORDER_LIST, tag="authenticate",
                              timeout_s=self.timeouts.probe_s)
        except BrokerError as e:
            state = {ErrorCode.SESSION_EXPIRED: SessionState.EXPIRED,
                     ErrorCode.AUTH_FAILED: SessionState.AUTH_FAILED}.get(
                         e.code, SessionState.ERROR)
            self._session = SessionStatus(state, checked_at=self._iso())
            raise
        if not (200 <= resp.status < 300):
            v = interpret_easytrader_response(resp.status, resp.body, where="session",
                                              headers=resp.headers)
            state = {ErrorCode.SESSION_EXPIRED: SessionState.EXPIRED,
                     ErrorCode.AUTH_FAILED: SessionState.AUTH_FAILED}.get(
                         v.error, SessionState.ERROR)
            self._session = SessionStatus(state, checked_at=self._iso())
            raise BrokerError(v.error or ErrorCode.UNKNOWN_RESULT, v.detail,
                              broker_message=v.message)
        env, _ = _envelope(resp.body)
        label = _text(_pick_any(env, "accountCode", "clientCode", "code"))
        self._ingest_rows(resp)
        self._session = SessionStatus(SessionState.CONNECTED,
                                      label or "easytrader-session", self._iso())
        return self._session

    # ---- ۷) ابزار ----------------------------------------------------------
    def add_instrument(self, ref: InstrumentRef) -> None:
        self._by_symbol[ref.symbol] = ref

    def resolve_instrument(self, symbol: str) -> InstrumentRef:
        """هیچ «نزدیک‌ترین» اینجا نیست (§۷-ب: fallback به ISINِ «زر» ممنوع)."""
        self.wire_calls.append("resolve:%s" % symbol)
        ref = self._by_symbol.get(symbol)
        if ref is None:
            return InstrumentRef(symbol=symbol, resolution=Resolution.UNRESOLVED)
        return ref

    def validate_order(self, draft: OrderDraft) -> str | None:
        structural = draft.sanity()
        if structural:
            return structural
        ok, reason = draft.instrument.orderable()
        if not ok:
            return reason
        if not self.capabilities().place:
            return "UNSUPPORTED:place"
        return None

    # ---- ۸) ارسال ----------------------------------------------------------
    def submit_order(self, draft: OrderDraft) -> ExecutionRecord:
        """یکِ POST، یکِ قصد، بی‌retry. نتیجهٔ نامعلوم ⇒ `BrokerError` نامعلوم."""
        if draft.execution_id in self._intents:
            raise BrokerError(ErrorCode.DUPLICATE_GUARD,
                              "%s پیش‌تر ارسال شده — تکرارِ همان execution_id "
                              "سفارشِ دوم می‌سازد، نه ترمیمِ اولی" % draft.execution_id)
        bad = self.validate_order(draft)
        if bad:
            raise BrokerError(_code_from_reason(bad), bad)

        intent = _Intent(execution_id=draft.execution_id, isin=draft.instrument.isin,
                         symbol=draft.instrument.symbol,
                         side=WIRE_SIDE_BUY if draft.side is Side.BUY else WIRE_SIDE_SELL,
                         price=draft.price, quantity=draft.quantity,
                         dispatched_at=self._clock(), mode=draft.mode)
        self._intents[draft.execution_id] = intent

        payload = easytrader_payload(draft)
        rec = self._new_record(draft)
        rec.scheduled_at = intent.dispatched_at
        rec.actual_send_at = self._clock()
        rec.status = ExecutionStatus.DISPATCHED
        rec.attempts = 1
        intent.attempts = 1

        try:
            resp = self._call("POST", WIRE_PATH_ORDER_CREATE, payload=payload,
                              tag="submit", timeout_s=self.timeouts.order_post_s)
        except BrokerError as e:
            # نامعلوم یعنی «شاید سرور پذیرفته و ما ندیده‌ایم» — تنها واکنشِ مجاز
            # reconcile است، پس قصد باید بماند و ack_lost علامت بخورد.
            if e.is_unknown_result:
                intent.ack_lost = True
            raise

        v = interpret_easytrader_response(resp.status, resp.body, where="submit",
                                          headers=resp.headers)
        self.last_verdict = v
        rec.rtt_ms = self._ms_since(rec.actual_send_at)
        rec.response_at = self._clock()

        if v.accepted is None:
            self._apply_session_verdict(v)
            intent.ack_lost = True
            rec.status = ExecutionStatus.UNKNOWN_RESULT
            rec.error_code = v.error or ErrorCode.UNKNOWN_RESULT
            rec.error_detail = v.detail
            rec.note(v.detail)
            raise BrokerError(rec.error_code, v.detail, broker_message=v.message)
        if v.accepted is not True:
            self._apply_session_verdict(v)
            rec.status = ExecutionStatus.FAILED
            rec.error_code = v.error or ErrorCode.BROKER_REJECTED
            rec.error_detail = v.detail
            rec.order_state = OrderState.REJECTED
            rec.note("%s: %s" % (v.detail, str(redact(v.message))[:80]))
            raise BrokerError(rec.error_code, v.detail, broker_message=v.message)

        rec.status = ExecutionStatus.ACKNOWLEDGED
        rec.broker_order_id = v.broker_order_id
        rec.order_state = v.state
        rec.note(v.detail)
        if v.broker_order_id:
            intent.broker_order_id = v.broker_order_id
            self._claimed_rows[v.broker_order_id] = draft.execution_id
            self.server_orders[v.broker_order_id] = rec
        return rec

    def _new_record(self, draft: OrderDraft) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=draft.execution_id, broker=self.name,
            account=self._session.account_label, symbol=draft.instrument.symbol,
            isin=draft.instrument.isin, side=draft.side, price=draft.price,
            quantity=draft.quantity, mode=draft.mode, clock_offset_ms=0.0)

    def _apply_session_verdict(self, v: WireVerdict) -> None:
        """۴۰۱ = «نشستی که داشتی باطل شد»، ۴۰۳ = «از اول اجازه‌ای نبود» (قفلِ ۳).

        بی‌این آداپتور پسِ یکِ ۴۰۱ هم CONNECTED نشان می‌داد و UI دروغ می‌شنید؛
        و بدتر، هر فراخوانِ بعدی همان tokenِ مرده را می‌فرستاد. خطایِ شبکه/timeout
        عمداً نشست را عوض نمی‌کند: «پاسخ نیامد» مدرکِ بی‌اعتباریِ نشست نیست.
        """
        if v.error is ErrorCode.SESSION_EXPIRED:
            self._session = SessionStatus(SessionState.EXPIRED,
                                         self._session.account_label, self._iso())
        elif v.error is ErrorCode.AUTH_FAILED:
            self._session = SessionStatus(SessionState.AUTH_FAILED, None, self._iso())

    # ---- ۹) خواندنِ وضعیت / reconcile --------------------------------------
    def get_orders(self) -> list[ExecutionRecord]:
        """فهرستِ سفارش‌ها — یکۀِ رفعِ ابهامِ timeout (قفلِ ۲).

        بی‌خواندنِ موفقِ این فهرست هیچ وضعیتی عوض نمی‌شود. اگر پرسیدنی خطا داد،
        `BrokerError` بالا می‌آید و رکورد درِ UNKNOWN می‌ماند: «نیافتیم» فقط وقتی
        مدرکِ نبودن است که فهرست را *دیدیم*.
        """
        if not self.capabilities().list_orders:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "easytrader: list_orders درِ این تنظیم در دسترس نیست")
        resp = self._call("GET", WIRE_PATH_ORDER_LIST, tag="get_orders",
                          timeout_s=self.timeouts.read_s)
        if not (200 <= resp.status < 300):
            v = interpret_easytrader_response(resp.status, resp.body, where="order list",
                                              headers=resp.headers)
            self._apply_session_verdict(v)
            raise BrokerError(v.error or ErrorCode.UNKNOWN_RESULT, v.detail,
                              broker_message=v.message)
        rows = self._ingest_rows(resp)
        return list(self.server_orders.values()) + self._ambiguous_records(rows)

    def _ingest_rows(self, resp: WireResponse) -> list[Mapping[str, Any]]:
        """ردیف‌هایِ سرور ← رکورد، با تطبیقِ دو-گذریِ بی‌ادعا.

        گذرِ اول شناسه‌هایِ شناخته‌شده را وصل می‌کند. گذرِ دوم یکِ قصدِ بی‌شناسه
        را *فقط* وقتی به یکِ ردیف می‌چسباند که جفت‌شان یک‌به‌یک باشد: دو ردیفِ
        همسان برایِ یکِ قصد ⇒ هیچ ادعایی، چون «اولی را بردار» حدس است نه شاهد.
        """
        rows = _order_rows(resp)
        for row in rows:
            self._claim_known(row)
        for it in [i for i in self._intents.values() if i.broker_order_id is None]:
            cands = [r for r in rows if self._row_matches(it, r)
                     and self._row_owner(r) is None]
            if len(cands) == 1:
                self._bind(it, cands[0])
        for row in rows:
            rec = self._record_from_row(row)
            if rec.broker_order_id:
                self.server_orders[rec.broker_order_id] = rec
        return rows

    @staticmethod
    def _row_id(row: Mapping[str, Any]) -> str | None:
        return _text(_pick_any(row, WIRE_KEY_ID, "orderId"))

    def _row_owner(self, row: Mapping[str, Any]) -> str | None:
        rid = self._row_id(row)
        return self._claimed_rows.get(rid) if rid else None

    @staticmethod
    def _row_matches(it: "_Intent", row: Mapping[str, Any]) -> bool:
        return it.matches(_text(_pick_any(row, WIRE_KEY_ISIN)),
                          _num(_pick_any(row, WIRE_KEY_SIDE)),
                          _num(_pick_any(row, WIRE_KEY_PRICE)),
                          _num(_pick_any(row, WIRE_KEY_QUANTITY)))

    def _claim_known(self, row: Mapping[str, Any]) -> None:
        rid = self._row_id(row)
        if not rid or rid in self._claimed_rows:
            return
        for eid, it in self._intents.items():
            if it.broker_order_id == rid:
                self._claimed_rows[rid] = eid
                return

    def _bind(self, it: "_Intent", row: Mapping[str, Any]) -> None:
        rid = self._row_id(row)
        if rid:
            it.broker_order_id = rid
            self._claimed_rows[rid] = it.execution_id

    def _record_from_row(self, row: Mapping[str, Any]) -> ExecutionRecord:
        isin = _text(_pick_any(row, WIRE_KEY_ISIN))
        qty = _num(_pick_any(row, WIRE_KEY_QUANTITY))
        filled = _num(_pick_any(row, WIRE_KEY_EXECUTED))
        raw_id = self._row_id(row)
        side_raw = _num(_pick_any(row, WIRE_KEY_SIDE))
        price = _num(_pick_any(row, WIRE_KEY_PRICE))
        eid = self._row_owner(row)
        intent = self._intents.get(eid) if eid else None
        side = Side.BUY if side_raw is None else (
            Side.SELL if side_raw == WIRE_SIDE_SELL else Side.BUY)
        rec = ExecutionRecord(
            execution_id=eid or "", broker=self.name,
            account=self._session.account_label,
            symbol=_text(_pick_any(row, WIRE_KEY_SYMBOL)) or (isin or ""),
            isin=isin, side=side, price=price, quantity=qty,
            mode=intent.mode if intent is not None else OrderMode.SAFE,
            status=ExecutionStatus.RECONCILED if eid else ExecutionStatus.UNKNOWN_RESULT,
            broker_order_id=raw_id,
            order_state=map_order_state(_pick_any(row, WIRE_KEY_STATE),
                                        quantity=qty, executed=filled),
            filled_quantity=filled)
        if side_raw is None:
            rec.note("side درِ ردیف نبود — جهتِ نمایشی رویِ خرید ماند (تأیید نشده)")
        if intent is None:
            rec.note("این ردیف به هیچ قصدِ محلی وصل نشد — بی‌execution_id")
        return rec

    def _ambiguous_records(self, rows: list[Mapping[str, Any]]) -> list[ExecutionRecord]:
        """قصدی که ack-اش گم شده و ردیفِ *تنهای* برایش پیدا نشده است.

        «ردیفی نبود» با «دو ردیفِ یکسان بود» یکی نیست. اگر فهرستِ سرور خوانده شد
        و هیچ ردیفی با قصدِ ما نمی‌خواند، نبودن **مدرک است** و `reconcile` حق دارد
        به FAILED برسد. اما وقتی دو یا چند ردیف می‌خوانند و نمی‌توان گفت کدام
        مالِ ماست، نه پذیرش ادعا می‌شود و نه «وجود ندارد»: یکِ رکوردِ مبهم با
        `status=UNKNOWN_RESULT` و `order_state=UNKNOWN` برمی‌گردد.
        """
        out = []
        for it in self._intents.values():
            if not it.ack_lost or it.broker_order_id is not None or it.reported_ambiguous:
                continue
            cands = [r for r in rows
                     if it.matches(_text(_pick_any(r, WIRE_KEY_ISIN)),
                                   _num(_pick_any(r, WIRE_KEY_SIDE)),
                                   _num(_pick_any(r, WIRE_KEY_PRICE)),
                                   _num(_pick_any(r, WIRE_KEY_QUANTITY)))]
            if len(cands) < 2:
                continue          # صفر = نبودِ مدرکِ وجود؛ یک = همان که claim شد
            it.reported_ambiguous = True
            rec = ExecutionRecord(
                execution_id=it.execution_id, broker=self.name,
                account=self._session.account_label, symbol=it.symbol, isin=it.isin,
                side=Side.BUY if it.side == WIRE_SIDE_BUY else Side.SELL,
                price=it.price, quantity=it.quantity, mode=it.mode,
                status=ExecutionStatus.UNKNOWN_RESULT,
                error_code=ErrorCode.UNKNOWN_RESULT,
                order_state=OrderState.UNKNOWN)
            rec.note("ack lost and the broker list is ambiguous (%d candidate rows) "
                     "— نتیجه نامعلوم می‌ماند و ارسالِ دوباره ممنوع" % len(cands))
            out.append(rec)
        return out

    def get_order(self, broker_order_id: str) -> ExecutionRecord | None:
        """وضعیتِ یکِ سفارش. مسیرِ تک‌سفارش درِ این پروتکل مستند نشده، پس ازِ همان
        فهرستِ معتبر خوانده می‌شود — نه از حدسِ محلی."""
        if not self.capabilities().order_state:
            raise BrokerError(ErrorCode.UNSUPPORTED, "easytrader: order_state unsupported")
        self.get_orders()
        return self.server_orders.get(str(broker_order_id))

    # ---- ۱۰) صف — فقط نمایش، با واحدِ نامعلوم (قفلِ ۸) ─────────────────────
    def get_queue_position(self, broker_order_id: str) -> QueueSnapshot | None:
        if not self.capabilities().queue_position:
            return None                    # بی‌داده، نه صفر
        resp = self._call("GET", WIRE_PATH_QUEUE + "?actionType=get",
                          headers={WIRE_HEADER_ORDER_ID: str(broker_order_id)},
                          tag="queue", timeout_s=self.timeouts.read_s)
        if not (200 <= resp.status < 300):
            return None
        env, rows = _envelope(resp.body)
        places: Any = None
        if env is not None:
            places = _pick(env, "orderPlaces")
        elif isinstance(rows, list):
            places = rows
        if not isinstance(places, list) or not places:
            return None                    # پاسخِ خالی = UNKNOWN، نه «اولِ صف»
        hit: Mapping[str, Any] | None = None
        for p in places:
            if isinstance(p, Mapping) and _text(_pick(p, "orderId")) == str(broker_order_id):
                hit = p
                break
        if hit is None and isinstance(places[0], Mapping):
            hit = places[0]
        if hit is None:
            return None
        pos = _num(_pick(hit, "orderPlace"))
        vol = _num(_pick(hit, "volumeAhead"))
        snap = QueueSnapshot(
            position=int(pos) if pos is not None else None, volume_ahead=vol,
            as_of=self._iso(),
            #: واحدِ `volumeAhead` درِ هیچ مرجعی تعریف نشده (ماتریس §۲) — پس هرگز
            #: به «اولِ صف» یا «حجمِ جلوتر» تعبیر نمی‌شود؛ فقط خام نشان داده می‌شود.
            source="easytrader:orderPlace/volumeAhead (واحد UNVERIFIED)")
        self.queue_by_order[str(broker_order_id)] = snap
        return snap

    # ---- ۱۱) چیزهایی که این پروتکل نمی‌دهد ---------------------------------
    def cancel_order(self, broker_order_id: str) -> bool:
        """لغو درِ هیچ مرجعِ بازبینی‌شده‌ای پیاده نشده بود (§۷-الف) ⇒ ادعا نمی‌شود."""
        raise BrokerError(ErrorCode.UNSUPPORTED,
                          "easytrader: مسیرِ لغو درِ هیچ منبعِ بازبینی‌شده‌ای مستند "
                          "نشده — هیچ درخواستی ساخته نشد")

    def get_balances(self):
        return None            # «نمی‌دانیم» ≠ «صفر»

    # ---- ۱۲) سنجشِ فقط‌خواندنی و ساعت --------------------------------------
    def probe(self) -> dict[str, Any]:
        """آزمونِ اتصالِ کم‌خطر: پرسیدنی‌هایِ فقط‌خواندنی، صفرِ POST.

        زمانِ هر مرحله جدا اندازه می‌شود (بندِ ۴-د مأموریت) و هیچ سفارشی برایِ
        سنجشِ RTT نمی‌رود. بی‌نشست، هیچ درخواستی نمی‌زند و همان را اعلام می‌کند.
        """
        out: dict[str, Any] = {"attempted": True, "live": self.live,
                               "read_only": True, "transport": self._transport.name,
                               "wire_hypothesis": WIRE_HYPOTHESIS,
                               "order_endpoint_touched": False,
                               "response_ms": None, "orders_seen": len(self.server_orders),
                               "clock": None}
        if not self.live:
            out.update({"ok": False, "state": self._session.state.value,
                        "error_code": ErrorCode.UNSUPPORTED.value,
                        "detail": "transport یا token در دسترس نیست — بی‌هیچ درخواست"})
            return out
        t0 = time.monotonic()
        submits_before = sum(1 for w in self.wire_calls if str(w).startswith("submit:"))
        try:
            st = self.authenticate()
            out.update({"ok": True, "state": st.state.value,
                        "orders_seen": len(self.server_orders)})
        except BrokerError as e:
            out.update({"ok": False, "state": self._session.state.value,
                        "error_code": e.code.value, "detail": str(redact(e.detail))})
        out["response_ms"] = round((time.monotonic() - t0) * 1000, 1)
        out["clock"] = self.server_clock()
        # آداپتور هرگز به درِ سفارش برایِ سنجشِ سرعت نمی‌زند — این خطِ سرخِ ماست
        # (مخزن ۱ و ۲ دقیقاً همین را می‌کردند، درِ ۲ با سفارشِ واقعی).
        out["order_endpoint_touched"] = sum(
            1 for w in self.wire_calls if str(w).startswith("submit:")) > submits_before
        return out

    def server_clock(self) -> dict[str, Any] | None:
        """ساعتِ کارگزاری، اگر مسیرش پاسخ داد. بی‌پاسخ ⇒ None، نه «ساعت درست است».

        قفلِ ۷ از ماتریس: منبعِ ساعت و اختلافش با ساعتِ سیستم *ثبت* می‌شود؛ هیچ
        وقتِ جابه‌جاییِ بی‌صدا انجام نمی‌شود.
        """
        if not self.live:
            return None
        try:
            resp = self._call("GET", WIRE_PATH_SERVER_TIME, tag="server_clock",
                              timeout_s=self.timeouts.probe_s)
        except BrokerError:
            return None
        if not (200 <= resp.status < 300):
            return None
        env, _ = _envelope(resp.body)
        txt = _text(_pick_any(env, "serverTime", "time", "now", "dateTime"))
        if not txt:
            return None
        return {"source": "broker", "broker_time": txt,
                "system_time": datetime.now().isoformat(timespec="seconds"),
                "delta_ms": None, "verified": False,
                "detail": "قالبِ ساعتِ کارگزاری تأیید نشده — فقط ثبتِ خام"}

    # ---- کمکی -------------------------------------------------------------
    def _iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _ms_since(self, epoch_s: float | None) -> float | None:
        if epoch_s is None:
            return None
        return round((self._clock() - epoch_s) * 1000.0, 1)


__all__ = [
    "ADAPTER_NAME", "WIRE_HYPOTHESIS", "EasyTraderAdapter", "WireResponse",
    "WireVerdict", "Transport", "RefusingTransport", "RequestsTransport",
    "TransportRefused", "TransportTimeout", "TransportNetwork", "Timeouts",
    "PROTOCOL_CAPS", "NO_CAPS", "interpret_easytrader_response",
    "easytrader_payload", "map_order_state", "client_clock_label",
]
