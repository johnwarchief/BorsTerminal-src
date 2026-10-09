# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess

# ── بدونِ پنجرهٔ کنسول + کدپیجِ خروجی (v1.0.13) ──────────────────────────
# با console=False در spec، sys.stdout/sys.stderr می‌توانند None باشند
# (PyInstaller در حالتِ windowless آن‌ها را می‌بندد). هر دست‌زدنی به آن‌ها
# AttributeError می‌شود، پس اول یک فایلِ لاگِ UTF-8 می‌سازیم و می‌بندیمش.
#
# دو هدفِ همزمان:
#   ۱) کدپیجِ پیش‌فرضِ ویندوز رویِ EXEِ فریزشده cp1252 است و هیچ حرفِ
#      فارسی‌ای قابلِ انکد نیست. اولین printِ فارسی کلِ درخواست را با
#      UnicodeEncodeError می‌کشد (دیده‌شده: api/screener.py:227 →
#      GET /api/screener 500 → صفحهٔ بنیادی خالی).
#   ۲) هیچ پنجرهٔ ترمینالی باز نشود و لاگی رویِ صفحه نباشد.
#
# BORS_SHOW_CONSOLE=1 در محیط، کنسول را برمی‌گرداند برایِ دیباگِ دستی.
def _setup_streams():
    if os.environ.get("BORS_SHOW_CONSOLE") == "1":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
        return
    try:
        _logdir = os.path.join(WORK, "logs")
        os.makedirs(_logdir, exist_ok=True)
        _logpath = os.path.join(_logdir, "bors.log")
        # حالتِ append: کرش‌هایِ قبلی حفظ شوند و چرخهٔ اجراها دیده شود.
        # buffering=1 (خط‌به‌خط): با بافرِ پیش‌فرضِ بلوکی، آخرین سطرهایِ پیش از
        # مرگِ پروسه داخلِ بافر می‌مانند و هرگز رویِ دیسک نمی‌آمدند — یعنی
        # دقیقاً همان سطرهایی که باید «چگونه مُرد» را بگویند گم می‌شدند و لاگ با
        # یک GET معمولی تمام می‌شد. (شاهد: هیچ «Shutting down» در کلِ لاگ نیست،
        # درحالی‌که ده بارِ اجرا از سر گرفته شده است.)
        _f = open(_logpath, "a", encoding="utf-8", errors="replace", buffering=1)
        sys.stdout = _f
        sys.stderr = _f
    except (AttributeError, ValueError, OSError, FileNotFoundError):
        # اگر نوشتن ممکن نبود، جریان‌ها را بی‌خطرِ صفر کن تا کرش ندهیم.
        class _Null:
            def write(self, *a, **k): return 0
            def flush(self): pass
            def reconfigure(self, **k): pass
            def close(self): pass
        sys.stdout = _Null()
        sys.stderr = _Null()

# ── ساعت و نشانِ خروج (v1.0.55) ───────────────────────────────────────────
# دو کورکنندهٔ «مرگِ بی‌صدای» برنامه، هر دو در همین فایل بودند:
#   ۱) لاگ هیچ زمانی نداشت (uvicorn access log با قالبِ بی‌زمانِ پیش‌فرض)، پس
#      هیچ واقعه‌ای در bors.log قابلِ زمان‌بندی نبود.
#   ۲) سطرهایِ آخر داخلِ بافرِ بلوکی می‌ماندند و با مرگِ پروسه می‌مردند.
# با این سه چیز داوری ممکن می‌شود: هر سطر زمان دارد، هر سطر بی‌درنگ رویِ
# دیسک می‌آید، و یک [exit] هنگامِ خروجِ عادی نوشته می‌شود. نبودِ [exit] پس از
# آخرین [beat] یعنی پروسه کشته شده، نه اینکه بسته شده است.
def _stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _note(msg):
    try:
        print(f'{_stamp()} [app] {msg}', flush=True)
    except Exception:
        pass


