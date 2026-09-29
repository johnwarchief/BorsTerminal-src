# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess, atexit

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
    """پوشهٔ داده‌ها: کنارِ EXE، یا _internal در بیلدِ onedir.

    v1.0.15: PyInstaller در onedir تمامِ datas را در _internal می‌گذارد،
    نه کنارِ EXE. جستجویِ نسبیِ market.db فقط cwd را می‌بیند و رویِ
    نصبِ تمیز شکست می‌خورد («market.db not found»).
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    for cand in (base, os.path.join(base, "_internal")):
        if os.path.isfile(os.path.join(cand, "market.db")) or \
           os.path.isfile(os.path.join(cand, "market.db.lzma")):
            return cand
    return base


def _preflight():
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
        db = bors_config.ensure_market_db(verbose=True)
    except Exception as e:
        print("  [ERR] ensure_market_db failed:", e)
        db = os.path.join(_data_root(), "market.db")
        ok = False
    root = _data_root()
    print(f"  data root: {root}")
    if not os.path.exists(db):
        print("  [ERR] market.db not found next to this EXE.")
        print("        Keep market.db/.lzma in the SAME folder as the EXE")
        print("        (it is inside the release ZIP, extract all files together).")
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

def main():
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
            return
        open_app_window(url)
        return
    if port_open(port):
        # پورت اشغال است ولی سرورِ ما نیست → پورت آزادِ دیگر
        port = pick_free_port(port)
        print(f'[OK] port busy -> using free port {port}')
    if not _preflight():
        # v1.0.15: console=False → sys.stdin می‌تواند None باشد و input()
        # با «RuntimeError: lost sys.stdin» کلِ برنامه را می‌کشد. فقط در
        # حالتی که واقعاً کنسول هست منتظر می‌شویم.
        if sys.stdin is not None and sys.stdin.isatty():
            try:
                input('Press Enter to close...')
            except Exception:
                pass
        return
    import uvicorn
    def run():
        import logging
        # اخطارها (مثلاً FutureWarningِ pandas درِ مسیرِ تابلو) بی‌این خط سطرِ
        # بی‌ساعت می‌سازند؛ سروِ py.warnings درِ _log_config_with_clock ساعت دارد.
        logging.captureWarnings(True)
        uvicorn.run('app:app', host='127.0.0.1', port=port, log_level='info',
                    log_config=_log_config_with_clock())
    th = threading.Thread(target=run, daemon=True)
    th.start()
    atexit.register(lambda: _note(f'[exit] process ending (pid={os.getpid()})'))
    threading.Thread(target=_beat_loop, args=(port,), daemon=True).start()
    if wait_http(port):
        print(f'[OK] http://127.0.0.1:{port}')
        url = f'http://127.0.0.1:{port}'
        if open_native_window(url):
            # تفکیکِ «چرا تمام شد»: نبودِ این سطر پیش از [exit] یعنی پنجرهٔ
            # بومی بسته نشد، بلکه خودِ پروسه از کار افتاد.
            _note('native window closed')
            return  # پنجرهٔ بومی بسته شد → خروج
        open_app_window(url)
    else:
        print('[ERR] server did not start')
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
