#!/usr/bin/env node
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { writeJson } from '../../../shared/lib/files.mjs';

function runNodeScript(scriptPath, configPath, label, extraArgs = []) {
  const result = spawnSync(process.execPath, [scriptPath, '--config', configPath, ...extraArgs], {
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

const config = await loadConfig();
const configPath = config.__meta.configPath;
const pluginRoot = config.__meta.pluginRoot;
const executions = [];
let appProcess = null;
let appReady = null;

try {
  if (config.project.appCommand) {
    appProcess = startApp(config.project.appCommand, config.__meta.configDir);
    appProcess.stdout?.on('data', chunk => process.stdout.write(`[app] ${chunk}`));
    appProcess.stderr?.on('data', chunk => process.stderr.write(`[app] ${chunk}`));
    appReady = await waitForUrl(config.project.appReadyUrl || config.project.baseUrl, config.project.appReadyTimeoutMs || 60000);
    if (!appReady.ok) {
      console.error(`App did not become ready: ${appReady.error}`);
    }
  }

  const steps = [
    ['skills/design-md-review/scripts/audit-design-md.mjs', 'DESIGN.md review'],
    ['skills/visual-regression-review/scripts/export-figma-frame.mjs', 'Figma export'],
    ['skills/visual-regression-review/scripts/capture-ui-screenshot.mjs', 'Screenshot capture'],
    ['skills/visual-regression-review/scripts/compare-images.mjs', 'Visual comparison'],
    ['skills/ui-alignment-review/scripts/audit-ui-alignment.mjs', 'UI alignment audit', ['--skip-sibling-audits', '--skip-app-start']],
    ['skills/accessibility-review/scripts/audit-a11y.mjs', 'Accessibility scan'],
    ['skills/component-library-alignment/scripts/audit-components.mjs', 'Component alignment'],
    ['skills/design-debt-review/scripts/audit-design-debt.mjs', 'Design debt scan'],
    ['skills/design-qa/scripts/generate-design-qa-report.mjs', 'Report generation'],
  ];

  for (const [script, label, extraArgs = []] of steps) {
    const scriptPath = path.join(pluginRoot, script);
    console.log(`\n[design-qa] ${label}`);
    const result = runNodeScript(scriptPath, configPath, label, extraArgs);
    executions.push(result);
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
  }
} finally {
  if (appProcess && !appProcess.killed) {
    appProcess.kill('SIGTERM');
  }
}

const runReport = {
  ok: executions.every(item => item.ok),
  generatedAt: new Date().toISOString(),
  configPath,
  pluginRoot,
  appReady,
  executions: executions.map(item => ({
    label: item.label,
    status: item.status,
    signal: item.signal,
    ok: item.ok,
    error: item.error,
  })),
};

const reportPath = path.join(config.project.outputDir, 'reports', 'run-design-qa.json');
await writeJson(reportPath, runReport);
console.log(JSON.stringify({ reportPath, ok: runReport.ok }, null, 2));