def _log_config_with_clock():
    """همان پیکربندیِ پیش‌فرضِ uvicorn، فقط با %(asctime)s در دو قالب."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s %(levelprefix)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": ('%(asctime)s %(levelprefix)s %(client_addr)s - '
                        '"%(request_line)s" %(status_code)s'),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {"formatter": "default", "class": "logging.StreamHandler",
                        "stream": "ext://sys.stderr"},
            "access": {"formatter": "access", "class": "logging.StreamHandler",
                       "stream": "ext://sys.stdout"},
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
            # قیدِ v1.0.55 «هر سطرِ لاگ با ساعت شروع می‌شود» فقط سه سروِ بالا را
            # می‌پوشاند: `warnings.warn` بی‌این سرو مستقیم در stderr می‌نویسد.
            # سنجشِ ۱۴۰۵-۰۷-۰۷: ۵٬۶۲۶ سطرِ بی‌ساعت از ۳۵٬۸۴۹ سطرِ روز (۱۶٫۶٪)،
            # همه یک اخطارِ pandas. با `captureWarnings` این‌ها هم از همان
            # قالبِ ساعت‌دار می‌گذرند.
            "py.warnings": {"handlers": ["default"], "level": "WARNING",
                            "propagate": False},
        },
    }


def _beat_loop(port):
    """ضربانِ زنده بودن هر ۵ دقیقه. مرزِ بین «برنامه مُرد» و «فاصلهٔ بی‌درخواست
    در ساعتِ بسته» را همین خط نگه می‌دارد."""
    while True:
        time.sleep(300)
        _note(f'beat pid={os.getpid()} port={port}')


# در حالت EXE (onefile): کتابخانه‌ها داخل _MEIPASS؛ DB ها کنار exe (از ZIP)
# توجه: _setup_streams() به WORK نیاز دارد (پوشهٔ لاگ کنارِ exe است)، پس
# این بلوک باید قبل از فراخوانیِ آن باشد.
if getattr(sys, 'frozen', False):
    BASE = sys._MEIPASS
    WORK = os.path.dirname(sys.executable)
    os.chdir(WORK)
else:
    WORK = os.path.dirname(os.path.abspath(__file__))

_setup_streams()

# ── گاردِ سازگاریِ ویندوز (v1.0.12) ───────────────────────────────────────
# ویندوزهایِ قدیمی (۷/۸/۸.۱) کرش‌های نامفهوم می‌دهند: TLSِ مدرن، فونت‌های
# فارسی، و رندرِ GPUِ کرومیوم رویِ درایورهایِ قدیمی. به‌جایِ کرشِ سایلنت،
# یک پیامِ واضح نشان می‌دهیم.
WIN_TOO_OLD = False
WIN_VER_NAME = "unknown"
try:
    _wv = sys.getwindowsversion()          # فقط رویِ ویندوز موجود است
    WIN_VER_NAME = "Windows %d.%d (build %d)" % (_wv.major, _wv.minor, _wv.build)
    if _wv.major < 10:
        WIN_TOO_OLD = True
except AttributeError:
    pass                                   # غیرِ ویندوز → هیچ گاردی لازم نیست


def _warn_old_windows():
    """پیامِ کاربرپسند برای ویندوزِ پشتیبانی‌نشده (به‌جای کرش)."""
    msg = (
        "⚠ این ویندوز برای اجرای کامل BorsTerminal پشتیبانی نمی‌شود.\n\n"
        "نسخهٔ سیستم‌عامل شما: %s\n"
        "حداقل نسخهٔ موردنیاز: Windows 10 (64-bit)\n\n"
        "برنامه اجرا می‌شود اما ممکن است:\n"
        "  • فونت‌های فارسی ناقص نمایش داده شوند\n"
        "  • رابط کاربری کند یا ناپایدار باشد\n"
        "  • برخی صفحات سفید شوند\n\n"
        "پیشنهاد: به Windows 10/11 ارتقا دهید." % WIN_VER_NAME
    )
    print("[WARN] unsupported Windows:", WIN_VER_NAME)
    try:
        # پیامِ نیتیو (نه کنسول) — کاربرِ دسکتاپ کنسول را نمی‌بیند.
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "BorsTerminal — هشدار سازگاری", 0x30)
    except Exception:
        print(msg)


# ── گاردِ رندرینگ (v1.0.12): GPU ضعیف/نبود GPU → رندرِ نرم‌افزاری ─────────
# رویِ سیستم‌های بدونِ GPU اختصاصی (Intel HD قدیمی، Microsoft Basic Display)
# یا رمِ کم، کرومیوم صفحهٔ سفید یا کرش می‌دهد. SwiftShader (رندرِ
# نرم‌افزاریِ رسمیِ کرومیوم) این حالت را نجات می‌دهد.
def _probe_gpu():
    """(has_dedicated, adapter_names, ram_gb) — از WMI. در صورتِ شکست، محتاطانه.

    wmic رویِ Windows 11 حذف شده (deprecation) و خروجیِ خالی برمی‌گرداند،
    پس powershell را امتحان می‌کنیم و wmic فقط جایگزینِ آخر است.
    """
    adapters, ram_gb = [], 0.0
    ps = None
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$ErrorActionPreference='SilentlyContinue';"
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name;"
             "[Environment]::PhysicalMemory"],
            capture_output=True, text=True, timeout=20, shell=True)
    except Exception:
        ps = None
    if ps is not None:
        lines = [ln.strip() for ln in (ps.stdout or "").splitlines() if ln.strip()]
        # خطِ آخر می‌تواند بایتِ کلِ رم باشد (یک عددِ بزرگ)
        for ln in lines:
            if ln.isdigit() and len(ln) >= 9:
                ram_gb = int(ln) / 1073741824.0
            elif ln.lower() not in ("name",):
                adapters.append(ln)
    if not adapters:
        try:                                   # جایگزینِ wmic برای ویندوزهای قدیمی
            out = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=15, shell=True)
            for ln in (out.stdout or "").splitlines():
                ln = ln.strip()
                if ln and ln.lower() != "name":
                    adapters.append(ln)
        except Exception:
            pass
    if not adapters:
        return None, adapters, ram_gb
    dedicated = False
    for a in adapters:
        low = a.lower()
        # آداپتورهایِ اختصاصی (نه یکپارچهٔ رویِ پردازنده)
        if any(k in low for k in ("nvidia", "geforce", "quadro", "radeon",
                                  "amd radeon", "firepro", "arc a")):
            if not any(k in low for k in ("basic display", "microsoft")):
                dedicated = True
    return dedicated, adapters, ram_gb


def _needs_software_rendering():
    """True اگر GPU اختصاصی نیست یا رم کم است → پرچم‌هایِ رندرِ نرم‌افزاری.

    در صورتِ شکستِ تشخیص (پروب خالی برگرداند) «True» برمی‌گرداند: یک صفحهٔ
    سفیدِ غیرقابلِ استفاده بدتر از کمی کندیِ رندرِ نرم‌افزاری است. این
    انتخابِ محتاطانه است، نه یک باگ.
    """
    dedicated, adapters, ram_gb = _probe_gpu()
    if not adapters:
        return True                            # تشخیص ناموفق → محتاطانه
    if dedicated:
        return False                           # GPU اختصاصی هست → GPU بزن
    if ram_gb and ram_gb < 4.0:
        return True                            # رمِ کم → نرم‌افزاری
    if any("basic display" in a.lower() for a in adapters):
        return True                            # درایورِ ویندوزِ پیش‌فرض
    return True                                # فقط Intel HD یکپارچه


def _set_dpi_awareness():
    """Per-Monitor V2 پیش از ساختِ هر پنجره.

    بدونِ اعلامِ آگاهیِ DPI، ویندوز کلِ پروسه را «ناآگاه» می‌گیرد و روی
    مانیتور ۲K/۴K با مقیاس ۱۲۵–۲۰۰٪ تصویر را بیت‌مپ می‌کند: نوشته‌ها و
    کندل‌ها تار می‌شوند و عرضِ در دسترس هم اشتباه محاسبه می‌شود. با این
    فراخوانی، ویندوز خودش مقیاس را به Chromium می‌دهد و چیدمانِ رزولوشنیِ
    tokens.css (۱۹۲۰/۲۵۶۰/۳۸۴۰) روی اندازهٔ واقعی باز می‌شود.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        try:                                            # ویندوز ۱۰ نسخهٔ ۱۷۰۳ به بعد
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except AttributeError:
            pass
        try:                                            # ویندوز ۸.۱/۱۰ قدیمی‌تر
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
        except AttributeError:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:                              # noqa: BLE001
        print(f'[dpi] awareness not set ({e}) - rendering may be scaled by Windows')


