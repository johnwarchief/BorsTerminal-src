// features/market/components/TapeFilterSettingsModal.tsx -- مدال شخصی‌سازی فیلترهای تابلو
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import {
  TAPE_PRESETS,
  isConfigCustomized,
  type LookbackDays,
  type TapePresetKey,
} from '../lib/tapeAlgorithms';
import { useTapeStore } from '../stores/tapeStore';

export function TapeFilterSettingsModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const config = useTapeStore((s) => s.tapeFilterConfig);
  const setConfig = useTapeStore((s) => s.setTapeFilterConfig);
  const resetConfig = useTapeStore((s) => s.resetTapeFilterConfig);
  const applyPreset = useTapeStore((s) => s.applyTapePreset);

  const [activeTab, setActiveTab] = useState<'presets' | 'clock' | 'susp' | 'jet' | 'noqteh' | 'smart'>('presets');

  if (!open) return null;
  if (typeof document === 'undefined') return null;

  const isCustom = isConfigCustomized(config);

  return createPortal(
    <div
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/65 p-3 sm:p-4 backdrop-blur-sm animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-label="شخصی‌سازی فیلترهای تابلو و الگوریتم‌ها"
    >
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl border border-border-c/90 bg-bg-primary shadow-2xl overflow-hidden">
        {/* هدر مدال */}
        <div className="flex items-center justify-between border-b border-border-c/70 px-5 py-3.5 bg-bg-card/60 backdrop-blur">
          <div className="flex items-center gap-2.5">
            <span className="text-sm sm:text-base font-black text-text-primary">⚙️ تنظیمات فیلترها</span>
            {isCustom ? (
              <span className="rounded-full bg-accent-blue/15 px-2.5 py-0.5 text-2xs font-bold text-accent-blue border border-accent-blue/30">
                شخصی‌سازی شده
              </span>
            ) : (
              <span className="rounded-full bg-bg-secondary px-2.5 py-0.5 text-2xs font-medium text-text-muted border border-border-c/50">
                پیش‌فرض استاندارد
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="flex size-8 items-center justify-center rounded-lg text-text-muted hover:bg-bg-secondary hover:text-text-primary transition-colors"
          >
            ✕
          </button>
        </div>

        {/* منوی تب‌های افقی */}
        <div className="flex overflow-x-auto border-b border-border-c/60 px-4 pt-2 gap-1.5 bg-bg-secondary/40 scrollbar-none">
          <button
            type="button"
            onClick={() => setActiveTab('presets')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'presets'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            🎯 استراتژی‌های آماده
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('clock')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'clock'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            ⏰ الگوی ساعت
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('susp')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'susp'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            📊 حجم مشکوک
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('jet')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'jet'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            🚀 فیلتر جت (سقف)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('noqteh')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'noqteh'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            🎯 کف‌یابی و نقطه
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('smart')}
            className={`shrink-0 rounded-t-lg border-b-2 px-3 py-2 text-xs font-bold transition-all ${
              activeTab === 'smart'
                ? 'border-accent-blue bg-bg-primary/80 text-accent-blue shadow-xs'
                : 'border-transparent text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
            }`}
          >
            💎 پول هوشمند
          </button>
        </div>

        {/* محتوای تب */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {/* تب استراتژی‌های آماده */}
          {activeTab === 'presets' && (
            <div className="space-y-3">
              <div className="rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-3 text-xs text-text-secondary leading-5 flex items-start gap-2">
                <span className="text-accent-blue text-sm">ℹ️</span>
                <span>
                  با انتخاب هر یک از الگوهای استراتژیک زیر، پارامترهای تایم‌فریم و آستانه‌های ریاضی کلیه فیلترها به صورت هوشمند و متناسب تنظیم می‌شوند:
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                {(Object.keys(TAPE_PRESETS) as TapePresetKey[]).map((key) => {
                  const p = TAPE_PRESETS[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => applyPreset(key)}
                      className="group flex flex-col items-start gap-1.5 rounded-xl border border-border-c/70 bg-bg-card/60 p-4 text-start transition-all hover:border-accent-blue hover:bg-accent-blue/10 hover:shadow-md focus:outline-none"
                    >
                      <div className="flex w-full items-center justify-between">
                        <span className="text-xs font-black text-text-primary group-hover:text-accent-blue transition-colors">{p.label}</span>
                        <span className="rounded-md bg-bg-secondary px-2 py-0.5 text-[10px] font-semibold text-text-muted group-hover:bg-accent-blue/20 group-hover:text-accent-blue transition-colors">
                          اعمال
                        </span>
                      </div>
                      <span className="text-2xs text-text-secondary leading-5">{p.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* تب الگوی ساعت */}
          {activeTab === 'clock' && (
            <div className="space-y-5">
              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-text-primary">
                    حداقل اختلاف قیمت آخرین و پایانی (دلتای ساعت)
                  </label>
                  <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-lg border border-accent-blue/20">
                    <span>+</span>
                    <span className="num">{toFaDigits(config.clock.minDeltaPct.toFixed(1))}</span>
                    <span className="text-2xs">درصد</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={0.3}
                  max={4.0}
                  step={0.1}
                  value={config.clock.minDeltaPct}
                  onChange={(e) =>
                    setConfig({
                      clock: { ...config.clock, minDeltaPct: Number(e.target.value) },
                    })
                  }
                  className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                />
                <p className="text-2xs text-text-muted leading-4">
                  فاصله آخرین معامله از قیمت پایانی نشان‌دهنده شدت بازگشت خریدار در دقایق پایانی بازار است.
                </p>
              </div>

              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4">
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.clock.requireGoldenHour}
                    onChange={(e) =>
                      setConfig({
                        clock: { ...config.clock, requireGoldenHour: e.target.checked },
                      })
                    }
                    className="size-4 rounded accent-[#38bdf8] cursor-pointer"
                  />
                  <span className="text-xs font-bold text-text-primary">
                    فقط ساعت طلایی (پایانی منفی و آخرین مثبت)
                  </span>
                </label>
                <p className="mt-1.5 text-2xs text-text-muted leading-4 ms-6.5">
                  در این حالت، فقط نمادهایی انتخاب می‌شوند که با وجود پایانی قرمز، آخرین معامله به بالای صفر کشیده شده است.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-1.5">
                  <label className="text-xs font-bold text-text-primary block">
                    حداقل ضریب حجم به میانگین ماه
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      max={5}
                      step={0.2}
                      value={config.clock.minVolRatio}
                      onChange={(e) =>
                        setConfig({
                          clock: { ...config.clock, minVolRatio: Number(e.target.value) },
                        })
                      }
                      className="num w-full rounded-lg border border-border-c bg-bg-secondary px-3 py-2 text-xs font-bold text-text-primary focus:border-accent-blue focus:outline-none"
                    />
                    <span className="text-xs text-text-secondary shrink-0">برابر</span>
                  </div>
                </div>
                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-1.5">
                  <label className="text-xs font-bold text-text-primary block">
                    حداقل تعداد معاملات
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={5}
                      max={200}
                      step={5}
                      value={config.clock.minTradeCount}
                      onChange={(e) =>
                        setConfig({
                          clock: { ...config.clock, minTradeCount: Number(e.target.value) },
                        })
                      }
                      className="num w-full rounded-lg border border-border-c bg-bg-secondary px-3 py-2 text-xs font-bold text-text-primary focus:border-accent-blue focus:outline-none"
                    />
                    <span className="text-xs text-text-secondary shrink-0">معامله</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* تب حجم مشکوک */}
          {activeTab === 'susp' && (
            <div className="space-y-5">
              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <label className="text-xs font-bold text-text-primary block">
                  تایم‌فریم مرجع سنجش حجم
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setConfig({
                        suspiciousVolume: { ...config.suspiciousVolume, timeframe: 'monthly_30d' },
                      })
                    }
                    className={`flex-1 rounded-xl border p-2.5 text-center text-xs font-bold transition-all ${
                      config.suspiciousVolume.timeframe === 'monthly_30d'
                        ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-xs'
                        : 'border-border-c bg-bg-secondary/70 text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    میانگین ۳۰ روزه (ماهانه)
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setConfig({
                        suspiciousVolume: { ...config.suspiciousVolume, timeframe: 'prev_day_dod' },
                      })
                    }
                    className={`flex-1 rounded-xl border p-2.5 text-center text-xs font-bold transition-all ${
                      config.suspiciousVolume.timeframe === 'prev_day_dod'
                        ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-xs'
                        : 'border-border-c bg-bg-secondary/70 text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    روز کاری قبل (Day-over-Day)
                  </button>
                </div>
              </div>

              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-text-primary">
                    آستانه ضریب حجم مشکوک
                  </label>
                  <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-lg border border-accent-blue/20">
                    <span className="text-2xs text-text-muted">حداقل:</span>
                    <span className="num">{toFaDigits(config.suspiciousVolume.minRatio.toFixed(1))}</span>
                    <span className="text-2xs">برابر</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={1.5}
                  max={8.0}
                  step={0.5}
                  value={config.suspiciousVolume.minRatio}
                  onChange={(e) =>
                    setConfig({
                      suspiciousVolume: { ...config.suspiciousVolume, minRatio: Number(e.target.value) },
                    })
                  }
                  className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                />
              </div>

              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-1.5">
                <label className="text-xs font-bold text-text-primary block">
                  حداقل تعداد معاملات معتبر
                </label>
                <div className="flex items-center gap-2 max-w-xs">
                  <input
                    type="number"
                    min={10}
                    max={300}
                    step={10}
                    value={config.suspiciousVolume.minTradeCount}
                    onChange={(e) =>
                      setConfig({
                        suspiciousVolume: { ...config.suspiciousVolume, minTradeCount: Number(e.target.value) },
                      })
                    }
                    className="num w-full rounded-lg border border-border-c bg-bg-secondary px-3 py-2 text-xs font-bold text-text-primary focus:border-accent-blue focus:outline-none"
                  />
                  <span className="text-xs text-text-secondary shrink-0">معامله</span>
                </div>
              </div>
            </div>
          )}

          {/* تب فیلتر جت */}
          {activeTab === 'jet' && (
            <div className="space-y-5">
              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-text-primary block">
                    تایم‌فریم شکست سقف قیمتی (Lookback High)
                  </label>
                  <span className="text-2xs font-bold text-accent-blue bg-accent-blue/10 px-2 py-0.5 rounded border border-accent-blue/20">
                    انتخاب فعلی: {
                      config.jet.lookbackDays === 1 ? 'سقف دیروز (۱ روزه)' :
                      config.jet.lookbackDays === 5 ? 'سقف هفتگی (۵ روزه)' :
                      config.jet.lookbackDays === 9 ? 'سقف ۲ هفته (۱۰ روزه)' :
                      config.jet.lookbackDays === 19 ? 'سقف ۱ ماهه (۲۰ روزه)' :
                      config.jet.lookbackDays === 29 ? 'سقف ۱.۵ ماهه (۳۰ روزه)' :
                      config.jet.lookbackDays === 39 ? 'سقف ۲ ماهه (۴۰ روزه)' :
                      config.jet.lookbackDays === 49 ? 'سقف ۲.۵ ماهه (۵۰ روزه)' :
                      'سقف فصلی ۳ ماهه (۶۰ روزه)'
                    }
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {([
                    { days: 1, label: '۱ روزه', sub: 'سقف دیروز' },
                    { days: 5, label: '۵ روزه', sub: 'هفتگی' },
                    { days: 9, label: '۱۰ روزه', sub: '۲ هفته' },
                    { days: 19, label: '۲۰ روزه', sub: '۱ ماهه' },
                    { days: 29, label: '۳۰ روزه', sub: '۱.۵ ماهه' },
                    { days: 39, label: '۴۰ روزه', sub: '۲ ماهه' },
                    { days: 49, label: '۵۰ روزه', sub: '۲.۵ ماهه' },
                    { days: 59, label: '۶۰ روزه', sub: 'فصلی (۳ ماه)' },
                  ] as { days: LookbackDays; label: string; sub: string }[]).map((opt) => {
                    const isSelected = config.jet.lookbackDays === opt.days;
                    return (
                      <button
                        key={opt.days}
                        type="button"
                        onClick={() =>
                          setConfig({
                            jet: { ...config.jet, lookbackDays: opt.days },
                          })
                        }
                        className={`flex flex-col items-center justify-center rounded-xl border py-2 px-1.5 text-center transition-all ${
                          isSelected
                            ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-xs ring-1 ring-accent-blue/30'
                            : 'border-border-c bg-bg-secondary/70 text-text-secondary hover:border-border-c hover:text-text-primary hover:bg-bg-secondary'
                        }`}
                      >
                        <span className="text-xs font-black">{opt.label}</span>
                        <span className="text-[10px] text-text-muted mt-0.5">{opt.sub}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="text-2xs text-text-muted leading-4">
                  قیمت پایانی سهم باید بالاتر از بیشترین سقف ثبت‌شده در تایم‌فریم انتخابی باشد.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-bold text-text-primary">حداقل قدرت خریدار</label>
                    <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2 py-0.5 rounded-lg border border-accent-blue/20">
                      <span className="num">{toFaDigits(config.jet.minBuyerPower.toFixed(1))}</span>
                      <span className="text-2xs">برابر</span>
                    </div>
                  </div>
                  <input
                    type="range"
                    min={1.1}
                    max={4.0}
                    step={0.1}
                    value={config.jet.minBuyerPower}
                    onChange={(e) =>
                      setConfig({
                        jet: { ...config.jet, minBuyerPower: Number(e.target.value) },
                      })
                    }
                    className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                  />
                </div>

                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-bold text-text-primary">حداقل ضریب حجم</label>
                    <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2 py-0.5 rounded-lg border border-accent-blue/20">
                      <span className="num">{toFaDigits(config.jet.minVolRatio.toFixed(1))}</span>
                      <span className="text-2xs">برابر</span>
                    </div>
                  </div>
                  <input
                    type="range"
                    min={1.5}
                    max={5.0}
                    step={0.5}
                    value={config.jet.minVolRatio}
                    onChange={(e) =>
                      setConfig({
                        jet: { ...config.jet, minVolRatio: Number(e.target.value) },
                      })
                    }
                    className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                  />
                </div>
              </div>

              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4">
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={config.jet.requireLastAboveClose}
                    onChange={(e) =>
                      setConfig({
                        jet: { ...config.jet, requireLastAboveClose: e.target.checked },
                      })
                    }
                    className="size-4 rounded accent-[#38bdf8] cursor-pointer"
                  />
                  <span className="text-xs font-bold text-text-primary">
                    آخرین معامله بالاتر یا مساوی پایانی باشد
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* تب نقطه‌زنی و کف‌یابی */}
          {activeTab === 'noqteh' && (
            <div className="space-y-5">
              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-text-primary">
                    حداکثر فاصله قیمت از کف ۳۰ روزه
                  </label>
                  <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-lg border border-accent-blue/20">
                    <span className="text-2xs text-text-muted">حداکثر:</span>
                    <span className="num">{toFaDigits(config.noqteh.maxDistPct.toFixed(1))}</span>
                    <span className="text-2xs">درصد</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={1.0}
                  max={8.0}
                  step={0.5}
                  value={config.noqteh.maxDistPct}
                  onChange={(e) =>
                    setConfig({
                      noqteh: { ...config.noqteh, maxDistPct: Number(e.target.value) },
                    })
                  }
                  className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                />
                <p className="text-2xs text-text-muted leading-4">
                  برای شناسایی سهم‌هایی که در کف حمایتی معتبر یک‌ماهه قرار دارند و ریسک افت اندکی دارند.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-1.5">
                  <label className="text-xs font-bold text-text-primary block">
                    حداقل تاییدیه حجم (ضریب به میانگین)
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0.5}
                      max={4.0}
                      step={0.2}
                      value={config.noqteh.minVolRatio}
                      onChange={(e) =>
                        setConfig({
                          noqteh: { ...config.noqteh, minVolRatio: Number(e.target.value) },
                        })
                      }
                      className="num w-full rounded-lg border border-border-c bg-bg-secondary px-3 py-2 text-xs font-bold text-text-primary focus:border-accent-blue focus:outline-none"
                    />
                    <span className="text-xs text-text-secondary shrink-0">برابر</span>
                  </div>
                </div>
                <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-1.5">
                  <label className="text-xs font-bold text-text-primary block">
                    حداقل تعداد معاملات
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={5}
                      max={100}
                      step={5}
                      value={config.noqteh.minTradeCount}
                      onChange={(e) =>
                        setConfig({
                          noqteh: { ...config.noqteh, minTradeCount: Number(e.target.value) },
                        })
                      }
                      className="num w-full rounded-lg border border-border-c bg-bg-secondary px-3 py-2 text-xs font-bold text-text-primary focus:border-accent-blue focus:outline-none"
                    />
                    <span className="text-xs text-text-secondary shrink-0">معامله</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* تب پول هوشمند */}
          {activeTab === 'smart' && (
            <div className="space-y-5">
              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-text-primary">
                    حداقل نسبت قدرت خریدار به فروشنده حقیقی
                  </label>
                  <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-lg border border-accent-blue/20">
                    <span className="text-2xs text-text-muted">حداقل:</span>
                    <span className="num">{toFaDigits(config.smartFlow.minBuyerPower.toFixed(1))}</span>
                    <span className="text-2xs">برابر</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={1.2}
                  max={5.0}
                  step={0.1}
                  value={config.smartFlow.minBuyerPower}
                  onChange={(e) =>
                    setConfig({
                      smartFlow: { ...config.smartFlow, minBuyerPower: Number(e.target.value) },
                    })
                  }
                  className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                />
              </div>

              <div className="rounded-xl border border-border-c/60 bg-bg-card/40 p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold text-text-primary">
                    حداقل ضریب حجم معاملات به میانگین ماه
                  </label>
                  <div className="flex items-center gap-1 text-xs font-black text-accent-blue bg-accent-blue/10 px-2.5 py-1 rounded-lg border border-accent-blue/20">
                    <span className="text-2xs text-text-muted">حداقل:</span>
                    <span className="num">{toFaDigits(config.smartFlow.minVolRatio.toFixed(1))}</span>
                    <span className="text-2xs">برابر</span>
                  </div>
                </div>
                <input
                  type="range"
                  min={1.0}
                  max={6.0}
                  step={0.5}
                  value={config.smartFlow.minVolRatio}
                  onChange={(e) =>
                    setConfig({
                      smartFlow: { ...config.smartFlow, minVolRatio: Number(e.target.value) },
                    })
                  }
                  className="w-full accent-[#38bdf8] cursor-pointer h-2 bg-bg-secondary rounded-lg"
                />
              </div>
            </div>
          )}
        </div>

        {/* فوتر مدال */}
        <div className="flex items-center justify-between border-t border-border-c/70 px-5 py-3.5 bg-bg-card/60 backdrop-blur">
          <button
            type="button"
            onClick={resetConfig}
            className="rounded-xl border border-border-c px-3.5 py-2 text-xs font-semibold text-text-secondary hover:border-accent-red/50 hover:text-accent-red transition-all"
          >
            بازنشانی به پیش‌فرض
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-accent-blue px-6 py-2 text-xs font-black text-white hover:opacity-90 active:scale-98 transition-all shadow-md"
          >
            تایید و بستن
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
