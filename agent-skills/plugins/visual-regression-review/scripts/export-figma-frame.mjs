#!/usr/bin/env node
import path from 'node:path';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { ensureDir, writeJson } from '../../../shared/lib/files.mjs';
import { expectedPathForScreen } from '../../../shared/lib/screens.mjs';
import { makeFinding } from '../../../shared/lib/findings.mjs';

function parseFigmaUrl(url) {
  if (!url) return {};
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split('/').filter(Boolean);
    const fileKey = parts[1];
    const nodeIdParam = parsed.searchParams.get('node-id') || parsed.searchParams.get('node_id');
    const nodeId = nodeIdParam ? nodeIdParam.replace('-', ':') : undefined;
    return { fileKey, nodeId };
  } catch {
    return {};
  }
}

async function downloadBinary(url, destPath) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download ${url}: ${response.status} ${response.statusText}`);
  }
  const arrayBuffer = await response.arrayBuffer();
  await ensureDir(path.dirname(destPath));
  await import('node:fs/promises').then(fs => fs.writeFile(destPath, Buffer.from(arrayBuffer)));
}

const config = await loadConfig();
const findings = [];
const exports = [];
const token = process.env.FIGMA_TOKEN;

for (const screen of config.screens) {
  const expected = screen.expected || {};
  if (expected.type !== 'figma' && !expected.figma) continue;

  const figma = { ...(expected.figma || {}) };
  const parsed = parseFigmaUrl(figma.url || expected.url);
  figma.fileKey = figma.fileKey || parsed.fileKey;
  figma.nodeId = figma.nodeId || parsed.nodeId;
  figma.format = figma.format || 'png';
  figma.scale = figma.scale || 1;

  if (!token) {
    findings.push(makeFinding({
      severity: 'major',
      type: 'figma-export',
      title: `Figma token missing for ${screen.name}`,
      evidence: 'FIGMA_TOKEN environment variable is not set',
      expected: 'Set FIGMA_TOKEN or provide expected.path with a local reference image',
      recommendation: 'Export the Figma frame manually or set FIGMA_TOKEN before running the export script.',
    }));
    continue;
  }

  if (!figma.fileKey || !figma.nodeId) {
    findings.push(makeFinding({
      severity: 'major',
      type: 'figma-export',
      title: `Figma fileKey/nodeId missing for ${screen.name}`,
      evidence: JSON.stringify(expected, null, 2),
      expected: 'expected.figma.fileKey and expected.figma.nodeId, or expected.figma.url with node-id',
      recommendation: 'Update design.qa.yaml with the Figma file key and node ID.',
    }));
    continue;
  }

  try {
    const params = new URLSearchParams({
      ids: figma.nodeId,
      format: figma.format,
      scale: String(figma.scale),
    });
    const endpoint = `https://api.figma.com/v1/images/${encodeURIComponent(figma.fileKey)}?${params.toString()}`;
    const response = await fetch(endpoint, {
      headers: { 'X-Figma-Token': token },
    });
    if (!response.ok) {
      throw new Error(`Figma API returned ${response.status} ${response.statusText}`);
    }
    const body = await response.json();
    const imageUrl = body.images?.[figma.nodeId];
    if (!imageUrl) {
      throw new Error(`Figma image URL not found for node ${figma.nodeId}: ${JSON.stringify(body)}`);
    }
    const outPath = expectedPathForScreen(config, screen);
    await downloadBinary(imageUrl, outPath);
    exports.push({
      screen: screen.name,
      fileKey: figma.fileKey,
      nodeId: figma.nodeId,
      format: figma.format,
      scale: figma.scale,
      path: outPath,
    });
  } catch (error) {
    findings.push(makeFinding({
      severity: 'major',
      type: 'figma-export',
      title: `Failed to export Figma frame for ${screen.name}`,
      evidence: error.message,
      expected: 'Figma frame should export to expected screenshot path',
      recommendation: 'Check FIGMA_TOKEN, file permissions, fileKey, nodeId, and image size.',
    }));
  }
}

const report = {
  ok: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  exports,
  findings,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'figma-export.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, exported: exports.length, findings: findings.length }, null, 2));