def _render_flags():
    """پرچم‌هایِ مرورگر بر اساسِ سخت‌افزار — برای جلوگیری از صفحهٔ سفید."""
    if _needs_software_rendering():
        print("[render] no dedicated GPU / low RAM -> software rendering (SwiftShader)")
        return ["--disable-gpu",
                "--use-angle=swiftshader",      # کرومیوم ۸۶+
                "--use-gl=swiftshader",         # نسخه‌های قدیمی‌تر
                "--disable-software-rasterizer=false"]
    return []

def _data_root():
    """ریشهٔ دادهٔ محلی؛ baseline بازار در نصب تازه از Release دریافت می‌شود."""

    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    for cand in (base, os.path.join(base, "_internal")):
        if os.path.isfile(os.path.join(cand, "market.db")) or \
           os.path.isfile(os.path.join(cand, "market.db.lzma")):
            return cand
    return base


# ── صفحۀ بوت: پیشرفتِ اولین اجرا ──────────────────────────────────────────
# تا این نسخه پنجره فقط *بعد* از بالا آمدنِ uvicorn باز می‌شد؛ در اولین اجرا
# دریافتِ market.db.lzma (۵۷ مگابایت) و بازکردنش (۹۸ مگابایت) روی سیستمِ ضعیف
# دقیقه‌ها طول می‌کشد و در آن مدّت کاربر هیچ چیز رویِ صفحه نمی‌دید — فقط یک
# پروسۀ بی‌صدا در تسک‌منیجر. این سرورِ کوچکِ stdlib روی یک پورتِ آزاد همان
# لحظۀ اول پنجره را با متنِ فارسیِ پیشرفت بالا می‌آورد؛ وقتی اپِ واقعی آماده
# شد خودِ صفحۀ بوت آدرس را عوض می‌کند. پس دو سرور روی یک پورت نمی‌نشینند و
# مسیرِ «سرورِ ما روی ۸۰۰۱ از قبل بالاست» دست‌نخورده می‌ماند.
#
# هیچ رقمی در متنِ پایتون تایپ نمی‌شود: JSON عددِ لاتین می‌برد و صفحۀ بوت با
# 0x06F0 فارسی‌اش می‌کند (قاعدۀ «رقمِ دزدیده‌شده» در AGENTS.md).
_BOOT_PHASES = {
    "check": "بررسیِ پایگاهِ دادهٔ بازار",
    "data-meta": "خواندنِ نشانیِ بستۀ داده",
    "download": "دریافتِ دادهٔ بازار",
    "extract": "بازکردنِ پایگاهِ دادهٔ بازار",
    "merge": "ادغامِ ردیف‌هایِ تازهٔ بازار",
    "rebuild": "ساختِ دوبارۀ پایگاهِ داده",
    "serve": "راه‌اندازیِ موتورِ برنامه",
}
_BOOT = {"phase": "check", "pct": None, "detail": "", "ready": False,
         "url": None, "error": None}
