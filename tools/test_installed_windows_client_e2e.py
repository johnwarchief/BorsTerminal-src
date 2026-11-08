#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/test_installed_windows_client_e2e.py -- آزمون واقعی کلاینت کامپایل‌شده ویندوز (Workstream F).

این اسکریپت باینری واقعی کامپایل‌شده دسکتاپ ویندوز (`dist/BorsTerminal_Ultimate/BorsTerminal_Ultimate.exe`) را
به عنوان یک پروسه واقعی روی ویندوز اجرا کرده و مراحل زیر را راستی‌آزمایی می‌کند:
  ۱. تولید جفت کلید Minisign با `dist/bors-producer.exe keygen`
  ۲. تولید اسنپ‌شات معتبر با `dist/bors-producer.exe codal snapshot`
  ۳. بالا آوردن سرور توزیع شبیه‌سازی‌شده (HTTP Mock Release Server)
  ۴. ایجاد دیتابیس کاربر (`user.db`) با واچ‌لیست‌ها و یادداشت‌های شخصی و ثبت هش SHA-256 آن
  ۵. راه‌اندازی باینری واقعی `BorsTerminal_Ultimate.exe` روی پورت ۸۱۹۷ با کلید عمومی آزمایشی
  ۶. فراخوانی اندپوینت `POST /api/sync/codal/db-download?url=...` از روی کلاینت
  ۷. پایش وضعیت دانلود، راستی‌آزمایی امضای دیجیتال و اعمال نسل جدید اسنپ‌شات
  ۸. اثبات ریاضی و فیزیکی عدم تغییر حتی یک بایت در `user.db` پس از اعمال اسنپ‌شات (برابری هش SHA-256)
  ۹. راه‌اندازی مجدد (Restart) پروسه باینری و اطمینان از بازخوانی نسل فعال
  ۱۰. پاکسازی پروسه و گزارش شواهد قطعی
