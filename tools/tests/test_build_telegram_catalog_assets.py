#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/tests/test_build_telegram_catalog_assets.py — آزمونِ پارسِ export تلگرام

شکلِ fixture عیناً از messages.html واقعیِ 2026-11-03 برداشته شده است، نه از
فرضِ ما: img به _thumb اشاره می‌کند، href به فایلِ تمام‌اندازه، کپشن در
div.text بعد از تصویر است، و نامِ پیوست در پیامِ *بعدی* داخل title bold
می‌آید و با «Not included» علامت می‌خورد.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.build_telegram_catalog_assets import (
    ExportShapeError,
    build_rows,
    parse_export,
    to_payload,
)

FIXTURE_HTML = """
<div class="message service" id="message-1">
  <div class="body details">2 November 2026</div>
</div>

<div class="message default clearfix" id="message758161">
  <div class="body">
    <div class="pull_right date details" title="02.11.2026 12:01:58 UTC+03:30">12:01</div>
    <div class="media_wrap clearfix">
      <a class="photo_wrap clearfix pull_left" href="photos/photo_1@02-11-2026_12-01-58.jpg">
        <img class="photo" src="photos/photo_1@02-11-2026_12-01-58_thumb.jpg" style="width: 260px; height: 123px"/>
      </a>
    </div>
    <div class="text"><strong>FB_OBwin MT4 Indicator</strong></div>
  </div>
</div>

<div class="message default clearfix joined" id="message758162">
  <div class="body">
    <div class="media_wrap clearfix">
      <div class="media clearfix pull_left media_file">
        <div class="body">
          <div class="title bold">FB_OBwin.ex4</div>
          <div class="description">Not included, change data exporting settings to download.</div>
          <div class="status details">17.4 KB</div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="message default clearfix joined" id="message758163">
  <div class="body">
    <div class="media_wrap clearfix">
      <a class="photo_wrap clearfix pull_left" href="photos/photo_2@02-11-2026_12-01-58.jpg">
        <img class="photo" src="photos/photo_2@02-11-2026_12-01-58_thumb.jpg" style="width: 119px; height: 260px"/>
      </a>
    </div>
    <div class="text">Fibo RSI8 SingleShot_v122<br>Timeframe M30</div>
  </div>
</div>

<div class="message default clearfix joined" id="message758164">
  <div class="body">
    <div class="media_wrap clearfix">
      <div class="media clearfix pull_left media_file">
        <div class="body">
          <div class="title bold">BBRSI&amp;MA_v2@IndicatorsforTV.mq4</div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="message default clearfix joined" id="message758165">
  <div class="body">
    <div class="media_wrap clearfix">
      <a class="photo_wrap clearfix pull_left" href="photos/photo_8@02-11-2026_12-01-58.jpg">
        <img class="photo" src="photos/photo_8@02-11-2026_12-01-58_thumb.jpg" style="width: 260px; height: 195px"/>
      </a>
    </div>
  </div>
</div>
"""


def _write_sources(entries, root):
    for entry in entries:
        target = root / entry.src
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1280, 640)).save(target)


def test_parse_export_reads_the_real_markup():
    entries = parse_export(FIXTURE_HTML)
    assert len(entries) == 3
    assert entries[0].src == "photos/photo_1@02-11-2026_12-01-58.jpg"
    assert entries[0].caption == "FB_OBwin MT4 Indicator"
    assert entries[0].files == ["FB_OBwin.ex4"]


def test_attachments_join_forward_to_the_previous_photo():
    entries = parse_export(FIXTURE_HTML)
    assert entries[1].files == ["BBRSI&MA_v2@IndicatorsforTV.mq4"]
    assert entries[2].files == []


def test_photo_without_a_text_block_has_an_empty_caption():
    entries = parse_export(FIXTURE_HTML)
    assert entries[2].caption == ""


def test_caption_lines_are_kept_and_blank_lines_dropped():
    entries = parse_export(FIXTURE_HTML)
    assert entries[1].caption.splitlines()[0] == "Fibo RSI8 SingleShot_v122"
    assert "Timeframe M30" in entries[1].caption


def test_build_rows_reads_dims_from_the_image_not_the_style(tmp_path):
    entries = parse_export(FIXTURE_HTML)
    _write_sources(entries, tmp_path)
    rows = build_rows(entries, tmp_path, expected=3)
    assert rows[0].dims == "1280×640"
    assert rows[0].id == "p01" and rows[0].photo == "p01.webp"


def test_to_payload_emits_camelcase_keys(tmp_path):
    entries = parse_export(FIXTURE_HTML)
    _write_sources(entries, tmp_path)
    rows = build_rows(entries, tmp_path, expected=3)
    payload = to_payload(rows)
    assert set(payload[0]) == {"id", "titleEn", "captionEn", "photo", "dims", "attachments"}
    assert payload[0]["attachments"] == ["FB_OBwin.ex4"]


def test_build_rows_fails_when_count_disagrees(tmp_path):
    entries = parse_export(FIXTURE_HTML)
    with pytest.raises(ExportShapeError):
        build_rows(entries, tmp_path, expected=64)


def test_build_rows_fails_when_the_source_image_is_absent(tmp_path):
    entries = parse_export(FIXTURE_HTML)
    _write_sources(entries[:-1], tmp_path)
    with pytest.raises(ExportShapeError):
        build_rows(entries, tmp_path, expected=3)
