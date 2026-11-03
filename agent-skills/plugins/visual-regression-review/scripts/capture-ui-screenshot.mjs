#!/usr/bin/env node
import path from 'node:path';
import { chromium } from '@playwright/test';
import { loadConfig, screenUrl } from '../../../shared/lib/config.mjs';
import { writeJson } from '../../../shared/lib/files.mjs';
import { actualPathForScreen } from '../../../shared/lib/screens.mjs';
import { makeFinding } from '../../../shared/lib/findings.mjs';

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

const config = await loadConfig();
const findings = [];
const captures = [];

if (config.screens.length === 0) {
  findings.push(makeFinding({
    severity: 'info',
    type: 'screenshot',
    title: 'No screens configured',
    evidence: config.__meta.configPath,
    recommendation: 'Add screens to design.qa.yaml before running screenshot capture.',
  }));
}

const browser = await chromium.launch({ headless: true });

for (const screen of config.screens) {
  const app = screen.app || {};
  const viewport = app.viewport || { width: 1440, height: 900 };
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: app.deviceScaleFactor || 1,
    reducedMotion: 'reduce',
  });
  if (app.freezeDate) {
    await context.addInitScript(freezeDateScript(app.freezeDate));
  }

  const page = await context.newPage();
  const url = screenUrl(config, screen);
  const outPath = actualPathForScreen(config, screen);

  try {
    await page.addStyleTag({
      content: `*, *::before, *::after { animation-duration: 0s !important; animation-delay: 0s !important; transition-duration: 0s !important; transition-delay: 0s !important; caret-color: transparent !important; }`,
    }).catch(() => {});

    await page.goto(url, {
      waitUntil: app.waitUntil || 'networkidle',
      timeout: app.timeoutMs || 45000,
    });

    if (app.waitForSelector) {
      await page.waitForSelector(app.waitForSelector, { timeout: app.waitForSelectorTimeoutMs || 15000 });
    }

    const ignoreSelectors = screen.compare?.ignoreSelectors || [];
    if (ignoreSelectors.length > 0) {
      const css = ignoreSelectors.map(selector => `${selector} { visibility: hidden !important; }`).join('\n');
      await page.addStyleTag({ content: css });
    }

    const masks = [];
    for (const mask of screen.compare?.masks || []) {
      if (mask.selector) masks.push(page.locator(mask.selector));
    }

    await page.screenshot({
      path: outPath,
      fullPage: app.fullPage !== false,
      animations: 'disabled',
      mask: masks,
    });

    captures.push({
      screen: screen.name,
      url,
      viewport,
      deviceScaleFactor: app.deviceScaleFactor || 1,
      fullPage: app.fullPage !== false,
      path: outPath,
      masks: (screen.compare?.masks || []).map(m => m.selector).filter(Boolean),
      ignoreSelectors,
    });
  } catch (error) {
    findings.push(makeFinding({
      severity: 'blocker',
      type: 'screenshot',
      title: `Failed to capture screenshot for ${screen.name}`,
      evidence: error.message,
      observed: `Could not capture ${url}`,
      expected: 'App route should render successfully in the configured viewport',
      recommendation: 'Check that the app is running, baseUrl is correct, and waitForSelector exists.',
      meta: { screen: screen.name, url, viewport },
    }));
  } finally {
    await context.close();
  }
}

await browser.close();

const report = {
  ok: findings.filter(f => f.severity === 'blocker').length === 0,
  generatedAt: new Date().toISOString(),
  captures,
  findings,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'screenshots.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, captured: captures.length, findings: findings.length }, null, 2));
