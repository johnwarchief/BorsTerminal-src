/**
 * frontend-v2/src/features/technical/ui/panels/IndicatorsPanel.tsx
 *
 * پنل کاتالوگ اندیکاتورها و مدهای معاملاتی (منتقل‌شده از کشوی میزکار عریض، بدون تغییر رفتار):
 * اندیکاتورهای هوشمند پرایس‌اکشن، اندیکاتورهای تکمیلی و کاتالوگ مرجع تلگرام.
 */

import React from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import type { ChannelMode, RsiVariant } from '../../model/types';
import { ADVANCED_INDICATORS_REGISTRY } from '../../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../../overlays/userIndicators';
import { TelegramCatalogList } from '../TelegramCatalogList';

function IndicatorRow({
  name,
  description,
  enabled,
  onToggle,
  testId,
  children,
}: {
  name: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
  testId: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-xs)] border border-line/60 bg-panel-2/40">
      <div className="flex min-h-9 items-center justify-between gap-2 px-2 py-1">
        <div className="min-w-0 flex-1">
          <div className="truncate t-10 font-medium text-text" title={name}>{name}</div>
          <div className="truncate t-85 text-text-3" title={description}>{description}</div>
        </div>
        <button
          type="button"
          data-testid={testId}
          aria-pressed={enabled}
          onClick={onToggle}
          className={`shrink-0 h-5 px-2 rounded-[var(--radius-xs)] t-85 border transition-colors ${
            enabled
              ? 'bg-accent/15 text-accent border-accent/40 font-semibold'
              : 'bg-panel text-text-3 border-line hover:text-text'
          }`}
        >
          {enabled ? 'روشن' : 'خاموش'}
        </button>
      </div>
      {children ? <div className="border-t border-line/50 px-2 py-1.5">{children}</div> : null}
    </div>
  );
}

