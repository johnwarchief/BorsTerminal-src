"""
v9.7.2 — گارد تاب‌آوری لایهٔ ADB در codal_fetcher

چرا این تست لازم است: چرخش IP با ADB تنها راه فرار از بن ۴۲۹ روی IP سلولی است
و کد آن پیش‌تر سه رفتار خطرناک داشت که هیچ‌کدام تست نمی‌شد:
  ۱) دستگاه offline/unauthorized مثل «دستگاه نیست» رد می‌شد (بدون احیا).
  ۲) خطای غیرمنتظره میانِ توگل، Wi-Fi میزبان را خاموش رها می‌کرد.
  ۳) کارگر دوم روی قفلِ ۲ دقیقه‌ای می‌خوابید (فریز ترد اسکن).

اجرا:  python dev/adb_resilience_v972.py
هیچ adb/گوشی/شبکه‌ای لازم نیست — همهٔ مرزها جعل می‌شوند.
"""
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as cf  # noqa: E402

# ارجاع اصلیِ توابع — هر تست که چیزی را جایگزین کند، reset() این‌ها را برمی‌گرداند.
_ORIG_FIND_ADB = cf._find_adb
_ORIG_ADB_RUN = cf._adb_run
_ORIG_ADB_DEVICES = cf._adb_devices
_ORIG_ADB_WAIT = cf._adb_wait_ready
_ORIG_ADB_RESTART = cf._adb_restart_server

PASS = FAIL = 0


def say(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")


class CP:
    """جای‌نمای subprocess.CompletedProcess."""
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class FakeTime:
    def __init__(self, start=10_000.0):
        self.now = start
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


class FakeSub:
    """فراخوانی‌های subprocess.run را ضبط می‌کند تا PowerShellها دیده شوند."""
    CREATE_NO_WINDOW = 0x08000000

    def __init__(self):
        self.calls = []

    def run(self, cmd, **kw):
        self.calls.append(list(cmd))
        return CP(0, "", "")

    def ps(self):
        return [" ".join(c) for c in self.calls if c and "powershell" in str(c[0]).lower()]


DEV = "List of devices attached\nRFCT30KRY6D\tdevice\n\n"
UNAUTH = "List of devices attached\nRFCT30KRY6D\tunauthorized\n\n"
OFFLINE = "List of devices attached\nRFCT30KRY6D\toffline\n\n"
NONE = "List of devices attached\n\n"


def reset(enabled=True):
    """وضعیت ماژول را به حالت قابل‌تست برمی‌گرداند.

    توابعی که در تست‌های پیشین جایگزین شده‌اند حتماً باید بازگردانده شوند،
    وگرنه تست بعدی روی lambdaِ تست قبلی اجرا می‌شود (منبع یک FAIL گمراه‌کننده).
    """
    cf._ADB_ROTATED_AT = 0.0
    cf._ADB_CMD = None
    cf.time = FakeTime()
    cf.subprocess = FakeSub()
    cf._find_adb = _ORIG_FIND_ADB
    cf._adb_run = _ORIG_ADB_RUN
    cf._adb_devices = _ORIG_ADB_DEVICES
    cf._adb_wait_ready = _ORIG_ADB_WAIT
    cf._adb_restart_server = _ORIG_ADB_RESTART
    cf._adb_enabled = lambda: enabled
    return cf


def queue_devices(*outs):
    """خروجی «adb devices» را به ترتیب برمی‌گرداند."""
    seq = list(outs)
    seen = {"n": 0}

    def fake(adb, args, timeout=10, tries=1):
        if list(args) == ["devices"]:
            i = min(seen["n"], len(seq) - 1)
            seen["n"] += 1
            out = seq[i]
            return CP(0, out, "") if out is not None else None
        return CP(0, "", "")

    cf._adb_run = fake
    return seen


# ─────────────── ۱) دسته‌بندی وضعیت دستگاه ───────────────
reset()
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, DEV, "")
say(cf._adb_devices("adb") == (["RFCT30KRY6D"], [], []), "state 'device' -> ready")
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, UNAUTH, "")
say(cf._adb_devices("adb") == ([], ["RFCT30KRY6D"], []), "state 'unauthorized' -> RSA bucket")
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, OFFLINE, "")
say(cf._adb_devices("adb") == ([], [], ["RFCT30KRY6D"]), "state 'offline' -> offline bucket")
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, NONE, "")
say(cf._adb_devices("adb") == ([], [], []), "empty device list -> all empty")
cf._adb_run = lambda adb, args, timeout=10, tries=1: None
say(cf._adb_devices("adb") == ([], [], []), "adb dead (None) -> no crash, all empty")

# ─────────────── ۲) حلقهٔ Retry + Re-connect ───────────────
reset()
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, DEV, "")
say(cf._adb_wait_ready("adb", quiet=True) == "RFCT30KRY6D",
    "ready device -> serial on first try")

