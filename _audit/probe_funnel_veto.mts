// _audit/probe_funnel_veto.mts -- اثباتِ زندهٔ وتوی مجمع با دادهٔ واقعی (#53)
// شش نمادِ وتوشدۀ همین تقویم همه صندوق‌اند و جدولِ بنیادی صندوق را با دروازۀ
// نوعِ دارایی حذف می‌کند؛ اما قیفِ «استراتژی FTS» آن دروازۀ را ندارد، پس همان
// ردیف‌های واقعی باید اینجا بجِ قرمز بگیرند و از مرحلۀ «تحویل» بیرون بیفتند.
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1200 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));

// مرجعِ بیرونی: خودِ بک‌اند کدام‌ها را وتو کرده و با چه دلیلی؟
const api = await (await p.request.get('http://127.0.0.1:8002/api/screener')).json();
const vetoed = (api.data ?? []).filter((r: { assembly_veto?: boolean }) => r.assembly_veto === true);

await p.goto('http://127.0.0.1:8002/#/master', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(45000);

const dom = await p.evaluate((syms: string[]) => {
  const stages = [...document.querySelectorAll('[data-testid^="funnel-stage-"]')] as HTMLElement[];
  const out: Record<string, unknown> = { stage_rows: {}, chips: [], in_handover: [], badge_text: null };
  for (const st of stages) {
    const key = st.getAttribute('data-testid')!.replace('funnel-stage-', '');
    out.stage_rows[key] = st.querySelectorAll('tbody tr[data-fkey]').length;
  }
  const handover = stages.find((s) => s.getAttribute('data-testid') === 'funnel-stage-handover');
  const handKeys = handover ? [...handover.querySelectorAll('tbody tr[data-fkey]')].map((tr) => tr.getAttribute('data-fkey')) : [];
  out.in_handover = handKeys;
  for (const s of syms) {
    const chip = document.querySelector(`[data-testid="funnel-assembly-veto-${CSS.escape(s)}"]`);
    if (chip) {
      const stage = chip.closest('[data-testid^="funnel-stage-"]')?.getAttribute('data-testid') ?? '?';
      out.chips = [...(out.chips as string[]), `${s}@${stage}`];
      out.badge_text = chip.textContent;
      out.badge_title = (chip as HTMLElement).getAttribute('title');
      out.badge_color = getComputedStyle(chip as HTMLElement).color;
    }
  }
  return out;
}, vetoed.map((r: { symbol: string }) => r.symbol));

await p.screenshot({ path: '_audit/funnel_veto_live.png' });
console.log(
  JSON.stringify(
    {
      backend_vetoed: vetoed.map((r: { symbol: string; assembly_days?: number; assembly_reason?: string; watchlist?: boolean; excluded?: boolean }) => ({
        s: r.symbol,
        days: r.assembly_days,
        why: r.assembly_reason ?? null,
        watchlist: r.watchlist,
        excluded: r.excluded,
      })),
      dom,
    },
    null,
    1,
  ),
);
await b.close();
