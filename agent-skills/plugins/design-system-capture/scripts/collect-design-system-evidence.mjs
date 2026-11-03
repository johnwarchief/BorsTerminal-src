#!/usr/bin/env node
import path from 'node:path';
import fg from 'fast-glob';
import { loadConfig, resolveConfigPath } from '../../../shared/lib/config.mjs';
import { pathExists, readJson, readText, writeJson, toPosixPath } from '../../../shared/lib/files.mjs';
import { makeFinding, sortFindings } from '../../../shared/lib/findings.mjs';

const SOURCE_PATTERNS = [
  'DESIGN.md',
  'SCREEN_SPEC.md',
  'design.qa.y{a,}ml',
  'tailwind.config.{js,cjs,mjs,ts}',
  'tokens/**/*.{json,js,ts,css,scss}',
  'theme/**/*.{json,js,ts,css,scss}',
  'src/**/*.{css,scss}',
  'app/**/*.{css,scss}',
  'styles/**/*.{css,scss}',
  'components/**/*.{ts,tsx,js,jsx,css,scss}',
];

const REPORT_FILES = [
  'design-md-audit.json',
  'design-debt.json',
  'component-alignment.json',
  'visual-comparison.json',
  'a11y.json',
];

function classifySource(relativePath, content) {
  const lower = relativePath.toLowerCase();
  if (lower === 'design.md') return 'design-contract';
  if (lower === 'screen_spec.md') return 'screen-spec';
  if (lower.includes('tailwind.config')) return 'tailwind-theme';
  if (lower.includes('token')) return 'token-file';
  if (lower.includes('theme')) return 'theme-file';
  if (/\.(css|scss)$/.test(lower)) return 'css-theme-source';
  if (/components?\//.test(lower)) return 'component-source';
  if (/--[a-z0-9-]+\s*:/.test(content)) return 'css-variables';
  return 'supporting-source';
}

function extractSamples(content) {
  const cssVariables = Array.from(content.matchAll(/--([a-zA-Z0-9-_]+)\s*:\s*([^;\n]+)/g))
    .slice(0, 80)
    .map(match => ({ name: `--${match[1]}`, value: match[2].trim() }));
  const hexColors = Array.from(new Set(Array.from(content.matchAll(/#[0-9a-fA-F]{3,8}\b/g)).map(match => match[0].toLowerCase()))).slice(0, 80);
  const tailwindArbitrary = Array.from(new Set(Array.from(content.matchAll(/[a-z-]+-\[[^\]]+\]/g)).map(match => match[0]))).slice(0, 80);
  return { cssVariables, hexColors, tailwindArbitrary };
}

const config = await loadConfig();
const files = await fg(SOURCE_PATTERNS, {
  cwd: config.__meta.configDir,
  absolute: true,
  onlyFiles: true,
  ignore: config.code.exclude,
  dot: true,
});

const sources = [];
const aggregate = {
  cssVariables: [],
  hexColors: new Set(),
  tailwindArbitrary: new Set(),
};

for (const filePath of files) {
  const content = await readText(filePath, '');
  const relative = toPosixPath(path.relative(config.__meta.configDir, filePath));
  const samples = extractSamples(content);
  for (const color of samples.hexColors) aggregate.hexColors.add(color);
  for (const item of samples.tailwindArbitrary) aggregate.tailwindArbitrary.add(item);
  aggregate.cssVariables.push(...samples.cssVariables.map(item => ({ ...item, file: relative })));
  sources.push({
    file: relative,
    kind: classifySource(relative, content),
    size: content.length,
    samples,
  });
}

const loadedReports = [];
for (const fileName of REPORT_FILES) {
  const filePath = path.join(config.project.outputDir, 'reports', fileName);
  if (await pathExists(filePath)) {
    loadedReports.push({ file: fileName, report: await readJson(filePath, {}) });
  }
}

const designMdPath = resolveConfigPath(config, config.design.designMd);
const findings = [];
if (!(await pathExists(designMdPath))) {
  findings.push(makeFinding({
    severity: 'major',
    type: 'capture-missing-contract',
    title: 'No DESIGN.md found for design-system capture',
    evidence: config.design.designMd,
    expected: 'A DESIGN.md contract should exist before Design QA becomes high confidence.',
    recommendation: 'Use the captured sources to draft DESIGN.md, then review it with design-md-review.',
  }));
}
if (sources.length === 0) {
  findings.push(makeFinding({
    severity: 'major',
    type: 'capture-no-sources',
    title: 'No design-system source files discovered',
    evidence: SOURCE_PATTERNS.join(', '),
    recommendation: 'Add Tailwind config, CSS variables, token files, component sources, screenshots, or Figma exports before attempting capture.',
  }));
}

const summaryByKind = sources.reduce((acc, source) => {
  acc[source.kind] = (acc[source.kind] || 0) + 1;
  return acc;
}, {});

const report = {
  ok: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  sourcePatterns: SOURCE_PATTERNS,
  sourceCount: sources.length,
  summaryByKind,
  sources,
  tokenSamples: {
    cssVariables: aggregate.cssVariables.slice(0, 200),
    hexColors: Array.from(aggregate.hexColors).slice(0, 200),
    tailwindArbitrary: Array.from(aggregate.tailwindArbitrary).slice(0, 200),
  },
  loadedReportSummaries: loadedReports.map(({ file, report }) => ({
    file,
    ok: report.ok,
    findingCount: report.findings?.length || 0,
    generatedAt: report.generatedAt,
  })),
  findings: sortFindings(findings),
};

const reportPath = path.join(config.project.outputDir, 'reports', 'design-system-capture.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, sourceCount: sources.length, findings: findings.length, summaryByKind }, null, 2));
