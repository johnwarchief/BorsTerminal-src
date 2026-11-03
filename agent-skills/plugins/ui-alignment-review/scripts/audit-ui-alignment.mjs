#!/usr/bin/env node
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { chromium } from '@playwright/test';
import { loadConfig, screenUrl } from '../../../shared/lib/config.mjs';
import { parseArgs } from '../../../shared/lib/args.mjs';
import { pathExists, readJson, writeJson, writeText, toPosixPath } from '../../../shared/lib/files.mjs';
import { makeFinding, sortFindings, verdictFromFindings, countBySeverity } from '../../../shared/lib/findings.mjs';

const STYLE_KEYS = [
  'display', 'position', 'fontFamily', 'fontSize', 'fontWeight', 'lineHeight',
  'letterSpacing', 'color', 'backgroundColor', 'borderColor', 'borderRadius',
  'boxShadow', 'opacity', 'paddingTop', 'paddingRight', 'paddingBottom',
  'paddingLeft', 'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
  'gap', 'alignItems', 'justifyContent', 'textAlign', 'whiteSpace', 'overflow',
  'textOverflow',
];

function runNodeScript(scriptPath, configPath, label) {
  const result = spawnSync(process.execPath, [scriptPath, '--config', configPath], {
    cwd: process.cwd(),
    encoding: 'utf8',
    env: process.env,
  });
  return {
    label,
    scriptPath,
    status: result.status,
    signal: result.signal,
    stdout: result.stdout,
    stderr: result.stderr,
    error: result.error?.message,
    ok: result.status === 0,
  };
}

async function waitForUrl(url, timeoutMs) {
  if (!url) return { ok: true, skipped: true };
  const start = Date.now();
  let lastError = '';
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url, { method: 'GET' });
      if (response.status < 500) return { ok: true, status: response.status };
      lastError = `${response.status} ${response.statusText}`;
    } catch (error) {
      lastError = error.message;
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return { ok: false, error: lastError || 'timeout' };
}

function startApp(command, cwd) {
  if (!command) return null;
  return spawn(command, {
    cwd,
    shell: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: process.env,
  });
}

function freezeDateScript(isoDate) {
  return `(() => {
    const fixed = new Date(${JSON.stringify(isoDate)}).getTime();
    const OriginalDate = Date;
    class FixedDate extends OriginalDate {
      constructor(...args) {
        if (args.length === 0) return new OriginalDate(fixed);
        return new OriginalDate(...args);
      }
      static now() { return fixed; }
    }
    FixedDate.UTC = OriginalDate.UTC;
    FixedDate.parse = OriginalDate.parse;
    FixedDate.prototype = OriginalDate.prototype;
    window.Date = FixedDate;
  })();`;
}

function cssKeyForExpected(key) {
  const aliases = {
    x: 'x', y: 'y', left: 'x', top: 'y', width: 'width', height: 'height',
    minHeight: 'height', minWidth: 'width', maxHeight: 'height', maxWidth: 'width',
    text: 'textContent', textIncludes: 'textContent', textExact: 'textContent', textRegex: 'textContent',
  };
  return aliases[key] || key;
}

function parsePx(value) {
  if (typeof value === 'number') return value;
  const match = String(value).match(/^(-?\d+(?:\.\d+)?)px$/);
  return match ? Number(match[1]) : null;
}

function normalizeExpectation(raw) {
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && Object.prototype.hasOwnProperty.call(raw, 'value')) {
    return { value: raw.value, tolerance: raw.tolerance };
  }
  return { value: raw, tolerance: undefined };
}

