"""آزمونِ مسیرِ به‌روزرسانی رویِ کپیِ ایزولۀ 1.0.83 (نه نصبِ واقعیِ کاربر).

کپی از ZIP پرتابیلِ v1.0.83 ساخته می‌شود و نشانۀ `bors_portable.flag` از آن
برداشته می‌شود، پس درِ همان پوشه مثلِ نسخۀ نصبی رفتار می‌کند (داده کنارِ EXE) و
آپدیترِ درون‌اپ مجاز به اجرای پچ است. هرچه ادعا می‌شود از همین اسکریپت می‌آید:
check → delta=true، دانلود، progress تا ready، هشِ فایلِ دانلودیِ برنامه با هشِ
دانلودِ مستقلِ همان دارایی، امضا با کلیدِ خودِ آپدیتِر، install، و در پایان
Version.txt/بیسِ فایل‌ها و دست‌نخورده‌بودنِ user.db و درختِ نسخۀ اصلیِ کاربر.

ثابت‌هایِ عددی (آدرسِ پچ، هش، اندازۀ اعلامی) از JSONِ راستی‌آزماییِ دارایی‌ها
خوانده می‌شود؛ چیزی دستی وارد نشده که با بایت‌هایِ واقعی نخوانده باشد.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

PORT = int(os.environ.get("PORT", "8124"))
FROM = os.environ.get("FROM", "1.0.83")
TO = os.environ.get("TO", "1.0.84")
COPY = os.environ.get("COPY", r"C:\Users\PCMOD\Desktop\up1084_verify\app")
ORIG = os.environ.get("ORIG", r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate")
VERIFY_JSON = os.environ.get("VERIFY_JSON", "_audit/up1084/assets_verify_v1.0.84.json")
OUT = os.environ.get("OUT", f"_audit/up1084/update_path_{FROM}_to_{TO}.json")
GIT_COMMIT = os.environ.get("GIT_COMMIT", "9546c81")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.update import UPDATE_PUBKEY                      # noqa: E402
from bors_minisign import verify_minisign                 # noqa: E402

V = json.load(open(VERIFY_JSON, encoding="utf-8"))
patch_name = f"BorsTerminal_Patch_{FROM}_to_{TO}.zip"
row = next(a for a in V["assets"] if a["name"] == patch_name)
ASSET, EXPECTED_SHA_REMOTE, DECLARED_SIZE = row["url"], row["sha256_local"], row["bytes_local"]
assert row["signature_ok"] is True, "دارایی درِ مرحلهٔ پیش امضایش تأیید نشده است"

R = {"port": PORT, "copy": COPY, "from": FROM, "to": TO, "asset": ASSET, "steps": []}


def api(path, method="GET", body=None, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 headers={"User-Agent": "probe", "Content-Type": "application/json"})
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def step(name, ok, detail=""):
    R["steps"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("  ok   " if ok else "  FAIL ") + name + ("  " + str(detail)[:150] if detail else ""))
    return ok


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stat(p):
    s = os.stat(p)
    return {"size": s.st_size, "mtime": int(s.st_mtime)}


def tree_sig(root):
    """اثرِ انگشتِ نام/size/mtimeِ درخت (بی‌خواندنِ بانک‌ها) — برایِ اثباتِ بی‌تغیری."""
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            if rel.startswith("market.db"):
                continue
            s = os.stat(p)
            out[rel] = (s.st_size, int(s.st_mtime))
    return hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()[:16], len(out)


def user_rows(db):
    """ردیف‌هایِ خودِ user.db (از اتصالِ خواندنیِ تازه) — ثابت می‌کند دادۀ کاربر
    فقط «دست‌نخورده» نیست بلکه همان سطرها بعد از پچ هم خوانده می‌شوند."""
    if not os.path.isfile(db):
        return None
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("SELECT symbol, note FROM user_watchlists ORDER BY symbol").fetchall()
    except sqlite3.Error:
        return "unreadable"
    finally:
        con.close()


# ۰) آمادگی: کپی بالا آمده؟ نسخۀ درست است؟
t0 = time.time()
ver = None
while time.time() - t0 < 300:
    try:
        ver = api("/api/update/version", timeout=5)
        break
    except Exception:
        time.sleep(3)
step(f"کپیِ {FROM} رویِ پورتِ {PORT} بالا آمد", ver is not None, ver)
step(f"نسخۀ در حالِ اجرا {FROM} است (پیش از پچ)", (ver or {}).get("version") == FROM, ver)
step("کپی در حالتِ نصبی است نه پرتابیل (آپدیتر مجاز به پچ)",
     (ver or {}).get("mode") != "portable", {"mode": (ver or {}).get("mode")})

pre = {"user_db": stat(os.path.join(COPY, "user.db")),
       "rows": user_rows(os.path.join(COPY, "user.db")),
       "screener_cache": stat(os.path.join(COPY, ".screener_cache.json"))
       if os.path.isfile(os.path.join(COPY, ".screener_cache.json")) else None,
       "orig_tree": tree_sig(ORIG)}
R["pre"] = pre
step("user.dbِ کپی ردیفِ کاربر دارد (پیش از پچ خوانده شد)", bool(pre["rows"]), pre["rows"])
step("درختِ نسخۀ اصلیِ کاربر برایِ مقایسه مهر شد", pre["orig_tree"][1] > 1000, pre["orig_tree"])

# ۱) check — باید دلتا را انتخاب کند، نه نصبکننده
chk = api("/api/update/check")
R["check"] = chk
step(f"check نسخهٔ {TO} را اعلام می‌کند", chk.get("available") is True
     and chk.get("latest_version") == TO, {k: chk.get(k) for k in ("available", "latest_version")})
step("check پچِ دلتا را به نصبِ کامل ترجیح می‌دهد (delta=true)", chk.get("delta") is True,
     {"delta": chk.get("delta"), "url_tail": (chk.get("url") or "")[-46:]})
step(f"همان URLِ پچِ {FROM}→{TO} درِ مانیفستِ عمومی است",
     (chk.get("url") or "").endswith(patch_name), chk.get("url"))
step("اندازۀ اعلامی با اندازۀ دانلودِ مستقل یکی است", int(chk.get("size") or 0) == DECLARED_SIZE,
     {"check": chk.get("size"), "independent": DECLARED_SIZE})

# ۲) دانلود + پیشرفت
api("/api/update/download", method="POST",
    body={"url": chk["url"], "signature": chk["signature"], "version": TO})
prog = None
t0 = time.time()
while time.time() - t0 < 420:
    prog = api("/api/update/progress")
    if prog.get("status") in ("ready", "error"):
        break
    time.sleep(2)
R["progress"] = prog
step("download به حالتِ ready رسید (امضا و هش درِ سرور راستیآزمایی شد)",
     prog.get("status") == "ready", {k: prog.get(k) for k in ("status", "downloaded", "total", "version")})

tmp = prog.get("path") or ""
step("فایلِ موقتِ دانلودی رویِ دیسک هست و sizeاش با مانیفست می‌خواند",
     bool(tmp) and os.path.isfile(tmp) and os.path.getsize(tmp) == DECLARED_SIZE,
     {"path": tmp, "bytes": os.path.getsize(tmp) if tmp and os.path.isfile(tmp) else None})

if tmp and os.path.isfile(tmp):
    local_sha = sha(tmp)
    step("هشِ فایلِ دانلودیِ برنامه = هشِ دانلودِ مستقلِ همان دارایی",
         local_sha == EXPECTED_SHA_REMOTE, local_sha)
    sig_text = chk.get("signature") or ""
    try:
        verify_minisign(open(tmp, "rb").read(), sig_text, UPDATE_PUBKEY)
        step("امضایِ minisignِ پچ با کلیدِ عمومیِ خودِ آپدیتِر تأیید شد", True, "verify_minisign ok")
    except Exception as e:
        step("امضایِ minisignِ پچ با کلیدِ عمومیِ خودِ آپدیتِر تأیید شد", False, repr(e)[:160])

# ۳) install — برنامه می‌میرد و apply_update.bat کار می‌کند (BORS_UPDATE_NORELAUNCH
#    درِ محیطِ پروسه set شده، پس relaunch نمی‌کند و چیزی بیرونِ کنترلِ ما بالا نمیآید)
try:
    ins = api("/api/update/install", method="POST", body={}, timeout=60)
except Exception as e:
    ins = {"status": "connection-reset", "message": str(e)[:120]}
R["install"] = ins
step("install پذیرفته شد (پاسخ یا resetِ عمدیِ پایانِ پروسه)",
     ins.get("status") in ("installing", "started", "connection-reset") or "spawn" in json.dumps(ins),
     {k: ins.get(k) for k in ("status", "mode", "message")})

# ۴) صبر برایِ اعمالِ پچ، بعد بررسیِ Version.txt و فایلها
t0 = time.time()
stamp = ""
while time.time() - t0 < 300:
    try:
        stamp = open(os.path.join(COPY, "Version.txt"), encoding="utf-8", errors="replace").read()
        if f"app_version={TO}" in stamp:
            break
    except OSError:
        pass
    time.sleep(3)
R["version_txt"] = stamp.strip()
step(f"Version.txt درِ کپی مهرِ {TO} را گرفت", f"app_version={TO}" in stamp,
     stamp.strip().replace("\n", " | "))
step("patch_from و git_commitِ درست مهر شده‌اند",
     f"patch_from={FROM}" in stamp and GIT_COMMIT in stamp, stamp.strip().replace("\n", " | "))

# درِ بیلدِ فریزشده (onedir) فایلِ `_internal/bors_config.py` وجود ندارد، پس
# سنجۀ پیشین همیشه «خوانده نشد» می‌داد و یک قرمزِ ساختگی درِ شواهد می‌گذاشت.
# نسخه را یا از فایلِ منبع می‌خوانیم (اجرایِ dev) یا از خودِ اپِ وصله‌خورده
# (با BOOT=1): بالا می‌آوریم، از اندپوینتِ زنده می‌خوانیم، و فقط PIDی را می‌کشیم
# که خودمان بالا آورده‌ایم. بی‌BOOT=1 این سنجه «سنجیده نشد» می‌ماند، نه «رد».
bc = os.path.join(COPY, "_internal", "bors_config.py")
if not os.path.isfile(bc):
    bc = os.path.join(COPY, "bors_config.py")
if os.path.isfile(bc):
    code = open(bc, encoding="utf-8", errors="replace").read()
    step(f"bors_config درِ کپی هم {TO} می‌گوید (لنگرِ نسخه با Version.txt میخواند)",
         f'APP_VERSION = "{TO}"' in code, "bors_config.py")
elif (os.environ.get("BOOT") or "").strip() == "1":
    import subprocess
    boot_port = int(os.environ.get("BOOT_PORT", str(PORT + 1)))
    exe = os.path.join(COPY, "BorsTerminal_Ultimate.exe")
    proc = subprocess.Popen([exe], cwd=COPY,
                            env=dict(os.environ, BORS_PORT=str(boot_port),
                                     BORS_NO_FETCH_LOOPS="1"),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    seen = None
    try:
        for _ in range(75):
            time.sleep(2)
            try:
                seen = api("/api/update/version", timeout=15).get("version")
                if seen:
                    break
            except Exception:
                continue
    finally:
        proc.kill()          # فقط همین PID — هرگز نامِ تصویر را نمی‌کشیم
    step(f"اپِ وصله‌خورده واقعاً بالا می‌آید و {TO} را اعلام می‌کند (پورتِ {boot_port})",
         seen == TO, f"version={seen}")
    R["boot"] = {"port": boot_port, "version": seen, "pid": proc.pid}
else:
    R["steps"].append({"name": f"نسخۀ {TO} درِ بیلدِ فریزشده از اندپوینتِ زنده",
                       "ok": None, "skipped": True,
                       "detail": "بیلدِ onedir بی‌bors_config.py است؛ با BOOT=1 سنجیده می‌شود"})
    print(f"  skip اپِ وصله‌خورده سنجیده نشد (بیلدِ فریزشده بی‌bors_config.py؛ BOOT=1)")

post = {"user_db": stat(os.path.join(COPY, "user.db")),
        "rows": user_rows(os.path.join(COPY, "user.db")),
        "screener_cache": stat(os.path.join(COPY, ".screener_cache.json"))
        if os.path.isfile(os.path.join(COPY, ".screener_cache.json")) else None,
        "orig_tree": tree_sig(ORIG)}
R["post"] = post
step("user.dbِ کاربر درِ کپی دست نخورد (size و mtime یکی ماند)",
     post["user_db"] == pre["user_db"], {"pre": pre["user_db"], "post": post["user_db"]})
step("همان سطرها بعد از پچ از اتصالِ تازه خوانده شدند (دادۀ کاربر زنده ماند)",
     post["rows"] == pre["rows"] and bool(post["rows"]),
     {"pre": pre["rows"], "post": post["rows"]})
step("تنظیم/کشِ کاربر (.screener_cache.json) دست نخورد",
     post["screener_cache"] == pre["screener_cache"],
     {"pre": pre["screener_cache"], "post": post["screener_cache"]})
step("درختِ نسخۀ اصلیِ کاربر اصلاً تغییر نکرد (مهرِ پیش = مهرِ پس)",
     post["orig_tree"] == pre["orig_tree"], {"pre": pre["orig_tree"], "post": post["orig_tree"]})

json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ok = sum(1 for s in R["steps"] if s["ok"])
measured = sum(1 for s in R["steps"] if s.get("ok") is not None)
skipped = len(R["steps"]) - measured
print(f"\n{ok}/{measured} سنجیده‌شده" + (f"، {skipped} سنجیده‌نشده" if skipped else "")
      + f" — {OUT}")
sys.exit(0 if ok == measured else 1)
