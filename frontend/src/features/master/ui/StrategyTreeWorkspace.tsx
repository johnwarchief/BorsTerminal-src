// features/master/ui/StrategyTreeWorkspace.tsx — پنج صفحهٔ درخت استراتژی
//
// صفحهٔ ۱..۴ = همان چهار چارتِ چاپی FTS (F/T/S/M) و صفحهٔ ۵ = نقشهٔ جامع. داده
// فقط از `ftsChartModel` می‌آید؛ این فایل هیچ گره/قاعده/یال نمی‌سازد.
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useFunnelRegistry } from '../api/useFunnelRegistry';
import {
  activeIdsForPreset, buildFtsChartModel, ZONE_BY_KEY,
  type FtsZone,
} from '../lib/ftsChartModel';
import { useActiveFunnelPreset } from '../lib/useActiveFunnelPreset';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import { StrategyChartCanvas } from '../components/StrategyChartCanvas';
import {
  StrategyTreeStepper, TREE_MASTER, TREE_STAGES, treeStagePath, type TreePage,
} from './StrategyTreeStepper';

const PRESETS = [
  { key: 'swing' as const, label: 'نوسان‌گیر' },
  { key: 'trend' as const, label: 'روندگیر' },
  { key: 'hourglass' as const, label: 'ساعت شنی' },
];

const ZONE_ORDER: FtsZone[] = ['S', 'T', 'F', 'M'];

function asPage(raw: string | null): TreePage {
  return raw === 'F' || raw === 'T' || raw === 'S' || raw === 'M' ? raw : 'master';
}

