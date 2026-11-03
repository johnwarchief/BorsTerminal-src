#!/usr/bin/env node
import path from 'node:path';
import fg from 'fast-glob';
import YAML from 'yaml';
import { loadConfig, resolveConfigPath } from '../../../shared/lib/config.mjs';
import { readText, writeJson, toPosixPath } from '../../../shared/lib/files.mjs';
import { makeFinding, sortFindings } from '../../../shared/lib/findings.mjs';

function extractFrontmatter(markdown) {
  const match = markdown.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/);
  if (!match) return null;
  try {
    return YAML.parse(match[1]);
  } catch {
    return null;
  }
}

function flattenValues(value, out = []) {
  if (value == null) return out;
  if (typeof value === 'string' || typeof value === 'number') {
    out.push(String(value).toLowerCase());
  } else if (Array.isArray(value)) {
    for (const item of value) flattenValues(item, out);
  } else if (typeof value === 'object') {
    for (const item of Object.values(value)) flattenValues(item, out);
  }
  return out;
}

function lineFindings({ content, file, config, tokenValues }) {
  const findings = [];
  const allowedColors = new Set((config.debt.allowedColorValues || []).map(v => String(v).toLowerCase()));
  const lines = content.split(/\r?\n/);
  const regexes = [
    {
      type: 'hard-coded-color',
      regex: /(^|[^\w])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w])/g,
      title: value => `Hard-coded color ${value}`,
      severity: value => tokenValues.has(value.toLowerCase()) ? 'debt' : 'major',
      recommendation: 'Replace direct color values with semantic tokens or CSS variables. If the value is intentional and reusable, add it to DESIGN.md and the theme first.',
    },
    {
      type: 'functional-color',
      regex: /\b(?:rgb|rgba|hsl|hsla)\([^)]*\)/g,
      title: value => `Hard-coded functional color ${value}`,
      severity: () => 'major',
      recommendation: 'Replace rgba/hsl values with semantic tokens or documented CSS variables.',
    },
    {
      type: 'tailwind-arbitrary-value',
      regex: /(?:[A-Za-z0-9_:/-]+-\[[^\]]+\])/g,
      title: value => `Arbitrary Tailwind value ${value}`,
      severity: () => 'debt',
      recommendation: 'Prefer theme tokens, component variants, or documented utility classes before arbitrary Tailwind values.',
    },
    {
      type: 'inline-style',
      regex: /\bstyle\s*=\s*(?:\{\{|"|')/g,
      title: () => 'Inline style in UI code',
      severity: () => 'major',
      recommendation: 'Move visual styling into design-system components, tokens, or approved CSS classes. Inline styles should be rare and justified.',
    },
    {
      type: 'px-magic-number',
      regex: /\b(?:[2-9]|[1-9]\d{1,3})px\b/g,
      title: value => `Hard-coded px value ${value}`,
      severity: value => tokenValues.has(value.toLowerCase()) ? 'debt' : 'minor',
      recommendation: 'Use spacing, typography, radius, or component tokens instead of local px values.',
    },
    {
      type: 'custom-shadow',
      regex: /\bbox-shadow\s*:|shadow-\[[^\]]+\]/g,
      title: () => 'Custom shadow value',
      severity: () => 'debt',
      recommendation: 'Use documented elevation/shadow tokens instead of one-off shadows.',
    },
  ];

  lines.forEach((line, idx) => {
    const tokenDeclaration = /^\s*--[A-Za-z0-9-_]+\s*:/u.test(line);
    for (const rule of regexes) {
      const matches = line.matchAll(rule.regex);
      for (const match of matches) {
        let value = match[0].trim();
        if (tokenDeclaration) continue;
        if (rule.type === 'hard-coded-color') {
          value = value.replace(/^[^#]*/, '');
          if (allowedColors.has(value.toLowerCase())) continue;
        }
        if (!value) continue;
        findings.push(makeFinding({
          severity: rule.severity(value),
          type: rule.type,
          title: rule.title(value),
          file,
          line: idx + 1,
          evidence: line.trim(),
          observed: value,
          expected: 'Feature code should express visual decisions through DESIGN.md tokens, theme variables, or design-system component variants.',
          recommendation: rule.recommendation,
          verification: 'Re-run design debt scan and visual/component checks.',
        }));
      }
    }
  });

  return findings;
}

const config = await loadConfig();
const designMdPath = resolveConfigPath(config, config.design.designMd);
const designMd = await readText(designMdPath, '');
const frontmatter = extractFrontmatter(designMd) || {};
const tokenValues = new Set(flattenValues(frontmatter.tokens || frontmatter).map(v => v.toLowerCase()));

const files = await fg(config.code.include, {
  cwd: config.__meta.configDir,
  absolute: true,
  onlyFiles: true,
  ignore: config.code.exclude,
  dot: false,
});

let findings = [];
const scannedFiles = [];
for (const filePath of files) {
  const content = await readText(filePath, '');
  const relative = toPosixPath(path.relative(config.__meta.configDir, filePath));
  scannedFiles.push(relative);
  findings.push(...lineFindings({ content, file: relative, config, tokenValues }));
}

findings = sortFindings(findings).slice(0, 1000);

const summary = findings.reduce((acc, finding) => {
  acc[finding.type] = (acc[finding.type] || 0) + 1;
  return acc;
}, {});

const report = {
  ok: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  scannedFileCount: scannedFiles.length,
  scannedFiles,
  tokenValueCount: tokenValues.size,
  summary,
  findings,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'design-debt.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, scannedFileCount: scannedFiles.length, findings: findings.length, summary }, null, 2));
