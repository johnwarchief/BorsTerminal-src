# -*- coding: utf-8 -*-
"""
dev/log_clock_guard_v1055.py — گاردِ «لاگ باید قابلِ داوری باشد».

سه چیز را می‌سنجد، هرکدام با کنترلِ منفیِ خودِش (اگر کنترلی با همان کدِ معیوب
سبز بماند، آن گارد بی‌ارزش است و اینجا همین را رد می‌کند):

  ۱) خط‌به‌خط بودنِ لاگ: سطرِ آخرِ پیش از مرگِ ناگهانیِ پروسه باید رویِ دیسک
     باشد. کنترلِ منفی: همان تست با بافرِ بلوکیِ پیش‌فرض، که سطر را گم می‌کند.
  ۲) پیکربندیِ لاگِ uvicorn باید %(asctime)s داشته باشد و رویِ سطرِ خروجی
     واقعاً ساعت چاپ شود. کنترلِ منفی: پیکربندیِ بی‌زمانِ پیش‌فرض.
  ۳) نشانِ [exit] و [beat] باید چاپ شوند.

اجرا:  python dev/log_clock_guard_v1055.py     (خروجی: PASS/FAIL و کدِ خروج)
"""
from __future__ import annotations

import io
import logging
import logging.config
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


# ── ۱) آیا سطرِ آخر پس از مرگِ ناگهانی می‌ماند؟ ────────────────────────────
_CHILD = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
import bors_entry as be
be.WORK = sys.argv[2]
buf = int(sys.argv[3])          # -1 = پیش‌فرضِ بلوکی (کنترلِ منفی)
_real_open = open
be.open = lambda *a, **k: _real_open(*a, **{**k, 'buffering': buf})
be._setup_streams()
print('LAST-LINE-MARKER-BEFORE-DEATH')
os._exit(9)                      # مرگِ بدونِ پاک‌سازیِ بافر
"""


def _spawn(mode_buf):
    d = tempfile.mkdtemp(prefix="bors_log_guard_")
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    p = os.path.join(tempfile.gettempdir(), "bors_log_guard_child.py")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(_CHILD)
    # BORS_SHOW_CONSOLE را باید حذف کنیم: با آن _setup_streams اصلاً فایلی
    # نمی‌سازد و تستِ بافر بی‌محتوا می‌شود (دیده‌شده: با این متغیر در محیط،
    # نسخهٔ خط‌به‌خط هم «FAIL» می‌داد، بی‌هیچ ربطی به کد).
    env = {k: v for k, v in os.environ.items() if k != "BORS_SHOW_CONSOLE"}
    subprocess.run([sys.executable, p, REPO, d, str(mode_buf)],
                   capture_output=True, timeout=60, env=env)
    log = os.path.join(d, "logs", "bors.log")
    txt = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    return "LAST-LINE-MARKER-BEFORE-DEATH" in txt


line_survives = _spawn(1)
line_survives_blockbuffered = _spawn(-1)
check("سطرِ آخر با killِ ناگهانی حفظ می‌شود (buffering=1)", line_survives)
check("کنترلِ منفی: بافرِ بلوکی همان سطر را گم می‌کند",
      not line_survives_blockbuffered,
      "اگر این هم حفظ شد، تستِ بالا چیزی را اثبات نمی‌کند")

# ── ۲) ساعت در لاگِ uvicorn ────────────────────────────────────────────────
import bors_entry as be  # noqa: E402

cfg = be._log_config_with_clock()
check("پیکربندیِ لاگ برای هر دو قالب ساعت دارد",
      "%(asctime)s" in cfg["formatters"]["default"]["fmt"]
      and "%(asctime)s" in cfg["formatters"]["access"]["fmt"])

_old_stderr, _old_stdout = sys.stderr, sys.stdout
buf_err, buf_out = io.StringIO(), io.StringIO()
sys.stderr, sys.stdout = buf_err, buf_out
try:
    logging.config.dictConfig(cfg)
    logging.getLogger("uvicorn.error").info("clock-probe")
finally:
    sys.stderr, sys.stdout = _old_stderr, _old_stdout
default_line = (buf_err.getvalue() + buf_out.getvalue()).strip().splitlines()[:1]


def _starts_with_clock(line):
    return len(line) >= 19 and line[:4].isdigit() and line[4] == "-" and line[7] == "-"


check("سطرِ uvicorn.error با ساعت شروع می‌شود",
      bool(default_line) and _starts_with_clock(default_line[0]), repr(default_line[:1]))

# سطرِ دسترسی (access) قالبِ خودش را دارد و باید جدا سنجیده شود؛ یک رکوردِ
# معمولی آن را رد می‌کند چون AccessFormatter فیلدهایِ client_addr/request_line
# را می‌خواهد. (اشتباهِ قبلیِ همین گارد: بی‌این فیلدها «Logging error» می‌داد و
# ساعت از سطرِ دیگر خوانده می‌شد — یعنی گارد چیزی را که می‌گفت اثبات نمی‌کرد.)
# AccessFormatter پنج‌تایی می‌خواهد: (client_addr, method, full_path,
# http_version, status_code) — و خودش request_line را می‌سازد.
rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                        '%s - "%s %s HTTP/%s" %s', None, None)
rec.args = ("127.0.0.1:1234", "GET", "/api/market", "1.1", 200)
from uvicorn.logging import AccessFormatter  # noqa: E402
access_line = AccessFormatter(fmt=cfg["formatters"]["access"]["fmt"],
                              datefmt=cfg["formatters"]["access"]["datefmt"],
                              use_colors=False
                              ).format(rec)
check("سطرِ access هم با ساعت شروع می‌شود", _starts_with_clock(access_line),
      repr(access_line[:56]))

# ── ۳) نشان‌ها ──────────────────────────────────────────────────────────────
_o = sys.stdout
sys.stdout = _c = io.StringIO()
try:
    be._note("probe")
finally:
    sys.stdout = _o
out = _c.getvalue()
check("_note() سطرِ زمان‌دارِ [app] چاپ می‌کند",
      out.startswith("20") and "[app] probe" in out, repr(out[:40]))

uv_src = open(os.path.join(REPO, "bors_entry.py"), encoding="utf-8").read()
check("atexit نشانِ [exit] را ثبت کرده است", "atexit.register" in uv_src
      and "[exit] process ending" in uv_src)
check("حلقۀ [beat] برایِ تفکیکِ «مرگ» از «بازارِ بسته» فعال است",
      "_beat_loop" in uv_src and "target=_beat_loop" in uv_src)
check("پنجرهٔ بومی هنگامِ بسته شدن علامت می‌زند",
      "native window closed" in uv_src)

print(f"\n{len(PASS)} pass / {len(FAIL)} fail")
sys.exit(1 if FAIL else 0)
