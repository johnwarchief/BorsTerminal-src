# -*- coding: utf-8 -*-
"""
notifier.py — Multi-Channel Notification Dispatcher (Telegram + Bale)
---------------------------------------------------------------------
Non-blocking, async, error-boundary. هرگز exception بالا نمیدهد؛ فقط log با تگ.

Whitelist routing (2026-08-31):
  TELEGRAM_ALLOWED_CHAT_IDS / BALE_ALLOWED_CHAT_IDS
  → comma-separated (مثبت: یوزر؛ منفی: گروه/سوپرگروه). همهٔ اعضا با asyncio.gather
  و هر ایدی در try/except ایزوله — یک گیرندهٔ ناکام بقیه را متوقف نمیکند.

محدودیت امنیتی: توکنها را به CLI/استاذ نمیدهد؛ فقط از ENV میخواند.
"""
import asyncio
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger("notifier")


def _load_dotenv(paths=None):
    """بارگذاری KEY=VALUE از فایل .env (سبک، بدون python-dotenv).
    مسیرهای پیشفرض: همسایهٔ این فایل + CWD. مقادیر موجود override نمیشوند."""
    candidates = paths or [Path(__file__).resolve().parent / ".env", Path.cwd() / ".env"]
    for f in candidates:
        try:
            if not f.is_file():
                continue
            for line in f.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
            log.debug("[notifier] loaded .env from %s", f)
        except Exception:
            pass


_load_dotenv()

# ---------- Config (از ENV / .env — بدون وابستگی، سبک) ----------

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on", "y")


def _parse_whitelist(raw: str) -> list:
    """پارسهٔ لیست کاما-سپریشن chat id ها: strip + هم مثبت هم منفی (گروه).
    ورودی نامعتبر (متن) اپ را نمیشکند — فقط warning."""
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except (TypeError, ValueError):
            log.warning("[notifier] invalid chat id in whitelist: %r", part)
    return out