export const IndicatorsPanel: React.FC = () => {
  const activeUserIndicators = useTechnicalStore((s) => s.activeUserIndicators);
  const toggleUserIndicator = useTechnicalStore((s) => s.toggleUserIndicator);
  const channelMode = useTechnicalStore((s) => s.channelMode);
  const setChannelMode = useTechnicalStore((s) => s.setChannelMode);
  const rsiVariant = useTechnicalStore((s) => s.rsiVariant);
  const setRsiVariant = useTechnicalStore((s) => s.setRsiVariant);
  const doubleTapProfile = useTechnicalStore((s) => s.doubleTapProfile);
  const setDoubleTapProfile = useTechnicalStore((s) => s.setDoubleTapProfile);
  const formationHorizon = useTechnicalStore((s) => s.indicatorParams.DoubleTap3D?.formationHorizon ?? 10);
  const setIndicatorParam = useTechnicalStore((s) => s.setIndicatorParam);

  return (
    <div data-testid="indicators-panel" className="p-3 flex flex-col gap-3">
      {/* بخش ۱: اندیکاتورهای جدید تلگرام (@IndicatorsforTV) */}
      <div className="flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-1.5">
          <div className="rounded-[var(--radius-xs)] border border-line bg-panel-2/50 px-2 py-1.5">
            <div className="t-8 text-text-3 mb-1">پروفایل تشخیص</div>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => setDoubleTapProfile('precision')}
                aria-pressed={doubleTapProfile === 'precision'}
                className={`flex-1 h-6 rounded-[var(--radius-xs)] t-85 transition-colors ${
                  doubleTapProfile === 'precision'
                    ? 'bg-accent/15 text-accent border border-accent/40'
                    : 'bg-panel text-text-3 border border-line hover:text-text'
                }`}
              >
                دقت بالا
              </button>
              <button
                type="button"
                onClick={() => setDoubleTapProfile('source')}
                aria-pressed={doubleTapProfile === 'source'}
                className={`flex-1 h-6 rounded-[var(--radius-xs)] t-85 transition-colors ${
                  doubleTapProfile === 'source'
                    ? 'bg-accent/15 text-accent border border-accent/40'
                    : 'bg-panel text-text-3 border border-line hover:text-text'
                }`}
              >
                منبع
              </button>
            </div>
          </div>
          <div className="rounded-[var(--radius-xs)] border border-line bg-panel-2/50 px-2 py-1.5">
            <div className="t-8 text-text-3 mb-1">افق احتمال (کندل)</div>
            <input
              type="number"
              min={5}
              max={30}
              value={formationHorizon}
              onChange={(e) => setIndicatorParam('DoubleTap3D', 'formationHorizon', Number(e.target.value))}
              className="w-full h-6 bg-panel border border-line rounded-[var(--radius-xs)] px-1 t-85 font-mono text-text text-center focus:outline-none"
            />
          </div>
        </div>
        <span className="t-10 font-bold text-accent">اندیکاتورهای هوشمند پرایس‌اکشن و الگو</span>

        {ADVANCED_INDICATORS_REGISTRY.map((ind) => {
          const isEnabled = activeUserIndicators.includes(ind.id);
          return (
            <IndicatorRow
              key={ind.id}
              name={ind.nameFa}
              description={ind.descriptionFa}
              enabled={isEnabled}
              testId={`toggle-indicator-${ind.id}`}
              onToggle={() => toggleUserIndicator(ind.id)}
            >
              {ind.id === 'MultiModeChannel' && isEnabled && (
                <div className="flex flex-col gap-1">
                  <span className="t-8 text-text-3">حالت کانال</span>
                  <div className="grid grid-cols-3 gap-1">
                    {(
                      [
                        ['regression', 'رگرسیون'],
                        ['retest_channel', 'شکست و پولبک'],
                        ['donchian', 'دانچیان'],
                      ] as Array<[ChannelMode, string]>
                    ).map(([m, label]) => (
                      <button
                        key={m}
                        type="button"
                        data-testid={`channel-mode-btn-${m}`}
                        onClick={() => setChannelMode(m)}
                        className={`h-6 px-1 rounded-[var(--radius-xs)] t-85 transition-colors ${
                          channelMode === m
                            ? 'bg-accent/15 text-accent border border-accent/40'
                            : 'bg-panel text-text-3 border border-line hover:text-text'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {ind.id === 'MultiVariantRSI' && isEnabled && (
                <div className="flex items-center justify-between gap-2">
                  <span className="t-8 text-text-3">فرمول RSI</span>
                  <select
                    data-testid="rsi-variant-select"
                    value={rsiVariant}
                    onChange={(e) => setRsiVariant(e.target.value as RsiVariant)}
                    className="bg-panel text-text border border-line rounded px-1.5 py-0.5 t-85 focus:outline-none cursor-pointer"
                  >
                    <option value="standard">استاندارد ۱۴</option>
                    <option value="fibo">فیبوناچی ۸</option>
                    <option value="bb">باند بولینگر</option>
                    <option value="smooth_ma">هموار با واگرایی</option>
                  </select>
                </div>
              )}
            </IndicatorRow>
          );
        })}
      </div>

      {/* بخش ۲: اندیکاتورهای تکمیلی و سفارشی */}
      <div className="flex flex-col gap-2 mt-2 pt-2 border-t border-line/60">
        <span className="t-10 font-bold text-accent">اندیکاتورهای تکمیلی و سفارشی</span>

        {USER_INDICATORS_REGISTRY.map((ind) => (
          <IndicatorRow
            key={ind.id}
            name={ind.nameFa}
            description={ind.descriptionFa}
            enabled={activeUserIndicators.includes(ind.id)}
            testId={`toggle-indicator-${ind.id}`}
            onToggle={() => toggleUserIndicator(ind.id)}
          />
        ))}
      </div>

      {/* بخش ۳: کاتالوگ مرجع ۶۴ اندیکاتورِ گروه indicators در تلگرام */}
      <div className="mt-2 flex flex-col gap-2 border-t border-line/60 pt-2">
        <TelegramCatalogList />
      </div>
    </div>
  );
};
