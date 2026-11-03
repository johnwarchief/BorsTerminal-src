#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { pathExists, writeJson, ensureDir } from '../../../shared/lib/files.mjs';
import {
  expectedPathForScreen,
  actualPathForScreen,
  diffPathForScreen,
  normalizedExpectedPathForScreen,
  normalizedActualPathForScreen,
} from '../../../shared/lib/screens.mjs';
import { makeFinding } from '../../../shared/lib/findings.mjs';

async function readPng(filePath) {
  const data = await fs.readFile(filePath);
  return PNG.sync.read(data);
}

function createCanvas(width, height, fill = [255, 255, 255, 255]) {
  const png = new PNG({ width, height });
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const idx = (width * y + x) << 2;
      png.data[idx] = fill[0];
      png.data[idx + 1] = fill[1];
      png.data[idx + 2] = fill[2];
      png.data[idx + 3] = fill[3];
    }
  }
  return png;
}

function paste(src, dest, offsetX = 0, offsetY = 0) {
  for (let y = 0; y < src.height; y += 1) {
    for (let x = 0; x < src.width; x += 1) {
      const srcIdx = (src.width * y + x) << 2;
      const destIdx = (dest.width * (y + offsetY) + (x + offsetX)) << 2;
      dest.data[destIdx] = src.data[srcIdx];
      dest.data[destIdx + 1] = src.data[srcIdx + 1];
      dest.data[destIdx + 2] = src.data[srcIdx + 2];
      dest.data[destIdx + 3] = src.data[srcIdx + 3];
    }
  }
}

async function writePng(filePath, png) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, PNG.sync.write(png));
}

const config = await loadConfig();
const findings = [];
const comparisons = [];

for (const screen of config.screens) {
  const expectedPath = expectedPathForScreen(config, screen);
  const actualPath = actualPathForScreen(config, screen);
  const diffPath = diffPathForScreen(config, screen);
  const compare = screen.compare || {};
  const mode = screen.mode || 'regression';

  const expectedExists = await pathExists(expectedPath);
  const actualExists = await pathExists(actualPath);

  if (!expectedExists || !actualExists) {
    findings.push(makeFinding({
      severity: expectedExists ? 'blocker' : (mode === 'regression' ? 'info' : 'major'),
      type: 'visual-comparison',
      title: `Missing ${!expectedExists ? 'expected' : 'actual'} screenshot for ${screen.name}`,
      evidence: JSON.stringify({ expectedPath, actualPath }, null, 2),
      expected: 'Both expected and actual screenshots must exist before comparison',
      recommendation: !expectedExists
        ? 'Provide a baseline/reference image or run Figma export.'
        : 'Run screenshot capture against the app route.',
      meta: { screen: screen.name, mode },
    }));
    continue;
  }

  try {
    const expected = await readPng(expectedPath);
    const actual = await readPng(actualPath);
    const width = Math.max(expected.width, actual.width);
    const height = Math.max(expected.height, actual.height);
    const normalizedExpected = createCanvas(width, height);
    const normalizedActual = createCanvas(width, height);
    paste(expected, normalizedExpected);
    paste(actual, normalizedActual);

    const dimensionsDiffer = expected.width !== actual.width || expected.height !== actual.height;
    if (dimensionsDiffer) {
      findings.push(makeFinding({
        severity: mode === 'conformance' ? 'major' : 'minor',
        type: 'visual-dimensions',
        title: `Screenshot dimensions differ for ${screen.name}`,
        evidence: JSON.stringify({ expected: { width: expected.width, height: expected.height }, actual: { width: actual.width, height: actual.height } }, null, 2),
        observed: `Actual image is ${actual.width}x${actual.height}; expected image is ${expected.width}x${expected.height}`,
        expected: 'Expected and actual should use the same viewport, device scale, and capture mode',
        recommendation: 'Align viewport, deviceScaleFactor, fullPage, and Figma export scale.',
        meta: { screen: screen.name, mode },
      }));
    }

    const diff = new PNG({ width, height });
    const diffPixels = pixelmatch(
      normalizedExpected.data,
      normalizedActual.data,
      diff.data,
      width,
      height,
      {
        threshold: compare.threshold ?? 0.2,
        includeAA: compare.includeAA ?? false,
      },
    );
    const totalPixels = width * height;
    const diffPixelRatio = totalPixels === 0 ? 0 : diffPixels / totalPixels;
    const maxDiffPixelRatio = compare.maxDiffPixelRatio ?? 0.02;
    const maxDiffPixels = compare.maxDiffPixels ?? Infinity;
    const passed = diffPixelRatio <= maxDiffPixelRatio && diffPixels <= maxDiffPixels;

    await writePng(diffPath, diff);
    await writePng(normalizedExpectedPathForScreen(config, screen), normalizedExpected);
    await writePng(normalizedActualPathForScreen(config, screen), normalizedActual);

    const comparison = {
      screen: screen.name,
      mode,
      passed,
      expectedPath,
      actualPath,
      diffPath,
      width,
      height,
      diffPixels,
      totalPixels,
      diffPixelRatio,
      maxDiffPixelRatio,
      maxDiffPixels,
      threshold: compare.threshold ?? 0.2,
      dimensionsDiffer,
    };
    comparisons.push(comparison);

    if (!passed) {
      const severity = diffPixelRatio > 0.05 ? 'blocker' : 'major';
      findings.push(makeFinding({
        severity,
        type: 'visual-comparison',
        title: `Visual difference exceeds threshold for ${screen.name}`,
        evidence: diffPath,
        observed: `${diffPixels} pixels differ (${(diffPixelRatio * 100).toFixed(2)}%)`,
        expected: `Diff <= ${(maxDiffPixelRatio * 100).toFixed(2)}% and <= ${Number.isFinite(maxDiffPixels) ? maxDiffPixels : 'unlimited'} pixels`,
        impact: mode === 'conformance'
          ? 'Implementation may not match the approved design reference.'
          : 'The UI changed compared with the approved baseline.',
        recommendation: 'Inspect the diff image, confirm masks for dynamic content, then fix layout/token/component deviations or approve a new baseline if intentional.',
        verification: 'Re-run visual comparison after fixing or updating the approved baseline.',
        meta: comparison,
      }));
    }
  } catch (error) {
    findings.push(makeFinding({
      severity: 'blocker',
      type: 'visual-comparison',
      title: `Image comparison failed for ${screen.name}`,
      evidence: error.message,
      expected: 'Expected and actual screenshots should be valid PNG files',
      recommendation: 'Regenerate screenshots as PNG files and retry.',
      meta: { screen: screen.name, mode },
    }));
  }
}

const report = {
  ok: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  comparisons,
  findings,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'visual-comparison.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, comparisons: comparisons.length, findings: findings.length }, null, 2));
