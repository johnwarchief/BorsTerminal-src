import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location("restore", Path(__file__).with_name("restore.py"))
restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(restore)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.dest = self.root / "checkout"
        self.dest.mkdir()
        self.fixture = self.root / "fixture.db"
        with sqlite3.connect(self.fixture) as con:
            con.execute("CREATE TABLE reference_raw(symbol TEXT, close REAL)")
            con.execute("INSERT INTO reference_raw VALUES('sample', 123.5)")
        con.close()
        self.payload = self.fixture.read_bytes()
        self.make_kit()

    def make_kit(self, name="_audit/phase49-3/db/cohort.db", payload=None, extra=False):
        content = self.payload if payload is None else payload
        archive = self.root / "kit.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(name, content)
            if extra:
                z.writestr("unexpected.txt", "not in manifest")
        packed = archive.read_bytes()
        part = self.data / "kit.zip.001"
        part.write_bytes(packed)
        self.manifest = {
            "schema": "phase49-continuation-v1",
            "archive": {"size": len(packed), "sha256": hashlib.sha256(packed).hexdigest()},
            "parts": [{"path": part.name, "size": len(packed),
                       "sha256": hashlib.sha256(packed).hexdigest()}],
            "files": [{"path": name, "size": len(self.payload),
                       "sha256": hashlib.sha256(self.payload).hexdigest(),
                       "sqlite": {"integrity_check": ["ok"], "tables": {"reference_raw": 1}}}],
        }
        self.mpath = self.data / "manifest.json"
        self.save_manifest()

    def save_manifest(self):
        self.mpath.write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_restore(self):
        return restore.restore(self.mpath, self.data, self.dest)

    def test_roundtrip_reads_persisted_database(self):
        report = self.run_restore()
        p = self.dest / self.manifest["files"][0]["path"]
        self.assertTrue(p.is_file(), "restore must write the archived file")
        self.assertEqual(p.read_bytes(), self.payload)
        con = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
        try:
            self.assertEqual(con.execute("SELECT * FROM reference_raw").fetchall(), [("sample", 123.5)])
        finally:
            con.close()
        self.assertEqual(report["files"][0]["sqlite"]["tables"], {"reference_raw": 1})
        self.assertEqual(report["status"], "PASS")

    def test_existing_file_is_never_overwritten(self):
        p = self.dest / self.manifest["files"][0]["path"]
        p.parent.mkdir(parents=True)
        p.write_bytes(b"keep user data")
        with self.assertRaises(FileExistsError):
            self.run_restore()
        self.assertEqual(p.read_bytes(), b"keep user data")

    def test_existing_sqlite_sidecars_are_rejected(self):
        p = self.dest / self.manifest["files"][0]["path"]
        p.parent.mkdir(parents=True)
        for suffix in ["-wal", "-shm", "-journal"]:
            with self.subTest(suffix=suffix):
                sidecar = Path(str(p) + suffix)
                sidecar.write_bytes(b"preserve existing recovery data")
                try:
                    with self.assertRaises(FileExistsError):
                        self.run_restore()
                    self.assertFalse(p.exists())
                    self.assertEqual(sidecar.read_bytes(), b"preserve existing recovery data")
                finally:
                    sidecar.unlink()

    def test_part_hash_is_checked_independently(self):
        self.manifest["parts"][0]["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "kit.zip.001"):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_assembled_archive_hash_is_checked_independently(self):
        self.manifest["archive"]["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "size/SHA-256 mismatch"):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_corrupt_part_fails_before_install(self):
        (self.data / "kit.zip.001").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_missing_part_fails_before_install(self):
        (self.data / "kit.zip.001").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_member_hash_mismatch_fails_before_install(self):
        self.make_kit(payload=bytes([self.payload[0] ^ 1]) + self.payload[1:])
        with self.assertRaisesRegex(ValueError, "size/SHA-256 mismatch"):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_sqlite_count_mismatch_fails_before_install(self):
        self.manifest["files"][0]["sqlite"]["tables"]["reference_raw"] = 2
        self.save_manifest()
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_unsafe_paths_fail_before_install(self):
        for name in ["../escape.db", "/escape.db", "C:/escape.db", "a\\escape.db", "a/../escape.db"]:
            with self.subTest(name=name):
                self.make_kit(name=name)
                with self.assertRaises(ValueError):
                    self.run_restore()
                self.assertEqual(list(self.dest.iterdir()), [])

    def test_unlisted_archive_member_is_rejected(self):
        self.make_kit(extra=True)
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_empty_manifest_cannot_pass(self):
        self.manifest["files"] = []
        self.save_manifest()
        with self.assertRaises(ValueError):
            self.run_restore()


if __name__ == "__main__":
    unittest.main()
