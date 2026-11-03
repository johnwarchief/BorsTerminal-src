# agent-skills — همۀ اسکیل‌های این ماشین، برای ادامه روی ماشینِ دیگر

این پوشه از روی ماشینِ اصلی کپی شده تا روی ماشینِ دوم همان اسکیل‌ها در دسترس باشند.

- ۱۲۲ اسکیل در سه گروه، ۱۰۴۱ فایل، حدود ۱۵ مگابایت.
- فایل‌های بیش از ۲ مگابایت کپی نشدند (هیچ‌کدام نبود) و `node_modules` / `.cache` / `.git` بیرون ماندند.
- اسکنِ رمز روی همۀ فایل‌های کپی‌شده اجرا شد: کلیدِ خصوصی، توکنِ GitHub، AWS و Slack — هیچ.

## اسکیل‌هایی که لازم نیست این‌جا باشند

این‌ها از قبل داخلِ همین شاخه‌اند و با clone آمدند (۲۹ اسکیل):

- `skills/` — هشت اسکیلِ قراردادِ کارِ همین پروژه
- `.agents/skills/` — بیست‌ویک اسکیلِ متدولوژیِ همین پروژه

## ~/.agents/skills — اسکیل‌های سراسریِ کاربر (51)

- `agents/antislop/` — 2 فایل
- `agents/antislop-code/` — 1 فایل
- `agents/antislop-copywriting/` — 1 فایل
- `agents/antislop-human/` — 6 فایل
- `agents/antislop-layoutmobile/` — 1 فایل
- `agents/antislop-ui/` — 4 فایل
- `agents/ask-matt/` — 3 فایل
- `agents/chief-of-staff/` — 2 فایل
- `agents/claude-handoff/` — 2 فایل
- `agents/cline-sdk/` — 16 فایل
- `agents/code-review/` — 2 فایل
- `agents/codebase-design/` — 4 فایل
- `agents/diagnosing-bugs/` — 3 فایل
- `agents/domain-modeling/` — 4 فایل
- `agents/find-skills/` — 1 فایل
- `agents/git-guardrails-claude-code/` — 3 فایل
- `agents/grill-me/` — 2 فایل
- `agents/grill-with-docs/` — 2 فایل
- `agents/grilling/` — 2 فایل
- `agents/handoff/` — 2 فایل
- `agents/implement/` — 2 فایل
- `agents/implement-spec/` — 2 فایل
- `agents/improve-codebase-architecture/` — 3 فایل
- `agents/landing-page-design/` — 1 فایل
- `agents/loop-me/` — 2 فایل
- `agents/migrate-to-shoehorn/` — 2 فایل
- `agents/pr/` — 3 فایل
- `agents/prototype/` — 4 فایل
- `agents/research/` — 2 فایل
- `agents/retro/` — 2 فایل
- `agents/review-team/` — 12 فایل
- `agents/scaffold-exercises/` — 2 فایل
- `agents/searching-sourcegraph/` — 8 فایل
- `agents/setup-matt-pocock-skills/` — 7 فایل
- `agents/setup-pre-commit/` — 2 فایل
- `agents/setup-ts-deep-modules/` — 3 فایل
- `agents/tdd/` — 4 فایل
- `agents/teach/` — 6 فایل
- `agents/to-questionnaire/` — 2 فایل
- `agents/to-spec/` — 2 فایل
- `agents/to-tickets/` — 2 فایل
- `agents/triage/` — 4 فایل
- `agents/unslop/` — 14 فایل
- `agents/wait-what/` — 2 فایل
- `agents/wayfinder/` — 2 فایل
- `agents/web-design-guidelines/` — 1 فایل
- `agents/wizard/` — 3 فایل
- `agents/writing-beats/` — 2 فایل
- `agents/writing-for-agents/` — 3 فایل
- `agents/writing-fragments/` — 2 فایل
- `agents/writing-shape/` — 2 فایل

## ~/.qoder/skills — اسکیل‌های سراسریِ Qoder (13)

- `qoder/bors-dual-jev-verification/` — 1 فایل
- `qoder/bors-jev-verification/` — 1 فایل
- `qoder/content-humanizer/` — 6 فایل
- `qoder/diagram-design/` — 290 فایل
- `qoder/drafter/` — 2 فایل
- `qoder/figma/` — 2 فایل
- `qoder/figma-design-analyzer/` — 10 فایل
- `qoder/frontend-agent/` — 3 فایل
- `qoder/image-ocr/` — 1 فایل
- `qoder/microsoft-foundry/` — 221 فایل
- `qoder/multi-agent-workflow/` — 4 فایل
- `qoder/pdf-to-word/` — 4 فایل
- `qoder/product-design/` — 2 فایل

