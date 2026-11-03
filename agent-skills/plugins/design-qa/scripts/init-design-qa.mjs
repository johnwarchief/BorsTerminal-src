#!/usr/bin/env node
import path from 'node:path';
import { parseArgs } from '../../../shared/lib/args.mjs';
import { pathExists, readText, writeText } from '../../../shared/lib/files.mjs';

const args = parseArgs();
function findPluginRoot() {
  const envRoot = process.env.DESIGN_PLUGIN_ROOT;
  if (envRoot) return path.resolve(envRoot);
  return path.resolve(new URL('../../..', import.meta.url).pathname);
}

const pluginRoot = findPluginRoot();
const cwd = process.cwd();
const force = Boolean(args.force);

const files = [
  ['templates/design.qa.yaml', 'design.qa.yaml'],
  ['templates/DESIGN.md', 'DESIGN.md'],
  ['templates/SCREEN_SPEC.md', 'SCREEN_SPEC.md'],
];

const results = [];
for (const [srcRel, destRel] of files) {
  const src = path.join(pluginRoot, srcRel);
  const dest = path.join(cwd, destRel);
  const exists = await pathExists(dest);
  if (exists && !force) {
    results.push({ file: destRel, status: 'skipped', reason: 'already exists' });
    continue;
  }
  const content = await readText(src);
  await writeText(dest, content);
  results.push({ file: destRel, status: exists ? 'overwritten' : 'created' });
}

console.log(JSON.stringify({ ok: true, cwd, pluginRoot, results }, null, 2));
