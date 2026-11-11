/**
 * Phase 4.9.1 C5 — the chart feature must not invent a "Live"/"Verified"
 * badge. `history_validity.status` is the only authority for a validity
 * claim, and the seed manifest marks most symbols `unverified`; a literal
 * label in the chart source would lie regardless of the API answer.
 *
 * Source-level on purpose: jsdom cannot prove which string reached the
 * screen when the label is a constant. Every rule below reads the actual
 * feature source, same style as fundamental-unslop.spec.tsx.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const FEATURE = resolve(process.cwd(), 'src/features/chart').replace(/\\/g, '/');
const USE_CHART = `${FEATURE}/api/useChart.ts`;

function sourceFiles(dir: string, into: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) sourceFiles(full, into);
    else if (/\.tsx?$/.test(entry.name) && !entry.name.includes('.test.')) into.push(full);
  }
  return into;
}

const FILES = sourceFiles(FEATURE).map((path) => ({
  path,
  text: readFileSync(path, 'utf8'),
}));

describe('chart labels come from the API, never from a literal', () => {
  it('has chart sources to scan', () => {
    expect(FILES.length).toBeGreaterThan(0);
  });

  it('renders no hard-coded Live/Verified label', () => {
    const literalLabel =
      /(?:>\s*(?:Live|Verified)\s*<)|(?:['"`](?:Live|Verified)['"`])/g;
    const hits = FILES.flatMap(({ path, text }) =>
      [...text.matchAll(literalLabel)].map((m) => `${path}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });

  it('never sets live/verified flags to true in the chart feature', () => {
    const hardClaim = /\b(?:live|verified|is_live|is_verified)\s*:\s*true\b/g;
    const hits = FILES.flatMap(({ path, text }) =>
      [...text.matchAll(hardClaim)].map((m) => `${path}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });

  it('keeps the API status in the payload schema so a label can be derived', () => {
    const src = readFileSync(USE_CHART, 'utf8');
    expect(src).toContain('status: z.string()');
  });
});