## ~/.qoder/plugins/cache/qoder-marketplace — اسکیل‌های افزونه‌های نصب‌شده (58)

- `plugins/a11y-debugging/` — 2 فایل
- `plugins/accessibility-review/` — 3 فایل
- `plugins/agent-browser/` — 1 فایل
- `plugins/agentcore/` — 1 فایل
- `plugins/architecture-communicator/` — 2 فایل
- `plugins/architecture-health/` — 3 فایل
- `plugins/audit/` — 1 فایل
- `plugins/banner-design/` — 2 فایل
- `plugins/better-harness/` — 14 فایل
- `plugins/brainstorming/` — 8 فایل
- `plugins/brand/` — 17 فایل
- `plugins/c4model/` — 2 فایل
- `plugins/chrome-devtools/` — 1 فایل
- `plugins/chrome-devtools-cli/` — 2 فایل
- `plugins/component-library-alignment/` — 3 فایل
- `plugins/context7-mcp/` — 1 فایل
- `plugins/cookie-debugging/` — 1 فایل
- `plugins/core/` — 12 فایل
- `plugins/debug-optimize-lcp/` — 5 فایل
- `plugins/dependency-impact-analyzer/` — 3 فایل
- `plugins/deployment-topology-analyzer/` — 2 فایل
- `plugins/design/` — 35 فایل
- `plugins/design-debt-review/` — 3 فایل
- `plugins/design-md-review/` — 3 فایل
- `plugins/design-qa/` — 7 فایل
- `plugins/design-system/` — 26 فایل
- `plugins/design-system-capture/` — 3 فایل
- `plugins/dispatching-parallel-agents/` — 1 فایل
- `plugins/dogfood/` — 3 فایل
- `plugins/drawio/` — 1 فایل
- `plugins/electron/` — 1 فایل
- `plugins/evolution-planner/` — 3 فایل
- `plugins/excel/` — 13 فایل
- `plugins/explore/` — 1 فایل
- `plugins/finishing-a-development-branch/` — 1 فایل
- `plugins/flow-visualizer/` — 4 فایل
- `plugins/graphviz/` — 2 فایل
- `plugins/init/` — 1 فایل
- `plugins/legacy-system-visualizer/` — 2 فایل
- `plugins/memory-leak-debugging/` — 2 فایل
- `plugins/mobile-use/` — 17 فایل
- `plugins/pptx/` — 3 فایل
- `plugins/receiving-code-review/` — 1 فایل
- `plugins/requesting-code-review/` — 2 فایل
- `plugins/risk-quality-reviewer/` — 4 فایل
- `plugins/setup-mobile-use/` — 6 فایل
- `plugins/slack/` — 3 فایل
- `plugins/slides/` — 6 فایل
- `plugins/system-modeler/` — 3 فایل
- `plugins/tarot-pixel/` — 1 فایل
- `plugins/troubleshooting/` — 1 فایل
- `plugins/ui-alignment-review/` — 7 فایل
- `plugins/ui-styling/` — 16 فایل
- `plugins/ui-ux-pro-max/` — 35 فایل
- `plugins/using-superpowers/` — 7 فایل
- `plugins/vercel-sandbox/` — 1 فایل
- `plugins/visual-regression-review/` — 5 فایل
- `plugins/writing-skills/` — 7 فایل

## روی ماشینِ دوم چه کنیم

این پوشه یک آرشیو است، نه مقصدی که خودکار خوانده شود. برای فعال‌شدن، هر گروه را
به همان مسیرِ اصلی‌اش برگردانید:

```
cp -r agent-skills/agents/*  ~/.agents/skills/
cp -r agent-skills/qoder/*   ~/.qoder/skills/
# افزونه‌ها بهتر است از مارکت‌پلیس دوباره نصب شوند تا نسخۀ ثبت‌شده‌شان دستکاری نشود
```

اسکیل‌های گروهِ `plugins` از بستۀ همان افزونه‌هاست؛ نصبِ دوباره‌شان از مارکت‌پلیس
نسخه‌های وابسته (اسکریپت‌ها و دارایی‌ها) را هم می‌آورد، چیزی که این کپی ندارد.