function compareExpectedValue({ rawKey, key, expectedRaw, actual, defaultTolerancePx }) {
  const { value: expected, tolerance } = normalizeExpectation(expectedRaw);
  const actualValue = actual[key];
  const tol = Number(tolerance ?? defaultTolerancePx ?? 6);

  if (actualValue == null) {
    return { passed: false, observed: undefined, expected, detail: `No actual value for ${key}` };
  }

  if (rawKey === 'textIncludes') {
    const passed = String(actualValue).includes(String(expected));
    return { passed, observed: actualValue, expected: `contains ${expected}`, detail: passed ? 'contains match' : 'text does not contain expected value' };
  }
  if (rawKey === 'textRegex') {
    const passed = new RegExp(String(expected)).test(String(actualValue));
    return { passed, observed: actualValue, expected: `matches ${expected}`, detail: passed ? 'regex match' : 'text does not match regex' };
  }
  if (rawKey === 'text' || rawKey === 'textExact') {
    const passed = String(actualValue).replace(/\s+/g, ' ').trim() === String(expected).replace(/\s+/g, ' ').trim();
    return { passed, observed: actualValue, expected, detail: passed ? 'exact text match' : 'exact text mismatch' };
  }

  const expectedPx = parsePx(expected);
  const actualPx = typeof actualValue === 'number' ? actualValue : parsePx(actualValue);

  if (rawKey?.startsWith?.('min') && expectedPx != null && actualPx != null) {
    const passed = actualPx >= expectedPx;
    return { passed, observed: actualValue, expected: `>= ${expectedPx}px`, detail: passed ? 'minimum satisfied' : `${actualPx.toFixed(2)}px < ${expectedPx}px` };
  }
  if (rawKey?.startsWith?.('max') && expectedPx != null && actualPx != null) {
    const passed = actualPx <= expectedPx;
    return { passed, observed: actualValue, expected: `<= ${expectedPx}px`, detail: passed ? 'maximum satisfied' : `${actualPx.toFixed(2)}px > ${expectedPx}px` };
  }

  if (expectedPx != null && actualPx != null) {
    const delta = Math.abs(actualPx - expectedPx);
    return { passed: delta <= tol, observed: actualValue, expected: `${expectedPx}px ± ${tol}px`, detail: `delta ${delta.toFixed(2)}px` };
  }

  if (typeof expected === 'number' && typeof actualValue === 'number') {
    const delta = Math.abs(actualValue - expected);
    return { passed: delta <= tol, observed: actualValue, expected: `${expected} ± ${tol}`, detail: `delta ${delta.toFixed(2)}` };
  }

  const passed = String(actualValue).trim() === String(expected).trim();
  return { passed, observed: actualValue, expected, detail: passed ? 'exact match' : 'exact value mismatch' };
}

function normalizeTargets(targets) {
  return targets.map(target => {
    const expected = { ...(target.expected || {}) };
    for (const [key, value] of Object.entries(expected.css || {})) {
      if (expected[key] == null) expected[key] = value;
    }
    delete expected.css;
    return { ...target, expected };
  });
}

function matchesScreen(target, screenName) {
  const screens = target.screens || (target.screen ? [target.screen] : []);
  if (!Array.isArray(screens) || screens.length === 0) return true;
  return screens.includes(screenName);
}

function screenInspectSelectors(config, screen) {
  const candidates = [
    ...(Array.isArray(config.uiAlignment?.anchors) ? config.uiAlignment.anchors : []),
    ...(Array.isArray(config.uiAlignment?.elements) ? config.uiAlignment.elements : []),
    ...(Array.isArray(config.uiAlignment?.checks) ? config.uiAlignment.checks : []),
    ...(Array.isArray(config.uiAlignment?.inspectSelectors) ? config.uiAlignment.inspectSelectors : []),
    ...(Array.isArray(screen.uiAlignment?.anchors) ? screen.uiAlignment.anchors : []),
    ...(Array.isArray(screen.uiAlignment?.elements) ? screen.uiAlignment.elements : []),
    ...(Array.isArray(screen.alignment?.anchors) ? screen.alignment.anchors : []),
    ...(Array.isArray(screen.alignment?.elements) ? screen.alignment.elements : []),
    ...(Array.isArray(screen.alignment?.inspectSelectors) ? screen.alignment.inspectSelectors : []),
  ];
  return normalizeTargets(candidates.filter(target => matchesScreen(target, screen.name)));
}

