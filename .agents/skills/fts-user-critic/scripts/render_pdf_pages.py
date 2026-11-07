#!/usr/bin/env python3
"""Render PDF pages to PNG for visual review. Prints one JSON object only."""
import argparse
import json
import sys
from pathlib import Path


def parse_pages(spec: str, total: int) -> list[int]:
    if spec.strip().lower() == "all":
        return list(range(1, total + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            if start > end:
                start, end = end, start
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    bad = [p for p in pages if p < 1 or p > total]
    if bad:
        raise ValueError(f"pages out of range 1..{total}: {bad}")
    return sorted(pages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render FTS PDF pages to PNG")
    parser.add_argument("--pdf", required=True, help="Path to the PDF")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--pages", default="all", help="all or 1-34 or 1,3,5-7")
    parser.add_argument("--dpi", type=int, default=120, help="Render DPI (default 120)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PNGs")
    args = parser.parse_args()

    try:
        import pymupdf  # noqa: F401
    except Exception:
        try:
            import fitz as pymupdf  # type: ignore
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"PyMuPDF unavailable: {exc}"}, ensure_ascii=False))
            return 2

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    if not pdf_path.exists():
        print(json.dumps({"ok": False, "error": f"PDF not found: {pdf_path}"}, ensure_ascii=False))
        return 2

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"cannot open PDF: {exc}"}, ensure_ascii=False))
        return 2

    total = doc.page_count
    try:
        pages = parse_pages(args.pages, total)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = args.dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    rendered = []
    skipped = []
    try:
        for number in pages:
            target = out_dir / f"page-{number:02d}.png"
            if target.exists() and not args.force:
                skipped.append(str(target))
                continue
            page = doc.load_page(number - 1)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(str(target))
            rendered.append(str(target))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"render failed: {exc}"}, ensure_ascii=False))
        return 2
    finally:
        doc.close()

    print(json.dumps({
        "ok": True,
        "pdf": str(pdf_path),
        "pages_total": total,
        "pages_requested": pages,
        "rendered": rendered,
        "skipped": skipped,
        "out_dir": str(out_dir),
        "dpi": args.dpi,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
