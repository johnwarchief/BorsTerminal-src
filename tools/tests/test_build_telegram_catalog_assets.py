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
    MAX_WIDTH,
    ExportShapeError,
    build_rows,
    main,
    parse_export,
    to_payload,
    write_photos,
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


def _build_synthetic_export(
    export_dir: Path,
    *,
    rows: int = 64,
    no_caption: int = 3,
    distinct_sources: int = 57,
    distinct_attachments: int = 60,
) -> None:
    """exportِ مصنوعی که هر چهار دروازۀ شکلی را دقیقاً صدق می‌کند
    (64/3/57/60، همان عددهایِ spec §11 روی exportِ واقعی). با kwargs می‌توان
    یک دروازه را شکست و ثابت کرد main بلند می‌شکند و چیزی نمی‌نویسد."""
    export_dir.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for i in range(1, rows + 1):
        src_idx = i if i <= distinct_sources else i - distinct_sources
        src = f"photos/photo_{src_idx}@02-11-2026_12-01-58.jpg"
        text = "" if 8 <= i < 8 + no_caption else f'<div class="text">Cap {i}</div>'
        blocks.append(
            f'<div class="message default clearfix" id="m{i}"><div class="body">'
            f'<div class="media_wrap clearfix">'
            f'<a class="photo_wrap clearfix pull_left" href="{src}">'
            f'<img class="photo" src="{src[:-4]}_thumb.jpg"/></a>'
            f"</div>{text}</div></div>"
        )
        if i <= distinct_attachments:
            blocks.append(
                f'<div class="message default clearfix joined" id="f{i}">'
                '<div class="body"><div class="media_wrap clearfix">'
                '<div class="media clearfix pull_left media_file"><div class="body">'
                f'<div class="title bold">file_{i}.mq4</div>'
                "</div></div></div></div></div>"
            )
    (export_dir / "messages.html").write_text("\n".join(blocks), encoding="utf-8")
    for s in range(1, distinct_sources + 1):
        target = export_dir / f"photos/photo_{s}@02-11-2026_12-01-58.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 60)).save(target)


def _main_argv(export_dir: Path, tmp_path: Path, extra: tuple = ()) -> list[str]:
    return [
        "--export-dir", str(export_dir),
        "--out-dir", str(tmp_path / "out"),
        "--json-out", str(tmp_path / "catalog.json"),
        *extra,
    ]


def test_main_accepts_an_export_matching_all_four_gates(tmp_path, capsys):
    export = tmp_path / "export"
    _build_synthetic_export(export)
    assert main(_main_argv(export, tmp_path, ("--dry-run",))) == 0
    printed = capsys.readouterr().out
    assert "rows: 64" in printed
    assert "rows with no caption: 3" in printed
    assert "distinct source images: 57" in printed
    assert "attachment names: 60" in printed


@pytest.mark.parametrize(
    "broken_gate",
    [
        {"no_caption": 2},
        {"no_caption": 4},
        {"distinct_sources": 56},
        {"distinct_sources": 58},
        {"distinct_attachments": 59},
        {"distinct_attachments": 61},
    ],
)
def test_main_fails_loudly_and_writes_nothing_on_any_gate_break(
    tmp_path, broken_gate
):
    export = tmp_path / "export"
    _build_synthetic_export(export, **broken_gate)
    with pytest.raises(ExportShapeError):
        main(_main_argv(export, tmp_path))
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "catalog.json").exists()


def test_dims_is_the_source_size_not_the_delivered_webp(tmp_path):
    """معنای قفل‌شده در review: dims ابعادِ تصویرِ مبدأِ export است، هرچند
    webpِ تحویلی روی MAX_WIDTH سقف می‌خورد (نسبت حفظ). اگر کسی بعداً dims را
    بی‌صدا به اندازهٔ فایلِ تحویلی «اصلاح» کند، این آزمون قرمز می‌شود."""
    entries = parse_export(FIXTURE_HTML)
    _write_sources(entries, tmp_path)
    rows = build_rows(entries, tmp_path, expected=3)
    out_dir = tmp_path / "webp"
    write_photos(rows, entries, tmp_path, out_dir)
    assert rows[0].dims == "1280×640"
    with Image.open(out_dir / "p01.webp") as delivered:
        assert delivered.size == (MAX_WIDTH, 450)
