import { Link, useNavigate, useSearchParams } from 'react-router';
import { useMemo } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useFtsFunnel } from '../api/useFtsFunnel';
import {
  activeIdsForPreset,
  buildFtsChartModel,
  descendantsOf,
  ZONES,
  ZONE_BY_KEY,
  type FtsPreset,
  type FtsZone,
} from '../lib/ftsChartModel';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import { StrategyTreeStepper, treeStagePath } from './StrategyTreeStepper';

const ORDER: FtsZone[] = ['S', 'T', 'F', 'M'];
const PRESETS = [
  { key: 'swing' as const, label: 'نوسان‌گیر' },
  { key: 'trend' as const, label: 'روندگیر' },
  { key: 'hourglass' as const, label: 'ساعت شنی' },
];

const TONE: Record<FtsZone, { border: string; text: string; soft: string }> = {
  S: { border: 'border-amber-500/40', text: 'text-amber-400', soft: 'bg-amber-500/8' },
  T: { border: 'border-sky-500/40', text: 'text-sky-400', soft: 'bg-sky-500/8' },
  F: { border: 'border-emerald-500/40', text: 'text-emerald-400', soft: 'bg-emerald-500/8' },
  M: { border: 'border-rose-500/40', text: 'text-rose-400', soft: 'bg-rose-500/8' },
};

function presetFromQuery(value: string | null, fallback: FtsPreset): FtsPreset {
  return value === 'swing' || value === 'trend' || value === 'hourglass' || value === 'custom' ? value : fallback;
}

function leafCount(model: ReturnType<typeof buildFtsChartModel>, id: string) {
  return descendantsOf(model, id).filter((n) => model.byId.get(n)?.kind === 'leaf').length;
}

function SymbolPhase({ zone, label }: { zone: FtsZone; label?: string }) {
  if (!label) return <span className="text-3xs text-text-muted">وضعیت نماد: —</span>;
  return <span className={`rounded-lg border ${TONE[zone].border} ${TONE[zone].soft} px-2 py-1 text-3xs font-black ${TONE[zone].text}`}>{label}</span>;
}

