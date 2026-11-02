import os
import sys
import time
import requests

MODELS = [
    "NeoQuasar/Kronos-mini",
    "NeoQuasar/Kronos-small",
    "NeoQuasar/Kronos-base",
    "NeoQuasar/Kronos-Tokenizer-2k",
    "NeoQuasar/Kronos-Tokenizer-base",
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "kronos"))

def download_file(url: str, dest_path: str, expected_size: int = None, max_retries: int = 5):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_path = dest_path + ".part"

    downloaded = 0
    if os.path.exists(temp_path):
        downloaded = os.path.getsize(temp_path)

    if os.path.exists(dest_path):
        current_size = os.path.getsize(dest_path)
        if expected_size is None or current_size == expected_size:
            print(f"  [OK] Already exists: {os.path.basename(dest_path)} ({current_size:,} bytes)")
            return True

    for attempt in range(1, max_retries + 1):
        headers = {}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"
            print(f"  Resuming from byte {downloaded:,} (attempt {attempt}/{max_retries})...")
        else:
            print(f"  Starting download (attempt {attempt}/{max_retries})...")

        try:
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                if r.status_code not in (200, 206):
                    if r.status_code == 416: # Range not satisfiable, file might already be complete
                        if os.path.exists(temp_path):
                            os.replace(temp_path, dest_path)
                            return True
                    print(f"  HTTP Error {r.status_code}")
                    time.sleep(2)
                    continue

                mode = "ab" if downloaded > 0 and r.status_code == 206 else "wb"
                if mode == "wb":
                    downloaded = 0

                total = r.headers.get("Content-Length")
                total_bytes = int(total) + downloaded if total else expected_size

                last_print = time.time()
                with open(temp_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024): # 1MB chunk
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if time.time() - last_print > 1.5:
                                pct = (downloaded / total_bytes * 100) if total_bytes else 0
                                print(f"    Progress: {downloaded:,} bytes ({pct:.1f}%)")
                                last_print = time.time()

                if total_bytes and downloaded < total_bytes:
                    print(f"  Incomplete download: {downloaded:,}/{total_bytes:,} bytes, retrying...")
                    continue

                os.replace(temp_path, dest_path)
                print(f"  [DONE] Successfully downloaded {os.path.basename(dest_path)} ({downloaded:,} bytes)")
                return True

        except Exception as e:
            print(f"  Network error during download: {e}")
            time.sleep(3)

    return False

def main():
    print(f"Target Kronos Models directory: {BASE_DIR}")
    os.makedirs(BASE_DIR, exist_ok=True)

    success_count = 0
    total_files = len(MODELS) * 2

    for model_id in MODELS:
        folder_name = model_id.split("/")[-1]
        model_dir = os.path.join(BASE_DIR, folder_name)
        print(f"\n==========================================")
        print(f"Checking & Downloading: {model_id} -> {folder_name}")
        print(f"==========================================")

        # 1. Download config.json
        config_url = f"https://huggingface.co/{model_id}/raw/main/config.json"
        config_dest = os.path.join(model_dir, "config.json")
        if download_file(config_url, config_dest):
            success_count += 1

        # 2. Download model.safetensors
        # First check remote size
        st_url = f"https://huggingface.co/{model_id}/resolve/main/model.safetensors"
        st_dest = os.path.join(model_dir, "model.safetensors")
        expected_size = None
        try:
            head = requests.head(st_url, allow_redirects=True, timeout=15)
            if head.status_code == 200 and "Content-Length" in head.headers:
                expected_size = int(head.headers["Content-Length"])
        except Exception:
            pass

        if download_file(st_url, st_dest, expected_size=expected_size):
            success_count += 1

    print(f"\nSummary: {success_count}/{total_files} files verified/downloaded.")
    if success_count == total_files:
        print("ALL KRONOS MODELS AND TOKENIZERS ARE SUCCESSFULLY READY!")
    else:
        print("Some files failed to download.")

if __name__ == "__main__":
    main()
