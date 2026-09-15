// features/fundamental/ui/FtsSettingsDrawer.tsx -- پنل تنظیمات پیش‌شرط‌های FTS
// اتصال مستقیم به fts_thresholds.json از طریق GET/POST /api/fts/config.
// پنل Overlay ثابت سمت راست است: با createPortal به document.body و
// `fixed inset-y-0 right-0 w-[420px]` — مستقل از اسکرول کانتینر داخلی
// AppShell، همیشه داخل viewport و بدون اشغال هیچ ابعادی از layout
// صفحه؛ backdrop نیمه‌شف z-[9998] و پنل z-[9999]. بستن: ✕ / backdrop / Esc.
// اسلایدر رشد درآمد، کف حاشیه، اسلایدر شاخص ۴ (کف فروش سالانه‌شده به
// ارزش بازار ۱۰٪..۱۰۰٪)، تاگل شاخص ۲ (سابقه ۳ ساله سودسازی)، گیت
// چندگزینه‌ای نرخ‌گذاری دستوری، تاگل هوشمند رشد فیزیکی (صرفاً تولیدی)،
// دروازه‌های سخت (تعلیق) و کلید بازنشانی به پیش‌فرض جزوه.
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { FTS_GUIDE_DEFAULTS, SALES_TO_MCAP_GUIDE_DEFAULT, useFtsConfig, useSaveFtsConfig, type FtsConfig } from '../api/useFtsConfig';

/** فیلدهایی که کشو ویرایش می‌کند — بقیهٔ کلیدها هنگام ذخیره از config فعلی می‌آیند */
type DraftConfig = Pick<
  FtsConfig,
  'growth_min' | 'margin_min' | 'industry_mode' | 'suspended_max_stale_sessions' | 'v10_eps_years' | 'v10_sales_to_mcap_min'
> & { v10_sales_to_mcap_min: number };

/** حالت گیت نرخ‌گذاری دستوری — چندگزینه‌ای به‌جای تاگل خشک */
type PricingGateMode = 'free_only' | 'jump_allowed' | 'all';

const PRICING_GATE_LABEL: Record<PricingGateMode, string> = {
  free_only: 'صنایع آزاد/صادراتی/بورس کالا',
  jump_allowed: 'صنایع مجاز با جهش نرخ (دارو، غذا)',
  all: 'همه صنایع',
};

/** صنایع دستوری جزوه؛ در حالت «جهش نرخ» دارو و غذا از فهرست حذف می‌شوند */
const JUMP_ALLOWED_SECTORS = ['دارو', 'غذا'];

