# Source precedence for FTS criticism

1. **Primary methodology:** `docs/جزوه FTS.pdf` (34 pages, image-only) and
   `docs/FTS.CHART_3.pdf` (4 pages). Read all pages visually. The PDF wins over
   every derived document.
2. **Explicit owner correction:** `docs/fts-notes/OWNER_RULINGS.md`, only where
   it names the disputed point and gives a clear ruling.
3. **Derived engineering specs and audits:** `docs/FTS_SPEC.md`,
   `docs/FTS_SYSTEM_SPECIFICATION_v2.md`, `docs/FTS-RULE-ALGORITHM-MAP.md`, and
   dated audit reports. Use them to locate code and understand intent, not as
   authority over the PDF.
4. **Transcriptions and extracted text:** `docs/fts-notes/transcription_*.md`,
   `docs/fts-notes/jozve_FTS_handwritten_pages_*.md`,
   `docs/fts-notes/FTS_CHART3_extracted_text.txt`. Search aids only; in an
   ambiguity, open the PDF page.

Conflict rules:
- Booklet vs derived spec → booklet.
- Booklet vs explicit owner ruling on the same point → owner ruling.
- Transcript vs booklet → booklet.
- Two derived specs disagree → report `AMBIGUOUS`; do not invent a rule.
- Implementation addition (e.g. 1b volume/real-growth layer) → label it as an
  addition, never as a booklet rule.

Current checkout is the only authority for UI behavior. Dated audits and
screenshots from other dates are evidence of that date, not current truth.