reset()
restarts = []
cf._adb_restart_server = lambda adb, quiet=False: restarts.append(1)
queue_devices(OFFLINE, DEV)
say(cf._adb_wait_ready("adb", quiet=True) == "RFCT30KRY6D",
    "offline then device -> recovered via retry loop")
say(len(restarts) == 1, "offline triggered exactly one adb-server restart")

reset()
restarts = []
cf._adb_restart_server = lambda adb, quiet=False: restarts.append(1)
queue_devices(UNAUTH, UNAUTH, DEV)
say(cf._adb_wait_ready("adb", quiet=True) == "RFCT30KRY6D",
    "unauthorized -> re-pinged and eventually accepted")
say(len(restarts) == 2, "each unauthorized round restarts the server")

reset()
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, NONE, "")
say(cf._adb_wait_ready("adb", quiet=True, tries=3) is None,
    "no device at all -> None after exhausting tries")
say(sum(1 for s in cf.time.slept if abs(s - cf._ADB_RETRY_DELAY) < 1e-9) == 2,
    "no-device path re-pings with a delay instead of hard-failing")

# ─────────────── ۳) درِ ورودی rotate_ip_via_adb ───────────────
reset(enabled=False)
say(cf.rotate_ip_via_adb(quiet=True) is False, "user toggle off -> no rotation")

reset()
cf._find_adb = lambda: None
say(cf.rotate_ip_via_adb(quiet=True) is False, "adb binary missing -> falls back to backoff")

reset()
cf._find_adb = lambda: "adb"
cf._ADB_ROTATED_AT = cf.time.monotonic()
say(cf.rotate_ip_via_adb(quiet=True) is True,
    "rotation inside MIN_GAP -> reports fresh IP, no second toggle")

# ─────────────── ۴) تضمین بازگشت Wi-Fi (رفع خطر قطع اینترنت) ───────────────
def wifi_restore_case(label, break_where):
    reset()
    cf._find_adb = lambda: "adb"
    cf._adb_wait_ready = lambda adb, quiet=False: "RFCT30KRY6D"

    def boom(adb, args, timeout=10, tries=1):
        if break_where(list(args)):
            raise RuntimeError("cable yanked mid-toggle")
        return CP(0, "", "")

    cf._adb_run = boom
    r = cf.rotate_ip_via_adb(quiet=True)
    ps = cf.subprocess.ps()
    re_en = [p for p in ps if "Enable-NetAdapter" in p and "Wi-Fi" in p]
    dis = [p for p in ps if "Disable-NetAdapter" in p and "Wi-Fi" in p]
    say(r is False, f"{label}: returns False (falls back to backoff)")
    say(bool(dis), f"{label}: Wi-Fi was disabled during rotation")
    say(bool(re_en), f"{label}: Wi-Fi RESTORED afterwards (no orphan outage)")


wifi_restore_case("exception during airplane-enable",
                  lambda a: "airplane-mode" in a and "enable" in a)
wifi_restore_case("exception during airplane-disable",
                  lambda a: "airplane-mode" in a and "disable" in a)

reset()
cf._find_adb = lambda: "adb"
cf._adb_wait_ready = lambda adb, quiet=False: "RFCT30KRY6D"
cf._adb_run = lambda adb, args, timeout=10, tries=1: (
    CP(1, "", "rejected") if "airplane-mode" in list(args) else CP(0, "", ""))
say(cf.rotate_ip_via_adb(quiet=True) is False, "airplane command rejected -> False")
say(any("Enable-NetAdapter" in p for p in cf.subprocess.ps()),
    "airplane rejection still restores Wi-Fi")

# ─────────────── ۵) قفل غیرهمبلوک (ضد فریز ترد) ───────────────
reset()
cf._find_adb = lambda: "adb"
cf._adb_wait_ready = lambda adb, quiet=False: "RFCT30KRY6D"
cf._adb_run = lambda adb, args, timeout=10, tries=1: CP(0, "", "")
cf._ADB_LOCK.acquire()          # یک کارگر در حال چرخش فرض می‌شود
try:
    done = {}
    t = threading.Thread(target=lambda: done.update(val=cf.rotate_ip_via_adb(quiet=True)))
    t.start()
    t.join(timeout=2.0)
    say(not t.is_alive(), "second worker returns promptly instead of blocking on the lock")
    say(done.get("val") is True, "second worker reports 'fresh IP coming' (True)")
finally:
    if cf._ADB_LOCK.locked():
        cf._ADB_LOCK.release()

# ─────────────── ۶) اعتبار مسیر کش‌شدهٔ adb ───────────────
reset()
cf._ADB_CMD = r"C:\definitely\not\here\adb.exe"
cf._find_adb()
say(cf._ADB_CMD != r"C:\definitely\not\here\adb.exe",
    "stale cached adb path is invalidated and re-searched")

total = PASS + FAIL
print(f"\n{total - FAIL}/{total} passed")
sys.exit(1 if FAIL else 0)

