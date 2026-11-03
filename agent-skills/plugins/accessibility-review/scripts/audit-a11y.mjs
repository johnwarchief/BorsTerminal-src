#!/usr/bin/env node
import path from 'node:path';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { loadConfig, screenUrl } from '../../../shared/lib/config.mjs';
import { writeJson } from '../../../shared/lib/files.mjs';
import { makeFinding } from '../../../shared/lib/findings.mjs';

const config = await loadConfig();
const findings = [];
const scans = [];

if (config.screens.length === 0) {
  findings.push(makeFinding({
    severity: 'info',
    type: 'a11y',
    title: 'No screens configured for accessibility scan',
    evidence: config.__meta.configPath,
    recommendation: 'Add screens to design.qa.yaml.',
  }));
}

const browser = await chromium.launch({ headless: true });

for (const screen of config.screens) {
  const app = screen.app || {};
  const viewport = app.viewport || { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const url = screenUrl(config, screen);

  try {
    await page.goto(url, {
      waitUntil: app.waitUntil || 'networkidle',
      timeout: app.timeoutMs || 45000,
    });
    if (app.waitForSelector) {
      await page.waitForSelector(app.waitForSelector, { timeout: app.waitForSelectorTimeoutMs || 15000 });
    }

    let builder = new AxeBuilder({ page });
    if (config.a11y.disabledRules?.length) {
      builder = builder.disableRules(config.a11y.disabledRules);
    }
    for (const selector of config.a11y.includeSelectors || []) {
      builder = builder.include(selector);
    }
    for (const selector of config.a11y.excludeSelectors || []) {
      builder = builder.exclude(selector);
    }

    const result = await builder.analyze();
    const summary = {
      screen: screen.name,
      url,
      viewport,
      violations: result.violations.map(v => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        help: v.help,
        helpUrl: v.helpUrl,
        nodes: v.nodes.map(n => ({
          target: n.target,
          html: n.html,
          failureSummary: n.failureSummary,
        })),
      })),
      passes: result.passes?.length || 0,
      incomplete: result.incomplete?.length || 0,
      inapplicable: result.inapplicable?.length || 0,
    };
    scans.push(summary);

    for (const violation of summary.violations) {
      const node = violation.nodes[0];
      const severity = violation.impact === 'critical' ? 'blocker'
        : violation.impact === 'serious' ? 'major'
        : violation.impact === 'moderate' ? 'minor'
        : 'info';
      findings.push(makeFinding({
        severity,
        type: 'a11y',
        title: `${violation.id}: ${violation.help}`,
        selector: node?.target?.join(', '),
        evidence: node?.failureSummary || violation.description,
        observed: node?.html,
        expected: violation.description,
        impact: `axe impact: ${violation.impact || 'unknown'}`,
        recommendation: `Fix according to ${violation.helpUrl}`,
        verification: 'Re-run the accessibility scan and perform keyboard/manual review for the affected flow.',
        meta: { screen: screen.name, url, ruleId: violation.id, helpUrl: violation.helpUrl },
      }));
    }
  } catch (error) {
    findings.push(makeFinding({
      severity: 'blocker',
      type: 'a11y',
      title: `Accessibility scan failed for ${screen.name}`,
      evidence: error.message,
      observed: `Could not scan ${url}`,
      expected: 'Route should render successfully for a11y scan',
      recommendation: 'Check app availability, baseUrl, route, and waitForSelector.',
      meta: { screen: screen.name, url, viewport },
    }));
  } finally {
    await context.close();
  }
}

await browser.close();

const report = {
  ok: findings.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  scans,
  findings,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'a11y.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, scans: scans.length, findings: findings.length }, null, 2));
