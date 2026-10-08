// features/master/ui/FtsCustomChainBuilder.tsx — زنجیرۀ ترتیبیِ Custom درِ همان workspace
//
// چرا این‌جا و نه در صفحۀ دیگر: رأیِ مالک (§۲۹ مأموریت) «Custom Builder باید
// همان‌جا یا در یک drawer سبک باز شود؛ صفحهٔ جدید نساز. Table باید همچنان بخش
// اصلی صفحه باشد». پس این خط زیرِ دکمه‌هایِ سیستم می‌نشیند و جدول دست‌نخورده
// بزرگ می‌ماند.
//
// این فایل هیچ داوری‌ای ندارد: فیلترها را از `GET /api/funnel/registry` می‌خواند،
// ترتیب را به `funnelPrefsStore` می‌سپارد و شمارشِ هر گام را از خودِ
// `/api/funnel` نشان می‌دهد (۵۸۶۵ → ۱۲۱ → ۴). تغییرِ ترتیب یعنی تغییرِ همان
// شمارش‌ها — چیزی که اثباتِ عملیاتیِ «اشتراکِ ترتیبی» است، نه OR.
import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { useFunnelRegistry } from '../api/useFunnelRegistry';
import { useFunnelPrefsStore } from '../stores/funnelPrefsStore';
import type { StageStep } from '../lib/ftsFunnel';

const stepOf = (steps: StageStep[], id: string) => steps.find((s) => s.filter_id === id);

