#!/usr/bin/env node
import path from 'node:path';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { pathExists, readJson, writeText, toPosixPath } from '../../../shared/lib/files.mjs';
import { sortFindings, verdictFromFindings, countBySeverity } from '../../../shared/lib/findings.mjs';

const REPORT_FILES = [
  ['design-md-audit.json', 'DESIGN.md review'],
  ['figma-export.json', 'Figma export'],
  ['screenshots.json', 'Screenshot capture'],
  ['visual-comparison.json', 'Visual comparison'],
  ['ui-alignment.json', 'UI alignment'],
  ['a11y.json', 'Accessibility'],
  ['component-alignment.json', 'Component alignment'],
  ['design-debt.json', 'Design debt'],
];

function rel(config, filePath) {
  if (!filePath) return '';
  return toPosixPath(path.relative(config.__meta.configDir, filePath));
}

function truncateLines(value, maxLines = 4) {
  return String(value).split('\n').slice(0, maxLines).join(' ');
}

function formatFinding(finding, index, config) {
  const parts = [];
  parts.push(`### ${index}. [${finding.severity || 'info'}] ${finding.title || finding.type || 'Finding'}`);
  if (finding.file) parts.push(`- File: ${finding.file}${finding.line ? `:${finding.line}` : ''}`);
  if (finding.selector) parts.push(`- Selector: \`${finding.selector}\``);
  if (finding.sourceReport) parts.push(`- Source report: ${finding.sourceReport}`);
  if (finding.evidence) parts.push(`- Evidence: ${truncateLines(finding.evidence, 6)}`);
  if (finding.observed) parts.push(`- Observed: ${truncateLines(finding.observed, 4)}`);
  if (finding.expected) parts.push(`- Expected: ${truncateLines(finding.expected, 4)}`);
  if (finding.impact) parts.push(`- Impact: ${truncateLines(finding.impact, 4)}`);
  if (finding.recommendation) parts.push(`- Fix: ${truncateLines(finding.recommendation, 4)}`);
  if (finding.verification) parts.push(`- Verification: ${truncateLines(finding.verification, 4)}`);
  if (finding.meta?.diffPath) parts.push(`- Diff: ${rel(config, finding.meta.diffPath)}`);
  return parts.join('\n');
}

function section(title, findings, config) {
  if (findings.length === 0) return `## ${title}\n\nNone.\n`;
  return `## ${title}\n\n${findings.map((f, i) => formatFinding(f, i + 1, config)).join('\n\n')}\n`;
}

const config = await loadConfig();
const reportsDir = path.join(config.project.outputDir, 'reports');
const loaded = [];
let findings = [];

for (const [fileName, label] of REPORT_FILES) {
  const filePath = path.join(reportsDir, fileName);
  if (!(await pathExists(filePath))) {
    loaded.push({ label, fileName, status: 'missing' });
    continue;
  }
  const report = await readJson(filePath, {});
  loaded.push({ label, fileName, status: report.ok ? 'ok' : 'has-findings' });
  findings.push(...(report.findings || []).map(f => ({ ...f, sourceReport: fileName })));
}

findings = sortFindings(findings);
const verdict = verdictFromFindings(findings);
const counts = countBySeverity(findings);
const blockers = findings.filter(f => f.severity === 'blocker');
const major = findings.filter(f => f.severity === 'major');
const minor = findings.filter(f => f.severity === 'minor');
const debt = findings.filter(f => f.severity === 'debt');
const info = findings.filter(f => !['blocker', 'major', 'minor', 'debt'].includes(f.severity));

const visualReport = await readJson(path.join(reportsDir, 'visual-comparison.json'), { comparisons: [] });
const comparisons = visualReport.comparisons || [];
const visualSummary = comparisons.length
  ? comparisons.map(c => `- ${c.screen}: ${c.passed ? 'pass' : 'fail'} — ${(c.diffPixelRatio * 100).toFixed(2)}% diff (${c.diffPixels}/${c.totalPixels} pixels), diff: ${rel(config, c.diffPath)}`).join('\n')
  : '- No visual comparisons were completed.';

const uiAlignmentReport = await readJson(path.join(reportsDir, 'ui-alignment.json'), { visualComparisons: [], domInspections: [], findings: [], counts: {} });
const uiAlignmentCompleted = Array.isArray(uiAlignmentReport.findings) || Array.isArray(uiAlignmentReport.domInspections);
const uiAlignmentSummary = uiAlignmentCompleted
  ? [
      `- Visual comparisons: ${(uiAlignmentReport.visualComparisons || []).length}`,
      `- DOM alignment targets inspected: ${(uiAlignmentReport.domInspections || []).length}`,
      `- UI alignment findings: ${(uiAlignmentReport.findings || []).length}`,
      `- Blocker/major alignment findings: ${(uiAlignmentReport.counts?.blocker || 0) + (uiAlignmentReport.counts?.major || 0)}`,
    ].join('\n')
  : '- No UI alignment audit was completed.';

const selectorSummary = (uiAlignmentReport.domInspections || []).length
  ? uiAlignmentReport.domInspections.map(item => {
      const total = (item.checks || []).length;
      const failed = (item.checks || []).filter(check => !check.passed).length;
      return `- ${item.screen} / ${item.name}: ${total - failed}/${total} checks passed (${item.selector})`;
    }).join('\n')
  : '- No anchor-level UI alignment checks were completed.';

const reportPaths = loaded.map(item => `- ${item.label}: ${item.status} (${toPosixPath(path.join(rel(config, reportsDir), item.fileName))})`).join('\n');

const markdown = `# Design QA Report\n\nGenerated: ${new Date().toISOString()}\n\nProject: ${config.project.name}\nConfig: ${rel(config, config.__meta.configPath)}\n\n## Verdict\n\n**${verdict}**\n\n## Summary\n\n- Blockers: ${counts.blocker || 0}\n- Major issues: ${counts.major || 0}\n- Minor issues: ${counts.minor || 0}\n- Design debt findings: ${counts.debt || 0}\n- Informational findings: ${info.length}\n\n## UI Alignment Summary\n\n${uiAlignmentSummary}\n\n## Anchor Alignment Summary\n\n${selectorSummary}\n\n## Visual Comparison Summary\n\n${visualSummary}\n\n${section('Blockers', blockers, config)}\n${section('Major Issues', major, config)}\n${section('Minor Issues', minor, config)}\n${section('Design Debt', debt, config)}\n${section('Info / Manual Review Notes', info, config)}\n## Automation Artifacts\n\n${reportPaths}\n\n## Verification Checklist\n\n- [ ] Re-run screenshot capture after fixes.\n- [ ] Re-run visual comparison and inspect diff images.\n- [ ] Re-run UI alignment audit.\n- [ ] Re-run accessibility scan.\n- [ ] Confirm mobile, tablet, and desktop viewports.\n- [ ] Confirm interactive states: hover, focus-visible, active, disabled, loading, empty, error.\n- [ ] Confirm fixes use DESIGN.md tokens and design-system components.\n- [ ] Confirm no new hard-coded visual values were introduced.\n`;

const reportPath = path.join(config.project.outputDir, 'DESIGN_QA_REPORT.md');
await writeText(reportPath, markdown);
console.log(JSON.stringify({ reportPath, verdict, counts, findings: findings.length }, null, 2));
