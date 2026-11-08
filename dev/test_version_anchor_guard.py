#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/test_version_anchor_guard.py -- آزمون خودکار رفتار گارد لنگه‌های نسخه.

بررسی سناریوهای:
  ۱. وضعیت سالم: تطابق ۱۰۰٪ تمام ۱۱ لنگه
  ۲. ناسازگاری: اختلاف نسخه در frontend-v2 یا backend-go یا installer
  ۳. فایل مفقود: حذف یکی از فایل‌های لنگه
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dev"))

import version_anchor_guard  # noqa: E402


class TestVersionAnchorGuard(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="bt_version_guard_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _setup_tree(self, version="1.0.95", overrides=None):
        if overrides is None:
            overrides = {}

        # 1. bors_config.py
        v = overrides.get("bors_config", version)
        with open(os.path.join(self.tmp_dir, "bors_config.py"), "w", encoding="utf-8") as f:
            f.write(f'APP_VERSION = "{v}"\n')

        # 2. frontend-v2
        os.makedirs(os.path.join(self.tmp_dir, "frontend-v2"), exist_ok=True)
        v = overrides.get("frontend_v2", version)
        if v is not None:
            with open(os.path.join(self.tmp_dir, "frontend-v2", "package.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"name": "bors-terminal-ui", "version": "{v}"}}\n')
            with open(os.path.join(self.tmp_dir, "frontend-v2", "package-lock.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"name": "bors-terminal-ui", "version": "{v}", "packages": {{"": {{"version": "{v}"}}}}}}\n')

        # 3. backend-go/cmd/bors-producer
        os.makedirs(os.path.join(self.tmp_dir, "backend-go", "cmd", "bors-producer"), exist_ok=True)
        v = overrides.get("backend_go", version)
        if v is not None:
            with open(os.path.join(self.tmp_dir, "backend-go", "cmd", "bors-producer", "main.go"), "w", encoding="utf-8") as f:
                f.write(f'package main\n\nvar version = "{v}"\n')

        # 4. frontend / src-tauri
        os.makedirs(os.path.join(self.tmp_dir, "frontend", "src-tauri"), exist_ok=True)
        v = overrides.get("tauri", version)
        if v is not None:
            with open(os.path.join(self.tmp_dir, "frontend", "src-tauri", "tauri.conf.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"package": {{"version": "{v}"}}, "version": "{v}"}}\n')
            with open(os.path.join(self.tmp_dir, "frontend", "src-tauri", "Cargo.toml"), "w", encoding="utf-8") as f:
                f.write(f'[package]\nname = "bors-shell"\nversion = "{v}"\n')

        # 5. installer
        os.makedirs(os.path.join(self.tmp_dir, "installer"), exist_ok=True)
        v = overrides.get("installer", version)
        if v is not None:
            with open(os.path.join(self.tmp_dir, "installer", "bors_setup.iss"), "w", encoding="utf-8") as f:
                f.write(f'#define AppVersion "{v}"\n')

        # 6. legacy frontend
        v = overrides.get("frontend_legacy", version)
        if v is not None:
            with open(os.path.join(self.tmp_dir, "frontend", "package.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"name": "bors-legacy", "version": "{v}"}}\n')
            with open(os.path.join(self.tmp_dir, "frontend", "package-lock.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"name": "bors-legacy", "version": "{v}", "packages": {{"": {{"version": "{v}"}}}}}}\n')

    def test_live_repo_passes(self):
        """راستی‌آزمایی اینکه کل ۱۱ لنگه ریپوی زنده یکسان و پاس هستند."""
        anchors = version_anchor_guard.collect_anchors(ROOT)
        code = version_anchor_guard.evaluate_anchors(anchors, verbose=False)
        self.assertEqual(code, 0, "مخزن زنده باید در گارد لنگه‌های نسخه با کد ۰ پاس شود")
        self.assertEqual(len(anchors), 11, "باید دقیقاً ۱۱ لنگه بررسی شود")

    def test_synthetic_tree_all_match(self):
        """هنگام تطابق کامل ۱۱ لنگه، خروجی باید ۰ باشد."""
        self._setup_tree(version="2.0.0")
        anchors = version_anchor_guard.collect_anchors(self.tmp_dir)
        code = version_anchor_guard.evaluate_anchors(anchors, verbose=False)
        self.assertEqual(code, 0)

    def test_mismatched_frontend_v2_fails(self):
        """اگر frontend-v2 نسخه ناهماهنگ داشته باشد، گارد باید کد ۱ بدهد."""
        self._setup_tree(version="1.0.95", overrides={"frontend_v2": "0.1.0"})
        anchors = version_anchor_guard.collect_anchors(self.tmp_dir)
        code = version_anchor_guard.evaluate_anchors(anchors, verbose=False)
        self.assertEqual(code, 1, "اختلاف نسخه در frontend-v2 باید گارد را مردود کند")

    def test_mismatched_backend_go_fails(self):
        """اگر باینری Go تولیدکننده نسخه ناهماهنگ داشته باشد، گارد باید کد ۱ بدهد."""
        self._setup_tree(version="1.0.95", overrides={"backend_go": "1.0.94"})
        anchors = version_anchor_guard.collect_anchors(self.tmp_dir)
        code = version_anchor_guard.evaluate_anchors(anchors, verbose=False)
        self.assertEqual(code, 1, "اختلاف نسخه در backend-go باید گارد را مردود کند")

    def test_missing_anchor_file_fails(self):
        """اگر یکی از فایل‌های لنگه (مثلاً installer یا frontend-v2) مفقود باشد، گارد باید کد ۱ بدهد."""
        self._setup_tree(version="1.0.95", overrides={"installer": None})
        anchors = version_anchor_guard.collect_anchors(self.tmp_dir)
        code = version_anchor_guard.evaluate_anchors(anchors, verbose=False)
        self.assertEqual(code, 1, "مفقود بودن فایل لنگه باید گارد را مردود کند")


if __name__ == "__main__":
    unittest.main()
