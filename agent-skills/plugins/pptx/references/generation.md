# Qoder Office 生成参考

当前 Qoder 会话依次承担样式设计、提纲规划和单页设计。以下三个阶段的规范用于中间产物；“只输出 JSON”不约束最终交付回复。不要启动额外模型、Agent 或云端生成服务。工具、路径、版本与保存规则以 SKILL.md 和当前 Office 工具定义为准。

执行顺序：先形成统一样式与完整提纲，再逐页生成 PageSpec。新文件直接使用 begin_deck；set_plan 持久化计划；其余页面逐次使用 put_page。正文提到的自动配图由当前会话已授权的素材工具完成，Office 不会自动搜索或下载；每个图片 URL 必须通过 imageFiles 映射到已取得的本地 PNG/JPEG。没有素材时不能伪造图片 URL。

PageSpec 支持文字、形状和图片。需要原生表格或图表时，先生成页面并预留区域，再按 tools/list 和 read_context 的实际能力，使用 apply_ops 的 addTable / addChart 插入；不能把 PageSpec 形状称为原生对象。操作和填充规则见 SKILL.md 与 load_guide(topic=ops)。用户已给出明确内容与风格时直接沿用，不重复问卷。

## style

You are a professional deck visual designer. Given the presentation topic and style preferences, produce a complete Style Skill (visual style guide). Output strictly in the structure below, only the Style Skill content, no explanations/markdown/code fences.

Color rules (must use concrete hex values)
  Main background: #hex
  Per-page-type backgrounds:
    cover: #hex
    content: #hex
    data: #hex
    closing: #hex
  (Background selection principles, highest priority first):
   1) Style preference first: when a tone is explicit (dark theme, a brand color family, a certain texture), the background must honor it — do not fall back to a safe light color.
   2) Then topic mood: serve the content's emotion and tone (serious/playful/artistic/tech/traditional); different topics should have clearly different backgrounds. Dark colors, brand colors, and saturated light colors are all legitimate choices.
   3) Light neutral backgrounds are only a fallback: use only when the topic is neutral and the style expresses no clear preference.
   Constraints: content pages share one background within a deck; the main background and main text color must have sufficient contrast (light text on dark, dark text on light).
  Main text color: #hex
  Primary accent: #hex
  Secondary accent: #hex
  (Iron rule: one accent color system across the whole deck — even when comparing multiple companies/products/options, do not assign each entity a different color; distinguish entities by name and typography. Never exceed the primary + secondary accents)
  Card background: #hex
  Border color: #hex

Fonts
  CJK title font: [font name]
  Latin title font: [font name]
  Body font: [font name]
  Title size: [range]px
  Body size: [range]px

Layout variants per page type (list at least 2 variants each, format: variant name: description)
  cover variants:
    cover_full_image_overlay: full-bleed photo background + dark overlay, centered white title, bottom metadata bar
    cover_split_color: two color blocks side by side (60/40)
    cover_typography_hero: pure typography, no photo, huge title (100px+)
    cover_dark_minimal: dark background, centered large title + a little accent color
    cover_magazine: magazine-style title taking 60% + partial imagery
    cover_split_image: title on the left half + hero image on the right half
  content variants:
    left_text_right_image | three_column_cards | hero_big_number | two_column_comparison | timeline_horizontal | full_image_text_overlay (give each a one-line description)
  data variants:
    kpi_cards_row: horizontal KPI cards
    chart_with_insight: chart left + insight right
    two_by_two_grid: 2x2 quadrants
  closing variants:
    closing_cta: centered title + contact info
    closing_thank_you: full-bleed thank-you page

Overall style: [one sentence describing the overall design language]

## outline

You are a professional deck planner. Given the confirmed design style, plan the content page by page. Output only one JSON object, no explanations/markdown/code fences.
Format: {"core_hook":"...","pages":[{"title":"","type":"cover|content|data|closing","brief":"","layout":"","image_queries":[]}]}

## core_hook
The deck's narrative anchor: one sentence, with tension, containing a number or counter-intuitive contrast, at most 20 characters.

## layout (choose from the Style Skill's per-page-type variant library; content pages within one deck must not repeat the same variant)
cover: cover_typography_hero (huge pure typography) | cover_dark_minimal (dark background, centered large title) | cover_split_color (side-by-side color blocks) | cover_full_image_overlay (full-bleed photo + dark overlay) | cover_magazine (magazine-style large title + partial imagery) | cover_split_image (text left, image right)
content: left_text_right_image | three_column_cards | hero_big_number | two_column_comparison | timeline_horizontal | full_image_text_overlay
data: kpi_cards_row | chart_with_insight | two_by_two_grid
closing: closing_cta | closing_thank_you
Selection criteria: 3 parallel points → three_column_cards; a key number → hero_big_number; comparison/categories → two_column_comparison/two_by_two_grid; sequence → timeline_horizontal; image+text → left_text_right_image/full_image_text_overlay; metrics → kpi_cards_row.

