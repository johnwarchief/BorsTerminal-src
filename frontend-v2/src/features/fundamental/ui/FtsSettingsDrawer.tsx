import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fa';
import {
  buildFtsPayload,
  buildResetPayload,
  draftFromConfig,
  useFtsConfig,
  useSaveFtsConfig,
  type FtsSettingsDraft,
} from '../api/useFtsConfig';
import {
  EXCLUDE_AXES,
  EXCLUDE_LABEL,
  NO_ROW_FLAG,
  resetExcludeAxes,
  toggleExcludeAxis,
  useExcludeAxes,
} from '../lib/exclusionFilter';

function Slider({
  testId,
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  testId: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={testId} className="fd-meta text-text-2">{label}</label>
        <span className="num rounded border border-line bg-panel-2 px-2 fd-meta text-text">
          {toFaDigits(value)}٪
        </span>
      </div>
      <input
        id={testId}
        data-testid={testId}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded bg-panel-3"
      />
    </div>
  );
}

function Toggle({
  testId,
  label,
  hint,
  checked,
  onChange,
}: {
  testId: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between gap-3 rounded border border-line bg-panel px-3 py-2 text-start hover:border-line-strong"
    >
      <span className="min-w-0 flex-1">
        <span className="block fd-meta text-text-2">{label}</span>
        {hint ? <span className="mt-1 block fd-meta leading-relaxed text-text-3">{hint}</span> : null}
      </span>
      <span
        aria-hidden
        dir="ltr"
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${checked ? 'bg-up/70' : 'bg-panel-3'}`}
      >
        <span className={`absolute h-3.5 w-3.5 rounded-full bg-white shadow transition-all ${checked ? 'left-[18px]' : 'left-1'}`} />
      </span>
    </button>
  );
}

function Radio({
  testId,
  label,
  checked,
  onChange,
}: {
  testId: string;
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      data-testid={testId}
      onClick={onChange}
      className={`flex items-center gap-2 rounded border px-3 py-2 text-start fd-meta ${checked ? 'border-line-strong bg-panel-2 text-text' : 'border-line bg-panel text-text-3'}`}
    >
      <span
        aria-hidden
        className={`inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border-2 ${checked ? 'border-accent' : 'border-line-strong'}`}
      >
        {checked ? <span className="h-1.5 w-1.5 rounded bg-accent" /> : null}
      </span>
      {label}
    </button>
  );
}

export function FtsSettingsTrigger({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <span className="inline-flex" data-testid="fts-settings-trigger">
      <button
        type="button"
        data-testid="fts-settings-btn"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={onToggle}
        className="tape-btn"
      >
        تنظیمات
      </button>
      {open ? <FtsSettingsDrawer open onClose={onToggle} /> : null}
    </span>
  );
}

export function FtsSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const cfg = useFtsConfig();
  const save = useSaveFtsConfig();
  const excludeAxes = useExcludeAxes();
  const [draft, setDraft] = useState<FtsSettingsDraft>(() => draftFromConfig(null));
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (cfg.data?.config) setDraft(draftFromConfig(cfg.data.config));
  }, [cfg.data]);

  useEffect(() => {
    if (!open) return;
    const root = panelRef.current;
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !root) return;
      const nodes = Array.from(root.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ));
      if (nodes.length === 0) return;
      const first = nodes[0]!;
      const last = nodes[nodes.length - 1]!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    root?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (typeof document === 'undefined') return null;

  const base = cfg.data?.config ?? null;
  const update = <K extends keyof FtsSettingsDraft>(key: K, value: FtsSettingsDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  const onSave = () => {
    if (!base) return;
    save.mutate(buildFtsPayload(base, draft), {
      onSuccess: (response) => {
        if (response.status === 'success' && response.config) setDraft(draftFromConfig(response.config));
      },
    });
  };

  const onReset = () => {
    if (base) save.mutate(buildResetPayload(base));
  };

  const serverError = save.isError
    ? 'ذخیره نشد — سرور در دسترس نیست'
    : save.data?.status === 'error'
      ? [save.data.message, ...Object.values(save.data.errors ?? {})].filter(Boolean).join(' · ')
      : null;
  const saved = save.isSuccess && save.data?.status === 'success';

  const panel = (
    <>
      <div
        data-testid="fts-settings-backdrop"
        aria-hidden
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/30"
      />
      <aside
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="پنل تنظیمات پیش‌شرط‌های FTS"
        data-testid="fts-settings-panel"
        className="fixed inset-y-0 start-0 z-50 flex w-[420px] max-w-[92vw] flex-col border-e border-line bg-panel shadow-2xl outline-none"
      >
        <header className="flex flex-none items-center justify-between border-b border-line px-4 py-3">
          <h3 className="fd-meta  text-text">تنظیمات پیش‌شرط‌های FTS</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن تنظیمات"
            data-testid="fts-settings-close"
            className="tape-btn"
          >
            ×
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-3">
          {cfg.isLoading ? (
            <p data-testid="fts-settings-loading" className="fd-meta text-text-3">در حال خواندن تنظیمات…</p>
          ) : null}
          {cfg.isError ? (
            <div data-testid="fts-settings-load-error" className="rounded border border-down/40 bg-down/10 p-2 fd-meta text-down">
              تنظیمات خوانده نشد.
              <button type="button" onClick={() => void cfg.refetch()} className="ms-2 underline">تلاش دوباره</button>
            </div>
          ) : null}

          {base ? (
            <>
              <section className="flex flex-col gap-3">
                <h4 className="fd-meta  text-text-2">آستانه‌های پنج شاخص</h4>
                <Slider testId="fts-growth-min" label="حداقل درصد رشد درآمد کدال" value={draft.growth_min} min={0} max={150} step={5} onChange={(value) => update('growth_min', value)} />
                <Slider testId="fts-monetary-growth" label="هدف درصد رشد (پوشش تورم)" value={draft.v10_monetary_growth_min} min={0} max={150} step={5} onChange={(value) => update('v10_monetary_growth_min', value)} />
                <Slider testId="fts-inflation-basis" label="مبنای تورم در فرمول رشد تولیدی" value={draft.v10_inflation_basis} min={0} max={100} step={5} onChange={(value) => update('v10_inflation_basis', value)} />
                <Toggle testId="fts-volume-gate" label="الزام رشد تولیدی / تناژ فیزیکی" hint="فقط برای شرکت‌های تولیدی/کالایی؛ خاموش‌کردن، الزام گسترهٔ فیزیکی را هم برمی‌دارد." checked={draft.volumeGate} onChange={(value) => update('volumeGate', value)} />
                <Toggle testId="fts-eps-gate" label="الزام سابقهٔ عملکرد سودسازی سه‌ساله" checked={draft.epsGate} onChange={(value) => update('epsGate', value)} />
                <Slider testId="fts-margin-min" label="کف حاشیهٔ سود ناخالص" value={draft.margin_min} min={5} max={60} step={1} onChange={(value) => update('margin_min', value)} />
                <Slider testId="fts-sales-to-mcap" label="کف نسبت فروش سالانه‌شده به ارزش بازار" value={Math.round(draft.v10_sales_to_mcap_min * 100)} min={10} max={100} step={5} onChange={(value) => update('v10_sales_to_mcap_min', value / 100)} />
                <Slider testId="fts-profit-potential" label="حداقل پوشش سود ناخالص تخمینی" value={draft.profit_potential_min} min={0} max={100} step={5} onChange={(value) => update('profit_potential_min', value)} />
              </section>

              <section className="flex flex-col gap-2 border-t border-line pt-3">
                <h4 className="fd-meta  text-text-2">دروازه‌های سخت</h4>
                <div className="flex flex-col gap-1" role="radiogroup" aria-label="نرخ‌گذاری دستوری">
                  <Radio testId="fts-pricing-free" label="حذف سه صنعت دستوری جزوه" checked={draft.pricingGate === 'free_only'} onChange={() => update('pricingGate', 'free_only')} />
                  <Radio testId="fts-pricing-all" label="همه صنایع" checked={draft.pricingGate === 'all'} onChange={() => update('pricingGate', 'all')} />
                </div>
                <Toggle testId="fts-suspended" label="حذف نمادهای مشمول تعلیق" checked={draft.suspended_max_stale_sessions > 0} onChange={(value) => update('suspended_max_stale_sessions', value ? 3 : 0)} />
                <Toggle testId="fts-insurance-gate" label="حذف کامل نمادهای صنعت بیمه" checked={draft.insuranceGate} onChange={(value) => update('insuranceGate', value)} />
                <Toggle testId="fts-holdings-na" label="عدم اعمال نسبت فروش بر هلدینگ‌ها و سرمایه‌گذاری‌ها (N/A)" checked={draft.holdingsNa} onChange={(value) => update('holdingsNa', value)} />
                <Toggle testId="fts-pharma-exempt" label="آزادسازی دارویی‌های با حاشیه سود ناخالص بالای ۵۰٪" checked={draft.pharmaExempt} onChange={(value) => update('pharmaExempt', value)} />
                <Toggle testId="fts-base-market" label="حذف نمادهای بازار پایه فرابورس" checked={draft.baseMarketGate} onChange={(value) => update('baseMarketGate', value)} />
              </section>

              <section className="flex flex-col gap-2 border-t border-line pt-3">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="fd-meta  text-text-2">فیلتر حذف بر اساس شاخص</h4>
                  {excludeAxes.length > 0 ? (
                    <button type="button" data-testid="fts-exclude-reset" onClick={resetExcludeAxes} className="fd-meta text-accent hover:underline">
                      بازنشانی فیلترها
                    </button>
                  ) : null}
                </div>
                {EXCLUDE_AXES.map((axis) => (
                  <Toggle
                    key={axis}
                    testId={`fts-exclude-${axis}`}
                    label={EXCLUDE_LABEL[axis]}
                    hint={NO_ROW_FLAG[axis]}
                    checked={excludeAxes.includes(axis)}
                    onChange={() => toggleExcludeAxis(axis)}
                  />
                ))}
              </section>

              {serverError ? (
                <div data-testid="fts-settings-error" className="rounded border border-down/40 bg-down/10 px-3 py-2 fd-meta text-down">
                  {serverError}
                </div>
              ) : null}
              {saved ? (
                <div data-testid="fts-settings-success" className="rounded border border-up/40 bg-up/10 px-3 py-2 fd-meta text-up">
                  تنظیمات ذخیره شد.
                </div>
              ) : null}

              <div className="flex flex-col gap-2 pt-1">
                <button
                  type="button"
                  data-testid="fts-settings-save"
                  onClick={onSave}
                  disabled={save.isPending}
                  className="rounded border border-accent/40 bg-accent/15 px-4 py-2 fd-meta  text-accent disabled:opacity-50"
                >
                  {save.isPending ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات'}
                </button>
                <button
                  type="button"
                  data-testid="fts-settings-reset"
                  onClick={onReset}
                  disabled={save.isPending}
                  className="rounded border border-line bg-panel-2 px-4 py-2 fd-meta text-text-2 disabled:opacity-50"
                >
                  بازگردانی آستانه‌های بنیادی به پیش‌فرض FTS
                </button>
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </>
  );

  return createPortal(panel, document.body);
}
