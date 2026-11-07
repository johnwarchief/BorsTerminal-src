# Critic run 2026-11-05 — پروفایل بنیادیِ هر نماد، از نگاهِ یک کاربر

## Scope
`fundamental` only. Chart/FTS technical layers are out of scope (next mission phase).

## Live environment (already running — do not start or kill servers)
- App: `http://localhost:7093/#` (hash router). Table: `#/fundamental`. Symbol profile:
  `#/fundamental/<symbol>` (URL-encode the Persian symbol).
- Static dist server proxies `/api` to `127.0.0.1:8110` (the backend of this checkout,
  started with `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data`; universe = 783 rows).
- Browser: Edge via `playwright-core` from `D:/BorsTerminal-tmp/s4b-browser`
  (`require('playwright-core')`, executablePath `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`,
  headless, viewport 1366×768, locale `fa-IR`, timezone `Asia/Tehran`).
  Harnesses to imitate: `p1b-acceptance.js` (measured px + panel text + screenshots).
- Verify the served build is THIS checkout before capturing anything: the profile must contain
  `[data-testid="eps-growth-chart"]`, the axis-4 label «پتانسیل سود تا آخر سال» and
  `[data-fund-surface]` must be absent (count 0). If not, stop and report the mismatch.

## Symbols to critique (one profile each, all five axis panels)
| symbol | why it is in the cohort |
|---|---|
| رنيك | خدماتی؛ ۱ب غیرقابل‌اعمال (نمونۀ صریحِ مالک) |
| فولاد | تولیدی/صادراتی؛ ۱الف قبول و ۱ب رد |
| ختور | خودرو — نرخ‌گذاری دستوریِ اجباری (شاخص ۵) |
| ناما | قطعات خودرو — شاخص ۵ با طبقهٔ متفاوت |
| بفجر | نیروگاه — شاخص ۵ اجباری |
| پاسا | لاستیک — شاخص ۵ اجباری |
| البرز | بیمه — وتوی شاخص ۵ |
| دزهراوي | دارو — معافیت/باند حاشیه |
| كوچين | غذا — آزاد/خنثی |
| آلومينا | بخش آزاد، امتیاز ۵، مسیر پذیرش ۴ از فروش÷ارزش |
| وسبحان | سرمایه‌گذاری — فروش نامعطّل/هلدینگ |
| وكار | بانک — ۱ب بی‌نظر، EPS و حاشیه با معنایِ خاص |
| فاهواز | شکافِ دادهٔ ۱ب — «بی‌نظر/نامشخص» در برابر «رد» |

For at least رنيك، فولاد، آلومينا capture both themes (`[data-testid="theme-brass"]`,
`[data-testid="theme-warm"]`) and both densities (`compact`/`comfortable`) of the table row.

## Questions the user must be able to answer from each profile (rubric)
1. Rule + threshold for each of the five indicators, on-screen.
2. This period's and the previous comparable period's inputs (for رشد: فروش جاری و قبل).
3. Computed value and distance to threshold (کف/هدف).
4. Verdict and **why** — with «سنجیده‌نشده/شکاف داده» clearly separate from «رد».
5. EPS: each period's EPS, the absolute change and the percentage change, plus the chart.
6. ۱الف و ۱ب separately, whether ۱ب applies, and the combined verdict.
7. Indicator 4: the headline is the final potential-profit percentage, with sales/market-cap as witnesses.
8. Indicator 5: the pricing regime and the sector rule, and what it does to the verdict.
9. Theme follows the app; status readable in both themes; charts legible (bars must show proportion).

## Evidence rules (non-negotiable)
- Every finding: `id | severity(Blocker/Major/Minor) | symbol | axis | source (booklet page or ruling)
  | expected | actual | evidence (screenshot path / DOM testid / API field) | user-voice sentence |
  suggested direction | confidence`.
- No invented rules or thresholds. Silent source → `AMBIGUOUS`, not a defect.
- Precedence: booklet/chart PDF → `docs/fts-notes/OWNER_RULINGS.md` → derived specs → transcripts.
- The booklet ledger from the 2026-11-04 run
  (`_audit/rebuild/fts-critic/2026-11-04/booklet-ledger.md`) is the baseline: verify it covers all
  34 booklet pages + 4 chart pages, re-read visually only the pages that carry F1–F5 rules, and say
  exactly which pages you re-read in the report. Do not claim full re-reading if you did not.
- No code changes. No push. Leave the repo clean except `_audit/rebuild/fts-critic/2026-11-05/`.

## Outputs (write them)
- `_audit/rebuild/fts-critic/2026-11-05/screenshots/` — per symbol and per axis panel, 1366×768.
- `_audit/rebuild/fts-critic/2026-11-05/evidence.json` — per symbol: API fields used, panel text,
  measured bar pixel heights, testids, theme, density, console errors.
- `_audit/rebuild/fts-critic/2026-11-05/report.md` — Persian, using
  `.agents/skills/fts-user-critic/references/report-template.md`: verdict paragraph, per-symbol
  scorecard for the five indicators, findings grouped by severity, owner-expectation checklist,
  source conflicts/ambiguities, prioritised P0/P1/P2 fix list with the smallest user-visible outcome,
  and what was tested vs not tested (with the commit SHA under test).