_BOOT_LOCK = threading.Lock()

_BOOT_HTML = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>بورس‌ترمینال</title>
<style>
 html,body{height:100%;margin:0;background:#0b0f17;color:#e6edf7;
  font:14px/1.9 Tahoma,'Segoe UI',sans-serif}
 .wrap{min-height:100%;display:flex;align-items:center;justify-content:center;padding:24px}
 .card{width:min(560px,100%);background:#111827;border:1px solid #1f2a3a;
  border-radius:18px;padding:28px 26px;box-shadow:0 18px 60px rgba(0,0,0,.55)}
 .brand{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;
  border-radius:9px;background:linear-gradient(135deg,#38bdf8,#2563eb);color:#04121f;
  font-weight:900;margin-bottom:14px}
 h1{margin:0 0 4px;font-size:17px;font-weight:900}
 .sub{margin:0 0 20px;font-size:11px;color:#8ea3bd;letter-spacing:.4px}
 .phase{margin:0 0 10px;font-size:13px;font-weight:700;color:#cfe3ff;min-height:20px}
 .bar{height:8px;border-radius:99px;background:#16212f;overflow:hidden}
 .bar i{display:block;height:100%;width:0%;border-radius:99px;
  background:linear-gradient(90deg,#38bdf8,#22d3ee);transition:width .35s ease}
 .bar.indet i{width:38%;animation:slide 1.25s ease-in-out infinite alternate}
 @keyframes slide{from{transform:translateX(0)}to{transform:translateX(175%)}}
 .detail{margin:10px 0 0;font-size:11px;color:#8ea3bd;min-height:18px}
 .note{margin:18px 0 0;font-size:11px;color:#6f8199}
 .err{margin:0 0 10px;font-size:13px;font-weight:700;color:#fca5a5}
</style></head><body>
<div class="wrap"><div class="card">
 <div class="brand">&#1576;</div>
 <h1>بورس‌ترمینال</h1>
 <p class="sub">FTS v2.1</p>
 <p class="err" id="err" style="display:none"></p>
 <p class="phase" id="phase">&nbsp;</p>
 <div class="bar indet" id="bar"><i id="fill"></i></div>
 <p class="detail" id="detail">&nbsp;</p>
 <p class="note" id="note">لطفاً این پنجره را نبندید؛ برنامه خودش ادامه می‌دهد.</p>
</div></div>
<script>
 var fa = function (s) {
   return String(s).replace(/[0-9]/g, function (d) { return String.fromCharCode(0x06F0 + (+d)); });
 };
 var elPhase = document.getElementById('phase'), elDetail = document.getElementById('detail');
 var elBar = document.getElementById('bar'), elFill = document.getElementById('fill');
 var elErr = document.getElementById('err'), elNote = document.getElementById('note');
 function setStatus(p) {
   if (p.error) {
     elErr.style.display = 'block'; elErr.textContent = p.error;
     elBar.style.display = 'none'; elDetail.textContent = '';
     elNote.textContent = '\u0628\u0631\u0646\u0627\u0645\u0647 \u0631\u0627 \u0628\u0633\u062a\u0647 \u0648 \u062f\u0648\u0628\u0627\u0631\u0647 \u0628\u0627\u0632 \u06a9\u0646\u06cc\u062f.';
     return;
   }
   elPhase.textContent = p.text || '';
   if (typeof p.pct === 'number') {
     elBar.className = 'bar';
     elFill.style.width = Math.max(2, Math.min(100, p.pct)) + '%';
     elDetail.textContent = fa(p.pct) + '\u066a' + (p.detail ? ' \u00b7 ' + fa(p.detail) : '');
   } else {
     elBar.className = 'bar indet'; elFill.style.width = '';
     elDetail.textContent = p.detail || '';
   }
   if (p.ready && p.url) {
     elPhase.textContent = '\u0622\u0645\u0627\u062f\u0647 \u0634\u062f';
     elBar.className = 'bar'; elFill.style.width = '100%';
     elDetail.textContent = '';
     location.replace(p.url);
   }
 }
 function poll() {
   fetch('/boot-status', {cache: 'no-store'}).then(function (r) { return r.json(); })
     .then(setStatus).catch(function () { setTimeout(poll, 1200); });
 }
 poll(); setInterval(poll, 500);
</script></body></html>
"""


def _boot_update(**kw):
    with _BOOT_LOCK:
        _BOOT.update(kw)


def _boot_progress(phase, done=0, total=0):
    """پیشرفتِ ساختِ دیتابیس را برایِ صفحۀ بوت ثبت می‌کند (از نخِ worker)."""
    pct = None
    detail = ""
    try:
        d, t = float(done), float(total)
        if t > 0 and d >= 0:
            pct = int(100.0 * d / t)
            detail = "%.1f / %.1f MB" % (d / 1048576.0, t / 1048576.0)
    except (TypeError, ValueError):
        pct = None
    _boot_update(phase=phase, pct=pct, detail=detail)


def _boot_fail(message):
    _boot_update(error=message, ready=False, pct=None, detail="")
    _note('boot failed: %s' % message)


def _boot_ready(url):
    _boot_update(ready=True, url=url, pct=100, error=None)


def _start_boot_server():
    """سرورِ موقتِ صفحۀ بوت روی پورتِ آزادِ سیستمی. None یعنی نشد — آن‌وقت
    برنامه دقیقاً مثلِ قبل (بدونِ صفحۀ پیشرفت) بالا می‌آید."""
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import json as _json
    except Exception as e:
        _note('boot page modules unavailable: %s' % e)
        return None

    class _Handler(BaseHTTPRequestHandler):
        server_version = "BorsBoot/1.0"

        def log_message(self, *args):
            pass                       # صفحۀ بوت لاگِ access تولید نمی‌کند

        def _send(self, code, body, ctype):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/boot-status":
                with _BOOT_LOCK:
                    payload = dict(_BOOT)
                    payload["text"] = _BOOT_PHASES.get(_BOOT["phase"], "")
                self._send(200, _json.dumps(payload, ensure_ascii=False),
                           "application/json")
            elif path in ("/", "/index.html"):
                self._send(200, _BOOT_HTML, "text/html")
            elif path == "/favicon.ico":
                # کرومیوم بی‌آیکون این را می‌خواهد؛ ۴۰۴ آن در کنسولِ صفحۀ بوت
                # خطا می‌نویسد و سنجشِ «بی‌خطا» را قرمز می‌کند.
                self.send_response(204)
                self.end_headers()
            else:
                self._send(404, "{}", "application/json")

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    except Exception as e:
        _note('boot server could not bind: %s' % e)
        return None
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5},
                     daemon=True).start()
    return srv, srv.server_address[1]


def _preflight(progress=None):
    """هوشمند: پیش‌اجرا + چک DB ها (مثل run_terminal)"""
    print("=" * 66)
    print("  BorsTerminal_Ultimate - smart preflight")
    print("=" * 66)
    ok = True
    # v1.0.20: این بلوکِ inline حذف شد و همان bors_config.ensure_market_db() صدا
    # زده می‌شود. شرطِ قبلی «فقط اگر وجود نداشت استخراج کن» بود، پس baselineِ تازهٔ
    # هر نسخهٔ جدید هرگز جای فایلِ استخراج‌شدهٔ قدیمی را نمی‌گرفت و دادهٔ بازار
    # برای کاربرِ ارتقا‌یافته کهنه می‌ماند. ensure_market_db حالا اثرِ انگشتیِ
    # market.db.lzma را با مُهرِ کنارِ فایل مقایسه می‌کند و در صورتِ تفاوت
    # بازمی‌گرداند، با نقلِ جدول‌هایِ کاربر.
    try:
        import bors_config
        db = bors_config.ensure_market_db(verbose=True, progress=progress)
    except Exception as e:
        print("  [ERR] ensure_market_db failed:", e)
        db = os.path.join(_data_root(), "market.db")
        ok = False
    root = _data_root()
    print(f"  data root: {root}")
    if not os.path.exists(db):
        print("  [ERR] market.db baseline is unavailable.")
        print("        The app downloads it from the external Release data asset.")
        print("        Check network access and retry the application.")
        ok = False
    else:
        try:
            import sqlite3
            c = sqlite3.connect(db)
            n = c.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
            c.close()
            print(f"  [OK]  market.db: {n:,} instruments (TSETMC + Codal data inside)")
        except Exception as e:
            print("  [WARN] market.db unreadable:", e)
    try:
        import pandas, numpy, fastapi, uvicorn, requests  # noqa
        print("  [OK]  bundled libraries: pandas/numpy/fastapi/uvicorn/requests (self-contained)")
    except ImportError as e:
        print("  [ERR] bundled library missing:", e)
        ok = False
    if ok:
        print("  [OK]  everything ready - starting ...")
    else:
        print("  [!!]  fix the missing files, then run this EXE again")
    print("=" * 66)
    return ok

def port_open(p):
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(('127.0.0.1', p)); return True
    except OSError:
        return False
    finally:
        s.close()

def server_is_ours(p):
    """آیا سرورِ در حال اجرا مالِ همین برنامه است (نه سرویس دیگر روی همان پورت)؟"""
    import urllib.request, json
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{p}/api/update/version', timeout=2) as r:
            data = json.loads(r.read().decode('utf-8', 'replace'))
            return 'version' in data
    except Exception:
        return False

def pick_free_port(preferred=8001):
    """پورت ترجیحی اگر آزاد بود؛ وگرنه یک پورت آزادِ سیستمی می‌گیرد تا هرگز
    با پورتِ اشغال تداخل نکند (پایانِ ماجرای «پورت اشغال است»)."""
    if not port_open(preferred):
        return preferred
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p

def wait_http(p, timeout=30):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{p}/', timeout=2) as r:
                if r.status == 200: return True
        except Exception:
            pass
        time.sleep(1)
    return False

def find_app_browser():
    """پیدا کردن مرورگرهای کرومیوم (Edge, Chrome, Brave) برای باز کردن پنجره اختصاصی نرم‌افزار"""
    import shutil
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("brave"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def _webview_storage_dir():
    """پروفایلِ پایدارِ WebView2 به‌جای پوشهٔ موقتِ هر اجرا.

    دلیلِ وجودش (سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ اپِ نصبی): pywebview با private_mode
    پیش‌فرضْ هر اجرا یک `tempfile.mkdtemp()` می‌سازد و درِ همان حالت هیچ
    localStorage را رویِ دیسک نمی‌نویسد. درِ %TEMP% همین ماشین ۳۶ پوشهٔ
    EBWebView با ۴۷۶ مگابایت جا ماند، و در ۳۴ مورد از ۳۵ِ قابلِ خواندن
    logِ Local Storage بی‌محتوا بود (۴۹ بایت) — یعنی هر چیزی که UI در
    localStorage می‌گذارد (بازهٔ پولینگ، «حذفِ پسوندِ عددی»، ترجیحاتِ قیف،
    پارامترهایِ استراتژی، تم، آستانهٔ سرمایه) با هر بارِ بستنِ برنامه می‌مرد.
    مسیرِ جایگزینِ مرورگری (`open_app_window`) پروفایلِ پایدار دارد؛ این
    تفاوتِ دو مسیر بود، نه باگِ فرانت‌اند.
    """
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'BorsTerminal_Ultimate', 'webview2')
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError as e:
        print(f'[native] storage dir unavailable ({e}) -> pywebview default')
        return ''


def open_native_window(url):
    """پنجرهٔ مستقلِ بومی با WebView2 (pywebview): بدون مرورگر/تب/نوار آدرس و
    بدون نامِ Edge در تسک‌بار — شبیهِ یک اپ دسکتاپ واقعی. اگر pywebview یا
    WebView2 نبود، False برمی‌گرداند تا مسیر مرورگرِ فعلی fallback شود."""
    if os.environ.get('BORS_NATIVE_WINDOW', '1') == '0':
        return False
    try:
        import webview  # pywebview
    except Exception as e:
        print(f'[native] pywebview unavailable ({e}) -> browser fallback')
        return False
    # خودِ pywebview وقتی رانتایم WebView2 نباشد بی‌صدا به MSHTML (IE) می‌افتد و
    # فقط یک warning می‌زند؛ پنجره باز می‌شود ولی SPA در حالت IE11 می‌شکند و این
    # except هیچ‌وقت فراخوانی نمی‌شود. پس تصمیمِ خودِ کتابخانه را می‌خوانیم و اگر
    # edgechromium نبود عمداً به مسیرِ مرورگر برمی‌گردیم.
    try:
        from webview.platforms import winforms as _wf
        _renderer = getattr(_wf, 'renderer', None)
        if _renderer != 'edgechromium':
            print(f'[native] webview backend is {_renderer!r}, not edgechromium '
                  '-> browser fallback')
            return False
    except Exception as e:
        print(f'[native] cannot resolve webview backend ({e}) -> browser fallback')
        return False
    try:
        # maximized: روی ۱۳۶۶×۷۶۸ هم ۱۴۴۰×۹۰۰ از صفحه بیرون می‌زند، و روی
        # ۲K/۴K نصف مانیتور را بی‌دلیل خالی می‌گذارد.
        webview.create_window('بورس‌ترمینال — BorsTerminal', url,
                              width=1440, height=900, min_size=(1024, 640),
                              maximized=True)
        storage = _webview_storage_dir()
        # private_mode باید صریحاً خاموش شود، وگرنه storage_path بی‌اثر است
        # (پیش‌فرضِ pywebviewْ حالتِ خصوصی/موقت است). نسخهٔ کتابخانه درِ
        # requirements پین نشده، پس فقط کلیدهایی پاس می‌شوند که امضایشان هست.
        kwargs = {}
        try:
            import inspect
            allowed = set(inspect.signature(webview.start).parameters)
            if 'private_mode' in allowed:
                kwargs['private_mode'] = False
            if storage and 'storage_path' in allowed:
                kwargs['storage_path'] = storage
        except (TypeError, ValueError) as e:
            print(f'[native] cannot read webview.start signature ({e})')
        if kwargs:
            print(f'[native] persistent webview profile: {kwargs.get("storage_path", "-")}')
        else:
            print('[native] webview.start has no private_mode/storage_path -> '
                  'settings will NOT survive a restart (upgrade pywebview)')
        webview.start(**kwargs)          # تا بستهٔ شدن پنجره بلاق میکند
        return True
    except Exception as e:
        print(f'[native] window failed ({e}) -> browser fallback')
        return False

def open_app_window(url):
    """باز کردن ترمینال در یک پنجره مستقل دسکتاپ (App Window Mode) بدون تب و نوار آدرس"""
    browser_exe = find_app_browser()
    if browser_exe:
        profile_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "BorsTerminal_Ultimate",
            "app_profile",
        )
        os.makedirs(profile_dir, exist_ok=True)
        cmd = [
            browser_exe,
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ] + _render_flags()
        try:
            # cwd = پروفایلِ مرورگر، نه پوشهٔ برنامه. مرورگرِ --app پس از
            # بستنِ سرور هم مدتی زنده می‌ماند و پوشهٔ جاریِ خودش را قفل
            # نگه می‌دارد؛ اگر آن پوشه {app} باشد، پایدارکنندهٔ درون‌برنامه
            # و نصب‌کننده نمی‌توانند فایل‌ها را جایگزین کنند (همین رویِ ماشین
            # توسعه، بیلد را با WinError 5/32 خواباند).
            subprocess.Popen(cmd, cwd=profile_dir)
            print(f"[OK] App window launched using {os.path.basename(browser_exe)}")
            return True
        except Exception as e:
            print(f"[WARN] Failed to launch app window ({e}), falling back...")
    webbrowser.open(url)
    return False

def _serve():
    _set_dpi_awareness()
    # v1.0.12: گاردِ ویندوز — قبل از هر چیز، تا روی ویندوزِ قدیمی کرشِ
    # نامفهوم ندهیم. هشدار نمایش می‌دهیم و ادامه می‌دهیم (نه مسدود).
    if WIN_TOO_OLD:
        _warn_old_windows()
    port = int(os.environ.get('BORS_PORT', '8001'))
    if port_open(port) and server_is_ours(port):
        print(f'[OK] Server already running on {port} -> open window')
        url = f'http://127.0.0.1:{port}'
        if open_native_window(url):
            _note('native window closed')
            return 'already-running-window'
        open_app_window(url)
        return 'already-running-browser'
    if port_open(port):
        # پورت اشغال است ولی سرورِ ما نیست → پورت آزادِ دیگر
        port = pick_free_port(port)
        print(f'[OK] port busy -> using free port {port}')
    boot = _start_boot_server()
    if boot is None:
        # سرورِ بوت بالا نیامد (مثلاً بستنِ localhost توسطِ امنیتی): همان
        # مسیرِ همیشگی، فقط بی‌صفحۀ پیشرفت.
        if not _preflight():
            _exit_preflight_failure()
            return 'preflight-failed'
        _start_uvicorn(port)
        if not wait_http(port):
            print('[ERR] server did not start')
            return 'http-never-came-up'
        print(f'[OK] http://127.0.0.1:{port}')
        url = f'http://127.0.0.1:{port}'
        if open_native_window(url):
            # تفکیکِ «چرا تمام شد»: نبودِ این سطر پیش از [exit] یعنی پنجرهٔ
            # بومی بسته نشد، بلکه خودِ پروسه از کار افتاد.
            _note('native window closed')
            return 'window-closed'  # پنجرهٔ بومی بسته شد → خروج
        open_app_window(url)
        return _hold_open()
    return _serve_with_boot(port, boot[1])


def _exit_preflight_failure():
    """v1.0.15: console=False → sys.stdin می‌تواند None باشد و input()
    با «RuntimeError: lost sys.stdin» کلِ برنامه را می‌کشد. فقط در
    حالتی که واقعاً کنسول هست منتظر می‌شویم."""
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input('Press Enter to close...')
        except Exception:
            pass


def _start_uvicorn(port):
    """uvicorn را در نخِ daemon بالا می‌آورد؛ ضربانِ زنده‌بودن هم همین‌جا."""
    import uvicorn

    def run():
        import logging
        # اخطارها (مثلاً FutureWarningِ pandas درِ مسیرِ تابلو) بی‌این خط سطرِ
        # بی‌ساعت می‌سازند؛ سروِ py.warnings درِ _log_config_with_clock ساعت دارد.
        logging.captureWarnings(True)
        uvicorn.run('app:app', host='127.0.0.1', port=port, log_level='info',
                    log_config=_log_config_with_clock())
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=_beat_loop, args=(port,), daemon=True).start()


def _bootstrap_worker(port, out):
    """نخِ سنگینِ مسیرِ بوت: اولِ دیتابیس (با گزارشِ پیشرفت)، بعدِ سرور، بعد
    تسلیمِ آدرس به صفحۀ بوت. نتیجه در `out` می‌نشیند تا نخِ اصلی بداند پنجره
    چرا بسته شده است."""
    if not _preflight(progress=_boot_progress):
        _boot_fail('پایگاهِ دادهٔ بازار ساخته نشد. اتصالِ اینترنت را بررسی کنید '
                   'و برنامه را دوباره باز کنید.')
        out['result'] = 'preflight-failed'
        return
    _boot_update(phase='serve')
    _start_uvicorn(port)
    if wait_http(port):
        print(f'[OK] http://127.0.0.1:{port}')
        _boot_ready(f'http://127.0.0.1:{port}/')
        out['result'] = 'serving'
    else:
        print('[ERR] server did not start')
        _boot_fail('سرورِ محلی بالا نیامد. فایلِ logs/bors.log را ببینید.')
        out['result'] = 'http-never-came-up'


def _hold_open():
    """پروسه را زنده نگه می‌دارد تا پنجرۀ مرورگر/سرور بمیرد؛ KeyboardInterrupt
    تنها خروجِ عادی است."""
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 'interrupted'
    return 'loop-ended'


def _serve_with_boot(port, boot_port):
    """پنجره را *همان لحظه* روی صفحۀ بوت باز می‌کند و کارِ سنگین را به نخِ
    worker می‌سپارد. صفحۀ بوت خودش وقتی سرورِ واقعی آماده شد آدرس را عوض
    می‌کند؛ سرورِ بوت تا پایانِ پروسه روی پورتِ آزاد می‌ماند (بی‌خطر: فقط یک
    صفحۀ ثابت و یک JSON می‌دهد)."""
    out = {}
    threading.Thread(target=_bootstrap_worker, args=(port, out), daemon=True).start()
    url = f'http://127.0.0.1:{boot_port}/'
    if open_native_window(url):
        _note('native window closed (boot worker: %s)'
              % (out.get('result') or 'never-finished'))
        return 'window-closed'
    open_app_window(url)
    # مسیرِ مرورگر: شکستِ قطعی پروسه را آزاد می‌کند، با مهلتی تا پیامِ خطا
    # رویِ صفحه بماند و خوانده شود (بی‌این‌جا نصبِ بی‌اینترنت بی‌صدا می‌مرد).
    for _ in range(600):
        if out.get('result'):
            break
        time.sleep(0.1)
    res = out.get('result')
    if res and res != 'serving':
        time.sleep(45)
        return res
    return _hold_open()


def main():
    # نشانِ [exit] بی‌این‌که خودِ لانچر بنویسد هرگز رویِ دیسک نمی‌آمد: پس از
    # بسته‌شدنِ پنجرهٔ بومی، .NET پروسه را می‌بندد و پایتون به قلابِ خروجِ
    # مفسر نمی‌رسد (سنجشِ لاگِ نصبی: ۱۰ اجرا و ۸ بارِ بستنِ پنجره، صفر سطرِ
    # [exit]). حالا «مُرد vs بسته شد» واقعاً سه‌حالتي می‌ماند.
    reason = 'returned'
    try:
        reason = _serve() or 'returned'
    finally:
        _note(f'[exit] process ending pid={os.getpid()} reason={reason}')

if __name__ == '__main__':
    main()
