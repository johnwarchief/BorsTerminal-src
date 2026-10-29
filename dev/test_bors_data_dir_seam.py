# dev/test_bors_data_dir_seam.py — درزِ داده برایِ پاریتی: BORS_DATA_DIR
"""اگر BORS_DATA_DIR تنظیم باشد، WORK_DIR/DB_PATH/USER_DB_PATH از آن می‌آیند؛
اگر نباشد، رفتارِ امروز دست‌نخورده است. بدونِ شبکه، فقط فایلِ موقت.

حالتِ «متغیر نیست» با reload واقعی سنجیده می‌شود، نه با مقایسهٔ یک مسیرِ
تصادفی: پیش از این فقط می‌گفت WORK_DIR با پوشهٔ موقتِ تازه یکی نیست، که با
هر پیاده‌سازیِ خرابی هم سبز می‌شد. حالا باید همان مسیرهایِ ریشۀ ریپو باشد.
"""
import importlib
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + (" — " + detail if detail else ""))


def main():
    old = os.environ.pop("BORS_DATA_DIR", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "market.db"), "wb").close()
            os.environ["BORS_DATA_DIR"] = tmp
            import bors_config
            importlib.reload(bors_config)
            check("WORK_DIR follows BORS_DATA_DIR",
                  bors_config.WORK_DIR == os.path.abspath(tmp), bors_config.WORK_DIR)
            check("DB_PATH is inside it",
                  bors_config.DB_PATH == os.path.join(os.path.abspath(tmp), "market.db"),
                  bors_config.DB_PATH)
            check("USER_DB_PATH is inside it",
                  bors_config.USER_DB_PATH == os.path.join(os.path.abspath(tmp), "user.db"),
                  bors_config.USER_DB_PATH)
            # رگرسیون: بانکِ خالیِ همین پوشه باید بر market.dbِ کدال‌دارِ ریشۀ ریپو
            # پیشی بگیرد؛ پیش از این exe_dir (ریشه) اول جستجو می‌شد و برنده بود.
            check("empty market.db under BORS_DATA_DIR beats repo market.db",
                  bors_config.DB_PATH == os.path.join(os.path.abspath(tmp), "market.db")
                  and bors_config.DB_PATH != os.path.join(ROOT, "market.db"),
                  bors_config.DB_PATH)
        # حالتِ بی‌متغیر: reload باید مسیرهایِ پیش‌فرضِ ریشۀ ریپو را برگرداند.
        os.environ.pop("BORS_DATA_DIR", None)
        import bors_config
        importlib.reload(bors_config)
        check("unset: WORK_DIR is the repo root",
              bors_config.WORK_DIR == ROOT, bors_config.WORK_DIR)
        check("unset: DB_PATH is the repo market.db",
              bors_config.DB_PATH == os.path.join(ROOT, "market.db"), bors_config.DB_PATH)
        check("unset: USER_DB_PATH is the repo user.db",
              bors_config.USER_DB_PATH == os.path.join(ROOT, "user.db"),
              bors_config.USER_DB_PATH)
    finally:
        os.environ.pop("BORS_DATA_DIR", None)
        if old is not None:
            os.environ["BORS_DATA_DIR"] = old
        import bors_config
        importlib.reload(bors_config)
    print("bors_data_dir_seam: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
