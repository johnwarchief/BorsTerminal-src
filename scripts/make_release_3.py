"""
Release builder for BorsTerminal_Ultimate v3 (seeded DB cold start).
Usage: python make_release_3.py

Bundles the CURRENT populated market.db as a pre-seeded cold start: a new user
gets all active symbols + historical reports instantly; the first 'Sync' is
only a rapid 30-second delta check on the latest feed.
"""
import os
import zipfile
import sqlite3
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
RELEASES = os.path.join(HERE, "releases")
VER_FILE = os.path.join(RELEASES, ".version")
DB_PATH = os.path.join(HERE, "market.db")

os.makedirs(RELEASES, exist_ok=True)

# Version bump: 3.0.0 -> 3.0.1 -> 3.0.2 (patch), 3.0.x -> 3.1.0 (minor bump via arg)
if os.path.exists(VER_FILE):
    ver = open(VER_FILE, encoding="utf-8").read().strip()
    try:
        parts = ver.split(".")
        if len(parts) == 3:
            major, minor, patch = parts
            ver = f"{major}.{minor}.{int(patch) + 1}"
        elif len(parts) == 2:
            major, minor = parts
            ver = f"{major}.{int(minor) + 1}.0"
        else:
            ver = "3.0.0"
    except ValueError:
        ver = "3.0.0"
else:
    ver = "3.0.0"

open(VER_FILE, "w", encoding="utf-8").write(ver)

PROJ = os.path.basename(HERE)
OUT = os.path.join(RELEASES, f"{PROJ}_v{ver}.zip")


def _make_seed():
    """Consistent pre-seeded market.db snapshot (copy + VACUUM).

    Uses SQLite's online backup API so the source is never touched mid-write,
    then VACUUMs to reclaim free pages. Returns (temp_path, stats) or None."""
    if not os.path.isfile(DB_PATH):
        print("  !! market.db not found — release would have NO pre-seeded DB")
        return None
    stats = {}
    try:
        src = sqlite3.connect(DB_PATH)
        try:
            for t in ("financial_statements", "monthly_sales", "codal_notices",
                      "instruments", "price_history"):
                try:
                    stats[t] = src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except Exception:
                    pass
            stats["fs_symbols"] = src.execute(
                "SELECT COUNT(DISTINCT symbol) FROM financial_statements").fetchone()[0]
        finally:
            src.close()
        fd, tmp = tempfile.mkstemp(suffix=".db", prefix="seed_")
        os.close(fd)
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(tmp)
        src.backup(dst)
        dst.close()
        src.close()
        vc = sqlite3.connect(tmp)
        vc.execute("VACUUM")
        vc.close()
    except Exception as e:
        print(f"  !! seed failed: {e}")
        try:
            os.remove(tmp)
        except (OSError, NameError):
            pass
        return None
    stats["size_mb"] = round(os.path.getsize(tmp) / 1e6, 1)
    print(f"  seed market.db: {stats['size_mb']} MB "
          f"({stats['fs_symbols']} FS symbols, {stats['financial_statements']} FS rows, "
          f"{stats['codal_notices']} notices)")
    return tmp, stats


seed = _make_seed()

skip_dirs = {"__pycache__", "releases", "dev", "logs", "backups", ".v2cache", "android", "build", "dist", ".venv", "venv", "venv_build", "portable", "_old_desktop"}
# آلودگیهای قبلی ریلیز: بکاپها/پروبهای قدیمی و لوگهای اسکن نباید به دست
# کاربر جدید برسند؛ market.db هم از walk حذف و بعداً بهصورت seed اضافه میشود.
skip_files = {"sync_status.json", "sync_summary.json", "sync_ondemand.json",
              "codal_state.json", "market_sync.json", ".version", ".gitignore",
              "scan_run.log", "scan_run2.log", "scan_run3.log", "scan_run4.log",
              "discovery_scan.log", "relauncher.log", "adb_config.json.tmp",
              "_backup_probe.db", "_backup_speed.db", "make_release.py",
              ".env", "notifier_secrets.json"}


def _is_junk(fn):
    return (fn == "market.db" or fn == "market.db.lzma" or fn in skip_files
            or fn.startswith("_backup") or fn.startswith("market_backup")
            or fn.startswith("scan_run") or fn.startswith("_dbg_")
            or fn == "seed_" + fn[:0]  # placeholder, never matches
            )


with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(HERE):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in sorted(filenames):
            if _is_junk(fn):
                continue
            full = os.path.join(dirpath, fn)
            zf.write(full, os.path.relpath(full, HERE))
            print(f"  + {os.path.relpath(full, HERE)}")
    if seed:
        zf.write(seed[0], "market.db")
        print("  + market.db  (pre-seeded — cold start, no full re-scan needed)")

if seed:
    try:
        os.remove(seed[0])
    except OSError:
        pass

print(f"\n✅ Version {ver} -> {OUT}")
