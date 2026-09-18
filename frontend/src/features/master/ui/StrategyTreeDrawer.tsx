// features/master/ui/StrategyTreeDrawer.tsx -- دیاگرام درختی و تنظیمات شخصی‌سازی استراتژی ۴ مرحله‌ای FTS
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fmt';
import {
  type StrategyTreeConfig,
  DEFAULT_STRATEGY_TREES,
  loadStrategyTree,
  saveStrategyTree,
} from '../lib/strategyTree';

export function StrategyTreeDrawer({
  open,
  onClose,
  onApplyTree,
}: {
  open: boolean;
  onClose: () => void;
  onApplyTree?: (config: StrategyTreeConfig) => void;
}) {
  const [config, setConfig] = useState<StrategyTreeConfig>(loadStrategyTree);
  const [activeTab, setActiveTab] = useState<'visual' | 'advanced'>('visual');

  useEffect(() => {
    if (open) {
      setConfig(loadStrategyTree());
    }
  }, [open]);

  if (!open) return null;

  const handlePresetChange = (key: 'standard_trend' | 'fast_swing' | 'deep_hourglass') => {
    const next = { ...DEFAULT_STRATEGY_TREES[key] };
    setConfig(next);
  };

  const handleSave = () => {
    saveStrategyTree(config);
    if (onApplyTree) onApplyTree(config);
    onClose();
  };

  const handleReset = () => {
    const next = { ...DEFAULT_STRATEGY_TREES.standard_trend };
    setConfig(next);
    saveStrategyTree(next);
    if (onApplyTree) onApplyTree(next);
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="strategy-tree-title"
      className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border-c bg-bg-primary shadow-2xl"
        data-testid="strategy-tree-modal"
      >
        {/* سربرگ */}
        <div className="flex items-center justify-between border-b border-border-c/70 px-5 py-3.5 bg-bg-card/40">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-neon-cyan/20 text-sm font-black text-neon-cyan">
              🌳
            </div>
            <div>
              <h2 id="strategy-tree-title" className="text-sm font-black text-text-primary">
                شخصی‌سازی نمودار درختی استراتژی ۴ مرحله‌ای FTS
              </h2>
              <span className="text-2xs text-text-muted">
                تنظیم قواعد وتو، آستانه‌های غربالگری و مدیریت سرمایه در هر شاخه از زنجیره
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-c text-text-muted hover:border-accent-red hover:text-accent-red transition-colors"
          >
            ✕
          </button>
        </div>

        {/* تولبار پری‌ست‌ها */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-c/70 bg-bg-card/20 px-5 py-2.5">
          <div className="flex items-center gap-1.5">
            <span className="text-2xs font-bold text-text-secondary">پلن‌های الگو:</span>
            <button
              type="button"
              onClick={() => handlePresetChange('standard_trend')}
              className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-all ${
                config.presetKey === 'standard_trend'
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-[0_0_8px_rgba(56,189,248,0.2)]'
                  : 'border-border-c bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              روندی استاندارد
            </button>
            <button
              type="button"
              onClick={() => handlePresetChange('fast_swing')}
              className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-all ${
                config.presetKey === 'fast_swing'
                  ? 'border-neon-cyan bg-neon-cyan/15 text-neon-cyan shadow-[0_0_8px_rgba(6,182,212,0.2)]'
                  : 'border-border-c bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              نوسان‌گیری سریع
            </button>
            <button
              type="button"
              onClick={() => handlePresetChange('deep_hourglass')}
              className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-all ${
                config.presetKey === 'deep_hourglass'
                  ? 'border-accent-yellow bg-accent-yellow/15 text-accent-yellow shadow-[0_0_8px_rgba(234,179,8,0.2)]'
                  : 'border-border-c bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              ساعت شنی اهرمی
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab(activeTab === 'visual' ? 'advanced' : 'visual')}
              className="text-2xs font-bold text-accent-blue hover:underline"
            >
              {activeTab === 'visual' ? 'نمایش گزینه‌های پیشرفته' : 'نمایش نمودار بصری'}
            </button>
          </div>
        </div>

        {/* محتوای بدنه (نمودار بصری یا فرم پیشرفته) */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* ساختار نمودار درختی بصری */}
          <div className="rounded-2xl border border-border-c/70 bg-bg-card/20 p-4 space-y-4">
            {/* ریشه */}
            <div className="flex items-center justify-between border-b border-border-c/50 pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-blue/20 text-xs font-black text-accent-blue">
                  ۰
                </span>
                <div>
                  <div className="text-xs font-black text-text-primary">
                    ریشه تصمیم‌گیری: {config.name}
                  </div>
                  <div className="text-3xs text-text-muted">
                    ورود هر نماد از گام ۱ آغاز شده و تا تایید گام ۴ برای صدور فرمان خرید ادامه می‌یابد.
                  </div>
                </div>
              </div>
            </div>

            {/* شاخه ۱: تابلو */}
            <div className="rounded-xl border border-border-c/70 bg-bg-primary/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-neon-cyan">گام ۱: غربالگری تابلوی بازار و حجم</span>
                  <label className="flex items-center gap-1.5 text-2xs text-text-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.tape.enabled}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          tape: { ...config.tape, enabled: e.target.checked },
                        })
                      }
                      className="rounded border-border-c accent-accent-blue"
                    />
                    فعال
                  </label>
                </div>
                <span className="text-2xs text-text-muted">وزن تحلیلی: {toFaDigits(config.tape.weight)}٪</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-2xs">
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>حداقل حجم مشکوک:</span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="range"
                      min="1.0"
                      max="5.0"
                      step="0.5"
                      value={config.tape.minVolumeRatio}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          tape: { ...config.tape, minVolumeRatio: parseFloat(e.target.value) },
                        })
                      }
                      className="w-20 accent-neon-cyan"
                    />
                    <span className="font-bold text-neon-cyan">{toFaDigits(config.tape.minVolumeRatio)}×</span>
                  </div>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>الزام الگوی ساعت (آخرین &gt; پایانی):</span>
                  <input
                    type="checkbox"
                    checked={config.tape.clockPatternRequired}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        presetKey: 'custom',
                        tape: { ...config.tape, clockPatternRequired: e.target.checked },
                      })
                    }
                    className="accent-neon-cyan"
                  />
                </div>
              </div>
            </div>

            {/* شاخه ۲: تکنیکال */}
            <div className="rounded-xl border border-border-c/70 bg-bg-primary/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-accent-blue">گام ۲: تحلیل تکنیکال ۲ زمانه</span>
                  <label className="flex items-center gap-1.5 text-2xs text-text-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.technical.enabled}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          technical: { ...config.technical, enabled: e.target.checked },
                        })
                      }
                      className="rounded border-border-c accent-accent-blue"
                    />
                    فعال
                  </label>
                </div>
                <span className="text-2xs text-text-muted">وزن تحلیلی: {toFaDigits(config.technical.weight)}٪</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-2xs">
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>وتوی روند ماژور هفتگی نزولی:</span>
                  <input
                    type="checkbox"
                    checked={config.technical.weeklyUptrendVeto}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        presetKey: 'custom',
                        technical: { ...config.technical, weeklyUptrendVeto: e.target.checked },
                      })
                    }
                    className="accent-accent-blue"
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>روش تعیین حد ضرر:</span>
                  <select
                    value={config.technical.stopLossMode}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        presetKey: 'custom',
                        technical: { ...config.technical, stopLossMode: e.target.value as any },
                      })
                    }
                    className="rounded border border-border-c bg-bg-primary px-2 py-0.5 text-2xs text-text-primary"
                  >
                    <option value="fixed_5pct">۵٪ زیر ورود (نوسانی FTS)</option>
                    <option value="major_low">زیر کف ماژور (روندی FTS)</option>
                    <option value="ma14">شکست MA-14 روزانه</option>
                  </select>
                </div>
              </div>
            </div>

            {/* شاخه ۳: بنیادی */}
            <div className="rounded-xl border border-border-c/70 bg-bg-primary/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-accent-green">گام ۳: سلامت ۵ شاخص بنیادی</span>
                  <label className="flex items-center gap-1.5 text-2xs text-text-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.fundamental.enabled}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          fundamental: { ...config.fundamental, enabled: e.target.checked },
                        })
                      }
                      className="rounded border-border-c accent-accent-blue"
                    />
                    فعال
                  </label>
                </div>
                <span className="text-2xs text-text-muted">وزن تحلیلی: {toFaDigits(config.fundamental.weight)}٪</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-2xs">
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>حداقل امتیاز بنیادی مجاز:</span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="range"
                      min="1"
                      max="5"
                      step="1"
                      value={config.fundamental.minScore}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          fundamental: { ...config.fundamental, minScore: parseInt(e.target.value, 10) },
                        })
                      }
                      className="w-20 accent-accent-green"
                    />
                    <span className="font-bold text-accent-green">{toFaDigits(config.fundamental.minScore)} از ۵</span>
                  </div>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>فیلتر سخت‌گیرانه حذف نرخ‌گذاری دستوری:</span>
                  <input
                    type="checkbox"
                    checked={config.fundamental.strictPriceControlExclusion}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        presetKey: 'custom',
                        fundamental: { ...config.fundamental, strictPriceControlExclusion: e.target.checked },
                      })
                    }
                    className="accent-accent-green"
                  />
                </div>
              </div>
            </div>

            {/* شاخه ۴: مستر */}
            <div className="rounded-xl border border-border-c/70 bg-bg-primary/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-accent-yellow">گام ۴: داوری مستر و مدیریت سرمایه</span>
                  <label className="flex items-center gap-1.5 text-2xs text-text-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.master.enabled}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          master: { ...config.master, enabled: e.target.checked },
                        })
                      }
                      className="rounded border-border-c accent-accent-blue"
                    />
                    فعال
                  </label>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-2xs">
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>قانون ذخیره سود ۵۰٪ در مقاومت اول R1:</span>
                  <input
                    type="checkbox"
                    checked={config.master.halfExitAtResistance}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        presetKey: 'custom',
                        master: { ...config.master, halfExitAtResistance: e.target.checked },
                      })
                    }
                    className="accent-accent-yellow"
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border-c/50 bg-bg-secondary/40 p-2">
                  <span>وزن سرمایه در هر پله خرید:</span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="range"
                      min="2.0"
                      max="10.0"
                      step="0.5"
                      value={config.master.basePositionWeightPct}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          presetKey: 'custom',
                          master: { ...config.master, basePositionWeightPct: parseFloat(e.target.value) },
                        })
                      }
                      className="w-20 accent-accent-yellow"
                    />
                    <span className="font-bold text-accent-yellow">{toFaDigits(config.master.basePositionWeightPct)}٪</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* پاورقی و دکمه‌های ذخیره */}
        <div className="flex items-center justify-between border-t border-border-c/70 px-5 py-3 bg-bg-card/40 text-2xs">
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-border-c px-3 py-1.5 font-bold text-text-muted hover:border-accent-red hover:text-accent-red transition-colors"
          >
            بازنشانی به پیش‌فرض FTS
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border-c px-3 py-1.5 font-bold text-text-secondary hover:text-text-primary transition-colors"
            >
              انصراف
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="rounded-lg bg-accent-blue px-4 py-1.5 font-bold text-black hover:bg-accent-blue/90 transition-colors shadow-[0_0_12px_rgba(56,189,248,0.25)]"
            >
              ذخیره و اعمال بر الگوریتم
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