export default function StrategyTreeOverview() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const horizon = useStrategyStore((s) => s.horizon);
  const storedSymbol = useSymbolStore((s) => s.symbol);
  const symbol = params.get('symbol') || storedSymbol;
  const strategyParams = useStrategyParamsStore((s) => s.params);
  const preset = presetFromQuery(params.get('preset'), horizon);
  const model = useMemo(() => buildFtsChartModel(strategyParams), [strategyParams]);
  const active = useMemo(() => activeIdsForPreset(preset, model), [preset, model]);
  const { funnel } = useFtsFunnel(preset);

  const candidate = useMemo(() => {
    if (!symbol) return null;
    const all = [
      ...funnel.stages.tape.entries,
      ...funnel.stages.technical.entries,
      ...funnel.stages.fundamental.entries,
      ...funnel.stages.handover.entries,
    ];
    return all.find((c) => c.symbol === symbol) ?? null;
  }, [funnel, symbol]);

  const phaseLabel = (zone: FtsZone) => {
    if (!candidate) return undefined;
    const key = zone === 'S' ? 'tape' : zone === 'T' ? 'technical' : zone === 'F' ? 'fundamental' : 'handover';
    const status = candidate.status[key];
    return `${status === 'pass' ? 'تأیید' : status === 'reject' ? 'رد' : status === 'pending' ? 'در انتظار' : 'بی‌داده'}`;
  };

  return (
    <div className="flex w-full flex-col gap-4" data-testid="strategy-tree-overview">
      <section className="rounded-3xl border border-border-c bg-bg-card/85 p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl">
            <div className="text-3xs font-black uppercase tracking-[0.18em] text-accent-blue">FTS · Strategy Roadmap</div>
            <h1 className="mt-1 text-xl font-black text-text-primary sm:text-2xl">درخت استراتژی FTS</h1>
            <p className="mt-2 text-xs leading-6 text-text-secondary">
              هر چهار صفحهٔ جزوه در یک نقشهٔ ساده دیده می‌شوند؛ مسیر فعلی روشن است و مسیرهای انتخاب‌نشده عمداً کم‌رنگ می‌مانند.
              برای دیدن جزئیات کامل هر صفحه، روی همان مرحله بروید.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <Link
                key={p.key}
                to="/strategy-tree"
                onClick={(e) => { e.preventDefault(); navigate(`/strategy-tree?preset=${p.key}${symbol ? `&symbol=${encodeURIComponent(symbol)}` : ''}`); }}
                className={preset === p.key ? 'rounded-xl border border-accent-blue/50 bg-accent-blue/10 px-3 py-2 text-2xs font-black text-accent-blue' : 'rounded-xl border border-border-c bg-bg-primary px-3 py-2 text-2xs font-bold text-text-muted hover:text-text-primary'}
              >
                {p.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="mt-5">
          <StrategyTreeStepper active={null} preset={preset} symbol={symbol || null} />
        </div>

        <div className="mt-4 flex flex-wrap gap-3 text-2xs text-text-muted">
          <span>مسیر انتخابی: <b className="text-text-primary">{PRESETS.find((p) => p.key === preset)?.label ?? 'سفارشی'}</b></span>
          {symbol ? <span>نماد فعال: <b className="text-accent-blue">{symbol}</b></span> : <span>نماد فعال انتخاب نشده</span>}
          <span>ترتیب جریان: <b className="text-text-primary">S → T → F → M</b></span>
        </div>
      </section>

      <section className="grid gap-3 xl:grid-cols-4" data-testid="strategy-roadmap-zones">
        {ORDER.map((zone) => {
          const meta = ZONE_BY_KEY[zone];
          const root = model.byId.get(model.roots[zone]);
          const children = root ? model.childrenOf.get(root.id) ?? [] : [];
          const tone = TONE[zone];
          const activeLeaves = children.reduce((sum, id) => sum + (active.has(id) ? 1 : 0), 0);
          return (
            <Link
              key={zone}
              to={treeStagePath(zone, preset, symbol || null)}
              className={`group flex min-h-[410px] flex-col rounded-3xl border ${tone.border} ${tone.soft} p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className={`text-3xs font-black uppercase tracking-[0.18em] ${tone.text}`}>{meta.page}</div>
                  <h2 className="mt-1 text-base font-black text-text-primary">{meta.title}</h2>
                  <div className="mt-1 text-3xs text-text-muted">{meta.sub}</div>
                </div>
                <div className={`rounded-xl border ${tone.border} px-2 py-1 text-xs font-black ${tone.text}`}>{zone}</div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-2 rounded-2xl border border-border-c bg-bg-card/55 px-3 py-2">
                <div>
                  <div className="text-3xs text-text-muted">وضعیت نماد</div>
                  <div className={`mt-0.5 text-xs font-black ${tone.text}`}>{phaseLabel(zone) ?? 'نمای کلی'}</div>
                </div>
                <div className="text-end">
                  <div className="text-3xs text-text-muted">شاخه‌های پیش رو</div>
                  <div className="mt-0.5 text-sm font-black num text-text-primary">{toFaDigits(children.length)}</div>
                </div>
              </div>

              <div className="mt-3 flex-1 space-y-2">
                {children.map((id) => {
                  const node = model.byId.get(id);
                  if (!node) return null;
                  const onPath = active.has(id);
                  const leaves = leafCount(model, id);
                  const isBranchOfSymbol = zone === 'T' && candidate && (
                    (candidate.trendD === 'up' && id === 't_daily_up') ||
                    (candidate.trendD === 'down' && id === 't_daily_down') ||
                    (candidate.trendD === 'range' && id === 't_daily_neutral')
                  );
                  return (
                    <div
                      key={id}
                      className={`rounded-2xl border p-2.5 transition-opacity ${onPath || isBranchOfSymbol ? 'border-border-accent bg-bg-card/80 opacity-100' : 'border-border-c/70 bg-bg-primary/20 opacity-38'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-2xs font-black text-text-primary">{node.label}</span>
                        <span className="text-3xs text-text-muted">{leaves ? `${toFaDigits(leaves)} مسیر داخلی` : 'گره'}</span>
                      </div>
                      <div className="mt-1 text-3xs leading-5 text-text-muted line-clamp-2">{node.description}</div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-3 flex items-center justify-between border-t border-border-c/50 pt-3 text-3xs">
                <SymbolPhase zone={zone} label={phaseLabel(zone)} />
                <span className={`${tone.text} font-black`}>{toFaDigits(activeLeaves)} شاخه روی مسیر</span>
              </div>
            </Link>
          );
        })}
      </section>

      {candidate?.trendD ? (
        <section className="rounded-3xl border border-accent-blue/30 bg-accent-blue/5 p-4 sm:p-5" data-testid="strategy-current-path">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-3xs font-black uppercase tracking-[0.18em] text-accent-blue">مسیر فعلی نماد</div>
              <div className="mt-1 text-sm font-black text-text-primary">
                هفتگی: {candidate.trendW || '—'} ← روزانه: {candidate.trendD}
              </div>
            </div>
            <div className="text-2xs font-bold text-text-secondary">شاخه روزانه: {candidate.dailyStrategy || '—'}</div>
          </div>
        </section>
      ) : null}

      <div className="flex justify-end">
        <span className="text-3xs text-text-muted">روی هر کارت = صفحهٔ کامل همان بخش با همهٔ شاخه‌ها و قوانین</span>
      </div>
    </div>
  );
}
