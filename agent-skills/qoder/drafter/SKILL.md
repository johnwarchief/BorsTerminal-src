---
name: drafter
version: 1.0.0
description: Generate technical diagrams using HTML/CSS in Flat Engineering Blueprint style. Use when the user wants to create architecture diagrams, system diagrams, flowcharts, or technical specification sheets that look like engineering blueprints. Triggers on requests for flat diagrams, blueprint-style visualizations, or technical drawings.
description_zh: 帮你把「系统怎么组成、流程怎么走、模块怎么连」画成一张好读的技术示意图，看起来像工整的工程图纸，线条清爽、不花哨。你只要说清楚主题和要点，就能得到一页可以保存或分享的成品；适合汇报、文档配图或和同事对齐思路。
category: design-ui
recommended: true
---

# Flat Engineering Blueprint Diagram Generator

Generate precise, objective diagrams with high data-ink ratio. Output should resemble technical specification sheets or architectural diagrams, NOT marketing landing pages.

## Core Philosophy

Precise, Objective, High Data-Ink Ratio.

## Visual Rules

### 1. No Decorations

- NO drop shadows
- NO gradients
- NO glassmorphism/blur
- NO rounded buttons

### 2. Flat & Outlined

- Use 1px or 2px solid borders for structure
- Use white backgrounds for content blocks

### 3. Monochrome Base

```css
:root {
  --c-bg: #f8fafc; /* Outer Background */
  --c-canvas: #ffffff; /* Diagram Background */
  --c-border: #cbd5e1; /* Slate-300 */
  --c-text-main: #0f172a; /* Slate-900 */
  --c-text-sub: #64748b; /* Slate-500 */
  --font-ui: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', Monaco, Consolas, monospace;
}
```

- Background: Light Gray (#f8fafc)
- Canvas: White (#ffffff) with Slate Border (#cbd5e1)
- Text: High contrast Black (#0f172a) and Slate Gray (#64748b)
- Accent: Use BLACK or ONE semantic color (e.g., Red for Error) sparingly

### 4. Typography

- Headings/Labels: Sans-serif (`system-ui, -apple-system, 'Segoe UI', sans-serif`)
- Data/Paths/Code: Monospace (`'SF Mono', Monaco, Consolas, monospace`)

### 5. Layout Structure

- Diagram must be contained within a `diagram-canvas` (bordered box with padding)
- Header: Title + Uppercase Subtitle, separated by solid bottom border
- Grid/Flexbox alignment: Everything must be strictly aligned

### 6. Elements

- Connectors: Thin, straight or orthogonal lines. Dashed lines for abstract relationships
- Icons: Simple stroke SVG icons (no fill or complex details)
- Badges: Outlined or solid black/gray blocks. Small font size

## Critical Requirements

1. Use ONLY system fonts, NO external CDN (like Google Fonts)
2. Return ONLY the complete HTML content, NO markdown code blocks
3. HTML must be a complete, self-contained document with `<!DOCTYPE html>`
4. All styles must be inline within `<style>` tags
5. Prefer Chinese text when appropriate, use system fonts

## Output Format

Return a complete HTML document:

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>[Diagram Title]</title>
    <style>
      :root {
        --c-bg: #f8fafc;
        --c-canvas: #ffffff;
        --c-border: #cbd5e1;
        --c-text-main: #0f172a;
        --c-text-sub: #64748b;
        --font-ui: system-ui, -apple-system, 'Segoe UI', sans-serif;
        --font-mono: 'SF Mono', Monaco, Consolas, monospace;
      }

      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        background: var(--c-bg);
        font-family: var(--font-ui);
        color: var(--c-text-main);
        padding: 40px;
      }

      .diagram-canvas {
        background: var(--c-canvas);
        border: 2px solid var(--c-border);
        padding: 32px;
        max-width: 1200px;
        margin: 0 auto;
      }

      .diagram-header {
        border-bottom: 1px solid var(--c-border);
        padding-bottom: 16px;
        margin-bottom: 24px;
      }

      .diagram-title {
        font-size: 24px;
        font-weight: 600;
        color: var(--c-text-main);
      }

      .diagram-subtitle {
        font-size: 12px;
        font-weight: 500;
        color: var(--c-text-sub);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
      }

      /* Add diagram-specific styles here */
    </style>
  </head>
  <body>
    <div class="diagram-canvas">
      <div class="diagram-header">
        <h1 class="diagram-title">[Title]</h1>
        <p class="diagram-subtitle">[SUBTITLE IN UPPERCASE]</p>
      </div>

      <!-- Diagram content here -->
    </div>
  </body>
</html>
```

## Common Components

### Node/Box

```css
.node {
  background: var(--c-canvas);
  border: 1px solid var(--c-border);
  padding: 12px 16px;
}
```

### Badge

```css
.badge {
  display: inline-block;
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 2px 6px;
  border: 1px solid var(--c-text-main);
  text-transform: uppercase;
}

.badge--filled {
  background: var(--c-text-main);
  color: var(--c-canvas);
}
```

### Connector Line (using pseudo-elements or SVG)

```css
.connector {
  border-top: 1px solid var(--c-border);
}

.connector--dashed {
  border-top-style: dashed;
}
```

### Monospace Text

```css
.mono {
  font-family: var(--font-mono);
  font-size: 13px;
}
```
