#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/build_telegram_catalog_assets.py — از export تلگرام به assets برنامۀ مهاجرتی

ورودی: پوشۀ «Export chat history» گروه indicators (فقط Photos تیک خورده).
خروجی: 64 فایل webp و telegram-indicators.json در frontend-v2.

export تنها سرچشمۀ ردیف‌هاست. telegram_indicators_catalog.json خوانده نمی‌شود:
آن فایل از dumpِ صفحه‌خوان ساخته شده و ترتیبش با پیام‌های واقعی فقط در ۱۰ ردیف
از ۶۴ می‌خواند، چون پیام‌های متنیِ ادامهٔ کپشن را سطرِ مستقل شماریده است.

هر انحرافِ شکلی بلند شکست می‌خورد، نه اینکه بی‌صدا سطرِ بی‌عکس بسازد — همان
دردی که frontend/src/features/technical/lib/tvIndicatorCatalog.ts:1 نوشته است.
چهار عددِ spec §11 (تعدادِ ردیف، ردیف‌های بی‌کپشن، مبدأهایِ متمایز، نام‌های
پیوستِ متمایز) ثابتِ module‌اند و در main پیش از نوشتنِ هر فایل وارسی می‌شوند.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOTAL_ROWS = 64
MAX_WIDTH = 900
WEBP_QUALITY = 78

# سه دروازۀ شکلیِ دیگر، هم‌سطحِ TOTAL_ROWS: همان سه عددی که spec §11 روی
# exportِ 2026-11-03 اندازه گرفته است. اگر چت پستِ تازه بگیرد، درستِ همان
# کاری را باید بکنیم که با TOTAL_ROWS می‌کنیم: ویرایشِ همین ثابت‌ها؛ پس این
# دروازه‌ها از دروازۀ تعدادِ ردیف شکننده‌تر نیستند. هر چهار عدد در main
# وارسی می‌شوند — پیش از write_photos، تا انحرافِ شکلی چیزی ننویسد.
EXPECTED_NO_CAPTION_ROWS = 3
EXPECTED_DISTINCT_SOURCE_IMAGES = 57
EXPECTED_DISTINCT_ATTACHMENT_NAMES = 60


class ExportShapeError(RuntimeError):
    """export با شکلی که در spec §۱۱ ثبت شده نمی‌خواند. چیزی نوشته نمی‌شود."""


@dataclass
class PhotoEntry:
    src: str
    caption: str
    files: list[str] = field(default_factory=list)


@dataclass
class CatalogRow:
    id: str
    title_en: str
    caption_en: str
    photo: str
    # معنا: ابعادِ تصویرِ مبدأ (source) در export، نه ابعادِ فایلِ webp
    # تحویل‌شده. تحویلی روی MAX_WIDTH سقف می‌خورد و نسبتِ اندازۀ اصلی حفظ
    # می‌شود؛ آزمونِ test_dims_is_the_source_size_not_the_delivered_webp
    # همین معنا را قفل می‌کند تا کسی بعداً بی‌صدا dims را به اندازهٔ فایل
    # تحویلی «اصلاح» نکند (p01: dims=1280×608، فایلِ روی‌دیسک 900×428).
    dims: str
    attachments: list[str] = field(default_factory=list)