export default function StrategyTreeWorkspace() {
  const [params, setParams] = useSearchParams();
  const page = asPage(params.get('page'));
  const horizon = useStrategyStore((s) => s.horizon);
  const storedSymbol = useSymbolStore((s) => s.symbol);
  const symbol = params.get('symbol') || storedSymbol || '';
  const preset = useActiveFunnelPreset(horizon);
  const strategyParams = useStrategyParamsStore((s) => s.params);
  const { hourglass } = useFunnelRegistry();
  const [focus, setFocus] = useState<FtsZone | null>(null);

  const model = useMemo(
    () => buildFtsChartModel(strategyParams, {
      rsiPeriod: hourglass?.hourglass_rsi_period ?? null,
      oversoldLevel: hourglass?.hourglass_rsi_oversold ?? null,
    }),
    [strategyParams, hourglass],
  );
  const active = useMemo(() => activeIdsForPreset(preset, model), [preset, model]);

  const rawNode = params.get('node');
  const candidate = rawNode ? model.byId.get(rawNode) : undefined;
  const selected = candidate && (page === 'master' || candidate.zone === page) ? candidate : null;

  useEffect(() => { setFocus(null); }, [page]);

  const select = (id: string | null) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (id) next.set('node', id); else next.delete('node');
      return next;
    }, { replace: true });
  };

  const zone = page === 'master' ? undefined : page;
  const meta = zone ? ZONE_BY_KEY[zone] : null;
  const root = zone ? model.byId.get(model.roots[zone]) : null;

  return (
    <div className="flex w-full flex-col gap-2" dir="rtl" data-testid="strategy-tree-workspace" data-page={page}>
      <StrategyTreeStepper active={page} preset={preset} symbol={symbol || null}
        node={selected?.id ?? null} />

      <section className="rounded-2xl border border-border-c bg-bg-card/70 px-3 py-2">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="text-3xs font-black uppercase tracking-[0.18em] text-accent-blue">
              FTS · {page === 'master' ? 'Master Strategy Map' : `Chart ${zone} · Page ${meta?.page}`}
            </div>
            <h1 className="mt-0.5 text-lg font-black text-text-primary">
              {page === 'master' ? TREE_MASTER.title : meta?.title}
            </h1>
            <p className="mt-1 max-w-5xl text-2xs leading-5 text-text-secondary">
              {page === 'master'
                ? 'چهار چارت اصلی FTS در یک بومِ پیوسته؛ یال‌های بین‌چارت فقط همان سه وابستگیِ اعلام‌شدهٔ چارت ۴ هستند (S→T→F→M). شاخه‌های هر چارت با «+N» باز می‌شوند؛ هیچ گره یا قاعده‌ای ساخته نشده است.'
                : root?.description ?? meta?.sub}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1" role="group" aria-label="پرستِ فعال">
            {PRESETS.map((p) => (
              <Link key={p.key}
                to={treeStagePath(page, p.key, symbol || null, selected?.id ?? null)}
                aria-current={preset === p.key ? 'true' : undefined}
                className={preset === p.key
                  ? 'rounded-lg border border-accent-blue/60 bg-accent-blue/15 px-2 py-1 text-2xs font-black text-accent-blue'
                  : 'rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-2xs font-bold text-text-muted hover:text-text-primary'}>
                {p.label}
              </Link>
            ))}
            {!PRESETS.some((p) => p.key === preset) ? (
              <span className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-text-muted">سفارشی</span>
            ) : null}
          </div>
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-3xs text-text-muted">
          <span>جریان مستند: <b className="text-text-primary">S → T → F → M</b></span>
          <span>نماد فعال: <b className="text-accent-blue">{symbol || 'انتخاب نشده'}</b></span>
          {page === 'master'
            ? ZONE_ORDER.map((z) => (
              <span key={z} data-testid={`strategy-zone-count-${z}`}>
                <b className={z === 'F' ? 'text-emerald-400' : z === 'T' ? 'text-sky-400' : z === 'S' ? 'text-amber-400' : 'text-rose-400'}>
                  {z}
                </b>{' '}
                <span className="num">{toFaDigits(model.byZone[z].length)}</span> گره
              </span>
            ))
            : <span><span className="num">{toFaDigits(model.byZone[zone as FtsZone].length)}</span> گره در این چارت</span>}
        </div>
      </section>

      <div className="grid min-w-0 gap-2 xl:grid-cols-[minmax(0,1fr)_310px]">
        <StrategyChartCanvas
          model={model}
          mode={page === 'master' ? 'master' : 'zone'}
          zone={zone}
          focus={focus}
          onFocusChange={setFocus}
          activeIds={active}
          selectedId={selected?.id ?? null}
          onSelect={select}
        />

        <aside className="min-w-0 rounded-2xl border border-border-c bg-bg-card/55 p-2.5">
          {selected ? (
            <div data-testid="strategy-node-detail" className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-1">
                <span className="rounded-md border border-border-c px-1.5 py-0.5 text-3xs font-black text-text-secondary">
                  {selected.zone} · {selected.page}
                </span>
                <span className="text-3xs text-text-muted">{selected.origin === 'chart' ? 'قاعدهٔ چارت' : 'منطق برنامه'}</span>
              </div>
              <h2 className="text-sm font-black text-text-primary">{selected.label}</h2>
              <p className="text-3xs leading-4 text-text-muted">{selected.fullTitle}</p>
              <p className="text-2xs leading-5 text-text-secondary">{selected.description}</p>
              {selected.ruleFormula ? (
                <code className="rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-3xs text-text-secondary">
                  {selected.ruleFormula}
                </code>
              ) : null}
              <div className="text-3xs text-text-muted">نشان: {selected.badge}</div>
              {selected.refs.length ? (
                <div className="border-t border-border-c/60 pt-1.5">
                  <div className="text-3xs font-black text-text-muted">هم‌زادِ مفهومی در چارت‌های دیگر</div>
                  <div className="mt-1 flex flex-col gap-1">
                    {selected.refs.map((r) => {
                      const ref = model.byId.get(r);
                      if (!ref) return null;
                      return page === 'master' ? (
                        <button key={r} type="button" onClick={() => select(r)}
                          className="rounded-md border border-dashed border-border-c px-1.5 py-0.5 text-start text-3xs text-text-secondary hover:text-accent-blue">
                          {ref.zone} · {ref.label}
                        </button>
                      ) : (
                        <Link key={r} to={treeStagePath(ref.zone, preset, symbol || null, r)}
                          className="rounded-md border border-dashed border-border-c px-1.5 py-0.5 text-3xs text-text-secondary hover:text-accent-blue">
                          {ref.zone} · {ref.label}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-1 border-t border-border-c/60 pt-1.5">
                <Link to={treeStagePath(selected.zone, preset, symbol || null, selected.id)}
                  className="rounded-lg border border-accent-blue/50 bg-accent-blue/10 px-2 py-1 text-2xs font-black text-accent-blue">
                  بازکردن در چارتِ مستقل
                </Link>
                {page === 'master' ? (
                  <button type="button" onClick={() => setFocus(selected.zone)}
                    className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-text-secondary hover:text-text-primary">
                    تمرکز روی {selected.zone}
                  </button>
                ) : null}
                <button type="button" onClick={() => select(null)}
                  className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-text-muted">
                  بستن
                </button>
              </div>
            </div>
          ) : (
            <div data-testid="strategy-chart-guide" className="flex flex-col gap-1.5">
              <h2 className="text-sm font-black text-text-primary">راهنمای نقشه</h2>
              <p className="text-2xs leading-5 text-text-muted">
                روی هر گره بزنید تا متن، قاعده، منبع و هم‌زادهایش را ببینید. کشیدن بوم جابه‌جا می‌کند و چرخ ماوس بزرگ‌نمایی.
              </p>
              <div className="mt-1 flex flex-col gap-1">
                {TREE_STAGES.map((s) => (
                  <Link key={s.zone} to={treeStagePath(s.zone, preset, symbol || null)}
                    className="flex items-center justify-between rounded-lg border border-border-c px-2 py-1 text-2xs text-text-secondary hover:border-accent-blue/40 hover:text-accent-blue">
                    <span>{s.short} · {s.title}</span>
                    <span className="text-3xs text-text-muted">{s.page} · {toFaDigits(model.byZone[s.zone].length)} گره</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
