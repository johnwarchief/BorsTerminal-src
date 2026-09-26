// features/market/components/FilterConfigPopover.tsx -- پاپ‌اور مدرن تنظیمات اختصاصی هر فیلتر
// گزینه‌ها باید از همان JET_LADDER و پیش‌فرض‌هایِ جزوه بیایند؛ فهرستِ دستیِ
// «۵، ۹، ۱۹، ۲۹، ۳۹» هیچ‌وقت ۵۹ نداشت، پس حالتِ پیش‌فرضِ جت در این پاپ‌اور
// انتخابی‌نشانه می‌ماند و کاربر فکر می‌کرد فیلتر روی ۳۹ روزه تنظیم شده است.
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import {
  DEFAULT_TAPE_FILTER_CONFIG,
  type TapeFilterConfig,
} from '../lib/tapeAlgorithms';
import { JET_LADDER } from '../lib/tapeMath';
import { QUICK_LABELS, useTapeStore, type QuickFilter } from '../stores/tapeStore';

export function FilterConfigPopover({
  filter,
  open,
  anchorRect,
  onClose,
}: {
  filter: QuickFilter;
  open: boolean;
  anchorRect: DOMRect | null;
  onClose: () => void;
}) {
  const config = useTapeStore((s) => s.tapeFilterConfig);
  const setConfig = useTapeStore((s) => s.setTapeFilterConfig);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const toggleQuickFilter = useTapeStore((s) => s.toggleQuickFilter);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (popoverRef.current?.contains(t)) return;
      onClose();
    };
    const onScrollOrResize = () => onClose();
    document.addEventListener('mousedown', onDown);
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open, onClose]);

  if (!open || !anchorRect || typeof document === 'undefined') return null;

  // موقعیت‌سنجی هوشمند زیر چیپ
  const top = anchorRect.bottom + 6;
  const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - 290));

  const isActive = quickFilters.includes(filter);

  const updateSubConfig = <K extends keyof TapeFilterConfig>(
    key: K,
    patch: Partial<TapeFilterConfig[K]>,
  ) => {
    setConfig({
      ...config,
      [key]: { ...config[key], ...patch },
    });
    // اگر فیلتر غیرفعال است، با تغییر اسلایدر فوراً فعال شود تا تغییرات در جدول و بج‌ها اعمال گردد
    if (!useTapeStore.getState().quickFilters.includes(filter)) {
      toggleQuickFilter(filter);
    }
  };

  const resetSingleFilter = () => {
    switch (filter) {
      case 'f_susp':
        updateSubConfig('suspiciousVolume', DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume);
        break;
      case 'f_clock':
        updateSubConfig('clock', DEFAULT_TAPE_FILTER_CONFIG.clock);
        break;
      case 'f_jet':
        updateSubConfig('jet', DEFAULT_TAPE_FILTER_CONFIG.jet);
        break;
      case 'f_roobi':
        updateSubConfig('roobi', DEFAULT_TAPE_FILTER_CONFIG.roobi);
        break;
      case 'f_noqteh':
        updateSubConfig('noqteh', DEFAULT_TAPE_FILTER_CONFIG.noqteh);
        break;
    }
  };

  return createPortal(
    <div
      ref={popoverRef}
      style={{
        position: 'fixed',
        top: `${top}px`,
        left: `${left}px`,
        zIndex: 9999,
      }}
      className="w-72 rounded-2xl border border-border-c bg-bg-primary p-3 shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-100"
      role="dialog"
      aria-label={`تنظیمات فیلتر ${QUICK_LABELS[filter]}`}
    >
      {/* هدر پاپ‌اور با کلید وضعیت فعال/غیرفعال */}
      <div className="flex items-center justify-between border-b border-border-c/60 pb-2 mb-2.5">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-black text-text-primary flex items-center gap-1">
            <span>⚙️</span>
            <span>{QUICK_LABELS[filter]}</span>
          </span>
          <button
            type="button"
            onClick={() => toggleQuickFilter(filter)}
            className={`rounded px-1.5 py-0.5 text-3xs font-black transition-colors ${
              isActive
                ? 'bg-accent-green/20 text-accent-green border border-accent-green/40'
                : 'bg-bg-secondary text-text-muted border border-border-c'
            }`}
          >
            {isActive ? 'فعال ✓' : 'خاموش'}
          </button>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="size-5 rounded-md text-text-muted hover:bg-bg-secondary hover:text-text-primary flex items-center justify-center text-xs"
        >
          ✕
        </button>
      </div>

      {/* فرم تنظیمات هر فیلتر */}
      <div className="flex flex-col gap-2.5 text-xs text-text-secondary">
        {filter === 'f_susp' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">ضریب حجم مشکوک:</span>
                <span className="num font-bold text-accent-susp">
                  {toFaDigits(config.suspiciousVolume.minRatio.toFixed(1))}×
                </span>
              </div>
              <input
                type="range"
                min="1.5"
                max="8.0"
                step="0.5"
                value={config.suspiciousVolume.minRatio}
                onChange={(e) =>
                  updateSubConfig('suspiciousVolume', { minRatio: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--accent-susp)] cursor-pointer"
              />
              <div className="flex justify-between text-3xs text-text-muted mt-0.5">
                <span>۱.۵×</span>
                <span>۳.۰× (استاندارد)</span>
                <span>۸.۰×</span>
              </div>
            </div>
            <div>
              <span className="block font-semibold text-text-primary mb-1">مبنای محاسبه حجم:</span>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => updateSubConfig('suspiciousVolume', { timeframe: 'monthly_30d' })}
                  className={`rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
                    config.suspiciousVolume.timeframe === 'monthly_30d'
                      ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                      : 'border-border-c bg-bg-card text-text-muted'
                  }`}
                >
                  میانگین ۳۰ روزه
                </button>
                <button
                  type="button"
                  onClick={() => updateSubConfig('suspiciousVolume', { timeframe: 'prev_day_dod' })}
                  className={`rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
                    config.suspiciousVolume.timeframe === 'prev_day_dod'
                      ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                      : 'border-border-c bg-bg-card text-text-muted'
                  }`}
                >
                  نسبت به روز قبل
                </button>
              </div>
            </div>
          </>
        )}

        {filter === 'f_clock' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">حداقل اختلاف آخرین/پایانی:</span>
                <span className="num font-bold text-accent-green">
                  {toFaDigits(config.clock.minDeltaPct.toFixed(1))}٪
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="4.0"
                step="0.5"
                value={config.clock.minDeltaPct}
                onChange={(e) =>
                  updateSubConfig('clock', { minDeltaPct: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--accent-green)] cursor-pointer"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer rounded-lg p-1 hover:bg-bg-card/60">
              <input
                type="checkbox"
                checked={config.clock.requireGoldenHour}
                onChange={(e) => updateSubConfig('clock', { requireGoldenHour: e.target.checked })}
                className="size-3.5 accent-[var(--accent-blue)]"
              />
              <span className="text-2xs font-semibold">فقط ساعت طلایی (پایانی منفی، آخرین مثبت)</span>
            </label>
          </>
        )}

        {filter === 'f_jet' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">حداقل قدرت خریدار:</span>
                <span className="num font-bold text-neon-cyan">
                  {toFaDigits(config.jet.minBuyerPower.toFixed(1))}×
                </span>
              </div>
              <input
                type="range"
                min="1.0"
                max="3.5"
                step="0.25"
                value={config.jet.minBuyerPower}
                onChange={(e) =>
                  updateSubConfig('jet', { minBuyerPower: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--neon-cyan)] cursor-pointer"
              />
            </div>
            <div>
              <span className="block font-semibold text-text-primary mb-1">تایم‌فریم شکست سقف:</span>
              <div className="flex flex-wrap gap-1">
                {JET_LADDER.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => updateSubConfig('jet', { lookbackDays: d })}
                    className={`rounded border px-2 py-0.5 text-2xs font-bold ${
                      config.jet.lookbackDays === d
                        ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan'
                        : 'border-border-c bg-bg-card text-text-muted'
                    }`}
                  >
                    {toFaDigits(d)} روزه
                  </button>
                ))}
              </div>
              <p className="text-3xs text-text-muted mt-1 leading-4">
                همهٔ نقاطِ کوتاه‌تر از انتخابِ شما هم باید شکسته شوند؛ ۵۹ روزه همان
                پلکانِ کاملِ جزوه است.
              </p>
            </div>
          </>
        )}

        {filter === 'f_roobi' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">سقف افت قیمت مجاز:</span>
                <span className="num font-bold text-accent-red">
                  {toFaDigits(config.roobi.maxChangePct.toFixed(1))}٪
                </span>
              </div>
              <input
                type="range"
                min="-5.0"
                max="0.0"
                step="0.5"
                value={config.roobi.maxChangePct}
                onChange={(e) =>
                  updateSubConfig('roobi', { maxChangePct: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--accent-red)] cursor-pointer"
              />
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">حداقل نسبت حجم جمع‌آوری:</span>
                <span className="num font-bold text-accent-blue">
                  {config.roobi.minVolRatio > 0
                    ? `${toFaDigits(config.roobi.minVolRatio.toFixed(1))}×` : 'بدون شرط'}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3.0"
                step="0.1"
                value={config.roobi.minVolRatio}
                onChange={(e) =>
                  updateSubConfig('roobi', { minVolRatio: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--accent-blue)] cursor-pointer"
              />
            </div>
          </>
        )}

        {filter === 'f_noqteh' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-text-primary">حداکثر فاصله از کف (درصد):</span>
                <span className="num font-bold text-accent-yellow">
                  {toFaDigits(config.noqteh.maxDistPct.toFixed(1))}٪
                </span>
              </div>
              <input
                type="range"
                min="1.0"
                max="10.0"
                step="1.0"
                value={config.noqteh.maxDistPct}
                onChange={(e) =>
                  updateSubConfig('noqteh', { maxDistPct: parseFloat(e.target.value) })
                }
                className="w-full accent-[var(--accent-yellow)] cursor-pointer"
              />
            </div>
          </>
        )}

        {/* دکمه بازنشانی این فیلتر */}
        <div className="flex justify-end pt-2 border-t border-border-c/50 mt-1">
          <button
            type="button"
            onClick={resetSingleFilter}
            className="text-3xs text-text-muted hover:text-accent-blue transition-colors"
          >
            بازنشانی به پیش‌فرض
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
