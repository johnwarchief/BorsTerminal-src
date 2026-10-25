#!/usr/bin/env python3
"""Build the three local update manifests used by the M2 updater test.

Input is the manifest emitted by `tinyjs publish` (Windows x86_64 block).
Outputs install/checksum/rollback variants next to a copy of the zip. The
checksum variant advertises 0.3.2 with a wrong sha256; the rollback variant
advertises 0.3.2 with the real 0.3.1 payload so the swap is reached and then
blocked by a deliberately locked file.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published-manifest", required=True)
    ap.add_argument("--published-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wrong-sha", default="0" * 64)
    args = ap.parse_args()

    src = Path(args.published_manifest)
    base = json.loads(src.read_text(encoding="utf-8"))
    win = base["win"]["x86_64"]
    zip_name = win["url"].rsplit("/", 1)[-1]
    zip_path = Path(args.published_dir) / zip_name
    real = sha256_file(zip_path)
    if real.lower() != str(win["sha256"]).lower():
        raise SystemExit(f"published manifest sha256 mismatch: {real} != {win['sha256']}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, out / zip_name)

    install = copy.deepcopy(base)
    (out / "install").mkdir(exist_ok=True)
    (out / "install" / "manifest.json").write_text(
        json.dumps(install, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(zip_path, out / "install" / zip_name)

    checksum = copy.deepcopy(base)
    checksum["version"] = "0.3.2"
    checksum["win"]["version"] = "0.3.2"
    checksum["win"]["x86_64"]["version"] = "0.3.2"
    checksum["win"]["x86_64"]["sha256"] = args.wrong_sha
    checksum["win"]["sha256"] = args.wrong_sha
    (out / "checksum").mkdir(exist_ok=True)
    (out / "checksum" / "manifest.json").write_text(
        json.dumps(checksum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(zip_path, out / "checksum" / zip_name)

    rollback = copy.deepcopy(base)
    rollback["version"] = "0.3.2"
    rollback["win"]["version"] = "0.3.2"
    rollback["win"]["x86_64"]["version"] = "0.3.2"
    (out / "rollback").mkdir(exist_ok=True)
    (out / "rollback" / "manifest.json").write_text(
        json.dumps(rollback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(zip_path, out / "rollback" / zip_name)

    print(json.dumps({
        "zip": zip_name,
        "zip_sha256": real,
        "install_version": install.get("version"),
        "current_baseline": base.get("version"),
        "checksum_wrong_sha": args.wrong_sha,
        "rollback_manifest_version": rollback.get("version"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
