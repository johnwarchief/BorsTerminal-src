#!/usr/bin/env node
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { loadConfig } from '../../../shared/lib/config.mjs';
import { writeJson } from '../../../shared/lib/files.mjs';

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

const config = await loadConfig();
const configPath = config.__meta.configPath;
const pluginRoot = config.__meta.pluginRoot;
const executions = [];

const steps = [
  ['skills/ui-alignment-review/scripts/audit-ui-alignment.mjs', 'UI alignment audit'],
  ['skills/ui-alignment-review/scripts/generate-ui-alignment-report.mjs', 'UI alignment report generation'],
];

for (const [script, label] of steps) {
  const scriptPath = path.join(pluginRoot, script);
  console.log(`\n[ui-alignment] ${label}`);
  const result = runNodeScript(scriptPath, configPath, label);
  executions.push(result);
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
}

const runReport = {
  ok: executions.every(item => item.ok),
  generatedAt: new Date().toISOString(),
  configPath,
  pluginRoot,
  executions: executions.map(item => ({
    label: item.label,
    status: item.status,
    signal: item.signal,
    ok: item.ok,
    error: item.error,
  })),
};

const reportPath = path.join(config.project.outputDir, 'reports', 'run-ui-alignment.json');
await writeJson(reportPath, runReport);
console.log(JSON.stringify({ reportPath, ok: runReport.ok }, null, 2));

process.exit(runReport.ok ? 0 : 1);