async function collectDomMeasurements(config) {
  const findings = [];
  const inspections = [];
  const screensWithTargets = config.screens.filter(screen => screenInspectSelectors(config, screen).length > 0);
  if (screensWithTargets.length === 0) return { inspections, findings };

  const browser = await chromium.launch({ headless: true });
  try {
    for (const screen of screensWithTargets) {
      const app = screen.app || {};
      const viewport = app.viewport || { width: 1440, height: 900 };
      const context = await browser.newContext({ viewport, deviceScaleFactor: app.deviceScaleFactor || 1, reducedMotion: 'reduce' });
      if (app.freezeDate) await context.addInitScript(freezeDateScript(app.freezeDate));
      const page = await context.newPage();
      const url = screenUrl(config, screen);

      try {
        await page.goto(url, { waitUntil: app.waitUntil || 'networkidle', timeout: app.timeoutMs || 45000 });
        if (app.waitForSelector) await page.waitForSelector(app.waitForSelector, { timeout: app.waitForSelectorTimeoutMs || 15000 });

        for (const target of screenInspectSelectors(config, screen)) {
          const selector = target.selector;
          const name = target.name || selector;
          if (!selector) continue;

          const count = await page.locator(selector).count();
          if (count === 0) {
            findings.push(makeFinding({
              severity: 'major',
              type: 'ui-alignment-target-missing',
              title: `Alignment target missing: ${name}`,
              selector,
              observed: `No element matched ${selector}`,
              expected: 'Configured alignment targets should be present in the rendered UI.',
              impact: 'The reviewer cannot verify a key element against the design reference.',
              recommendation: 'Confirm the route/state is correct or add a stable data-testid selector to the target element.',
              verification: 'Re-run UI alignment after the selector resolves.',
              meta: { screen: screen.name, url },
            }));
            continue;
          }

          const locator = page.locator(selector).first();
          const box = await locator.boundingBox();
          const styles = await locator.evaluate((element, keys) => {
            const computed = window.getComputedStyle(element);
            const out = {};
            for (const key of keys) out[key] = computed[key];
            return out;
          }, STYLE_KEYS);
          const textContent = await locator.evaluate(element => element.textContent || '');
          const actual = { x: box?.x, y: box?.y, width: box?.width, height: box?.height, textContent, ...styles };
          const expected = target.expected || {};
          const checks = [];

          for (const [rawKey, expectedRaw] of Object.entries(expected)) {
            const actualKey = cssKeyForExpected(rawKey);
            const comparison = compareExpectedValue({
              rawKey,
              key: actualKey,
              expectedRaw,
              actual,
              defaultTolerancePx: config.uiAlignment?.measurementTolerancePx ?? config.uiAlignment?.defaultTolerancePx ?? 6,
            });
            checks.push({ key: rawKey, actualKey, ...comparison });
            if (!comparison.passed) {
              findings.push(makeFinding({
                severity: target.severity || 'minor',
                type: 'ui-alignment-measurement',
                title: `${name} ${rawKey} does not match expected value`,
                selector,
                observed: String(comparison.observed),
                expected: String(comparison.expected),
                evidence: `${screen.name} ${selector} ${rawKey}: observed ${comparison.observed}; expected ${comparison.expected}; ${comparison.detail}`,
                impact: 'Measured UI property differs from the configured alignment target.',
                recommendation: target.recommendation || 'Map the style to the correct token/component variant or update the expected value after design approval.',
                verification: 'Re-run UI alignment DOM measurement and visual comparison.',
                meta: { screen: screen.name, url, property: rawKey, actualKey },
              }));
            }
          }

          inspections.push({ screen: screen.name, url, name, selector, count, box, styles, expected, checks });
        }
      } catch (error) {
        findings.push(makeFinding({
          severity: 'major',
          type: 'ui-alignment-dom-inspection',
          title: `DOM inspection failed for ${screen.name}`,
          evidence: error.message,
          expected: 'The app route should render and allow configured alignment targets to be inspected.',
          recommendation: 'Check baseUrl, app state, waitForSelector, auth/data fixtures, and selector stability.',
          meta: { screen: screen.name, url },
        }));
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  return { inspections, findings };
}

function rel(config, filePath) {
  if (!filePath) return '';
  return toPosixPath(path.relative(config.__meta.configDir, filePath));
}

function findingToMarkdown(finding, index) {
  const lines = [`### ${index}. [${finding.severity || 'info'}] ${finding.title || finding.type || 'Finding'}`];
  if (finding.type) lines.push(`- Category: ${finding.type}`);
  if (finding.selector) lines.push(`- Selector: \`${finding.selector}\``);
  if (finding.file) lines.push(`- File: ${finding.file}${finding.line ? `:${finding.line}` : ''}`);
  if (finding.evidence) lines.push(`- Evidence: ${String(finding.evidence).split('\n').slice(0, 6).join(' ')}`);
  if (finding.observed) lines.push(`- Observed: ${String(finding.observed).split('\n').slice(0, 4).join(' ')}`);
  if (finding.expected) lines.push(`- Expected: ${String(finding.expected).split('\n').slice(0, 4).join(' ')}`);
  if (finding.impact) lines.push(`- Impact: ${String(finding.impact).split('\n').slice(0, 4).join(' ')}`);
  if (finding.recommendation) lines.push(`- Recommended frontend fix: ${String(finding.recommendation).split('\n').slice(0, 4).join(' ')}`);
  if (finding.verification) lines.push(`- Verification: ${String(finding.verification).split('\n').slice(0, 4).join(' ')}`);
  return lines.join('\n');
}

function section(title, findings) {
  if (findings.length === 0) return `## ${title}\n\nNone.\n`;
  return `## ${title}\n\n${findings.map((finding, index) => findingToMarkdown(finding, index + 1)).join('\n\n')}\n`;
}

function summarizeVisual(config, visualReport) {
  const comparisons = visualReport.comparisons || [];
  if (comparisons.length === 0) return '- No visual comparisons completed.';
  return comparisons.map(item => {
    const diff = typeof item.diffPixelRatio === 'number' ? `${(item.diffPixelRatio * 100).toFixed(2)}%` : 'n/a';
    return `- ${item.screen}: ${item.passed ? 'pass' : 'needs review'} (${diff} diff), expected ${rel(config, item.expectedPath)}, actual ${rel(config, item.actualPath)}, diff ${rel(config, item.diffPath)}`;
  }).join('\n');
}

const cliArgs = parseArgs();
const config = await loadConfig({ args: cliArgs });
config.uiAlignment = {
  runVisualComparison: true,
  runComponentAudit: true,
  runDebtAudit: true,
  runA11yAudit: false,
  measurementTolerancePx: config.uiAlignment?.defaultTolerancePx ?? 6,
  ...(config.uiAlignment || {}),
};

function isTruthyFlag(value) {
  return value === true || ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}

if (isTruthyFlag(cliArgs.skipVisual)) config.uiAlignment.runVisualComparison = false;
if (isTruthyFlag(cliArgs.skipComponentAudit) || isTruthyFlag(cliArgs.skipSiblingAudits)) config.uiAlignment.runComponentAudit = false;
if (isTruthyFlag(cliArgs.skipDebtAudit) || isTruthyFlag(cliArgs.skipSiblingAudits)) config.uiAlignment.runDebtAudit = false;
if (isTruthyFlag(cliArgs.skipA11yAudit) || isTruthyFlag(cliArgs.skipSiblingAudits)) config.uiAlignment.runA11yAudit = false;


const configPath = config.__meta.configPath;
const pluginRoot = config.__meta.pluginRoot;
const reportsDir = path.join(config.project.outputDir, 'reports');
const executions = [];
let appProcess = null;
let appReady = null;

try {
  if (config.project.appCommand && !isTruthyFlag(cliArgs.skipAppStart)) {
    appProcess = startApp(config.project.appCommand, config.__meta.configDir);
    appProcess.stdout?.on('data', chunk => process.stdout.write(`[app] ${chunk}`));
    appProcess.stderr?.on('data', chunk => process.stderr.write(`[app] ${chunk}`));
    appReady = await waitForUrl(config.project.appReadyUrl || config.project.baseUrl, config.project.appReadyTimeoutMs || 60000);
    if (!appReady.ok) console.error(`App did not become ready: ${appReady.error}`);
  }

  const steps = [];
  const visualReportPath = path.join(config.project.outputDir, 'reports', 'visual-comparison.json');
  const canReuseVisualReport = await pathExists(visualReportPath);
  const shouldRunVisual = config.uiAlignment.runVisualComparison !== false && (!canReuseVisualReport || config.uiAlignment.forceVisualRefresh === true);
  if (shouldRunVisual) {
    steps.push(['skills/visual-regression-review/scripts/export-figma-frame.mjs', 'Figma/reference export']);
    steps.push(['skills/visual-regression-review/scripts/capture-ui-screenshot.mjs', 'Actual UI screenshot capture']);
    steps.push(['skills/visual-regression-review/scripts/compare-images.mjs', 'Expected vs actual visual comparison']);
  } else if (config.uiAlignment.runVisualComparison !== false) {
    executions.push({ label: 'Reuse existing visual comparison', scriptPath: visualReportPath, status: 0, signal: null, stdout: '', stderr: '', ok: true });
  }
  if (config.uiAlignment.runComponentAudit !== false) steps.push(['skills/component-library-alignment/scripts/audit-components.mjs', 'Component alignment scan']);
  if (config.uiAlignment.runDebtAudit !== false) steps.push(['skills/design-debt-review/scripts/audit-design-debt.mjs', 'Design token/debt scan']);
  if (config.uiAlignment.runA11yAudit === true) steps.push(['skills/accessibility-review/scripts/audit-a11y.mjs', 'Accessibility scan']);

  for (const [script, label] of steps) {
    const scriptPath = path.join(pluginRoot, script);
    console.log(`\n[ui-alignment] ${label}`);
    const result = runNodeScript(scriptPath, configPath, label);
    executions.push(result);
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
  }
} finally {
  if (appProcess && !appProcess.killed) appProcess.kill('SIGTERM');
}

const dom = await collectDomMeasurements(config);
const visualReport = await readJson(path.join(reportsDir, 'visual-comparison.json'), { comparisons: [], findings: [] });
const componentReport = await readJson(path.join(reportsDir, 'component-alignment.json'), { findings: [] });
const debtReport = await readJson(path.join(reportsDir, 'design-debt.json'), { findings: [] });
const a11yReport = await readJson(path.join(reportsDir, 'a11y.json'), { findings: [] });

let findings = [];
findings.push(...(visualReport.findings || []).map(f => ({ ...f, sourceReport: 'visual-comparison.json' })));
findings.push(...dom.findings.map(f => ({ ...f, sourceReport: 'ui-alignment-dom' })));
if (config.uiAlignment.runComponentAudit !== false) findings.push(...(componentReport.findings || []).map(f => ({ ...f, sourceReport: 'component-alignment.json' })));
if (config.uiAlignment.runDebtAudit !== false) findings.push(...(debtReport.findings || []).map(f => ({ ...f, sourceReport: 'design-debt.json' })));
if (config.uiAlignment.runA11yAudit === true) findings.push(...(a11yReport.findings || []).map(f => ({ ...f, sourceReport: 'a11y.json' })));

findings = sortFindings(findings).slice(0, 1000);
const verdict = verdictFromFindings(findings);
const counts = countBySeverity(findings);

const report = {
  ok: verdict === 'Pass' || verdict === 'Pass with warnings',
  generatedAt: new Date().toISOString(),
  configPath,
  pluginRoot,
  appReady,
  alignmentConfig: config.uiAlignment,
  executions: executions.map(item => ({ label: item.label, status: item.status, signal: item.signal, ok: item.ok, error: item.error })),
  summary: {
    screens: config.screens.length,
    anchorsConfigured: config.screens.reduce((sum, screen) => sum + screenInspectSelectors(config, screen).length, 0),
    anchorsInspected: dom.inspections.length,
    blockerOrMajorFindings: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length,
  },
  visualComparisons: visualReport.comparisons || [],
  domInspections: dom.inspections,
  counts,
  verdict,
  findings,
};

const reportPath = path.join(reportsDir, 'ui-alignment.json');
await writeJson(reportPath, report);

const blockers = findings.filter(f => f.severity === 'blocker');
const major = findings.filter(f => f.severity === 'major');
const minor = findings.filter(f => f.severity === 'minor');
const debt = findings.filter(f => f.severity === 'debt');
const info = findings.filter(f => !['blocker', 'major', 'minor', 'debt'].includes(f.severity));

const markdown = `# UI Alignment Report\n\nGenerated: ${new Date().toISOString()}\n\nProject: ${config.project.name}\nConfig: ${rel(config, config.__meta.configPath)}\n\n## Verdict\n\n**${verdict === 'Fail' ? 'Needs fixes' : verdict}**\n\n## Summary\n\n- Blockers / must-fix: ${counts.blocker || 0}\n- Major / should-fix: ${counts.major || 0}\n- Minor / polish: ${counts.minor || 0}\n- Design debt signals: ${counts.debt || 0}\n- Informational notes: ${info.length}\n- DOM alignment targets inspected: ${dom.inspections.length}\n\n## Visual Comparison Summary\n\n${summarizeVisual(config, visualReport)}\n\n${section('Must Fix', blockers)}\n${section('Should Fix', major)}\n${section('Polish', minor)}\n${section('Design Debt Signals', debt)}\n${section('Acceptable Differences / Setup Notes', info)}\n## Artifacts\n\n- UI alignment JSON: ${rel(config, reportPath)}\n- Visual comparison JSON: ${rel(config, path.join(reportsDir, 'visual-comparison.json'))}\n- Component alignment JSON: ${rel(config, path.join(reportsDir, 'component-alignment.json'))}\n- Design debt JSON: ${rel(config, path.join(reportsDir, 'design-debt.json'))}\n\n## Verification Checklist\n\n- [ ] Re-run UI alignment automation after fixes.\n- [ ] Inspect expected/actual/diff screenshots at each target viewport.\n- [ ] Confirm masks only hide dynamic or irrelevant content.\n- [ ] Confirm fixes use design tokens and shared components.\n- [ ] Confirm remaining differences are approved by the design owner before updating baselines.\n`;

const markdownPath = path.join(config.project.outputDir, 'UI_ALIGNMENT_REPORT.md');
await writeText(markdownPath, markdown);
console.log(JSON.stringify({ reportPath, markdownPath, verdict, counts, findings: findings.length }, null, 2));
