# -*- coding: utf-8 -*-
"""_audit/dump_jozve_pages.py — بیرون‌کشیدنِ صفحۀ خودِ جزوۀ چاپی از PDF

`docs/جزوه FTS.pdf` سی و چهار سطر تصویرِ اسکن‌شده است (JPEG2000، بی‌لایۀ متن)، پس
هیچ ابزارِ متنی روی آن کار نمی‌کند و نقل‌قولِ دست‌نویس‌ها از رویدادِ پیشین دو
نسخۀ ناهمخوان دارند (`jozve_FTS_handwritten_pages_1-24.md` در برابر
`transcription_p01-p09.md`). مرجعِ این حسابرسی خودِ جزوه است، پس همان تصویرِ
صفحه را بدونِ هیچ تبدیلِ دیگری بیرون می‌دهیم تا چشمِ انسان/مدل قضاوت کند، نه
OCR.

    py -3.14 _audit/dump_jozve_pages.py 4 5 6
"""
import io
import re
import sys
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "docs", "جزوه FTS.pdf")
OUT = os.path.join(ROOT, "_audit")


def page_images():
    raw = open(PDF, "rb").read()
    blocks = []
    for m in re.finditer(rb"/Subtype\s*/Image", raw):
        s = raw.find(b"stream", m.end(), m.end() + 4000)
        if s < 0:
            continue
        e = raw.find(b"endstream", s)
        if e < 0:
            continue
        blocks.append(raw[s + 6 : e].strip(b"\r\n"))
    return blocks


def main():
    wanted = [int(a) for a in sys.argv[1:]] or [4]
    blocks = page_images()
    print("صفحۀ PDF:", len(blocks))
    for n in wanted:
        if not 1 <= n <= len(blocks):
            print("بیرونِ دامنه:", n)
            continue
        im = Image.open(io.BytesIO(blocks[n - 1]))
        path = os.path.join(OUT, "jozve_p%02d.png" % n)
        im.convert("RGB").save(path, "PNG")
        print("نوشته شد:", os.path.relpath(path, ROOT), im.size)


if __name__ == "__main__":
    main()