def _clean_text(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _clean_name(fragment: str) -> str:
    """نامِ فایل: entity باز می‌شود ولی فاصله‌های داخلی دست نمی‌خورند،
    چون همان‌طور که در تلگرام ذخیره شده‌اند ممکن است دو فاصله داشته باشند."""
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_export(html_text: str) -> list[PhotoEntry]:
    rows: list[PhotoEntry] = []
    for block in re.split(r"(?=<div class=\"message )", html_text):
        if "photo_wrap" in block:
            href = re.search(r"<a class=\"photo_wrap[^\"]*\" href=\"([^\"]+)\"", block)
            if href is None:
                continue
            caption = re.search(r"<div class=\"text\">(.*?)</div>", block, re.S)
            rows.append(
                PhotoEntry(
                    src=href.group(1).strip(),
                    caption=_clean_text(caption.group(1)) if caption else "",
                )
            )
        elif rows and "media_file" in block:
            for name in re.findall(r"<div class=\"title bold\">(.*?)</div>", block, re.S):
                cleaned = _clean_name(name)
                if cleaned and cleaned not in rows[-1].files:
                    rows[-1].files.append(cleaned)
    return rows


def image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as im:
        return im.width, im.height


def build_rows(
    entries: list[PhotoEntry], export_dir: Path, expected: int = TOTAL_ROWS
) -> list[CatalogRow]:
    if len(entries) != expected:
        raise ExportShapeError(f"export has {len(entries)} photo messages, expected {expected}")
    rows: list[CatalogRow] = []
    for i, entry in enumerate(entries, start=1):
        source = export_dir / entry.src
        if not source.is_file():
            raise ExportShapeError(f"p{i:02d}: source image missing at {source}")
        width, height = image_size(source)
        lines = entry.caption.splitlines()
        rows.append(
            CatalogRow(
                id=f"p{i:02d}",
                title_en=lines[0] if lines else "",
                caption_en="\n".join(lines[1:]) if len(lines) > 1 else "",
                photo=f"p{i:02d}.webp",
                dims=f"{width}×{height}",
                attachments=list(entry.files),
            )
        )
    return rows


def to_payload(rows: list[CatalogRow]) -> list[dict[str, Any]]:
    """کلیدها صریحاً camelCase ساخته می‌شوند، نه از __dict__ِ dataclass:
    zod در telegramIndicatorCatalog.ts title_en را نمی‌شناسد."""
    return [
        {
            "id": r.id,
            "titleEn": r.title_en,
            "captionEn": r.caption_en,
            "photo": r.photo,
            "dims": r.dims,
            "attachments": list(r.attachments),
        }
        for r in rows
    ]


def write_photos(
    rows: list[CatalogRow], entries: list[PhotoEntry], export_dir: Path, out_dir: Path
) -> int:
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for row, entry in zip(rows, entries):
        with Image.open(export_dir / entry.src) as im:
            im = im.convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)))
            dest = out_dir / row.photo
            im.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
            total += dest.stat().st_size
    return total


def find_export_html(export_dir: Path) -> Path:
    candidates = sorted(export_dir.glob("*.html"))
    preferred = [c for c in candidates if c.name == "messages.html"] or candidates
    if not preferred:
        raise ExportShapeError(f"no export html found under {export_dir}")
    return preferred[0]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export-dir", required=True, type=Path)
    ap.add_argument(
        "--out-dir",
        default=Path("frontend-v2/src/features/technical/assets/telegram-indicators"),
        type=Path,
    )
    ap.add_argument(
        "--json-out",
        default=Path("frontend-v2/src/features/technical/data/telegram-indicators.json"),
        type=Path,
    )
    ap.add_argument("--dry-run", action="store_true", help="فقط بساز و گزارش کن؛ چیزی ننویس")
    args = ap.parse_args(argv)

    html_path = find_export_html(args.export_dir)
    entries = parse_export(html_path.read_text(encoding="utf-8", errors="replace"))
    rows = build_rows(entries, args.export_dir)

    no_caption = [r.id for r in rows if not r.title_en]
    distinct_sources = len({e.src for e in entries})
    distinct_attachments = len({f for r in rows for f in r.attachments})
    print(f"html: {html_path.name}")
    print(f"rows: {len(rows)}")
    print(f"rows with no caption: {len(no_caption)} {no_caption}")
    print(f"distinct source images: {distinct_sources}")
    print(f"attachment names: {distinct_attachments}")

    # هر چهار دروازۀ شکلی اینجا اثبات می‌شوند، نه فقط چاپ: TOTAL_ROWS را
    # build_rows زده است و سه دروازۀ دیگر همین‌جا. انحراف بلند می‌شکند و
    # چون این وارسی پیش از write_photos است، هیچ فایلِ تازه‌ای نوشته نمی‌شود.
    if len(no_caption) != EXPECTED_NO_CAPTION_ROWS:
        raise ExportShapeError(
            f"rows with no caption: {len(no_caption)} {no_caption}, "
            f"expected {EXPECTED_NO_CAPTION_ROWS}"
        )
    if distinct_sources != EXPECTED_DISTINCT_SOURCE_IMAGES:
        raise ExportShapeError(
            f"distinct source images: {distinct_sources}, "
            f"expected {EXPECTED_DISTINCT_SOURCE_IMAGES}"
        )
    if distinct_attachments != EXPECTED_DISTINCT_ATTACHMENT_NAMES:
        raise ExportShapeError(
            f"attachment names: {distinct_attachments}, "
            f"expected {EXPECTED_DISTINCT_ATTACHMENT_NAMES}"
        )

    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    written = write_photos(rows, entries, args.export_dir, args.out_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(to_payload(rows), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {len(rows)} webp files, {written / 1_048_576:.2f} MB total")
    print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
