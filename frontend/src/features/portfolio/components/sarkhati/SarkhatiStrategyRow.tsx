// features/portfolio/components/sarkhati/SarkhatiStrategyRow.tsx — انتخابِ مسیرِ
// اجرا، فقط با شواهدِ خودِ همان پروسه.
//
// قاعده‌ها:
//  • فقط dry-run از این ردیف اجرا می‌شود؛ ارسالِ زنده همچنان از درِ اصلی و با
//    گیت‌های تأیید/env می‌گذرد. هیچ دکمه‌ای «آماده برای پول» نشان داده نمی‌شود.
//  • p50/p95 فقط وقتی نمونهٔ کافی باشد نمایش داده می‌شود؛ نبودِ نمونه یعنی
//    «بدون نمونه»، نه صفر.
//  • Probe فقط ساختار (tag/name/aria/testid) را نشان می‌دهد، نه مقدارِ input.
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import {
  orderApi, useExecutionStrategies, type StrategyRowView,
} from '../../lib/orderClient';

function num(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? '—' : toFaDigits(v.toFixed(1));
}

const MODE_LABEL: Record<string, string> = {
  live: 'زنده', shadow: 'سایه', off: 'خاموش',
};

export function SarkhatiStrategyRow({ body, enabled }: {
  body: () => Record<string, unknown>;
  enabled: boolean;
}) {
  const q = useExecutionStrategies(enabled);
  const rows = q.data?.strategies ?? [];
  const [selected, setSelected] = useState('direct_api');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [prepared, setPrepared] = useState('');
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);

  const sel: StrategyRowView | undefined = useMemo(
    () => rows.find((r) => r.id === selected) ?? rows[0],
    [rows, selected]);
  const total = sel?.metrics?.total;
  const canDry = Boolean(sel?.available && sel?.configured && !busy);

  async function dryRun() {
    if (!sel) return;
    setBusy(true);
    setNote('');
    setProbe(null);
    try {
      // dry-run فوری است: هدفِ زمان‌بندی‌شده و تأییدِ زنده را حذف می‌کنیم؛
      // شناسۀ تازه هم می‌گذاریم تا دو آزمونِ پیاپی به duplicate guard نخورند.
      const rest: Record<string, unknown> = { ...body() };
      delete rest.target_wall_ms;
      delete rest.one_way_ms;
      delete rest.margin_ms;
      delete rest.confirmed;
      delete rest.confirm_phrase;
      const base = String(rest.execution_id ?? 'dry');
      const pr = await orderApi.strategyPrepare({
        ...rest,
        execution_id: `${base}-dry-${Date.now().toString(36)}`,
        strategy: sel.id,
        live_intent: false,
      });
      if (String(pr.status) !== 'success') {
        setNote(`آماده‌سازی رد شد: ${String(pr.code ?? '')} ${String(pr.detail ?? '')}`.trim());
        return;
      }
      const pid = String(pr.prepared_id ?? '');
      setPrepared(pid);
      const tr = await orderApi.strategyTrigger({ prepared_id: pid });
      if (String(tr.status) !== 'success') {
        setNote(`اجرا رد شد: ${String(tr.code ?? '')} ${String(tr.detail ?? '')}`.trim());
        return;
      }
      const result = (tr.result ?? {}) as Record<string, unknown>;
      const timings = (result.timings ?? {}) as Record<string, unknown>;
      setNote(`dry-run: ${String(result.status ?? '?')} · action ${num(Number(timings.action ?? NaN))}ms`
        + ` · send ${num(Number(timings.send ?? NaN))}ms · POST واقعی: صفر`);
    } catch (e) {
      setNote(`خطا: ${e instanceof Error ? e.message.slice(0, 120) : 'نامعلوم'}`);
    } finally {
      setBusy(false);
    }
  }

  async function abort() {
    if (!prepared) return;
    try {
      await orderApi.strategyAbort(prepared);
      setNote('آماده‌سازی لغو شد.');
      setPrepared('');
    } catch (e) {
      setNote(`لغو نشد: ${e instanceof Error ? e.message.slice(0, 100) : 'نامعلوم'}`);
    }
  }

  async function doProbe() {
    if (!sel) return;
    setBusy(true);
    setNote('');
    try {
      const res = await orderApi.strategyProbe(sel.id);
      if (String(res.status) !== 'success') {
        setNote(`Probe نشد: ${String(res.code ?? '')} ${String(res.detail ?? '')}`.trim());
        return;
      }
      setProbe((res.probe ?? {}) as Record<string, unknown>);
      setNote('ساختار صفحه خوانده شد؛ هیچ مقدارِ input نمایش داده نمی‌شود.');
    } catch (e) {
      setNote(`Probe نشد: ${e instanceof Error ? e.message.slice(0, 120) : 'نامعلوم'}`);
    } finally {
      setBusy(false);
    }
  }

  if (!enabled) return null;
  return (
    <div className="mt-1 border-t border-border-c/60 pt-1" data-testid="sarkhati-strategy-row">
      <div className="flex flex-wrap items-center gap-1 text-3xs">
        <span className="font-bold text-text-muted">مسیرِ اجرا:</span>
        <select
          value={sel?.id ?? ''}
          onChange={(e) => { setSelected(e.target.value); setNote(''); setProbe(null); }}
          data-testid="sarkhati-strategy-select"
          className="max-w-[10rem] rounded-lg border border-border-c bg-bg-primary px-1 py-0.5 text-3xs font-bold text-text-primary"
        >
          {rows.map((r) => (
            <option key={r.id} value={r.id} disabled={!r.available}>
              {r.label}{r.available ? '' : ' (ناموجود)'}
            </option>
          ))}
        </select>
        <span className="num text-text-muted" data-testid="sarkhati-strategy-metrics">
          {total && total.count > 0
            ? `p50 ${num(total.p50)} · p95 ${num(total.p95)} · n=${toFaDigits(total.count)}`
            : 'بدون نمونه'}
        </span>
        {sel ? (
          <span className="text-text-muted" data-testid="sarkhati-strategy-mode">
            {MODE_LABEL[sel.settings.mode] ?? sel.settings.mode}
            {sel.live_ready ? ' · آمادهٔ زنده' : ''}
          </span>
        ) : null}
        {sel && !sel.configured && sel.requires_browser ? (
          <span className="text-accent-yellow" data-testid="sarkhati-strategy-needs-config">
            selector پیکربندی نشده
          </span>
        ) : null}
        <button type="button" onClick={() => void dryRun()} disabled={!canDry}
          data-testid="sarkhati-strategy-dryrun"
          className={`rounded-lg border px-2 py-0.5 text-3xs font-bold ${
            canDry ? 'border-accent-blue/40 text-accent-blue hover:bg-accent-blue/10'
              : 'cursor-not-allowed border-border-c/60 text-text-muted/60'}`}>
          {busy ? 'در حال اجرا…' : 'آماده‌سازی + dry-run'}
        </button>
        {prepared ? (
          <button type="button" onClick={() => void abort()}
            data-testid="sarkhati-strategy-abort"
            className="rounded-lg border border-accent-red/40 px-2 py-0.5 text-3xs font-bold text-accent-red">
            لغو
          </button>
        ) : null}
        {sel?.requires_browser ? (
          <button type="button" onClick={() => void doProbe()} disabled={busy}
            data-testid="sarkhati-strategy-probe"
            className="rounded-lg border border-border-c px-2 py-0.5 text-3xs text-text-secondary hover:bg-bg-card">
            Probe
          </button>
        ) : null}
        {sel && sel.id !== 'direct_api' ? (
          <span className="text-text-muted">ارسالِ زندهٔ این مسیر در رابط فعال نیست</span>
        ) : null}
      </div>
      {note ? (
        <div className="mt-0.5 text-3xs text-text-muted" data-testid="sarkhati-strategy-note">
          {note}
        </div>
      ) : null}
      {probe ? (
        <details className="mt-0.5 text-3xs text-text-secondary" data-testid="sarkhati-strategy-probe-details">
          <summary className="cursor-pointer text-text-muted">ساختارِ صفحه (بی‌مقدار)</summary>
          <pre className="mt-0.5 max-h-32 overflow-auto rounded border border-border-c/60 bg-bg-primary p-1 text-3xs">
            {JSON.stringify(probe, null, 1).slice(0, 4000)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
