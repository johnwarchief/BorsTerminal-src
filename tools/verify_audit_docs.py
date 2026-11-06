#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_audit_docs.py — اعتبارسنجی خودکار اسناد ممیزی فاز ۱ مهاجرت به Go."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
DOCS_DIR = os.path.join(ROOT, "docs", "migration", "python-elimination")
DOC1_PATH = os.path.join(DOCS_DIR, "01-runtime-inventory.md")
DOC2_PATH = os.path.join(DOCS_DIR, "02-api-and-data-ownership.md")
ROUTES_JSON = os.path.join(ROOT, "backend-go", "internal", "httpapi", "routes.json")

def verify():
    print("===> شروع بررسی اسناد ممیزی فاز ۱...")
    
    # ۱. وجود فایل‌ها
    assert os.path.exists(DOC1_PATH), f"فایل {DOC1_PATH} یافت نشد!"
    assert os.path.exists(DOC2_PATH), f"فایل {DOC2_PATH} یافت نشد!"
    
    with open(DOC1_PATH, "r", encoding="utf-8") as f:
        doc1 = f.read()
    with open(DOC2_PATH, "r", encoding="utf-8") as f:
        doc2 = f.read()
        
    assert len(doc1) > 2000, f"سند 01 خیلی کوتاه است ({len(doc1)} بایت)"
    assert len(doc2) > 4000, f"سند 02 خیلی کوتاه است ({len(doc2)} بایت)"
    
    # ۲. عدم وجود placeholderهای ممنوعه
    for p in ["TODO", "TBD", "implement later", "fill in details"]:
        assert p not in doc1, f"پلیس‌هولدر {p} در سند 01 یافت شد!"
        assert p not in doc2, f"پلیس‌هولدر {p} در سند 02 یافت شد!"
        
    # ۳. پوشش ۱۰۰٪ تمام ۱۰۵ اندپوینت در سند 02
    with open(ROUTES_JSON, "r", encoding="utf-8") as f:
        routes = json.load(f)
        
    print(f"تعداد اندپوینت‌های مرجع در routes.json: {len(routes)}")
    missing_routes = []
    for r in routes:
        # هر اندپوینت باید در سند 02 نام برده شده باشد
        parts = r.split(" ", 1)
        path = parts[1]
        if path not in doc2:
            missing_routes.append(r)
            
    if missing_routes:
        print(f"خطا: {len(missing_routes)} اندپوینت در سند 02 مفقود هستند:")
        for mr in missing_routes[:10]:
            print("  -", mr)
        sys.exit(1)
        
    # ۴. بررسی برچسب‌های استاندارد در سند 02
    valid_tags = ["COMPLETE_VERIFIED", "PARTIAL_OR_DEGRADED", "STUB_501", "MISSING"]
    for tag in valid_tags:
        assert tag in doc2, f"برچسب {tag} در سند 02 یافت نشد!"
        
    # ۵. بررسی تفکیک دیتابیس‌ها
    for db_name in ["market.db", "codal.db", "user.db"]:
        assert db_name in doc2, f"دیتابیس {db_name} در سند 02 ذکر نشده است!"
        
    print("✅ تمام اعتبارسنجی‌های اسناد ممیزی 01 و 02 با موفقیت پاس شدند!")

if __name__ == "__main__":
    verify()