TG_ENABLED      = _env_bool("TELEGRAM_ENABLED", False)
TG_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID", "").strip()          # legacy single
TG_API_BASE     = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org/bot").strip()
TG_PROXY        = os.getenv("TELEGRAM_PROXY", "").strip() or None
TG_ALLOWED_IDS  = _parse_whitelist(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", ""))

BALE_ENABLED    = _env_bool("BALE_ENABLED", False)
BALE_TOKEN      = os.getenv("BALE_BOT_TOKEN", "").strip()
BALE_CHAT_ID    = os.getenv("BALE_CHAT_ID", "").strip()              # legacy single
BALE_API_BASE   = os.getenv("BALE_API_BASE", "https://tapi.bale.ai/bot").strip()
BALE_ALLOWED_IDS = _parse_whitelist(os.getenv("BALE_ALLOWED_CHAT_IDS", ""))


def _redact(secret: str) -> str:
    """نمایش امن توکن برای log — فقط ۴ کاراکتر اول+آخر."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return secret[:2] + "***"
    return secret[:4] + "..." + secret[-4:]


def status() -> dict:
    """وضعیت پیکربندی — بدون توکن (برای UI/دیباگ)."""
    return {
        "telegram": {
            "enabled": TG_ENABLED,
            "configured": bool(TG_TOKEN and (TG_ALLOWED_IDS or TG_CHAT_ID)),
            "chat_id": _redact(TG_CHAT_ID),
            "allowed_ids": TG_ALLOWED_IDS,
            "api_base": TG_API_BASE,
            "proxy": bool(TG_PROXY),
        },
        "bale": {
            "enabled": BALE_ENABLED,
            "configured": bool(BALE_TOKEN and (BALE_ALLOWED_IDS or BALE_CHAT_ID)),
            "chat_id": _redact(BALE_CHAT_ID),
            "allowed_ids": BALE_ALLOWED_IDS,
            "api_base": BALE_API_BASE,
        },
    }


def _bot_url(api_base: str, token: str, method: str) -> str:
    """ساخت URL استاندارد Bot API:
    هر دو تلگرام و بله به فرم `<base><token>/<method>` نیاز دارند — یعنی اگر
    base با '/bot' ختم شود (مثل 'https://api.telegram.org/bot' یا 'https://tapi.bale.ai/bot')
    AFTER آن نباید '/' بیاید:  '/bot/<token>' → 404،  '/bot<token>' → 200.
    اگر base user-defined بدون 'bot' باشد، با '/' جدا میکند."""
    base = api_base.rstrip("/")
    if base.endswith("bot"):
        return f"{base}{token}/{method}"
    return f"{base}/{token}/{method}"


# ---------- Send functions (async, resilient) ----------

async def _post_json(client: httpx.AsyncClient, url: str, payload: dict, tag: str) -> bool:
    """POST + تست/تبدیل — هرگز raise نمیکند. True فقط با 200 و ok=true."""
    try:
        r = await client.post(url, json=payload)
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, dict) and data.get("ok") is False:
                    log.error("[%s] API returned ok=false: %s", tag,
                              str(data.get("description", ""))[:200])
                    return False
            except Exception:
                pass
            return True
        # log خطاهای 4xx/5xx
        body = r.text[:160].replace("\n", " ")
        log.error("[%s] HTTP %s: %s", tag, r.status_code, body)
        return False
    except httpx.TimeoutException:
        log.error("[%s] timeout (10s)", tag)
        return False
    except httpx.ProxyError as e:
        log.error("[%s] proxy error: %s", tag, str(e)[:160])
        return False
    except (httpx.ConnectError, httpx.NetworkError, OSError) as e:
        log.error("[%s] network error: %s", tag, str(e)[:160])
        return False
    except Exception as e:  # strict error boundary — هرگز به بیرون نده
        log.error("[%s] unexpected error: %s", tag, str(e)[:200])
        return False


def _empty_summary(reason: str) -> dict:
    return {"ok": False, "success": 0, "failed": 0, "summary": None,
            "detail": reason}


def _summarize(results: dict) -> dict:
    succ = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    return {"ok": fail == 0 and succ > 0,
            "success": succ, "failed": fail,
            "summary": {str(k): bool(v) for k, v in results.items()},
            "detail": f"{succ} موفق / {fail} ناموفق"}


async def _broadcast(client: httpx.AsyncClient, url: str, ids: list,
                     text: str, parse_mode: str, tag: str) -> dict:
    """ارسال همزمان به همهٔ ids در whitelist — هر ایدی isolated try/except؛
    خطای یک گیرنده (banned/blocked/left) بقیه را متوقف نمیکند."""
    results = {}

    async def _one(cid: int):
        try:
            payload = {"chat_id": cid, "text": text, "parse_mode": parse_mode}
            return await _post_json(client, url, payload, f"{tag}/{cid}")
        except Exception as e:
            log.error("[%s] recipient %s error: %s", tag, cid, str(e)[:140])
            return False

    try:
        gathered = await asyncio.gather(*[_one(c) for c in ids],
                                        return_exceptions=True)
        for cid, r in zip(ids, gathered):
            results[cid] = bool(r)
    except Exception as e:  # gather هرگز raise نمیشود، ولی مرز محکم
        log.error("[%s] gather error: %s", tag, str(e)[:140])
        for cid in ids:
            results.setdefault(cid, False)
    return _summarize(results)


async def send_telegram_msg(text: str, parse_mode: str = "HTML") -> dict:
    """ارسال به همهٔ گیرندههای whitelist تلگرام (همزمان). خروجی: خلاصهٔ ارسال."""
    if not TG_ENABLED:
        log.debug("[notifier-telegram] disabled — skip")
        return _empty_summary("غير فعال (TELEGRAM_ENABLED=false)")
    if not TG_TOKEN:
        log.error("[notifier-telegram] missing token — check .env")
        return _empty_summary("توکن تلگرام تنظیم نشده")
    ids = TG_ALLOWED_IDS or ([int(TG_CHAT_ID)] if TG_CHAT_ID else [])
    if not ids:
        log.warning("[notifier-telegram] TELEGRAM_ALLOWED_CHAT_IDS empty/unset — skip dispatch")
        return _empty_summary("TELEGRAM_ALLOWED_CHAT_IDS خالی است — ارسال متوقف")
    url = _bot_url(TG_API_BASE, TG_TOKEN, "sendMessage")
    try:
        async with httpx.AsyncClient(proxy=TG_PROXY, timeout=10.0) as client:
            return await _broadcast(client, url, ids, text, parse_mode, "notifier-telegram")
    except Exception as e:
        log.error("[notifier-telegram] client error: %s", str(e)[:200])
        return _empty_summary(str(e)[:140])


async def send_bale_msg(text: str, parse_mode: str = "HTML") -> dict:
    """ارسال به همهٔ گیرندههای whitelist بله (همزمان). خروجی: خلاصهٔ ارسال."""
    if not BALE_ENABLED:
        log.debug("[notifier-bale] disabled — skip")
        return _empty_summary("غير فعال (BALE_ENABLED=false)")
    if not BALE_TOKEN:
        log.error("[notifier-bale] missing token — check .env")
        return _empty_summary("توکن بله تنظیم نشده")
    ids = BALE_ALLOWED_IDS or ([int(BALE_CHAT_ID)] if BALE_CHAT_ID else [])
    if not ids:
        log.warning("[notifier-bale] BALE_ALLOWED_CHAT_IDS empty/unset — skip dispatch")
        return _empty_summary("BALE_ALLOWED_CHAT_IDS خالی است — ارسال متوقف")
    url = _bot_url(BALE_API_BASE, BALE_TOKEN, "sendMessage")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await _broadcast(client, url, ids, text, parse_mode, "notifier-bale")
    except Exception as e:
        log.error("[notifier-bale] client error: %s", str(e)[:200])
        return _empty_summary(str(e)[:140])


async def send_telegram_doc(text: str, file: bytes, filename: str,
                            parse_mode: str = "HTML") -> dict:
    """ارسال سند (PDF/XLSX) به همهٔ whitelist تلگرام — اختیاری."""
    if not TG_ENABLED or not TG_TOKEN:
        return _empty_summary("تلگرام غيرفعال/بدون توکن")
    ids = TG_ALLOWED_IDS or ([int(TG_CHAT_ID)] if TG_CHAT_ID else [])
    if not ids:
        log.warning("[notifier-telegram] no allowed ids for doc — skip")
        return _empty_summary("TELEGRAM_ALLOWED_CHAT_IDS خالی است")
    url = _bot_url(TG_API_BASE, TG_TOKEN, "sendDocument")
    results = {}

    async def _one(cid: int):
        try:
            async with httpx.AsyncClient(proxy=TG_PROXY, timeout=30.0) as client:
                r = await client.post(url, data={**{"chat_id": cid, "caption": text,
                                                  "parse_mode": parse_mode}},
                                      files={"document": (filename, file)})
                if r.status_code == 200:
                    return True
                log.error("[notifier-telegram] doc %s HTTP %s: %s", cid, r.status_code,
                          r.text[:140].replace("\n", " "))
                return False
        except Exception as e:
            log.error("[notifier-telegram] doc %s error: %s", cid, str(e)[:140])
            return False

    gathered = await asyncio.gather(*[_one(c) for c in ids], return_exceptions=True)
    for cid, r in zip(ids, gathered):
        results[cid] = bool(r)
    return _summarize(results)


# ---------- Master dispatcher ----------

async def dispatch_alert(text: str, parse_mode: str = "HTML") -> dict:
    """ارسال همزمان به همهٔ کانالهای فعال. هیچوقت uncaught exception ندارد.
    خروجی: {'sent': {channel: خلاصه}, 'total': {'success': n, 'failed': m}}"""
    tasks = []
    labels = []
    if TG_ENABLED and TG_TOKEN and (TG_ALLOWED_IDS or TG_CHAT_ID):
        tasks.append(send_telegram_msg(text, parse_mode))
        labels.append("telegram")
    if BALE_ENABLED and BALE_TOKEN and (BALE_ALLOWED_IDS or BALE_CHAT_ID):
        tasks.append(send_bale_msg(text, parse_mode))
        labels.append("bale")
    if not tasks:
        log.warning("[notifier] no enabled channel configured")
        return {"ok": False, "sent": {}, "total": {"success": 0, "failed": 0},
                "detail": "هیچ کانالی فعال نیست"}
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        log.error("[notifier] gather error: %s", str(e)[:200])
        return {"ok": False, "sent": {}, "total": {"success": 0, "failed": 0},
                "detail": str(e)[:150]}
    out = {}
    total_s = total_f = 0
    for lab, res in zip(labels, results):
        if isinstance(res, Exception):
            log.error("[notifier-%s] gathered exception: %s", lab, str(res)[:160])
            out[lab] = _empty_summary(str(res)[:120])
        else:
            out[lab] = res
            total_s += int(res.get("success", 0))
            total_f += int(res.get("failed", 0))
    return {"ok": total_f == 0 and total_s > 0,
            "sent": out,
            "total": {"success": total_s, "failed": total_f},
            "detail": "، ".join(f"{k}: {v.get('success', 0)}✓/{v.get('failed', 0)}✗"
                                for k, v in out.items())}
