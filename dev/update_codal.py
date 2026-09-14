import datetime
import sqlite3

import codal_fetcher


def force_sync():
    print("Forcing Global Codal Sync...")
    s = codal_fetcher.make_session()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(codal_fetcher.DB_PATH)
    codal_fetcher.create_schema(conn)
    codal_fetcher.migrate_schema(conn)
    codal_fetcher.write_od_status("ALL", "codal", "در حال اسکن اطلاعیه‌های جدید کل بازار...")
    rows, _ = codal_fetcher.fetch_notices(s, now, max_saved_tn=0, resume_from=0)
    if rows:
        conn.executemany(codal_fetcher.NOTICE_UPSERT, rows)
        conn.commit()
    pool = [tuple(r) for r in conn.execute(
        "SELECT tracing_no, symbol, company_name, title, letter_code, publish_date,"
        " sent_date, url, fetched_at, pdf_url, excel_url FROM codal_notices"
        " ORDER BY publish_date DESC LIMIT 300")]
    fs_targets = [n for n in pool if codal_fetcher.kind_of(n[3]) == "Financial Statements"]
    fs = []
    for i, n in enumerate(fs_targets, 1):
        try:
            vals, meta, unit = codal_fetcher.scrape_report(s, n[7])
            if vals.get("revenue") is not None:
                fs.append((n[0], n[1], n[2], n[3], codal_fetcher.kind_of(n[3]),
                           meta.get("period"), meta.get("end"), n[5])
                          + tuple(vals.get(k) for k in codal_fetcher.FS_KEYS)
                          + (unit, n[7], now))
                print(f"    [{i}/{len(fs_targets)}] {n[1]} -> {meta.get('end')}")
        except Exception:
            pass
    if fs:
        conn.executemany(codal_fetcher.FS_UPSERT, fs)
        conn.commit()
    codal_fetcher.write_od_status("ALL", "done", "بروزرسانی کامل شد.")
    print(f"Codal Sync Complete! ({len(fs)} financial statements saved)")


if __name__ == "__main__":
    force_sync()
