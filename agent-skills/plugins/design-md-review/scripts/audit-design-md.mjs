#!/usr/bin/env node
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import YAML from 'yaml';
import { loadConfig, resolveConfigPath } from '../../../shared/lib/config.mjs';
import { pathExists, readText, writeJson } from '../../../shared/lib/files.mjs';
import { makeFinding, sortFindings } from '../../../shared/lib/findings.mjs';

const REQUIRED_SECTIONS = [
  'Overview',
  'Colors',
  'Typography',
  'Layout',
  'Elevation & Depth',
  'Shapes',
  'Components',
  "Do's and Don'ts",
];
const REQUIRED_FRONTMATTER_GROUPS = ['colors', 'typography', 'rounded', 'spacing', 'components'];
const MAJOR_FRONTMATTER_GROUPS = new Set(['colors', 'typography', 'components']);
const STANDARD_COMPONENT_PROPERTIES = new Set(['backgroundColor', 'textColor', 'typography', 'rounded', 'padding', 'size', 'height', 'width']);

function extractFrontmatter(markdown) {
  const match = markdown.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/);
  if (!match) return { raw: null, data: null, error: null, body: markdown };
  try {
    return {
      raw: match[1],
      data: YAML.parse(match[1]),
      error: null,
      body: markdown.slice(match[0].length),
    };
  } catch (error) {
    return { raw: match[1], data: null, error, body: markdown.slice(match[0].length) };
  }
}

function sectionRegex(title) {
  const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`^##\\s+${escaped}\\s*$`, 'mi');
}