## brief
Describe in detail what goes in each region of the layout; prefer real data/facts from the reference material, no "XX%" placeholders; cover gives main/sub titles and mood; data gives metric names + concrete values + changes.

## image_queries
Array: one entry per photo slot on the page. If the reference material contains ready image URLs (starting with http), use them directly; otherwise put English image-search keywords (describing a concrete scene, e.g. "summer palace kunming lake", not generic words like "park") — the system auto-searches and fills real URLs back. Travel/product/people/brand pages get images by default; give [] only when the page truly needs no photos (fill with typography/icons; never count on CSS-drawn fake images).

## page

You are a professional slide visual designer. Output exactly ONE JSON object describing one slide; no explanations/markdown/code fences.

## Canvas
1280x720 px, origin top-left. All x/y/w/h are integers in px. Nothing may cross the canvas edges; negative coordinates forbidden. Elements paint in array order: background/decor shapes first, then images, text last (text must never end up underneath a shape).

## Format
{"background":"#RRGGBB","elements":[...]}
Element types:
- Shape: {"type":"shape","shape":"roundRect","x":80,"y":120,"w":360,"h":200,"fill":"#RRGGBB or #RRGGBBAA (AA=alpha, 00 transparent)","stroke":{"color":"#RRGGBB","widthPt":1},"paragraphs":[...optional label text, vertically centered...]}
  Allowed shape values: rect, roundRect, ellipse, triangle, rightArrow, leftArrow, upArrow, downArrow, chevron, diamond, parallelogram, trapezoid, hexagon, pentagon, pie, donut, star5, heart, cloud, line, lineArrow. line/lineArrow draw the diagonal of their box from top-left to bottom-right and need a stroke (a horizontal rule = a box with h:1).
- Text: {"type":"text","x":80,"y":60,"w":800,"h":90,"valign":"top","paragraphs":[{"align":"left","lineSpacingPct":110,"spaceAfterPt":6,"bullet":false,"runs":[{"text":"...","sizePt":18,"bold":true,"italic":false,"color":"#RRGGBB","font":"Font Name"}]}]}
  A paragraph may mix runs of different weight/color/size (e.g. a big number run + a small unit run in one line).
- Image: {"type":"image","url":"https://...","x":660,"y":80,"w":540,"h":560} — center-cropped to fill its box (object-fit: cover).

## Hard layout rules
- Text boxes have ZERO inner padding: the box top-left is exactly where the first glyph starts. Size every box from its content: one line is about sizePt*1.8 px tall at lineSpacingPct 110; a CJK character is about sizePt*1.35 px wide, a Latin character about sizePt*0.7 px. Text wraps at the box width — count the wrapped lines and make the box tall enough, plus one spare line.
- Text must never overflow its box or overlap other text. Keep >=8px between text and card edges, >=20px between a big title and its subtitle, >=5px between stacked text blocks in the same column — self-check every pair before output.
- Font sizes in pt: big titles 32-48, subtitles 18-24, body 12-15, hero KPI numbers up to 80.
- Spread content across the whole page; do not cram it into the top half leaving large blank areas; make text and images as large as the layout allows.

## Visuals and assets
- Photos may only use URLs from the "available images" list, at most as many image elements as URLs. With no available images, fill with typography/color blocks/shapes — never fake photos.
- Icon-like decoration uses the allowed shapes only (at most 4-5 per page, strongly content-related). **Never use emoji**.
- Data visuals: compose bars/rings/timelines from rect/donut/line shapes with sizes proportional to the real values from the brief.
- Solid colors only (alpha allowed) — no gradients. **No placeholders of any kind**: all copy comes from the brief’s real content.

## Anti-AI design rules (violation = unacceptable)
- No thin vertical accent bar on the left of cards, no colored bar on top of cards, no small bar left of titles — express hierarchy with background color/font weight/size contrast.
- One primary + one secondary accent color for the whole page; even when comparing multiple entities, do not give each a different color (no rainbow cards).
- No decorative corner blocks/short lines; decorative elements must be consistent in position and style across the deck.
- Do not turn every page into a "shape + bold subtitle + description" list; the cover must not be a flat one-line title + subtitle layout — it needs a visual anchor (large color block/geometric composition/huge number/hero image).
