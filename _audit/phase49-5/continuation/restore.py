#!/usr/bin/env python3
"""Restore a SHA-pinned continuation kit without overwriting existing files."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import zipfile


def safe_path(root, name):
    rel = PurePosixPath(name)
    if (not name or rel.is_absolute() or ".." in rel.parts
            or "\\" in name or ":" in name or rel.as_posix() != name):
        raise ValueError("unsafe archive path: " + name)
    target = root.joinpath(*rel.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("path escapes destination: " + name)
    return target


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def check_file(path, expected):
    actual = {"size": path.stat().st_size, "sha256": digest(path)}
    if any(actual[k] != expected[k] for k in actual):
        raise ValueError("size/SHA-256 mismatch: " + str(path))
    if "sqlite" in expected:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            counts = {t: con.execute('SELECT COUNT(*) FROM "' + t.replace('"', '""')
                                     + '"').fetchone()[0] for t in tables}
            actual["sqlite"] = {
                "integrity_check": [r[0] for r in con.execute("PRAGMA integrity_check")],
                "tables": counts,
            }
        finally:
            con.close()
        if actual["sqlite"]["integrity_check"] != ["ok"] or actual["sqlite"] != expected["sqlite"]:
            raise ValueError("SQLite integrity/count mismatch: " + str(path))
    return actual


def restore(manifest_path, data_root, destination):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    data_root, destination = Path(data_root).resolve(), Path(destination).resolve()
    if (manifest.get("schema") != "phase49-continuation-v1"
            or not manifest.get("files") or not manifest.get("parts")):
        raise ValueError("invalid or empty continuation manifest")
    targets = [safe_path(destination, e["path"]) for e in manifest["files"]]
    if len(set(targets)) != len(targets):
        raise ValueError("duplicate destination paths")
    for target in targets:
        candidates = [target]
        if target.suffix == ".db":
            candidates.extend(Path(str(target) + s) for s in ("-wal", "-shm", "-journal"))
        for candidate in candidates:
            if candidate.exists() or candidate.is_symlink():
                raise FileExistsError("refusing existing file/recovery data: " + str(candidate))
    parts = [safe_path(data_root, e["path"]) for e in manifest["parts"]]
    if len(set(parts)) != len(parts):
        raise ValueError("duplicate archive parts")
    for part, expected in zip(parts, manifest["parts"]):
        check_file(part, expected)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase49-restore-", dir=destination.parent) as tmp:
        stage = Path(tmp)
        archive = stage / "kit.zip"
        with archive.open("xb") as out:
            for part in parts:
                with part.open("rb") as src:
                    shutil.copyfileobj(src, out, 1 << 22)
        check_file(archive, manifest["archive"])
        payload = stage / "payload"
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            expected_names = [e["path"] for e in manifest["files"]]
            if len(names) != len(set(names)) or set(names) != set(expected_names):
                raise ValueError("archive members differ from manifest")
            for expected in manifest["files"]:
                name = expected["path"]
                info = z.getinfo(name)
                if info.is_dir() or info.file_size != expected["size"]:
                    raise ValueError("archive member size/type mismatch: " + name)
                local = safe_path(payload, name)
                local.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, local.open("xb") as out:
                    shutil.copyfileobj(src, out, 1 << 22)
                check_file(local, expected)

        rows = []
        for expected in manifest["files"]:
            target = safe_path(destination, expected["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with safe_path(payload, expected["path"]).open("rb") as src, target.open("xb") as out:
                shutil.copyfileobj(src, out, 1 << 22)
            rows.append({"path": expected["path"], **check_file(target, expected)})
    return {"status": "PASS", "destination": str(destination),
            "manifest_sha256": digest(Path(manifest_path)),
            "archive_sha256": manifest["archive"]["sha256"],
            "file_count": len(rows), "files": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--destination", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError(args.report)
    report = restore(args.manifest, args.data_root, args.destination)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
