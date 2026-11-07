# -*- coding: utf-8 -*-
"""dev/broker_connect_v1120.py — گاردِ تنظیمِ اتصال، حالتِ فقط‌خواندنی، و شاهدِ نشست.

چرا این گارد هست: درِ v1.0.93 دو چیز برایِ کاربرِ واقعی ممکن نبود — (۱) انتخاب
آداپتورِ مفید، چون تنها کلید `BORS_EXECUTION_ADAPTER` بود و بیلدِ منجمدِ دسکتاپ هیچ
env ای از کاربر نمی‌گیرد؛ (۲) تأییدِ نشست، چون `token` فقط با `BORS_EXECUTION_LIVE=1`
پذیرفته می‌شد و همان کلید *ارسالِ* سفارش را هم باز می‌کرد. پس «نشستِ واقعی» همیشه
UNKNOWN می‌ماند و رابط «نشستِ بدل باز است» نشان می‌داد.

همه بی‌هیچ سوکتی. ثابت‌شدنی‌ها:
  الف) تنظیمِ دیسک آداپتور را انتخاب می‌کند و env مقدم است؛
  ب) هیچ تنظیمِ دیسکی «ارسالِ سفارش» را باز نمی‌کند (گیتِ نوشتن فقط env)؛
  پ) درِ فقط‌خواندنی خواندن بله و POSTِ سفارش نه، و `capabilities.place` false؛
  ت) «متصل» فقط باِ پرسشِ واقعی گفته می‌شود و *کدام مسیر* ثابتش کرده ثبت می‌شود؛
  ث) ۴۰۱ هرگز «متصل» نمی‌شود؛ ۴۰۴ رویِ مسیرِ حدسی هم شواهدِ دیدہ‌شدہ را باطل نمی‌کند؛
  ج) پاسخ‌هایِ config و portfolio هیچ مقدارِ محرمانه‌ای ندارند و «بی‌منبع» را
     «صفر» یا «ردیفِ خالی» نشان نمی‌دهند.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_settings as ES                                        # noqa: E402
from api import execution as EX                                        # noqa: E402
from execution_contract import BrokerError, ErrorCode, SessionState    # noqa: E402
from execution_easytrader import (EasyTraderAdapter, WireResponse,     # noqa: E402
                                  WIRE_BASE_URL, WIRE_PATH_ORDER_CREATE,
                                  WIRE_PATH_ORDER_LIST, WIRE_PATH_SERVER_TIME)

SECRET = "super-secret-token-value-for-guard-only"
#: همان «مسیرِ دیدہ‌شدہ» که درِ ماتریس capture عمومی است — از ثابتِ خودِ ماژول برداشته
#: می‌شود تا گارد به عددِ دستِ‌نویسِ تاریخ‌خورده گره نخورد.
SERVER_TIME = WIRE_PATH_SERVER_TIME
PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + what + (("  | " + str(got)[:150]) if got else ""))
    else:
        FAIL += 1
        print("  FAIL " + what + (("  | " + str(got)[:150]) if got else ""))
    return bool(cond)


class PathTransport:
    """ترافیکِ بدیلِ مسیربه‌مسیر. `is_live=True` — ولی هیچ سوکتی نمی‌زند."""
    name = "paths"
    is_live = True

    def __init__(self, table):
        self.table = dict(table)
        self.calls: list[str] = []

    def request(self, *, method, url, headers=None, payload=None, timeout_s=7.0):
        path = url.replace(WIRE_BASE_URL, "")
        self.calls.append("%s %s" % (method, path))
        for prefix, (status, body) in self.table.items():
            if path.startswith(prefix):
                return WireResponse(status, {},
                                    json.dumps(body) if body is not None else "")
        return WireResponse(404, {},
                            json.dumps({"isSuccessful": False, "message": "no path"}))


def build(table, *, writes=False, token=SECRET):
    return EasyTraderAdapter(transport=PathTransport(table), token=token,
                             writes_allowed=writes)


def draft_for(eid):
    """بدنه‌ای که به `submit_order` برسد؛ اینجا هیچ POSTی نباید ازِ آن بیرون رود.

    ابزار کاملِ سفارش‌پذیر است (`resolution=EXACT` + isin + broker_instrument)، وگرنه
    بندِ ۸ گارد با «NOT_ORDERABLE» رد می‌شود و کنترلِ منفیِ خودِ گارد کور می‌گردد.
    """
    from execution_contract import InstrumentRef, OrderDraft, Resolution, Side

    ins = InstrumentRef(symbol="فولاد", ins_code="17001", isin="IRO1FOO00001",
                        broker_instrument="IRO1FOO00001", resolution=Resolution.EXACT)
    return OrderDraft(execution_id=eid, instrument=ins, side=Side.BUY,
                      price=12610, quantity=1000)


print("dev/broker_connect_v1120 — تنظیمِ اتصال، فقط‌خواندنی، شاهدِ نشست")

# ── ۱) تنظیم: انتخابِ آداپتور از خودِ برنامه، با مقدم بودنِ env ──────────────
ck(ES._normalise("adapter", "mofid") == "easytrader"
   and ES._normalise("adapter", "EASYTRADER") == "easytrader",
   "۱) نامِ کارگزاری و بزرگ/کوچکی به یک آداپتور می‌رسند")
for bad_key, bad_val in (("token", "x"), ("secret", "x"), ("adapter", "binance"),
                         ("read_only", "maybe")):
    try:
        ES._normalise(bad_key, bad_val)
        ck(False, "کلید/مقدارِ ناشناخته باید رد شود", "%s=%s" % (bad_key, bad_val))
    except ValueError:
        ck(True, "۱) ردِ %s=%s (فقط دو کلیدِ غیرمحرمانه)" % (bad_key, bad_val))
ck(EX._configured_adapter({"adapter": "easytrader"}) == "easytrader"
   and EX._configured_adapter({}) == "mock",
   "۱) env نبود ⇒ تنظیمِ ذخیره‌شده؛ هیچ‌کدام نبود ⇒ mock")
os.environ["BORS_EXECUTION_ADAPTER"] = "mock"
try:
    ck(EX._configured_adapter({"adapter": "easytrader"}) == "mock",
       "۱) env بر تنظیمِ دیسک مقدم است")
finally:
    os.environ.pop("BORS_EXECUTION_ADAPTER", None)

# ── ۲) گیتِ نوشتن فقط از env؛ تنظیمِ دیسک هرگز باز نمی‌کند ──────────────────
# پایگاهِ داده‌ایِ موقت: گارد هرگز `user.dbِ` واقعی را نمی‌نویسد، و نتیجه به
# تنظیمِ ذخیره‌شده رویِ ماشینِ خواننده وابسته نمی‌ماند.
_tmp = tempfile.mkdtemp(prefix="bors_broker_guard_")
_tmp_db = os.path.join(_tmp, "settings.db")
for _k in (ES.ENV_ADAPTER, ES.ENV_LIVE):
    os.environ.pop(_k, None)
ES.set_value("adapter", "easytrader", db_path=_tmp_db)
ES.set_value("read_only", "1", db_path=_tmp_db)
disk = ES.read(_tmp_db)
ck(disk["adapter"] == "easytrader" and disk["source"] == "settings"
   and disk["read_only"] is True and disk["writes_allowed"] is False
   and disk["traffic_allowed"] is True,
   "۲) تنظیمِ دیسک: آداپتور و ترافیکِ خواندن روشن، «ارسالِ سفارش» خاموش",
   "src=%s ro=%s writes=%s traffic=%s" % (disk["source"], disk["read_only"],
                                          disk["writes_allowed"], disk["traffic_allowed"]))
os.environ[ES.ENV_LIVE] = "1"
try:
    ck(ES.read(_tmp_db)["writes_allowed"] is True,
       "۲) گیتِ نوشتن باِ BORS_EXECUTION_LIVE روشن می‌شود (آداپتور ازِ دیسک)")
    os.environ[ES.ENV_ADAPTER] = "mock"
    w = ES.read(_tmp_db)
    ck(w["writes_allowed"] is False and w["source"] == "env",
       "۲) آداپتورِ mock ⇒ حتی با envِ نوشتن چیزی نوشته نمی‌شود",
       "src=%s writes=%s" % (w["source"], w["writes_allowed"]))
finally:
    os.environ.pop(ES.ENV_LIVE, None)
    os.environ.pop(ES.ENV_ADAPTER, None)
    shutil.rmtree(_tmp, ignore_errors=True)

# ── ۳) حالتِ فقط‌خواندنی: خواندن بله، ارسال نه ──────────────────────────────
ORDERS_OK = {WIRE_PATH_ORDER_LIST: (200, {"orders": []})}
a = build(ORDERS_OK, writes=False)
ck(a.live is True and a.writes_allowed is False and a.read_only_mode is True,
   "۳) ترافیک وصل است ولی نوشتن آزاد نیست",
   "live=%s writes=%s ro=%s" % (a.live, a.writes_allowed, a.read_only_mode))
caps_ro = a.capabilities()
ck(caps_ro.place is False and caps_ro.list_orders is True
   and caps_ro.order_state is True,
   "۳) capabilities درِ فقط‌خواندنی «ارسال» را false می‌دهد (UI همین را می‌خواند)",
   str(caps_ro)[:120])
try:
    a.submit_order(draft_for("EX-RO"))
    ck(False, "۳) ارسالِ سفارش درِ فقط‌خواندنی باید رد شود")
except BrokerError as e:
    ck(e.code is ErrorCode.UNSUPPORTED and "فقط‌خواندنی" in str(e.detail),
       "۳) ردِ ارسال باِ دلیلِ همان حالت", str(e.code.value))
ck(not [w for w in a.wire_calls if str(w).startswith("submit:POST")],
   "۳) هیچ POST سفارشی ازِ حالتِ فقط‌خواندنی بیرون نرفت", str(a.wire_calls)[:130])
st = a.authenticate()
ck(st.state is SessionState.CONNECTED and a.session_proven() is True,
   "۳) نشست درِ فقط‌خواندنی هم *واقعاً* تأیید می‌شود", st.state.value)
ck(a.session_proof.get("path") == WIRE_PATH_ORDER_LIST
   and a.session_proof.get("hypothesis") is True,
   "۳) شاهد ثبت می‌شود: کدام مسیر، و اینکہ مسیرش درِ سندِ رسمی نیست",
   str(a.session_proof)[:140])

# ── ۴) مسیرِ حدسی ۴۰۴ ⇒ شاهد ازِ مسیرِ دیدہ‌شدہ ─────────────────────────────
t2 = PathTransport({SERVER_TIME: (200, {"diff": 45, "serverTimestamp": 1767700032066})})
b = EasyTraderAdapter(transport=t2, token=SECRET, writes_allowed=False)
st2 = b.authenticate()
ck(st2.state is SessionState.CONNECTED,
   "۴) ۴۰۴ رویِ «فهرستِ سفارش» نشست را باطل اعلام نمی‌کند",
   str(t2.calls)[:150])
ck(b.session_proof.get("kind") == "observed-read-only"
   and str(b.session_proof.get("path") or "").startswith(SERVER_TIME),
   "۴) اتصال ازِ مسیرِ مشاهده‌شده ثابت شد، نه ازِ کدِ شخصِ ثالث",
   str(b.session_proof)[:150])

# ── ۵) کنترلِ منفی: ۴۰۱ هیچ‌وقت «متصل» نمی‌شود ─────────────────────────────
t3 = PathTransport({SERVER_TIME: (401, {"isSuccessful": False, "message": "expired"}),
                    WIRE_PATH_ORDER_LIST: (401, {"isSuccessful": False,
                                                 "message": "expired"})})
c = EasyTraderAdapter(transport=t3, token=SECRET, writes_allowed=False)
try:
    c.authenticate()
    ck(False, "۵) ۴۰۱ باید خطایِ نشست بدهد")
except BrokerError as e:
    ck(e.code is ErrorCode.SESSION_EXPIRED and c.session_proven() is False,
       "۵) ۴۰۱ ⇒ نشستِ باطل؛ نه اتصال، نه ادعایِ شاهد",
       "%s proven=%s" % (e.code.value, c.session_proven()))
ck(not c.session_proof, "۵) بدونِ پرسشِ موفق هیچ شاهدی ثبت نمی‌شود",
   str(c.session_proof)[:90])

# ── ۶) نشانیِ بی‌تأیید «متصل» نیست؛ set_token تنها «هست» را می‌گوید ──────────
d = build(ORDERS_OK, writes=False)
d.clear_token()
ck(d.has_token() is False and d.session_proven() is False,
   "۶) بی‌نشست: نه توکن، نه ادعایِ اتصال")
d.set_token(SECRET)
ck(d.has_token() is True and d.session_proven() is False
   and d.session_status().state is SessionState.UNKNOWN,
   "۶) فقط ریختنِ نشانی ⇒ UNKNOWN، هرگز CONNECTED", str(d.session_status())[:110])
d.set_token("completely-different-token")
ck(d.session_proven() is False,
   "۶) نشانیِ تازه تأییدِ پیشین را می‌اندازد (مقایسه باِ identity، نه مقدار)")

# ── ۷) دروازۀ HTTP: منشأِ نشست، config بدونِ سر، portfolio بدونِ عددِ بدل ─────
sd = EX._session_dict()
ck(sd.get("origin") in ("mock", "easytrader") and "proven" in sd and "verified_by" in sd,
   "۷) نشست ازِ خودِ پاسخ منشأ و «اثبات‌شدن» دارد", str(sd)[:130])
cfg = EX.get_config()
ck(cfg["status"] == "success" and cfg["applies_on_restart"] is True
   and cfg["secrets_stored"] is False
   and set(cfg["stored"]) == {"adapter", "read_only", "source", "updated_at"},
   "۷) config فقط دو کلیدِ غیرمحرمانه را نگه می‌دارد و restart لازم را می‌گوید",
   str(cfg["stored"])[:120])
stat = EX.get_status()
ck("connection_config" in stat and "read_only" in stat and "traffic_allowed" in stat,
   "۷) status هر سه گیت را جدا اعلام می‌کند",
   str({k: stat.get(k) for k in ("adapter", "live_enabled", "read_only",
                                 "traffic_allowed")})[:150])
pf = EX.get_portfolio()
ck(pf["status"] in ("blocked", "unverified_session", "no_source", "success")
   and pf["rows"] is None,
   "۷) پرتفوی بی‌منبع «ردیفِ خالی» یا «صفر» نمی‌سازد", str(pf)[:130])
blob = json.dumps({"cfg": cfg, "pf": pf}, ensure_ascii=False)
ck(SECRET not in blob and "authorization" not in blob.lower(),
   "۷) هیچ پاسخِ config/portfolio نشانیِ نشست را بیرون نمی‌دهد")

# ── ۸) کنترلِ منفیِ خودِ گارد: اگر transport را «نوشتن‌پذیر» بسازیم، POST می‌رود
t4 = PathTransport({WIRE_PATH_ORDER_LIST: (200, {"orders": []}),
                    WIRE_PATH_ORDER_CREATE: (200, {"isSuccessful": True, "id": "BR-9",
                                                   "message": "ok",
                                                   "orderStateStr": "Waiting",
                                                   "executedQuantity": 0})})
e = EasyTraderAdapter(transport=t4, token=SECRET, writes_allowed=True)
try:
    e.authenticate()
    e.add_instrument(draft_for("EX-W").instrument)
    rec = e.submit_order(draft_for("EX-W"))
    ok_post = any(c0.startswith("submit:POST") for c0 in e.wire_calls)
except BrokerError as err:
    ok_post = False
    rec = err
ck(ok_post,
   "۸) سنسور گارد زنده است: باِ گیتِ نوشتنِ باز، POST می‌رود (پس بندِ ۳ تهی نبود)",
   str(getattr(rec, "broker_order_id", rec))[:110])

# ── ۹) حالتِ «فقط‌خواندنی روشن، بی‌نشست» — همان چیزی که سنجشِ زندهٔ ۱۸ اکتبر لو داد ─
# گاردِ بالا این حالت را ندید، چون فقط `mock` و `live` را ساخت. واقعیتِ کاربر:
# تنظیم را ذخیره و restart می‌کند، ولی هنوز واردِ پنجره نشده. آنجا پیامِ درست
# «نشستِ شما کم است» است، نه «BORS_EXECUTION_LIVE=1 لازم است» — چیزی که کاربرِ
# فقط‌خواندنی هرگز نباید بکند.
from execution_easytrader import RefusingTransport                    # noqa: E402
import execution_connect as EXC                                       # noqa: E402

#: ترانسپورتِ «زنده» ولی بی‌نشست — همان حالتی که کاربر بعدِ restart دارد. هیچ
#: سوکتی نمی‌زند: `live` بی‌token false است و `_call` پیش ازِ درخواست می‌شکند.
_ro = EasyTraderAdapter(transport=PathTransport({}), token=None, writes_allowed=False)
_saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.READ_ONLY_REQUESTED,
         EX.TRAFFIC_ALLOWED, EX.DRY_RUN, EX._ACTIVE_ADAPTER, EX._CFG)
EX.ADAPTER_KIND = "easytrader"
EX.LIVE_REQUESTED = False
EX.READ_ONLY_REQUESTED = True
EX.TRAFFIC_ALLOWED = True
EX.DRY_RUN = True
EX._ACTIVE_ADAPTER = _ro
EX._CFG = {"adapter": "easytrader", "read_only": True, "source": "settings",
            "live_env": False, "writes_allowed": False, "traffic_allowed": True}
try:
    s9 = EX.get_status()
    ck(s9["read_only"] is True and s9["traffic_allowed"] is True
       and s9["live_enabled"] is False,
       "۹) سه گیت درِ «فقط‌خواندنی، بی‌نشست» جدا می‌مانند",
       "ro=%s traffic=%s writes=%s" % (s9["read_only"], s9["traffic_allowed"],
                                       s9["live_enabled"]))
    why = " | ".join(s9["blocked_on"])
    ck("نشست" in why and "BORS_EXECUTION_LIVE=1 لازم است" not in why,
       "۹) کمبودِ اصلی «نشستِ شما» گزارش می‌شود، نه روشن‌کردنِ درِ ارسال", why[:170])
    p9 = EX.get_portfolio()
    ck(p9["status"] == "unverified_session" and "/api/execution/session" in str(p9["error"])
       and "restart" not in str(p9["error"]),
       "۹) پرتفوی بی‌نشست «restart لازم است» نمی‌گوید؛ می‌گوید وارد شوید",
       "%s: %s" % (p9["status"], str(p9["error"])[:110]))
    ck(p9["rows"] is None, "۹) بی‌پرسشِ موفق هیچ ردیفی ساخته نمی‌شود", str(p9["rows"]))
    # `/connect` باید همان راستِ `/status` را بگوید. گره‌زدنِ `traffic_mode` به
    # `adapter.live` (که توکن می‌خواهد) درِ سنجشِ زنده با «ترافیک مجاز»ِ `/status`
    # تناقض داد — رابطِ یکِ کارت دو چیزِ متضاد می‌گفت.
    con9 = EXC.status_dict(_ro, None)
    ck(con9.get("traffic_mode") == "read_only" and con9.get("session_proven") is False,
       "۹) /connect درِ همین حالت «فقط‌خواندنی» می‌گوید، نه «مسدود»",
       str(con9.get("traffic_mode")))
    _blocked = EasyTraderAdapter(transport=RefusingTransport(), token=None,
                                writes_allowed=False)
    ck(EXC.status_dict(_blocked, None).get("traffic_mode") == "blocked",
       "۹) ترانسپورتِ ردکننده ⇒ blocked (کنترلِ منفیِ همان برچسب)")
    EX.TRAFFIC_ALLOWED = False
    p10 = EX.get_portfolio()
    ck(p10["status"] == "blocked" and "تنظیمِ اتصال" in str(p10["error"]),
       "۹) کنترلِ منفی: باِ ترافیکِ بسته پیامِ همان حالت می‌آید، نه پیامِ نشست",
       p10["status"])
finally:
    (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.READ_ONLY_REQUESTED, EX.TRAFFIC_ALLOWED,
     EX.DRY_RUN, EX._ACTIVE_ADAPTER, EX._CFG) = _saved

# ── ۱۰) بیلدِ منجمد: ماژولِ تازه درِ هر دو spec باید باشد ───────────────────
# `execution_settings` درِ بدنهٔ تابع import می‌شود، پس اسکنِ ایستا نمی‌بیندش؛
# نبودش یعنی اولین `/api/execution/status` درِ EXE با ModuleNotFoundError می‌افتد
# (همان خطایِ تاریخِ این مخزن). سنجشِ متن، نه حدسِ اسکن.
for _spec in ("fts_terminal.spec", "bors_setup.spec"):
    _t = open(os.path.join(ROOT, _spec), encoding="utf-8").read()
    _hid = _t[_t.index("hiddenimports"):]
    ck("'execution_settings'" in _hid, "۱۰) %s درِ hiddenimports 'execution_settings' دارد" % _spec)

print(f"\nbroker_connect_v1120: {PASS} passed / {FAIL} failed")
sys.exit(1 if FAIL else 0)
