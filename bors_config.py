"""bors_config.py -- paths and FTS threshold defaults shared by api/*.

Split verbatim out of app.py so the router modules no longer need the app
object just to reach a constant. Resolved relative to APP_DIR (repo root,
which is also where the packaged EXE expects market.db / *.json).
"""
import os
import sys


_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    """در حالت EXE: دیتاهای فقط‌خواندنی باندل در _MEIPASS (onedir: _internal)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base and os.path.isdir(base):
            return base
    return _SRC_DIR


def _writable(path):
    """آیا می‌توان در این مسیر فایل نوشت؟ (Program Files برای کاربر عادی: خیر)"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".wtprobe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _user_data_dir():
    """%LOCALAPPDATA%\\BorsTerminal_Ultimate — داده‌های قابل‌نوشتنِ هر کاربر."""
    return os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "BorsTerminal_Ultimate", "data")


def _work_dir():
    """مسیر نوشتن فایل‌های وضعیت/تنظیمات.

    در حالت EXE اولویت با پوشهٔ کنار باینری است (حالت پرتابیل: وقتی ZIP را
    در یک پوشهٔ نوشتنی باز می‌کنید همان‌جا کار می‌کند)، اما اگر آن پوشه
    نوشتنی نباشد (نصب در Program Files با PrivilegesRequired=admin) تمام
    داده‌های کاربر به %LOCALAPPDATA%\\BorsTerminal_Ultimate منتقل می‌شوند؛
    در غیر این صورت استخراج market.db.lzma و سینک بازار با «Permission
    denied» گیر می‌کنند. در حالت dev همان ریشهٔ ریپو است.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if _writable(exe_dir):
            return exe_dir
        return _user_data_dir()
    return _SRC_DIR


APP_DIR = _app_dir()
WORK_DIR = _work_dir()

def _db_has_codal(path):
    """True اگر این market.db دادهٔ کدال دارد (financial_statements/monthly_sales).

    v1.0.16: همگام‌سازیِ زندهٔ تابلو یک market.db کوچک می‌سازد که فقط
    instruments/market_watch دارد و صورت‌های مالی درش نیستند. بدون این
    بررسی، آن فایلِ تهی از کدال بر فایلِ ۹۵ مگابایتیِ باندل‌شده ترجیح
    داده می‌شود و کلِ تب بنیادی «بدون داده» می‌ماند.
    """
    try:
        import sqlite3 as _sq
        con = _sq.connect(f"file:{path}?mode=ro", uri=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
            return int(n or 0) > 0
        finally:
            con.close()
    except Exception:
        return False


def _resolve_market_db():
    """مسیر market.db: فایل موجود، وگرنه مسیر برنامه‌ریزی‌شده برای استخراج.

    خودِ استخراج (حدود ۴۰ ثانیه) به ensure_market_db() موکول شده تا
    bors_entry در preflight پیشرفت را به کاربر نشان دهد؛ اینجا فقط مسیر
    نهایی را تعیین می‌کنیم. جستجو شامل کنار EXE (محل نصب)، WORK_DIR و
    مسیرهای نسبی (dev) می‌شود. کنارِ EXE فقط در صورتی انتخاب می‌شود که
    پوشهٔ نصب نوشتنی باشد؛ در غیر این صورت WAL نمی‌تواند -wal/-shm بسازد.
    """
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _SRC_DIR
    # ۱) market.db از قبل موجود (پرتابیل کنار EXE / دادهٔ کاربر / dev).
    # exe_dir فقط وقتی در نظر گرفته می‌شود که نوشتنی باشد: در نصبِ
    # all-users پوشهٔ نصب فقط‌خواندنی است و sqlite برای WAL باید -wal/-shm
    # را کنارِ db بسازد که ممکن نیست → «unable to open database file» روی
    # هر اتصال. مثلِ _work_dir() از exe_dirِ غیرنوشتنی صرف‌نظر می‌کنیم.
    dirs = [exe_dir, WORK_DIR] if _writable(exe_dir) else [WORK_DIR]
    # v1.0.16: در بیلدِ onedir، PyInstaller داده‌ها را در _internal می‌گذارد.
    # اگر آنجا market.db با دادهٔ کدال هست، باید بر فایلِ کوچکِ کنارِ EXE
    # (که همگام‌سازیِ زندهٔ تابلو می‌سازد) ارجح باشد.
    if getattr(sys, "frozen", False):
        internal = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal):
            dirs.append(internal)
    for d in dirs:
        p = os.path.join(d, "market.db")
        if os.path.exists(p) and _db_has_codal(p):
            return p
    # هیچ کدام دادهٔ کدال نداشتند: فایلِ موجود را برگردان (همگام‌سازیِ زنده
    # هنوز در حال نوشتنش است) تا ensure_market_db() بعداً استخراج کند.
    for d in dirs:
        p = os.path.join(d, "market.db")
        if os.path.exists(p):
            return p
    if not getattr(sys, "frozen", False):
        for p in ("market.db", "../market.db"):
            if os.path.exists(p):
                return p
    # ۲) مسیر برنامه‌ریزی‌شده برای استخراج (همیشه در WORK_DIR نوشتنی)
    return os.path.join(WORK_DIR, "market.db")


DB_PATH = _resolve_market_db()

# جدول‌هایی از market.db که نوشتهٔ خودِ کاربرند، نه دادهٔ بازار. هنگامِ
# جایگزینیِ baseline این‌ها از فایلِ قدیمی به فایلِ تازه منتقل می‌شوند؛ در غیر
# این صورت یک ارتقای ساده، واچ‌لیست و تصمیماتِ کاربر را پاک می‌کرد.
MARKET_DB_USER_TABLES = ("user_watchlists", "selection_decisions")

# جدول‌های «مراجع»: معناشان را خودِ baseline تعریف می‌کند (نامِ شرکت، تالار،
# صنعت). اگر محلی برنده بماند، یک اصلاحِ داده درِ نسخهٔ جدید هرگز به کاربر
# نمی‌رسد — همان چیزی که dev/test_cumulative_db_v1020.py می‌خواست ثابت کند.
# بقیهٔ جدول‌های بازار «واقعاً» محلی‌اند: ردیف‌هایی که برنامه خودش سینک کرده
# نباید درِ یک ارتقا با نسخهٔ قدیمی‌تر جایگزین شوند.
_MARKET_REF_TABLES = ("instruments", "boards", "symbol_sectors")

_REQUIRED_MARKET_TABLES = {"instruments", "daily_prices", "financial_statements"}


def _market_db_tables(path):
    """مجموعهٔ جدول‌های یک فایل DB (بدون نوشتن). خطا ⇒ مجموعهٔ خالی."""
    try:
        import sqlite3 as _sq
        probe = _sq.connect("file:%s?mode=ro" % path, uri=True)
        try:
            return {r[0] for r in probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            probe.close()
    except Exception:
        return set()


def _sha256_file(path, chunk=1 << 20):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


MARKET_DATA_RELEASE_TAG = "data-latest"
MARKET_DATA_RELEASE_BASE = (
    "https://github.com/johnwarchief/BorsTerminal/releases/download/"
    + MARKET_DATA_RELEASE_TAG + "/"
)
MARKET_DATA_RELEASE_ASSET = MARKET_DATA_RELEASE_BASE + "market.db.lzma"
MARKET_DATA_RELEASE_META = MARKET_DATA_RELEASE_BASE + "market.db.meta.json"


def _download_market_db_lzma(verbose=False):
    """Download and verify the external market baseline release."""
    import hashlib
    import json
    import tempfile
    import urllib.request

    os.makedirs(WORK_DIR, exist_ok=True)
    target = os.path.join(WORK_DIR, "market.db.lzma")
    tmp = None
    try:
        req = urllib.request.Request(
            MARKET_DATA_RELEASE_META,
            headers={"User-Agent": "BorsTerminal-DataBootstrap/1"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            meta = json.loads(resp.read().decode("utf-8"))

        want_sha = str(meta.get("sha256", "")).lower()
        want_size = int(meta.get("size", 0) or 0)
        if len(want_sha) != 64 or any(c not in "0123456789abcdef" for c in want_sha):
            raise ValueError("market-data release metadata has no valid sha256")

        fd, tmp = tempfile.mkstemp(prefix="market.db.", suffix=".lzma", dir=WORK_DIR)
        os.close(fd)

        h = hashlib.sha256()
        total = 0
        req = urllib.request.Request(
            MARKET_DATA_RELEASE_ASSET,
            headers={"User-Agent": "BorsTerminal-DataBootstrap/1"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                total += len(chunk)

        got_sha = h.hexdigest()
        if want_size and total != want_size:
            raise ValueError("market.db.lzma size mismatch: %d != %d" % (total, want_size))
        if got_sha != want_sha:
            raise ValueError("market.db.lzma sha256 mismatch: %s != %s" % (got_sha, want_sha))

        os.replace(tmp, target)
        tmp = None
        if verbose:
            print("  [OK]  market.db.lzma downloaded from Release (%.1f MB)" % (total / 1048576.0))
        return target
    except Exception as e:
        if verbose:
            print("  [ERR] market.db.lzma Release download failed:", e)
        return None
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _find_bundled_db_lzma():
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _SRC_DIR
    for candidate in (os.path.join(exe_dir, "market.db.lzma"),
                      os.path.join(WORK_DIR, "market.db.lzma"),
                      "market.db.lzma", "../market.db.lzma"):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _baseline_stamp_path():
    return os.path.join(os.path.dirname(DB_PATH) or ".", "market.db.baseline")


def _read_baseline_stamp():
    try:
        with open(_baseline_stamp_path(), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _write_baseline_stamp(value):
    try:
        with open(_baseline_stamp_path(), "w", encoding="utf-8") as f:
            f.write(value)
    except OSError:
        pass


def _carry_user_tables(old_db, new_db, verbose=False):
    """جدول‌های کاربر را از baselineِ قدیمی به تازه کپی می‌کند. بی‌صدا رد می‌شود
    اگر جدولی در هیچ‌کدام نبود — نبودنش شکافِ داده نیست، فقط بی‌اهمیت است."""
    import sqlite3 as _sq
    try:
        # عمدیِ read-only نیست: فایلِ .stale ممکن است WALِ خودش را داشته باشد و
        # بازکردنِ ro بدونِ ability to build -shm شکست می‌خورد و نقلِ دادهٔ کاربر
        # بی‌صدا رد می‌شد.
        src = _sq.connect(old_db)
    except Exception:
        return
    try:
        have = {r[0] for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        dst_have = _market_db_tables(new_db)
        dst = _sq.connect(new_db)
        try:
            for t in MARKET_DB_USER_TABLES:
                if t not in have or t not in dst_have:
                    continue
                cols = [r[1] for r in dst.execute('PRAGMA table_info("%s")' % t)]
                collist = ",".join('"%s"' % c for c in cols)
                rows = src.execute('SELECT %s FROM "%s"' % (collist, t)).fetchall()
                if not rows:
                    continue
                dst.execute('DELETE FROM "%s"' % t)
                dst.executemany(
                    'INSERT INTO "%s" (%s) VALUES (%s)'
                    % (t, collist, ",".join("?" * len(cols))), rows)
                if verbose:
                    print("  [OK]  carried %s: %d rows" % (t, len(rows)))
            dst.commit()
        finally:
            dst.close()
    except Exception as e:
        if verbose:
            print("  [WARN] could not carry user tables:", e)
    finally:
        src.close()


def _table_pk(conn, name, schema="main"):
    """کلیدهای اصلی یک جدول؛ خالی یعنی جدول بی‌کلید (پس ادغامش امن نیست)."""
    try:
        return [r[1] for r in conn.execute(
            'PRAGMA %s.table_info("%s")' % (schema, name)) if r[5] > 0]
    except Exception:
        return []


def _union_forward(live_db, fresh_db, verbose=False):
    """ردیف‌های baselineِ تازه را به دیتابیسِ زنده «افزوده» می‌کند؛ هیچ ردیفِ
    زنده‌ای پاک یا بازنویسی نمی‌شود.

    چرا: `ensure_market_db` پیش از این با تغییرِ هشِ .lzma کل market.db را با
    baselineِ داخلِ نصاب عوض می‌کرد و فقط واچ‌لیست/تصمیمات را نگه می‌داشت. یعنی
    یک ارتقا — و مخصوصاً «نصبِ کامل» که سهمِ کاربرِ خیلی‌گذشته به آن می‌افتد —
    کندل‌ها و نبضِ روزهایی را که خودِ برنامه سینک کرده بود پاک می‌کرد و چارت را
    به عقب می‌انداخت. ادغامِ رو‌به‌جلو همان داده را نگه می‌دارد و پوششِ baseline
    را هم می‌گیرد.

    بازگشت: تعدادِ ردیف‌های اضافه‌شده به‌ازایِ جدول.
    """
    import sqlite3 as _sq
    added = {}
    try:
        dst = _sq.connect(live_db)
    except Exception:
        return added
    try:
        try:
            dst.execute('ATTACH DATABASE ? AS src', (fresh_db,))
        except Exception:
            return added
        try:
            src_tables = {r[0] for r in dst.execute(
                "SELECT name FROM src.sqlite_master WHERE type='table'")}
            dst_tables = {r[0] for r in dst.execute(
                "SELECT name FROM main.sqlite_master WHERE type='table'")}
            dst.execute("BEGIN IMMEDIATE")
            for t in sorted(src_tables):
                if t == "sqlite_stat1":
                    continue                      # آمارِ ANALYZE، داده نیست
                if t in MARKET_DB_USER_TABLES:
                    # نوشتهٔ خودِ کاربر. baselineِ نصاب ممکن است واچ‌لیستِ
                    # ماشینِ سازنده را داشته باشد؛ ادغامش یعنی نمادهایِ ساختگی
                    # در واچ‌لیستِ کاربر. (مسیرِ قدیمی با DELETE همان را پنهان
                    # می‌کرد؛ این خطِ روشن‌تر، همان تضمین را نگه می‌دارد.)
                    continue
                if t not in dst_tables:
                    # جدولی که baseline دارد و نصبِ کاربر نه — مثلاً
                    # tape_history در نسخه‌های قدیمی. بسازش و کپی‌اش کن.
                    ddl = dst.execute(
                        "SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                        (t,)).fetchone()
                    if not ddl or not ddl[0] or not _table_pk(dst, t, "src"):
                        continue
                    try:
                        dst.execute(ddl[0])
                    except Exception:
                        continue
                    dst.execute('INSERT OR IGNORE INTO main."%s" SELECT * FROM src."%s"' % (t, t))
                    added[t] = dst.execute("SELECT changes()").fetchone()[0]
                    continue
                if not _table_pk(dst, t):
                    continue                      # بی‌کلید ⇒ تکراری‌شدنِ بی‌صدا
                shared = [r[1] for r in dst.execute('PRAGMA main.table_info("%s")' % t)]
                src_cols = {r[1] for r in dst.execute('PRAGMA src.table_info("%s")' % t)}
                cols = [c for c in shared if c in src_cols]
                if not cols:
                    continue
                collist = ",".join('"%s"' % c for c in cols)
                verb = "INSERT OR REPLACE" if t in _MARKET_REF_TABLES else "INSERT OR IGNORE"
                dst.execute('%s INTO main."%s" (%s) SELECT %s FROM src."%s"'
                            % (verb, t, collist, collist, t))
                n = dst.execute("SELECT changes()").fetchone()[0]
                if n:
                    added[t] = n
            dst.commit()
        except Exception:
            try:
                dst.rollback()
            except Exception:
                pass
            return added if added else {}
        finally:
            try:
                dst.execute("DETACH DATABASE src")
            except Exception:
                pass
    finally:
        dst.close()
    if verbose and added:
        print("  [OK]  market.db kept; merged %d rows from the new baseline (%s)"
              % (sum(added.values()),
                 ", ".join("%s+%d" % (k, v) for k, v in sorted(added.items())[:6])))
    return added


def _frontend_asset_names(assets_dir):
    """نامِ فایل‌هایِ کدِ build شده (js/css/mjs) درِ پوشهٔ assets."""
    try:
        return {n for n in os.listdir(assets_dir)
                if n.lower().endswith((".js", ".mjs", ".css"))}
    except OSError:
        return set()


_ASSET_REF_RE = None


def prune_stale_frontend_assets(dist_dir, marker_version, verbose=False):
    """chunkهایِ کهنۀ frontend را ازِ محلِ نصبِ درجا پاک می‌کند.

    چرا: پچِ دلتا فقط «رویهمگذاری» می‌کند و هیچ‌وقت فایلی را حذف نمی‌کند. Vite
    هر بارِ build نامِ hash‌شده را عوض می‌کند، پس هر آپدیتِ جزئی چندصدِ فایلِ
    مرده در `_internal/frontend/dist/assets` می‌گذارد. شمارشِ واقعی رویِ نصبیِ
    مالک (۱٫۰٫۶۸، سه پچِ رویهم): ۲٫۲۹۲ فایلِ رویِ دیسک در برابرِ ۱٫۴۵۹ فایلِ
    manifestِ همان نسخه — یعنی ~۸۳۰ chunk که هیچ‌کس واردشان نمی‌شود.

    تشخیصِ «مرده» بی‌حدس: ازِ هر فایلِ بیرونِ پوشهٔ assets (index.html و
    `vendor/`) شروع می‌شود و بستهٔ importهایِ هر chunkِ زنده را دنبال می‌کند
    (closure). هر فایلِ js/css که درِ هیچِ فایلِ زنده‌ای نامش نیاید، مرده است.
    نگهبان‌ها: اگر closure کمتر از دو فایل شد هیچی پاک نمی‌شود — buildِ واقعی
    هرگز دو فایلِ زنده ندارد، پس آن حالت یعنی «فهمیدنِ ارجاع‌ها شکست خورده».
    رویِ ماشینِ trading، پاککردنِ چارت بدترِ نگه‌داشتنِ چند مگابایت است.

    یک‌بار به‌ازایِ هر نسخه اجرا می‌شود (stamp کنارِ فایل‌ها)، تاِ startupِ
    هر روز رویِ سخت‌افزارِ ضعیف گران نشود.
    """
    import re
    global _ASSET_REF_RE
    if _ASSET_REF_RE is None:
        _ASSET_REF_RE = re.compile(r"[A-Za-z0-9_@./+\-]+\.(?:js|mjs|css)")
    assets = os.path.join(dist_dir, "assets")
    if not os.path.isdir(assets):
        return 0
    stamp = os.path.join(assets, ".live_chunks_stamp")
    try:
        with open(stamp, encoding="utf-8") as f:
            if f.read().strip() == str(marker_version):
                return 0
    except OSError:
        pass
    candidates = _frontend_asset_names(assets)
    if not candidates:
        return 0

    def refs(text):
        out = set()
        for token in _ASSET_REF_RE.findall(text):
            out.add(os.path.basename(token))
        return out

    # ریشه‌ها: هر نامِ asset که بیرونِ پوشهٔ assets صدا زده شود. index.html
    # ورودیِ SPA است، ولی `vendor/` (klinecharts روی window) و هر html/jsِ
    # هم‌سطح هم می‌تواند chunkی را مستقیم بخواهد؛ اگر آن‌ها را ندید، همان chunk
    # «مرده» خوانده و پاک می‌شد.
    roots = set()
    for dirpath, dirnames, filenames in os.walk(dist_dir):
        if os.path.abspath(dirpath) == os.path.abspath(assets):
            continue
        for fn in filenames:
            if not fn.lower().endswith((".html", ".js", ".mjs", ".css")):
                continue
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8",
                          errors="replace") as f:
                    roots |= refs(f.read())
            except OSError:
                continue
    live = roots & candidates
    if len(live) < 2:
        return 0                 # buildِ واقعی هیچ‌وقت دو فایلِ زنده ندارد
    queue = sorted(live)
    seen = set()
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            with open(os.path.join(assets, name), encoding="utf-8",
                      errors="replace") as f:
                body = f.read()
        except OSError:
            continue
        for nxt in refs(body) & candidates:
            if nxt not in live:
                live.add(nxt)
                queue.append(nxt)
    dead = sorted(candidates - live)
    if not dead:
        return 0
    freed = 0
    for name in dead:
        try:
            p = os.path.join(assets, name)
            freed += os.path.getsize(p)
            os.remove(p)
        except OSError:
            continue
    try:
        with open(stamp, "w", encoding="utf-8") as f:
            f.write(str(marker_version))
    except OSError:
        pass
    if verbose:
        print("  [OK]  pruned %d stale frontend chunks (%.1f MB freed)"
              % (len(dead), freed / 1048576.0))
    return len(dead)


def ensure_market_db(verbose=False):
    """(idempotent) market.db را از market.db.lzma می‌سازد یا تازه می‌کند.

    دو شرطِ جدا گلوگاه بودند:
      ۱) ناقص‌بودن — یک مسیرِ فرعی (مثل --codal-worker) با connect خالی فایل
         می‌ساخت و اسکرینر تا ابد «داده نیست» می‌داد.
      ۲) کهنه‌بودن — استخراج فقط با «وجود نداشتن فایل» فعال می‌شد، پس baselineِ
         تازهٔ یک نسخهٔ جدید هرگز جای فایلِ استخراج‌شدهٔ قدیمی را نمی‌گرفت و
         «ارتقای انباشته» برای دادهٔ بازار عملاً دروغ بود.
    راهِ دوم: اثرِ انگشتی (sha256) از .lzma کنارِ فایل نگه می‌داریم؛ اگر عوض شد،
    baselineِ تازه استخراج و جدول‌هایِ کاربر از نسخهٔ قدیمی منتقل می‌شود. فایلِ
    قدیمی با پسوندِ .stale-<ts> نگه داشته می‌شود، نه حذف.

    v1.0.69: «جایگزینیِ کلِ فایل» فقط برایِ دیتابیسِ ناقص. دیتابیسِ سالمِ کاربر
    دیگر با baseline له نمی‌شود — ردیف‌هایِ تازه ادغامِ رو‌به‌جلو می‌شوند. دلیلش
    یک شمارشِ واقعی بود: نصبی که daily_prices‌اش تا ۲۰۲۶۰۹۳۰ و price_history‌اش
    ۳۷۵٫۱۵۴ ردیف بود، با یکِ «نصبِ کامل» به ۸۷٫۱۴۶ و ۳۲۱٫۳۸۹ ردیفِ baseline برمی‌گشت
    و tape_history‌اش (۱۵۱٫۳۵۶ ردیف) هم می‌توانست برود.
    """
    src_lzma = _find_bundled_db_lzma()
    if not src_lzma:
        src_lzma = _download_market_db_lzma(verbose=verbose)
    want = None
    if src_lzma:
        try:
            want = _sha256_file(src_lzma)
        except OSError:
            want = None

    if os.path.exists(DB_PATH):
        tables = _market_db_tables(DB_PATH)
        complete = _REQUIRED_MARKET_TABLES <= tables
        current = bool(want) and _read_baseline_stamp() == want
        if complete and current:
            return DB_PATH
        if complete:
            # سالم است و فقط baseline عوض شده ⇒ ادغام، نه جایگزینی.
            fresh = _extract_market_db(src_lzma, verbose=verbose,
                                       scratch_name="market.db.baseline.new")
            if fresh:
                _union_forward(DB_PATH, fresh, verbose=verbose)
                try:
                    os.remove(fresh)
                except OSError:
                    pass
            _write_baseline_stamp(want or "")
            return DB_PATH
        # تا این‌جا فقط دیتابیسِ ناقص/خراب می‌رسد: سالم‌ها بالا ادغام شدند.
        if verbose:
            print("  [..]  market.db is incomplete — re-extracting from market.db.lzma")
        stale_path = DB_PATH + ".stale"
        try:
            os.replace(DB_PATH, stale_path)
        except OSError:
            return DB_PATH
        # sidecar‌های WAL حتماً باید با فایلِ اصلی جابه‌جا شوند. اگر بمانند،
        # SQLite آن‌ها را به baselineِ تازه می‌چسباند و محتوای قدیمی دوباره
        # بازپخش می‌شود — یعنی جایگزینیِ تازه بی‌صدا به همان دادهٔ کهنه برمی‌گردد.
        for suffix in ("-wal", "-shm"):
            try:
                if os.path.exists(DB_PATH + suffix):
                    os.replace(DB_PATH + suffix, stale_path + suffix)
            except OSError:
                pass
        # baselineِ تازه را استخراج کن، بعد دادهٔ کاربر را از نسخهٔ قدیمی برگردان
        new_db = _extract_market_db(src_lzma, verbose=verbose)
        if new_db:
            _carry_user_tables(stale_path, new_db, verbose=verbose)
            _write_baseline_stamp(want or "")
        return new_db or DB_PATH

    new_db = _extract_market_db(src_lzma, verbose=verbose)
    if new_db:
        _write_baseline_stamp(want or "")
    return new_db or DB_PATH


def _extract_market_db(src_lzma, verbose=False, scratch_name=None):
    """market.db.lzma را به WORK_DIR/market.db باز می‌کند. None یعنی نشد.

    scratch_name داده شود یعنی فقط بازکردنِ موقت برایِ ادغام: فایلِ market.dbِ
    کاربر دست‌نخورده می‌ماند و مسیرِ باز شده برایِ پاک‌شدن به caller برمی‌گردد.
    """
    if not src_lzma:
        return None
    try:
        import lzma
        os.makedirs(WORK_DIR, exist_ok=True)
        target_db = os.path.join(WORK_DIR, scratch_name or "market.db")
        tmp = target_db + ".part"
        if verbose:
            print("  [..]  extracting market.db.lzma (one-time, ~40s) ...")
        with open(src_lzma, "rb") as fi, open(tmp, "wb") as fo:
            fo.write(lzma.decompress(fi.read()))
        if not _REQUIRED_MARKET_TABLES <= _market_db_tables(tmp):
            if verbose:
                print("  [ERR] extracted market.db is missing required tables")
            os.remove(tmp)
            return None
        os.replace(tmp, target_db)
        if not scratch_name and verbose:
            print("  [OK]  market.db extracted from .lzma")
        return target_db
    except Exception as e:
        if verbose:
            print("  [ERR] lzma extraction failed:", e)
        return None


# دیتابیس اختصاصی کاربر — هیچ‌وقت با آپدیت بازار جایگزین نمی‌شود.
# محل ذخیره: WORK_DIR (کنار EXE در حالت پرتابیل، وگرنه %LOCALAPPDATA%) یا
# ریشه ریپو (در حالت dev). این فایل در .gitignore است تا داده شخصی
# توسعه‌دهنده push نشود.
USER_DB_PATH = os.path.join(WORK_DIR, "user.db")

# فایل‌های چندنویسنده در WORK_DIR می‌مانند (نوشتنی؛ نه داخل _internal)
STATUS_PATH = os.path.join(WORK_DIR, "sync_status.json")
OD_STATUS_PATH = os.path.join(WORK_DIR, "sync_ondemand.json")
MARKET_STATUS_PATH = os.path.join(WORK_DIR, "market_sync.json")
CONTROL_PATH = os.path.join(WORK_DIR, "codal_control.json")
FTS_CONFIG_PATH = os.path.join(WORK_DIR, "fts_thresholds.json")
# تنظیماتِ رسمیِ «Price Source» (کارِ #73 قدمِ ۳؛ docs/CANDLE-CONTRACT.md §۱-ث):
# `{"basis": "last"|"closing"}`، پیش‌فرض last، سمتِ سرور — تنها خواننده‌اش price_basis.py
# است تا چارت/غربگر/کارت همه یک مبنایِ یکسان ببینند.
PRICE_BASIS_PATH = os.path.join(WORK_DIR, "price_basis.json")
_ADB_CFG = os.path.join(WORK_DIR, "adb_config.json")

FTS_DEFAULTS = {
    # ۱) رشد فروش تجمیعی ÷ همان دورهٔ سال قبل
    "growth_min": 40.0,            # Min_Sales_Growth = ۴۰٪
    # ۲) روند EPS — صورت مالی ۱۲ماههٔ حسابرسی‌شدهٔ شرکت اصلی
    "eps_years": 3,                # EPS_Consecutive_Growth_Years = ۳
    # ۳) حاشیه سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
    "margin_min": 20.0,            # Min_Gross_Margin = ۲۰٪
    "margin_optimal": 30.0,        # ایده‌آل = ۳۰٪
    # ۴) فروش سالانهٔ Annualized به ارزش بازار + پتانسیل سود ناخالص
    # حکمِ مالک جزوه (ص ۶): کفِ قبولی «حداقل ۱/۳ ارزش بازار» = ۰٫۳۳ است و
    # ۱٫۰ حالتِ ایده‌آل — نه آستانهٔ رد. پیش از این هر دو جا ۱٫۰ به‌عنوان
    # «پیش‌فرضِ جزوه» نوشته شده بود و نمادهای سالمِ ۰٫۳۳ تا  رد می‌شدند.
    "sales_to_mcap_min": 0.33,     # Min_Annualized_Sales_To_MarketCap = ⅓× (کف قبولی)
    "sales_to_mcap_ideal": 1.0,    # ایده‌آل = ۱× — نمایشی، نه گیتِ رد
    "profit_potential_min": 40.0,  # Min_Profit_Potential_To_MarketCap = ۴۰٪ (سند v2.1)
    # ۵) فیلتر صنعت — تفکیک قیمت‌گذاری آزاد/بورس کالا از دستوری
    "industry_mode": "Exclude_Mandatory_Pricing",
    "mandatory_sectors": ["خودرو", "نیروگاه", "قند و شکر", "لاستیک", "شوینده", "بیمه"],
    "free_sectors": ["سیمان", "پتروشیمی", "شیمیایی", "فلزات", "کانی", "کاشی", "سرامیک", "شیشه",
                     "کانه", "معادن", "نفت", "محصولات فلزی"],
    # غربالگری نهایی
    "watchlist_max": 50,           # سقف واچ‌لیست (جزوه: نهایتاً ۵۰ سهم)
    "mcap_min_hmt": 0.0,           # پیش‌شرط: حداقل ارزش بازار (همت)
    # سند v2.1 / فرم تنظیمات: کلیدهای دروازهٔ سخت و استثنائات
    "holdings_sales_na": True,          # عدم اعمال نسبت فروش بر هلدینگ/سرمایه‌گذاری (N/A)
    # استثنای دارویی: در جزوه تعریف نشده ⇒ خاموش (رأیِ مالک ۱۴۰۵-۰۷-۱۱).
    # هر وقت مالک عدد را تنظیم کند، `sector_filter` همان را می‌خواند.
    "pharma_margin_exempt_min": 0.0,
    "exclude_base_market": True,
    "exclude_rejected_indicators": [],   # کدهای شاخصی که نماد مردود/ناقص‌شان از جدول حذف شود        # حذف نمادهای بازار پایهٔ فرابورس
    "suspended_max_stale_sessions": 3,   # نماد با ≥ این تعداد نشست عقب‌مانده = تعلیق
    # v9.7 — دو پارامتر کمکی بنیادی/تابلوخوانی
    # ماده ۱۴۱ قانون تجارت: زیان انباشته > نصف سرمایه → حذف از واچ‌لیست.
    # تشخیص از آخرین صورت مالی ۱۲ماهه: total_equity <= 0.5 * capital
    "filter_m141": False,
    # نقدشوندگی: حداقل میانگین ارزش معاملات روزانه (همت); ۰ = بدون فیلتر
    "min_trade_val": 0.0,
    # v10 — آستانه‌های «حکمِ جزوه» برای کارتِ بنیادی. این کلیدها عمداً از
    # کلیدهای اسکرینر (growth_min/margin_min/…) جدا‌اند: تغییرِ عددِ اسکرینر
    # نباید بی‌صدا چکِ ۱الفِ کارت (۶۰٪) یا کفِ نسبتِ فروش÷ارزش را شل کند.
    # پنلِ تنظیمات همین‌ها را می‌نویسد و v10_thresholds() می‌خواند.
    "v10_monetary_growth_min": 60.0,
    # ۱ب — مبنای تورمی که از رشدِ اسمی کسر می‌شود تا «رشد تولیدی» بیرون بیاید.
    # حکمِ مالک 2026-09-26: این عدد کلیدِ خودش را دارد و از هدفِ ۶۰٪ِ بالا جداست؛
    # ۰ یعنی «بدون تعدیلِ تورم» و باید همان‌طور بماند.
    "v10_inflation_basis": 60.0,
    "v10_volume_growth_min": 0.0,
    "v10_volume_breadth_min": 0.60,
    "v10_eps_years": 3,
    "v10_margin_min": 20.0,
    "v10_margin_ideal": 30.0,
    "v10_sales_to_mcap_min": 0.33,      # ص ۶ جزوه: کف قبولی ⅓× ارزش بازار (ایده‌آل ۱× در سطر بعد)
    "v10_potential_min": 40.0,
    # v10 — فیلترِ دستیِ صنایع از پنل (جدا از رژیم قیمت‌گذاری).
    # industry_mode = Include_Industries → فقط فهرستِ include می‌ماند
    # industry_mode = Exclude_Industries  → فهرستِ exclude حذف میشود
    # فهرست‌ها با «,» یا «،» نوشته میشوند و با norm_fa نرمال‌سازی می‌شوند.
    "include_industries": [],
    "exclude_industries": [],
}

FTS_LEGACY_SCALARS = {
    "streak_periods": "eps_years",
    "ps_good": "sales_to_mcap_ideal",       # P/S ≤ 1  ⇔  Sales/Mcap ≥ 1.0
    "potential_min": "profit_potential_min",
}
FTS_LEGACY_LISTS = {"bad_sectors": "mandatory_sectors", "good_sectors": "free_sectors"}
FTS_LIST_KEYS = ("mandatory_sectors", "free_sectors", "include_industries",
                 "exclude_industries", "exclude_rejected_indicators")
FTS_STR_KEYS = ("industry_mode",)

_CAL_CACHE_PATH = os.path.join(APP_DIR, "static", "calendar", "cache.json")
_cal_cache = {"mtime": 0.0, "events": []}

MA_WINDOWS = [5, 20, 50, 120]

# v1.0.10 — نسخهٔ برنامه؛ منبعِ واحد برای api/update.py (مقایسهٔ semver).
# هر بار که نسخه در installer/bors_setup.iss و tauri.conf.json بالا می‌رود،
# اینجا هم باید به‌روز شود (scripts/publish_github_release.py هم همین نسخه را
# در latest.json می‌نویسد).
APP_VERSION = "1.0.79"