function getSectionBody(markdown, title) {
  const regex = sectionRegex(title);
  const match = regex.exec(markdown);
  if (!match) return null;
  const after = markdown.slice(match.index + match[0].length);
  const next = after.search(/^##\s+/m);
  return (next === -1 ? after : after.slice(0, next)).trim();
}

function hasAny(text, words) {
  const lower = text.toLowerCase();
  return words.some(word => lower.includes(word));
}

function isRecord(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

const config = await loadConfig();
const designMdPath = resolveConfigPath(config, config.design.designMd);
const findings = [];
let officialLint = null;

if (!(await pathExists(designMdPath))) {
  findings.push(makeFinding({
    severity: 'blocker',
    type: 'design-md',
    title: 'DESIGN.md is missing',
    file: path.relative(config.__meta.configDir, designMdPath),
    evidence: designMdPath,
    expected: 'A DESIGN.md file should define global design-system tokens and design rationale.',
    recommendation: 'Create DESIGN.md from templates/DESIGN.md and replace starter values with real project tokens and rules.',
  }));
} else {
  const markdown = await readText(designMdPath);
  const parsed = extractFrontmatter(markdown);

  if (!parsed.raw) {
    findings.push(makeFinding({
      severity: 'major',
      type: 'design-md-frontmatter',
      title: 'DESIGN.md has no YAML frontmatter',
      file: path.relative(config.__meta.configDir, designMdPath),
      expected: 'YAML frontmatter should contain machine-readable design tokens.',
      recommendation: 'Add standard DESIGN.md frontmatter with `version`, `name`, `description`, `colors`, `typography`, `rounded`, `spacing`, and `components`.',
    }));
  } else if (parsed.error) {
    findings.push(makeFinding({
      severity: 'blocker',
      type: 'design-md-frontmatter',
      title: 'DESIGN.md frontmatter is invalid YAML',
      file: path.relative(config.__meta.configDir, designMdPath),
      evidence: parsed.error.message,
      expected: 'Valid YAML frontmatter between --- delimiters.',
      recommendation: 'Fix YAML indentation, quoting, and object structure.',
    }));
  } else {
    const frontmatter = isRecord(parsed.data) ? parsed.data : {};
    const nestedTokens = isRecord(frontmatter.tokens) || isRecord(frontmatter.designTokens) || isRecord(frontmatter.design_tokens);
    const standardGroupCount = REQUIRED_FRONTMATTER_GROUPS.filter(key => isRecord(frontmatter[key])).length;

    if (nestedTokens && standardGroupCount < 3) {
      findings.push(makeFinding({
        severity: 'major',
        type: 'design-md-tokens',
        title: 'DESIGN.md frontmatter uses a nested tokens object instead of the public schema',
        file: path.relative(config.__meta.configDir, designMdPath),
        expected: 'Machine-readable tokens should use top-level `colors`, `typography`, `rounded`, `spacing`, and `components` groups.',
        recommendation: 'Promote nested token groups to the standard top-level DESIGN.md schema and keep plugin-specific metadata in markdown sections.',
      }));
    }

    for (const key of REQUIRED_FRONTMATTER_GROUPS) {
      if (!isRecord(frontmatter[key])) {
        findings.push(makeFinding({
          severity: MAJOR_FRONTMATTER_GROUPS.has(key) ? 'major' : 'minor',
          type: 'design-md-tokens',
          title: `DESIGN.md frontmatter missing ${key}`,
          file: path.relative(config.__meta.configDir, designMdPath),
          expected: `Top-level \`${key}\` should define the reusable ${key} system.`,
          recommendation: `Add evidenced \`${key}\` entries using the standard DESIGN.md schema, or explain why the project intentionally omits them.`,
        }));
      }
    }

    if (isRecord(frontmatter.typography)) {
      const weakTypography = Object.entries(frontmatter.typography).filter(([, value]) => !isRecord(value));
      if (weakTypography.length > 0) {
        findings.push(makeFinding({
          severity: 'major',
          type: 'design-md-tokens',
          title: 'DESIGN.md typography tokens are not structured',
          file: path.relative(config.__meta.configDir, designMdPath),
          evidence: weakTypography.slice(0, 8).map(([key]) => key).join(', '),
          expected: 'Typography tokens should be named levels with fontFamily, fontSize, fontWeight, lineHeight, and letterSpacing when evidenced.',
          recommendation: 'Replace shallow font metadata with structured levels such as `display-lg`, `heading-md`, `body-md`, `body-sm`, `caption`, `button-md`, and `code-md`.',
        }));
      }
    }

    if (isRecord(frontmatter.components)) {
      const weakComponents = Object.entries(frontmatter.components)
        .filter(([, value]) => !isRecord(value) || !Object.keys(value).some(property => STANDARD_COMPONENT_PROPERTIES.has(property)));
      if (weakComponents.length > 0) {
        findings.push(makeFinding({
          severity: 'minor',
          type: 'design-md-components',
          title: 'Some component tokens do not expose standard component properties',
          file: path.relative(config.__meta.configDir, designMdPath),
          evidence: weakComponents.slice(0, 8).map(([key]) => key).join(', '),
          expected: 'Component tokens should map implementation components and states to properties such as backgroundColor, textColor, typography, rounded, padding, height, or width.',
          recommendation: 'Model variants and states as component token entries such as `button-primary`, `button-primary-hover`, `text-input-focused`, and `table-row-selected`.',
        }));
      }
    }
  }

  for (const section of REQUIRED_SECTIONS) {
    const body = getSectionBody(markdown, section);
    if (body === null) {
      findings.push(makeFinding({
        severity: 'major',
        type: 'design-md-section',
        title: `DESIGN.md missing section: ${section}`,
        file: path.relative(config.__meta.configDir, designMdPath),
        expected: `Section "${section}" should explain design intent and usage rules.`,
        recommendation: `Add a ## ${section} section with actionable guidance for agents and developers.`,
      }));
    } else if (body.length < 80) {
      findings.push(makeFinding({
        severity: 'minor',
        type: 'design-md-section',
        title: `DESIGN.md section is too thin: ${section}`,
        file: path.relative(config.__meta.configDir, designMdPath),
        evidence: body,
        expected: 'Sections should provide enough rationale and rules for implementation decisions.',
        recommendation: `Expand ## ${section} with token references, examples, and Do/Don't guidance.`,
      }));
    }
  }

  const components = getSectionBody(markdown, 'Components') || '';
  if (components && !hasAny(components, ['hover', 'focus', 'disabled', 'loading', 'error'])) {
    findings.push(makeFinding({
      severity: 'minor',
      type: 'design-md-components',
      title: 'Components section does not define interaction states',
      file: path.relative(config.__meta.configDir, designMdPath),
      expected: 'Interactive components should define hover, focus-visible, active, disabled, loading, and error states when relevant.',
      recommendation: 'Add a component state matrix for Button, Input, Select, Dialog, Card, and other shared components.',
    }));
  }

  if (config.design.runOfficialLint || process.env.RUN_DESIGN_MD_LINT === '1') {
    const result = spawnSync('npx', ['--yes', '@google/design.md', 'lint', designMdPath], {
      cwd: config.__meta.configDir,
      encoding: 'utf8',
      timeout: 30000,
    });
    officialLint = {
      command: `npx --yes @google/design.md lint ${path.relative(config.__meta.configDir, designMdPath)}`,
      status: result.status,
      stdout: result.stdout,
      stderr: result.stderr,
      error: result.error?.message,
    };
    if (result.status !== 0) {
      findings.push(makeFinding({
        severity: 'major',
        type: 'design-md-official-lint',
        title: 'Official design.md lint reported issues',
        file: path.relative(config.__meta.configDir, designMdPath),
        evidence: `${result.stdout || ''}\n${result.stderr || ''}`.trim(),
        expected: 'Official lint should pass or all deviations should be intentionally documented.',
        recommendation: 'Review lint output and fix broken token references, section issues, or contrast/token problems.',
      }));
    }
  }
}

const sorted = sortFindings(findings);
const report = {
  ok: sorted.filter(f => f.severity === 'blocker' || f.severity === 'major').length === 0,
  generatedAt: new Date().toISOString(),
  designMdPath,
  officialLint,
  findings: sorted,
};

const reportPath = path.join(config.project.outputDir, 'reports', 'design-md-audit.json');
await writeJson(reportPath, report);
console.log(JSON.stringify({ reportPath, findings: sorted.length, ok: report.ok }, null, 2));