export default function FtsCustomChainBuilder() {
  const { filters, rulesetVersion, loading, error } = useFunnelRegistry();
  const chain = useFunnelPrefsStore((s) => s.chain);
  const addFilter = useFunnelPrefsStore((s) => s.addFilter);
  const removeFilter = useFunnelPrefsStore((s) => s.removeFilter);
  const moveFilter = useFunnelPrefsStore((s) => s.moveFilter);
  const resetToCanonical = useFunnelPrefsStore((s) => s.resetToCanonical);
  const savedChains = useFunnelPrefsStore((s) => s.savedChains);
  const saveChain = useFunnelPrefsStore((s) => s.saveChain);
  const loadChain = useFunnelPrefsStore((s) => s.loadChain);
  const deleteChain = useFunnelPrefsStore((s) => s.deleteChain);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const { funnel } = useFtsFunnel('custom');
  const steps = funnel.stages.tape.steps;
  const left = filters.filter((f) => !chain.includes(f.filter_id));

  return (
    <div
      className="flex flex-col gap-1 rounded-xl border border-border-c bg-bg-card/50 px-2 py-1.5"
      data-testid="funnel-custom-builder"
    >
      <div className="flex flex-wrap items-center gap-1.5" data-testid="funnel-chain-row">
        {chain.length === 0 ? (
          <span className="text-3xs text-text-muted" data-testid="funnel-chain-empty">
            {loading
              ? 'رجیستری در حالِ خواندن…'
              : error
                ? `رجیستری نرسید: ${error}`
                : 'زنجیره خالی است — تا انتخاب نکنید، قیف چیزی برای داوریِ تابلو ندارد.'}
          </span>
        ) : null}
        {chain.map((id, i) => {
          const f = filters.find((x) => x.filter_id === id);
          const st = stepOf(steps, id);
          return (
            <span
              key={id}
              data-testid={`funnel-chain-${id}`}
              className="flex items-center gap-1 rounded-lg border border-accent-blue/40 bg-accent-blue/10 px-1.5 py-0.5 text-2xs font-bold text-text-primary"
              title={f ? `${f.description ?? ''}\nمنبع: ${f.source_file ?? ''}#${f.source_hash ?? ''}\nفرمول: ${f.formula_version ?? ''}` : id}
            >
              <span className="num opacity-60">{toFaDigits(i + 1)}</span>
              <span className="truncate max-w-[16ch]">{f?.name ?? id}</span>
              {st ? (
                <span className="num text-3xs text-text-secondary" data-testid={`funnel-chain-count-${id}`}>
                  {toFaDigits(st.input_count)} ← {toFaDigits(st.matched_count)}
                </span>
              ) : null}
              <button
                type="button"
                aria-label="یک گام بالا"
                data-testid={`funnel-chain-up-${id}`}
                disabled={i === 0}
                onClick={() => moveFilter(i, i - 1)}
                className="px-0.5 text-text-muted hover:text-accent-blue disabled:opacity-30"
              >
                ↑
              </button>
              <button
                type="button"
                aria-label="یک گام پایین"
                data-testid={`funnel-chain-down-${id}`}
                disabled={i === chain.length - 1}
                onClick={() => moveFilter(i, i + 1)}
                className="px-0.5 text-text-muted hover:text-accent-blue disabled:opacity-30"
              >
                ↓
              </button>
              <button
                type="button"
                aria-label="حذف از زنجیره"
                data-testid={`funnel-chain-remove-${id}`}
                onClick={() => removeFilter(id)}
                className="px-0.5 text-text-muted hover:text-accent-red"
              >
                ×
              </button>
            </span>
          );
        })}

        <span className="relative">
          <button
            type="button"
            data-testid="funnel-chain-add"
            aria-expanded={adding}
            onClick={() => setAdding((v) => !v)}
            className="rounded-lg border border-dashed border-accent-blue/50 px-2 py-0.5 text-2xs font-bold text-accent-blue hover:bg-accent-blue/10"
          >
            + افزودن فیلتر
          </button>
          {adding ? (
            <div
              className="absolute z-30 mt-1 max-h-64 w-64 overflow-y-auto rounded-xl border border-border-c bg-bg-primary p-1 shadow-lg"
              data-testid="funnel-chain-menu"
              role="menu"
            >
              {left.length === 0 ? (
                <p className="px-2 py-1 text-3xs text-text-muted">همۀ فیلترهایِ رجیستری درِ زنجیره‌اند.</p>
              ) : null}
              {left.map((f) => (
                <button
                  key={f.filter_id}
                  type="button"
                  role="menuitem"
                  data-testid={`funnel-chain-pick-${f.filter_id}`}
                  title={`${f.description ?? ''}\nمنبع: ${f.source_file ?? ''}#${f.source_hash ?? ''}`}
                  onClick={() => { addFilter(f.filter_id); setAdding(false); }}
                  className="block w-full rounded-lg px-2 py-1 text-start text-2xs font-bold text-text-secondary hover:bg-bg-card hover:text-text-primary"
                >
                  {f.name}
                  <span className="num ms-1 text-3xs font-normal text-text-muted">
                    {toFaDigits((f.params ?? []).length)} پارامتر
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </span>

        <span className="ms-auto flex flex-wrap items-center gap-1">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="نامِ این زنجیره"
            aria-label="نامِ preset"
            data-testid="funnel-chain-name"
            className="w-28 rounded-lg border border-border-c bg-bg-card px-1.5 py-0.5 text-2xs text-text-primary placeholder:text-text-muted"
          />
          <button
            type="button"
            data-testid="funnel-chain-save"
            disabled={!chain.length || !name.trim()}
            onClick={() => { saveChain(name.trim(), rulesetVersion); setName(''); }}
            className="rounded-lg border border-border-c px-2 py-0.5 text-2xs font-bold text-text-secondary hover:border-accent-blue hover:text-accent-blue disabled:opacity-40"
          >
            ذخیره
          </button>
          {savedChains.length ? (
            <span className="flex flex-wrap items-center gap-1" data-testid="funnel-chain-saved">
              {savedChains.map((c) => (
                <span
                  key={c.id}
                  className="flex items-center gap-0.5 rounded-lg border border-border-c bg-bg-secondary/60 px-1.5 py-0.5 text-2xs font-bold text-text-secondary"
                  title={`بازخوانیِ ${c.chain.join(' → ')} · سخت‌گیریِ ${c.fundMode} · رجیستری ${c.registryVersion}`}
                >
                  <button
                    type="button"
                    data-testid={`funnel-chain-load-${c.name}`}
                    onClick={() => loadChain(c.id)}
                    className="hover:text-accent-blue"
                  >
                    {c.name}
                    <span className="num ms-1 opacity-60">{toFaDigits(c.chain.length)}</span>
                  </button>
                  <button
                    type="button"
                    aria-label={`حذفِ ${c.name}`}
                    data-testid={`funnel-chain-delete-${c.id}`}
                    onClick={() => deleteChain(c.id)}
                    className="px-0.5 text-text-muted hover:text-accent-red"
                  >
                    ×
                  </button>
                </span>
              ))}
            </span>
          ) : null}
          <button
            type="button"
            data-testid="funnel-chain-reset"
            onClick={() => { resetToCanonical(); setName(''); }}
            className="rounded-lg border border-border-c px-2 py-0.5 text-2xs font-bold text-text-muted hover:text-accent-amber"
          >
            بازگشت به جزوه
          </button>
        </span>
      </div>
      {chain.length ? (
        <p className="text-3xs text-text-muted" data-testid="funnel-chain-note">
          اشتراکِ ترتیبی است، نه OR: هر فیلتر فقط رویِ بازماندۀ فیلترِ قبل اجرا می‌شود ·
          رجیستری: {toFaDigits(filters.length)} فیلتر · ruleset{' '}
          <span className="num opacity-70">{rulesetVersion || '—'}</span>
        </p>
      ) : null}
    </div>
  );
}
