#!/usr/bin/env node
import path from 'node:path';
import fg from 'fast-glob';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { readText, writeJson, toPosixPath } from '../../../shared/lib/files.mjs';
import { makeFinding, sortFindings } from '../../../shared/lib/findings.mjs';

function globToRegex(glob) {
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '.*')
    .replace(/\*/g, '[^/]*');
  return new RegExp(`^${escaped}$`);
}

function isAllowedFile(relativePath, patterns = []) {
  return patterns.some(pattern => globToRegex(pattern).test(relativePath));
}

function hasLibraryImport(content, patterns) {
  return patterns.some(pattern => content.includes(pattern));
}

function findLine(content, index) {
  return content.slice(0, index).split(/\r?\n/).length;
}

const config = await loadConfig();
const patterns = config.components.libraryImportPatterns || [];
const rawPolicy = config.components.rawElementPolicy || {};
const allowedFiles = config.components.allowedRawElementFiles || [];

const files = await fg(config.code.include, {
  cwd: config.__meta.configDir,
  absolute: true,
  onlyFiles: true,
  ignore: config.code.exclude,
  dot: false,
});

const findings = [];
const scannedFiles = [];
const rawElements = Object.keys(rawPolicy).filter(element => rawPolicy[element] === 'prefer-design-system');
const fileRecords = [];

for (const filePath of files) {
  const content = await readText(filePath, '');
  const relative = toPosixPath(path.relative(config.__meta.configDir, filePath));
  scannedFiles.push(relative);
  fileRecords.push({ filePath, content, relative });
}

const libraryImportFiles = patterns.length > 0
  ? fileRecords.filter(record => hasLibraryImport(record.content, patterns)).map(record => record.relative)
  : [];
const scanRawElements = patterns.length === 0 || libraryImportFiles.length > 0;

if (patterns.length > 0 && libraryImportFiles.length === 0) {
  findings.push(makeFinding({
    severity: 'needs-design-decision',
    type: 'component-library-not-detected',
    title: 'Configured component-library imports were not found',
    evidence: patterns.join(', '),
    observed: 'No scanned file imports a configured design-system component library.',
    expected: 'Component alignment requires project-specific libraryImportPatterns or an explicit decision that this project has no shared component library.',
    impact: 'Raw element findings would be noisy until the project component-library baseline is configured.',
    recommendation: 'Update design.qa.yaml components.libraryImportPatterns and allowedRawElementFiles for this project, or capture a design-system decision that raw semantic elements are the approved baseline.',
    verification: 'Re-run component alignment after configuring the project component-library baseline.',
  }));
}

for (const { content, relative } of fileRecords) {
  const allowed = isAllowedFile(relative, allowedFiles);
  const importsLibrary = hasLibraryImport(content, patterns);

  if (scanRawElements) {
    for (const element of rawElements) {
      const regex = new RegExp(`<${element}(\\s|>|/)`, 'g');
      const matches = content.matchAll(regex);
      for (const match of matches) {
        if (allowed) continue;
        const line = findLine(content, match.index || 0);
        findings.push(makeFinding({
          severity: importsLibrary ? 'minor' : 'major',
          type: 'component-library-bypass',
          title: `Raw <${element}> used in feature code`,
          file: relative,
          line,
          evidence: content.split(/\r?\n/)[line - 1]?.trim(),
          observed: `Raw <${element}> element`,
          expected: 'Use the project design-system component or an allowed primitive file.',
          impact: 'Raw elements can bypass shared variants, accessibility states, focus styles, and visual tokens.',
          recommendation: `Replace with a design-system ${element} component if one exists, or move the primitive into an allowed component-library file.`,
          verification: 'Re-run component alignment scan and check visual/a11y states.',
        }));
      }
    }
  }

  const duplicateComponentRegex = /(?:function|const|class)\s+([A-Z][A-Za-z0-9]*(?:Button|Modal|Dialog|Card|Input|Select|Badge|Toast|Table|Tabs|Tooltip|Dropdown))[\s=({]/g;
  for (const match of content.matchAll(duplicateComponentRegex)) {
    if (allowed) continue;
    const name = match[1];
    const line = findLine(content, match.index || 0);
    findings.push(makeFinding({
      severity: 'debt',
      type: 'possible-duplicate-component',
      title: `Possible local component variant: ${name}`,
      file: relative,
      line,
      evidence: content.split(/\r?\n/)[line - 1]?.trim(),
      observed: `Local component-like declaration ${name}`,
      expected: 'Common UI patterns should be centralized in the design-system component library.',
      impact: 'Local variants can drift from approved component behavior and visual states.',
      recommendation: 'Confirm whether this should be a documented design-system variant or a feature-specific wrapper around the shared component.',
      verification: 'Check component library docs/stories and update if centralization is needed.',
    }));
  }
}

const sorted = sortFindings(findings).slice(0, 1000);
const summary = sorted.reduce((acc, finding) => {
  acc[finding.type] = (acc[finding.type] || 0) + 1;
  return acc;
}, {});

const report = {
  ok: sorted.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  scannedFileCount: scannedFiles.length,
  scannedFiles,
  componentLibraryImportPatterns: patterns,
  allowedRawElementFiles: allowedFiles,
  summary,
  findings: sorted,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'component-alignment.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, scannedFileCount: scannedFiles.length, findings: sorted.length, summary }, null, 2));