function draftFrom(c: FtsConfig | null | undefined): DraftConfig {
  return {
    growth_min: c?.growth_min ?? FTS_GUIDE_DEFAULTS.growth_min,
    margin_min: c?.margin_min ?? FTS_GUIDE_DEFAULTS.margin_min,
    industry_mode: c?.industry_mode ?? FTS_GUIDE_DEFAULTS.industry_mode,
    suspended_max_stale_sessions: c?.suspended_max_stale_sessions ?? FTS_GUIDE_DEFAULTS.suspended_max_stale_sessions,
    v10_eps_years: c?.v10_eps_years ?? FTS_GUIDE_DEFAULTS.v10_eps_years,
    v10_sales_to_mcap_min: c?.v10_sales_to_mcap_min ?? SALES_TO_MCAP_GUIDE_DEFAULT,
  };
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  hint,
  onChange,
  formatValue,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  hint?: string;
  onChange: (v: number) => void;
  formatValue?: (v: number) => string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <label className="min-w-0 break-words text-right text-xs font-bold leading-snug text-text-secondary">{label}</label>
        <span className="num shrink-0 rounded-md border border-border-c bg-bg-primary px-1.5 py-0.5 text-xs font-black text-accent-blue">
          {formatValue ? formatValue(value) : `${toFaDigits(value)}٪`}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-bg-card accent-[var(--accent-blue)]"
        aria-label={label}
      />
      {hint ? <span className="break-words text-2xs leading-snug text-text-muted">{hint}</span> : null}
    </div>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      className="flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--hairline)] bg-bg-card/40 px-3.5 py-2.5 text-right transition-colors hover:border-border-accent"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="break-words text-xs font-bold leading-snug text-text-primary">{label}</span>
        {hint ? <span className="break-words text-2xs leading-snug text-text-muted">{hint}</span> : null}
      </span>
      <span
        aria-hidden
        dir="ltr"
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 ${
          checked ? 'bg-accent-green/80' : 'bg-bg-card'
        }`}
      >
        <span
          className={`absolute h-3.5 w-3.5 rounded-full bg-white shadow transition-all duration-200 ${
            checked ? 'left-[18px]' : 'left-1'
          }`}
        />
      </span>
    </button>
  );
}

/** دکمهٔ ⚙ + پنل Overlay ثابت سمت راست — پنل با createPortal به
 *  document.body رندر می‌شود و `fixed inset-y-0 right-0` است: مستقل از
 *  هر اسکرول/جریان صفحه، همیشه داخل viewport. Esc و کلیک بیرون می‌بندند. */
export function FtsSettingsTrigger({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  const close = () => {
    if (open) onToggle();
  };
  return (
    <span className="inline-flex" data-testid="fts-settings-trigger">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="تنظیمات پیش‌شرط‌های FTS"
        title="تنظیمات پیش‌شرط‌های FTS"
        className={`shrink-0 rounded-lg border px-2.5 py-1.5 text-sm transition-all duration-200 ${
          open
            ? 'border-border-accent bg-bg-card/80 text-accent-blue'
            : 'border-[var(--hairline)] bg-bg-card/60 text-text-secondary hover:border-border-accent hover:text-accent-blue'
        }`}
      >
        ⚙
      </button>
      <FtsSettingsDrawer open={open} onClose={close} />
    </span>
  );
}

export function FtsSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const cfg = useFtsConfig();
  const save = useSaveFtsConfig();
  const [draft, setDraft] = useState<DraftConfig>(draftFrom(null));
  /** چک‌باکس الزام رشد مقداری/تناژ فیزیکی — v10_volume_growth_min (۰٪ = الزام فعال) */
  const [volumeGate, setVolumeGate] = useState(true);
  /** شاخص ۲: الزام عملکرد سودسازی ۳ ساله (EPS صعودی) — v10_eps_years 3=فعال، 1=غیرفعال */
  const [epsGate, setEpsGate] = useState(true);
  /** گیت نرخ‌گذاری دستوری — چندگزینه‌ای */
  const [pricingGate, setPricingGate] = useState<PricingGateMode>('free_only');

  /** Esc در حالت باز می‌بندد — بدون هیچ anchor-math؛ پنل fixed سمت راست است */
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (cfg.data?.config) {
      const d = draftFrom(cfg.data.config);
      setDraft(d);
      setEpsGate((d.v10_eps_years ?? 3) >= 3);
      // جهش‌مجاز یعنی جزوه-دستوری منهای دارو/غذا؛ همه یعنی Rank_Only
      const mandatory = cfg.data.config.mandatory_sectors ?? FTS_GUIDE_DEFAULTS.mandatory_sectors;
      if (cfg.data.config.industry_mode === 'Rank_Only') {
        setPricingGate('all');
      } else if (JUMP_ALLOWED_SECTORS.every((s) => !mandatory.includes(s))) {
        setPricingGate('jump_allowed');
      } else {
        setPricingGate('free_only');
      }
    }
  }, [cfg.data]);

  /** چک‌باکس رشد فیزیکی روی v10_volume_growth_min سوار است (پیش‌فرض جزوه ۰٪ = روشن) */
  useEffect(() => {
    setVolumeGate(true);
  }, [cfg.data]);

  const onSave = () => {
    const base = cfg.data?.config ?? FTS_GUIDE_DEFAULTS;
    const mandatorySectors =
      pricingGate === 'free_only'
        ? [...FTS_GUIDE_DEFAULTS.mandatory_sectors]
        : pricingGate === 'jump_allowed'
          ? [...FTS_GUIDE_DEFAULTS.mandatory_sectors].filter((s) => !JUMP_ALLOWED_SECTORS.includes(s))
          : [...(base.mandatory_sectors ?? FTS_GUIDE_DEFAULTS.mandatory_sectors)];
    const nextIndustryMode = pricingGate === 'all' ? 'Rank_Only' : 'Exclude_Mandatory_Pricing';
    const payload: Record<string, unknown> = {
      ...base,
      ...draft,
      industry_mode: nextIndustryMode,
      mandatory_sectors: mandatorySectors,
      v10_eps_years: epsGate ? 3 : 1,
      v10_volume_growth_min: volumeGate ? 0 : -1,
      v10_monetary_growth_min: draft.growth_min,
      /** اسلایدر شاخص ۴: کف نسبت فروش سالانه‌شده به ارزش بازار (۰.۱۰..۱.۰۰) */
      v10_sales_to_mcap_min: draft.v10_sales_to_mcap_min,
      margin_optimal: Math.max(draft.margin_min, FTS_GUIDE_DEFAULTS.margin_optimal),
    };
    if (volumeGate) delete payload.v10_volume_growth_min_error;
    save.mutate(payload);
  };

  const onReset = () => {
    const payload: Record<string, unknown> = {
      ...FTS_GUIDE_DEFAULTS,
      v10_monetary_growth_min: FTS_GUIDE_DEFAULTS.growth_min,
      v10_volume_growth_min: 0,
      v10_sales_to_mcap_min: SALES_TO_MCAP_GUIDE_DEFAULT,
    };
    save.mutate(payload, {
      onSuccess: () => {
        setDraft(draftFrom(null));
        setPricingGate('free_only');
        setVolumeGate(true);
        setEpsGate(true);
      },
    });
  };

  if (typeof document === 'undefined') return null;
  return createPortal(
    <>
      {/* backdrop: کلیک بیرون پنل می‌بندد — fixed، بدون اندازه در layout */}
      {open ? (
        <div
          aria-hidden
          onClick={onClose}
          data-testid="fts-settings-backdrop"
          className="fixed inset-0 z-[9998] bg-black/25"
        />
      ) : null}
      {/* ⚠️ CSS: عمداً کلاس glass-panel روی این پنل نیست.
          در index.css قاعدهٔ `.glass-panel{position:relative; ...}` بیرون از
          @layer نوشته شده؛ در آبشار CSS، استایل بیرون از layer بر utilities
          تیلویند (که داخل @layer utilities هستند) مقدم است و `fixed` را
          باطل می‌کند — نتیجه: پنل به‌جای دراور ثابت سمت راست، داخل جریان
          صفحه و در پایین ظاهر می‌شود. ظاهر شیشه‌ای با utilityهای صریح
          بازسازی شده تا positioning زیر هیچ قاعدهٔ بیرون‌از‌layer نرود. */}
      <aside
        aria-label="پنل تنظیمات پیش‌شرط‌های FTS"
        aria-hidden={!open}
        role="dialog"
        data-testid="fts-settings-panel"
        className={`fixed inset-y-0 right-0 z-[9999] flex w-[420px] max-w-[92vw] shrink-0 flex-col rounded-none border-l border-[var(--hairline)] bg-[var(--glass-tint)] shadow-[var(--glass-shadow)] backdrop-blur-md backdrop-saturate-125 transition-all duration-200 ease-out ${
          open ? 'visible translate-x-0 opacity-100' : 'invisible translate-x-full opacity-0'
        }`}
        {...{ inert: !open ? ('' as unknown as boolean) : undefined }}
      >
        <div className="flex items-center justify-between border-b border-[var(--hairline)] bg-bg-primary/85 px-6 py-3 backdrop-blur-md">
          <h3 className="text-sm font-black text-text-primary">تنظیمات پیش‌شرط‌های FTS</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن تنظیمات"
            className="rounded-md border border-transparent px-1.5 py-0.5 text-xs text-text-muted transition-colors hover:border-[var(--hairline)] hover:text-accent-red"
          >
            ✕
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6 py-5">
        <Slider
          label="حداقل درصد رشد درآمد کدال"
          value={draft.growth_min}
          min={0}
          max={150}
          step={5}
          hint={`پیش‌فرض جزوه: ${toFaDigits(FTS_GUIDE_DEFAULTS.growth_min)}٪ (یا تورم سالانه)`}
          onChange={(v) => setDraft((d) => ({ ...d, growth_min: v }))}
        />

        <ToggleRow
          label="الزام رشد مقداری / تناژ فیزیکی"
          hint="صرفاً برای شرکت‌های تولیدی — هلدینگ‌ها و خدماتی‌ها خودکار نادیده گرفته می‌شوند (N/A)"
          checked={volumeGate}
          onChange={setVolumeGate}
        />

        <ToggleRow
          label="الزام سابقه عملکرد سودسازی ۳ ساله"
          hint="شاخص ۲ — EPS باید در ۳ سال مالی گذشته صعودی باشد"
          checked={epsGate}
          onChange={setEpsGate}
        />

        <Slider
          label="کف حاشیه سود ناخالص"
          value={draft.margin_min}
          min={5}
          max={60}
          step={1}
          hint={`استاندارد ${toFaDigits(30)}٪ · حد قابل قبول ${toFaDigits(20)}٪ · زیر ۲۰٪ مردود`}
          onChange={(v) => setDraft((d) => ({ ...d, margin_min: v }))}
        />

        <Slider
          label="کف نسبت فروش سالانه‌شده به ارزش بازار"
          value={Math.round(draft.v10_sales_to_mcap_min * 100)}
          min={10}
          max={100}
          step={5}
          formatValue={(v) => `${toFaDigits(v)}٪`}
          hint={`شاخص ۴ — پیش‌فرض جزوه ${toFaDigits(50)}٪ · فروش سالانه ÷ ارزش بازار نباید از این کف پایین‌تر باشد`}
          onChange={(v) => setDraft((d) => ({ ...d, v10_sales_to_mcap_min: v / 100 }))}
        />

        <div className="flex flex-col gap-3 rounded-xl border border-[var(--hairline)] bg-bg-card/30 p-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-text-primary">دروازه‌های سخت</span>
            <Badge tone="red">Hard Gates</Badge>
          </div>

          <div className="flex flex-col gap-1.5" role="group" aria-label="گیت نرخ‌گذاری دستوری">
            <span className="text-xs font-bold text-text-primary">نرخ‌گذاری دستوری</span>
            <div className="flex flex-col gap-1">
              {(Object.keys(PRICING_GATE_LABEL) as PricingGateMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={pricingGate === m}
                  onClick={() => setPricingGate(m)}
                  className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-right text-2xs font-bold transition-colors ${
                    pricingGate === m
                      ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue'
                      : 'border-[var(--hairline)] bg-bg-card/40 text-text-secondary hover:border-border-accent'
                  }`}
                >
                  <span
                    aria-hidden
                    className={`inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border-2 ${
                      pricingGate === m ? 'border-accent-blue' : 'border-text-muted/40'
                    }`}
                  >
                    {pricingGate === m ? <span className="h-1.5 w-1.5 rounded-full bg-accent-blue" /> : null}
                  </span>
                  <span className="break-words leading-snug">{PRICING_GATE_LABEL[m]}</span>
                </button>
              ))}
            </div>
            <span className="break-words text-2xs leading-snug text-text-muted">
              خودرو، دارو، نیروگاه، غذا و… بسته به حالت انتخابی از غربالگری کنار گذاشته می‌شوند
            </span>
          </div>

          <ToggleRow
            label="حذف نمادهای مشمول تعلیق"
            hint="نماد با ۳ نشست عقب‌مانده از تابلو"
            checked={draft.suspended_max_stale_sessions > 0}
            onChange={(v) =>
              setDraft((d) => ({ ...d, suspended_max_stale_sessions: v ? FTS_GUIDE_DEFAULTS.suspended_max_stale_sessions : 0 }))
            }
          />
        </div>

        {save.isError ? (
          <div className="rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-2xs text-accent-red">
            ذخیره نشد — سرور در دسترس نیست
          </div>
        ) : save.data && !save.data.ok ? (
          <div className="rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-2xs text-accent-red">
            {save.data.message ?? 'برخی مقادیر معتبر نیستند'}
          </div>
        ) : save.isSuccess && save.data?.ok ? (
          <div className="rounded-xl border border-accent-green/40 bg-accent-green/10 px-3 py-2 text-2xs text-accent-green">
            پیش‌شرط‌ها در fts_thresholds.json ذخیره شد
          </div>
        ) : null}

        <div className="mt-auto flex flex-col gap-2 pt-2">
          <button
            type="button"
            onClick={onSave}
            disabled={save.isPending}
            className="rounded-full border border-accent-blue/40 bg-accent-blue/15 px-4 py-2 text-xs font-black text-accent-blue transition-all hover:border-accent-blue disabled:opacity-50"
          >
            {save.isPending ? 'در حال ذخیره…' : 'ذخیرهٔ پیش‌شرط‌ها'}
          </button>
          <button
            type="button"
            onClick={onReset}
            disabled={save.isPending}
            className="rounded-full border border-[var(--hairline)] bg-bg-card/60 px-4 py-2 text-xs font-bold text-text-secondary transition-all hover:border-accent-yellow hover:text-accent-yellow disabled:opacity-50"
          >
            Reset to FTS Defaults
          </button>
        </div>
      </div>
      </aside>
    </>,
    document.body,
  );
}