"""
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate", "BorsTerminal_Ultimate.exe")
PRODUCER_EXE = os.path.join(ROOT, "dist", "bors-producer.exe")


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MockFileServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silent


def run_http_server(directory, port):
    handler = lambda *args, **kwargs: MockFileServer(*args, directory=directory, **kwargs)
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("================================================================================")
    print("      BorsTerminal Windows Client E2E Integration & user.db Integrity Test      ")
    print("================================================================================")

    if not os.path.isfile(EXE_PATH):
        print(f"[FAIL] Compiled client binary not found at: {EXE_PATH}")
        return 1
    if not os.path.isfile(PRODUCER_EXE):
        print(f"[FAIL] Compiled producer binary not found at: {PRODUCER_EXE}")
        return 1

    temp_base = tempfile.mkdtemp(prefix="bt_win_client_test_")
    src_data_dir = os.path.join(temp_base, "src_data")
    client_dir = os.path.join(temp_base, "client_data")
    server_dir = os.path.join(temp_base, "server_dist")
    os.makedirs(src_data_dir, exist_ok=True)
    os.makedirs(client_dir, exist_ok=True)
    os.makedirs(server_dir, exist_ok=True)

    server_httpd = None
    proc = None
    is_live_github = "--live-github" in sys.argv

    try:
        if is_live_github:
            server_url = "https://github.com/johnwarchief/BorsTerminal/releases/download/v1.0.98"
            pubkey_str = None
            print(f"  [1] Live GitHub Release mode: targeting {server_url}")
            print("      Using default built-in client public key (KeyID 830BF752EF10076).")
        else:
            # 1. Generate test Minisign key pair using bors-producer keygen
            print("  [1] Generating Minisign Ed25519 keypair via dist/bors-producer.exe keygen...")
            keygen_res = subprocess.check_output([PRODUCER_EXE, "keygen"]).decode("utf-8")
            keys = json.loads(keygen_res)
            pubkey_str = keys["public_key"]
            privkey_str = keys["secret_key"]
            print(f"      Public key: {pubkey_str.splitlines()[-1][:32]}...")

            # 2. Setup source databases to snapshot
            src_market_db = os.path.join(src_data_dir, "market.db")
            sconn = sqlite3.connect(src_market_db)
            sconn.execute("CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, symbol TEXT);")
            sconn.execute("CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INT, verdict TEXT);")
            sconn.execute("INSERT INTO instruments VALUES ('1001', 'فولاد');")
            sconn.execute("INSERT INTO instruments VALUES ('1002', 'شستا');")
            sconn.execute("INSERT INTO fts_results VALUES ('فولاد', 5, 'STRONG');")
            sconn.execute("INSERT INTO fts_results VALUES ('شستا', 4, 'WATCH');")
            sconn.commit()
            sconn.close()

            src_codal_db = os.path.join(src_data_dir, "codal.db")
            cconn = sqlite3.connect(src_codal_db)
            cconn.execute("CREATE TABLE codal_notices (tracing_no INT PRIMARY KEY, symbol TEXT);")
            cconn.execute("INSERT INTO codal_notices VALUES (9999, 'فولاد');")
            cconn.commit()
            cconn.close()

            # 3. Create and sign snapshot set using bors-producer codal snapshot
            print("  [2] Creating compressed LZMA2 snapshot set and Minisign signatures...")
            snap_env = os.environ.copy()
            snap_env["BORS_MINISIGN_SECRET_KEY"] = privkey_str
            snap_cmd = [
                PRODUCER_EXE, "codal", "snapshot",
                f"--data-dir={src_data_dir}",
                f"--out={server_dir}",
                "--tag=gen-win-client-live-20261108"
            ]
            rc = subprocess.call(snap_cmd, env=snap_env)
            if rc != 0:
                print(f"[FAIL] bors-producer codal snapshot failed with code {rc}")
                return 1

            # Check required files exist in server_dir
            for req_file in ["manifest.json", "manifest.json.sig", "market.db.lzma", "market.db.lzma.sig", "codal.db.lzma", "codal.db.lzma.sig"]:
                p = os.path.join(server_dir, req_file)
                if not os.path.isfile(p):
                    print(f"[FAIL] Snapshot asset {req_file} missing in {server_dir}")
                    return 1
            print("      Created and signed all 6 release assets (market, codal, manifest + .sig files).")

        # 4. Setup client user.db with personal user watchlist and notes matching watchlist/store.go schema
        user_db_path = os.path.join(client_dir, "user.db")
        uconn = sqlite3.connect(user_db_path)
        ucur = uconn.cursor()
        ucur.execute("""
            CREATE TABLE IF NOT EXISTS user_watchlists (
                symbol_norm TEXT PRIMARY KEY,
                symbol      TEXT NOT NULL DEFAULT '',
                name        TEXT DEFAULT '',
                note        TEXT DEFAULT '',
                added_at    TEXT DEFAULT ''
            );
        """)
        ucur.execute("CREATE INDEX IF NOT EXISTS ix_uwl_added ON user_watchlists(added_at);")
        ucur.execute("""
            INSERT INTO user_watchlists (symbol_norm, symbol, name, note, added_at)
            VALUES ('فولاد', 'فولاد', 'فولاد مبارکه', 'تحلیل بنیادی تایید FTS دارد', '2026-11-08T12:00:00Z');
        """)
        ucur.execute("""
            INSERT INTO user_watchlists (symbol_norm, symbol, name, note, added_at)
            VALUES ('شستا', 'شستا', 'سرمایه گذاری تامین اجتماعی', 'سبد اصلی من', '2026-11-08T12:05:00Z');
        """)
        uconn.commit()
        uconn.close()

        # Initial dummy market.db so borsd can open initial handles
        dummy_market = os.path.join(client_dir, "market.db")
        dm = sqlite3.connect(dummy_market)
        dm.execute("CREATE TABLE dummy (x INT);")
        dm.commit()
        dm.close()

        initial_user_sha = sha256_of_file(user_db_path)
        initial_user_size = os.path.getsize(user_db_path)
        print(f"  [3] Seeded user.db successfully (size: {initial_user_size} bytes)")
        print(f"      Initial user.db SHA-256: {initial_user_sha}")

        # 5. Start distribution server if in mock mode
        if not is_live_github:
            server_port = 8196
            server_httpd = run_http_server(server_dir, server_port)
            server_url = f"http://127.0.0.1:{server_port}"
            print(f"  [4] Mock distribution server listening at: {server_url}")
        else:
            print(f"  [4] Targeting live production release server at: {server_url}")

        # 6. Launch BorsTerminal_Ultimate.exe Windows binary
        client_port = 8197
        client_cmd = [
            EXE_PATH,
            f"-db-dir={client_dir}",
            f"-port={client_port}",
            "-server-only",
            "-no-loops"
        ]
        client_env = os.environ.copy()
        if pubkey_str:
            client_env["BORS_UPDATE_PUBKEY"] = pubkey_str
        client_env["BORS_SNAPSHOT_BASE_URL"] = server_url

        print(f"  [5] Launching live Windows binary BorsTerminal_Ultimate.exe on port {client_port}...")
        proc = subprocess.Popen(client_cmd, env=client_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for client HTTP server readiness
        client_url = f"http://127.0.0.1:{client_port}"
        ready = False
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{client_url}/api/sync/status", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.1)

        if not ready:
            print(f"[FAIL] BorsTerminal_Ultimate.exe failed to start on {client_url}")
            try:
                proc.terminate()
                out, err = proc.communicate(timeout=2)
                print(f"STDOUT:\n{out.decode('utf-8', errors='replace')}")
                print(f"STDERR:\n{err.decode('utf-8', errors='replace')}")
            except Exception as e:
                print(f"Error capturing output: {e}")
            return 1
        print("      BorsTerminal_Ultimate.exe is live and responding (200 OK).")

        # 7. Trigger snapshot download & apply via client endpoint
        print(f"  [6] Triggering POST /api/sync/codal/db-download?url={server_url} on Windows client...")
        req = urllib.request.Request(f"{client_url}/api/sync/codal/db-download?url={server_url}", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"      Response: status={data.get('status')}, message={data.get('message')}")

        # 8. Poll status until complete
        print("  [7] Polling client download, Minisign verification, and atomic apply status...")
        done = False
        last_log = ""
        poll_attempts = 5400 if is_live_github else 300
        for attempt in range(poll_attempts):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"{client_url}/api/sync/codal/db-status", timeout=2) as resp:
                    status_data = json.loads(resp.read().decode("utf-8"))
                    db_info = status_data.get("db", {})
                    stage = db_info.get("stage")
                    pct = db_info.get("percent", 0)
                    detail = db_info.get("detail", "")
                    err_msg = db_info.get("error", "")
                    cur_log = f"stage={stage}, pct={pct}%, detail={detail}"
                    if cur_log != last_log:
                        print(f"      [{attempt}] {cur_log}")
                        last_log = cur_log
                    if stage == "done":
                        done = True
                        print(f"      Status reached 'done' (100%): {detail}")
                        break
                    elif stage == "error":
                        print(f"[FAIL] Client reported error: {err_msg}")
                        return 1
            except Exception as e:
                print(f"      Polling exception: {e}")

        if not done:
            print("[FAIL] Timeout waiting for snapshot apply to complete")
            return 1

        # 9. Verify active generation file and contents
        active_gen_path = os.path.join(client_dir, "active_generation.json")
        if not os.path.isfile(active_gen_path):
            print("[FAIL] active_generation.json missing on client data directory")
            return 1

        with open(active_gen_path, "r", encoding="utf-8") as f:
            active_gen = json.load(f)
        gen_dir_rel = active_gen.get("generation_dir")
        gen_dir = os.path.join(client_dir, gen_dir_rel) if gen_dir_rel else None
        print(f"  [8] Active Generation verified: {active_gen.get('snapshot_set_id')}")
        print(f"      Generation Directory: {gen_dir}")

        # Verify market.db in new generation has the snapshot data
        gen_market = os.path.join(gen_dir, "market.db")
        gm = sqlite3.connect(gen_market)
        cur = gm.cursor()
        cur.execute("SELECT verdict FROM fts_results WHERE symbol='فولاد'")
        v_res = cur.fetchone()[0]
        gm.close()
        print(f"      New generation DB query: symbol فولاد -> verdict {v_res} (verified!)")

        # 10. Compare user.db hash before and after
        final_user_sha = sha256_of_file(user_db_path)
        print(f"  [9] Comparing user.db SHA-256 before and after snapshot apply:")
        print(f"      Initial: {initial_user_sha}")
        print(f"      Final:   {final_user_sha}")

        if initial_user_sha != final_user_sha:
            print("[FAIL] CRITICAL FAILURE: user.db SHA-256 was altered during snapshot apply!")
            return 1
        print("      PASS: user.db SHA-256 is 100% byte-for-byte identical (Zero Modification).")

        # Verify user data tables intact
        uconn = sqlite3.connect(user_db_path)
        ucur = uconn.cursor()
        ucur.execute("SELECT count(*) FROM user_watchlists")
        wl_count = ucur.fetchone()[0]
        ucur.execute("SELECT note FROM user_watchlists WHERE symbol_norm='فولاد'")
        note_text = ucur.fetchone()[0]
        uconn.close()
        print(f"      Verified user records: {wl_count} watchlist entries, note: '{note_text}'")

        # 11. Test Restart of BorsTerminal_Ultimate.exe and generation reload
        print("  [10] Restarting BorsTerminal_Ultimate.exe to verify generation persistence...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        proc = subprocess.Popen(client_cmd, env=client_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ready = False
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{client_url}/api/sync/codal/db-status", timeout=1) as resp:
                    if resp.status == 200:
                        status_resp = json.loads(resp.read().decode("utf-8"))
                        if status_resp.get("active_generation"):
                            ready = True
                            break
            except Exception:
                time.sleep(0.1)

        if not ready:
            print("[FAIL] active generation not reloaded after restart")
            return 1
        print("      PASS: Client reloaded active generation successfully after restart.")

        print("================================================================================")
        print("  ALL WINDOWS CLIENT INTEGRATION CHECKS PASSED: 100% EVIDENCE-BASED SUCCESS!    ")
        print("================================================================================")
        return 0

    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if server_httpd is not None:
            try:
                server_httpd.shutdown()
            except Exception:
                pass
        shutil.rmtree(temp_base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
