/**
 * frontend-v2/src/features/technical/ui/CandleEdgeCard.tsx
 *
 * کارت لبه آماری، ساختار بازار و SMC (پالایش‌شده بر اساس Unslop):
 * - رنگ‌ها بر پایه توکن‌های برنجی (panel, panel-2, line, text, accent, up, down)
 * - کروم آرام بدون زرق‌وبرق نئونی و بدون گرادیان‌های رنگی اضافی
 * - اعداد جدول‌بندی‌شده (tabular-nums) در مقیاس‌های دقیق تایپوگرافی
 * - اندازه‌گذاری روی شبکه ۴px
 */

import React, { useState } from 'react';
import { toFaDigits, faNum } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import {
  getPatternExplanation,
  STATISTICAL_EDGE_EDUCATION,
} from '../model/patternGlossary';
import type { CandleEdgeReport, PriceZone } from '../model/types';

export interface CandleEdgeCardProps {
  symbol?: string;
  className?: string;
  data?: CandleEdgeReport | null;
}

export const FAMOUS_20_SYMBOLS = [
  { symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', sector: 'فلزات اساسی' },
  { symbol: 'فملی', name: 'ملی صنایع مس ایران', sector: 'فلزات اساسی' },
  { symbol: 'شستا', name: 'سرمایه‌گذاری تامین اجتماعی', sector: 'چندرشته‌ای صنعتی' },
  { symbol: 'شپنا', name: 'پالایش نفت اصفهان', sector: 'فرآورده‌های نفتی' },
  { symbol: 'شبندر', name: 'پالایش نفت بندرعباس', sector: 'فرآورده‌های نفتی' },
  { symbol: 'شتران', name: 'پالایش نفت تهران', sector: 'فرآورده‌های نفتی' },
  { symbol: 'خودرو', name: 'ایران خودرو', sector: 'خودرو و قطعات' },
  { symbol: 'خساپا', name: 'سایپا', sector: 'خودرو و قطعات' },
  { symbol: 'وبملت', name: 'بانک ملت', sector: 'بانک‌ها' },
  { symbol: 'وتجارت', name: 'بانک تجارت', sector: 'بانک‌ها' },
  { symbol: 'وبصادر', name: 'بانک صادرات ایران', sector: 'بانک‌ها' },
  { symbol: 'فارس', name: 'صنایع پتروشیمی خلیج فارس', sector: 'محصولات شیمیایی' },
  { symbol: 'تاپیکو', name: 'س. نفت و گاز و پتروشیمی تامین', sector: 'محصولات شیمیایی' },
  { symbol: 'کگل', name: 'معدنی و صنعتی گل گهر', sector: 'کانه‌های فلزی' },
  { symbol: 'کچاد', name: 'معدنی و صنعتی چادرملو', sector: 'کانه‌های فلزی' },
  { symbol: 'وغدیر', name: 'سرمایه‌گذاری غدیر', sector: 'چندرشته‌ای صنعتی' },
  { symbol: 'ومعادن', name: 'توسعه معادن و فلزات', sector: 'سرمایه‌گذاری‌ها' },
  { symbol: 'وامید', name: 'مدیریت سرمایه‌گذاری امید', sector: 'چندرشته‌ای صنعتی' },
  { symbol: 'رمپنا', name: 'گروه مپنا', sector: 'خدمات مهندسی' },
  { symbol: 'پارس', name: 'پتروشیمی پارس', sector: 'محصولات شیمیایی' },
];

export const CandleEdgeCard: React.FC<CandleEdgeCardProps> = ({
  symbol,
  className = '',
  data: propData,
}) => {
  const storeData = useTechnicalStore((s) => s.candleEdgeData);
  const isLoading = useTechnicalStore((s) => s.isLoadingEdge);
  const showSMCZones = useTechnicalStore((s) => s.showSMCZones);
  const toggleSMCZones = useTechnicalStore((s) => s.toggleSMCZones);
  const selectedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);
  const corporateEvents = useTechnicalStore((s) => s.corporateEvents);

  const activeSymbol = symbol || selectedSymbol;
  const edge = propData ?? storeData;
  const [activeTab, setActiveTab] = useState<'edge' | 'symbols' | 'smc'>('edge');
  const [symbolFilter, setSymbolFilter] = useState('');
  const [isGuideOpen, setIsGuideOpen] = useState(false);

  if (isLoading && !edge) {
    return (
      <div
        data-testid="candle-edge-card"
        className={`flex flex-col gap-3 p-3 bg-panel border border-line rounded-[var(--radius-md)] text-text-3 ${className}`}
        dir="rtl"
      >
        <div className="h-5 bg-panel-2 rounded-[var(--radius-xs)] w-1/2" />
        <div className="h-16 bg-panel-2 rounded-[var(--radius-xs)]" />
        <div className="h-20 bg-panel-2 rounded-[var(--radius-xs)]" />
        <div className="h-24 bg-panel-2 rounded-[var(--radius-xs)]" />
      </div>
    );
  }

  const winRate1 = edge ? Math.round(edge.winRate1Bar * 100) : 54;
  const winRate3 = edge ? Math.round(edge.winRate3Bar * 100) : 61;
  const winRate5 = edge ? Math.round(edge.winRate5Bar * 100) : 58;
  const profitFactor = edge ? edge.profitFactor : 1.65;
  const riskReward = edge ? edge.riskRewardRatio : 1.8;
  const sampleCount = edge ? edge.sampleCount : 240;
  const marketRegime = edge ? edge.marketRegime : 'TRENDING_BULL';
  const patternName = edge?.patternName || 'Hammer';
  const activeZones = edge?.activeZones || [];

  const patternEdu = getPatternExplanation(patternName);

  const renderRegimeBadge = () => {
    switch (marketRegime) {
      case 'TRENDING_BULL':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--radius-xs)] text-xs font-medium bg-panel-3 text-up border border-line">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
              <polyline points="17 6 23 6 23 12" />
            </svg>
            روند صعودی
          </span>
        );
      case 'TRENDING_BEAR':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--radius-xs)] text-xs font-medium bg-panel-3 text-down border border-line">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
              <polyline points="17 18 23 18 23 12" />
            </svg>
            روند نزولی
          </span>
        );
      case 'RANGING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--radius-xs)] text-xs font-medium bg-panel-3 text-text-2 border border-line">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
            بدون روند (رنج)
          </span>
        );
    }
  };

  return (
    <div
      data-testid="candle-edge-card"
      aria-label="کارت لبه آماری و پرایس‌اکشن"
      className={`flex flex-col gap-2.5 p-3 bg-panel border border-line rounded-[var(--radius-md)] text-text select-none ${className}`}
      dir="rtl"
    >
      {/* تب‌های سایدبار هوشمند */}
      <div
        data-testid="sidebar-tabs"
        className="flex items-center bg-panel-2 p-0.5 rounded-[var(--radius-sm)] border border-line shrink-0"
      >
        <button
          type="button"
          data-testid="tab-edge-btn"
          onClick={() => setActiveTab('edge')}
          className={`flex-1 py-1 text-center text-xs font-medium rounded-[var(--radius-xs)] transition-colors ${
            activeTab === 'edge' ? 'bg-panel-3 text-accent font-semibold shadow-xs' : 'text-text-3 hover:text-text'
          }`}
        >
          لبه و الگو
        </button>
        <button
          type="button"
          data-testid="tab-symbols-btn"
          onClick={() => setActiveTab('symbols')}
          className={`flex-1 py-1 text-center text-xs font-medium rounded-[var(--radius-xs)] transition-colors ${
            activeTab === 'symbols' ? 'bg-panel-3 text-accent font-semibold shadow-xs' : 'text-text-3 hover:text-text'
          }`}
        >
          ۲۰ نماد برتر
        </button>
        <button
          type="button"
          data-testid="tab-smc-btn"
          onClick={() => setActiveTab('smc')}
          className={`flex-1 py-1 text-center text-xs font-medium rounded-[var(--radius-xs)] transition-colors ${
            activeTab === 'smc' ? 'bg-panel-3 text-accent font-semibold shadow-xs' : 'text-text-3 hover:text-text'
          }`}
        >
          زون‌های SMC
        </button>
      </div>

      {/* محتوای تب ۱: لبه آماری و الگو */}
      {activeTab === 'edge' && (
        <div className="flex flex-col gap-2.5">
          {/* سربرگ کارت */}
          <div className="flex items-center justify-between border-b border-line pb-2">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-text">
                لبه آماری و SMC ({activeSymbol})
              </h3>
          <button
            type="button"
            data-testid="toggle-guide-btn"
            onClick={() => setIsGuideOpen(!isGuideOpen)}
            className={`h-5 px-1.5 rounded-[var(--radius-xs)] text-xs font-medium border transition-colors duration-150 flex items-center gap-1 ${
              isGuideOpen
                ? 'bg-panel-3 text-accent border-accent/40'
                : 'bg-panel-2 text-text-3 border-line hover:text-text'
            }`}
            title="راهنمای مفاهیم آماری، نرخ برد و روانشناسی الگوها"
          >
            <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>راهنما (؟)</span>
          </button>
        </div>
        {renderRegimeBadge()}
      </div>

      {/* پنل آموزشی تاشوی معامله‌گر */}
      {isGuideOpen && (
        <div
          data-testid="traders-guide-panel"
          className="bg-panel-2 border border-accent/30 rounded-[var(--radius-sm)] p-2.5 flex flex-col gap-2 text-xs"
        >
          <div className="flex items-center justify-between border-b border-line pb-1 text-accent font-bold">
            <span>کالبدشکافی الگوی {patternEdu.nameFa}</span>
            <span className="text-xs text-text-3 font-normal">({patternEdu.typeFa})</span>
          </div>

          {/* روانشناسی الگو */}
          <p className="text-text-2 leading-relaxed text-xs">
            {patternEdu.psychologyFa}
          </p>

          {/* توصیه عملی معامله‌گر */}
          <div className="bg-panel p-1.5 rounded-[var(--radius-xs)] border border-line flex items-center gap-1.5 text-text-3">
            <span className="text-accent font-semibold shrink-0">توصیه:</span>
            <span>{patternEdu.adviceFa}</span>
          </div>

          <div className="border-t border-line/60 pt-1.5 flex flex-col gap-1.5">
            <div>
              <span className="font-semibold text-text-2 block mb-0.5">
                {STATISTICAL_EDGE_EDUCATION.winRateFa.titleFa}:
              </span>
              <p className="text-text-3 leading-relaxed text-xs">
                {STATISTICAL_EDGE_EDUCATION.winRateFa.explanationFa}
              </p>
            </div>

            <div>
              <span className="font-semibold text-text-2 block mb-0.5">
                {STATISTICAL_EDGE_EDUCATION.profitFactorFa.titleFa} و {STATISTICAL_EDGE_EDUCATION.riskRewardFa.titleFa}:
              </span>
              <p className="text-text-3 leading-relaxed text-xs">
                {STATISTICAL_EDGE_EDUCATION.profitFactorFa.explanationFa}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ۱. الگوی اخیر */}
      <div className="bg-panel-2 border border-line rounded-[var(--radius-sm)] p-2.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-3">الگوی اخیر:</span>
          <span
            data-testid="active-pattern-badge"
            className={`font-medium px-2 py-0.5 rounded-[var(--radius-xs)] text-xs bg-panel-3 border border-line ${
              patternEdu.isBullish ? 'text-up' : 'text-down'
            }`}
          >
            {patternEdu.nameFa}
          </span>
        </div>
        <p className="text-xs text-text-3 leading-relaxed mt-1.5 pt-1.5 border-t border-line/60">
          {patternEdu.psychologyFa}
        </p>
        <div className="flex items-center justify-between text-xs text-text-3 mt-1.5 pt-1 border-t border-line/40">
          <span>نمونه‌های آماری:</span>
          <span className="text-text-2 num">
            {toFaDigits(sampleCount)} کندل
          </span>
        </div>
      </div>

      {/* ۲. نرخ برد تاریخی (Win Rate) */}
      <div className="bg-panel-2 border border-line rounded-[var(--radius-sm)] p-2.5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-xs font-bold text-text-2">
            نرخ برد تاریخی الگو (Win Rate)
          </div>
          <span className="text-xs text-text-3" title={STATISTICAL_EDGE_EDUCATION.winRateFa.explanationFa}>
            احتمال رشد قیمت
          </span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-center">
          <div className="bg-panel border border-line rounded-[var(--radius-xs)] p-1.5">
            <span className="text-xs text-text-3 block mb-0.5">۱ کندل بعد</span>
            <span
              className={`text-xs font-bold num ${
                winRate1 >= 50 ? 'text-up' : 'text-down'
              }`}
            >
              {toFaDigits(winRate1)}٪
            </span>
            <div className="w-full bg-panel-3 rounded-full h-1 mt-1 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  winRate1 >= 50 ? 'bg-up' : 'bg-down'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, winRate1))}%` }}
              />
            </div>
          </div>

          <div className="bg-panel border border-line rounded-[var(--radius-xs)] p-1.5">
            <span className="text-xs text-text-3 block mb-0.5">۳ کندل بعد</span>
            <span
              className={`text-xs font-bold num ${
                winRate3 >= 50 ? 'text-up' : 'text-down'
              }`}
            >
              {toFaDigits(winRate3)}٪
            </span>
            <div className="w-full bg-panel-3 rounded-full h-1 mt-1 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  winRate3 >= 50 ? 'bg-up' : 'bg-down'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, winRate3))}%` }}
              />
            </div>
          </div>

          <div className="bg-panel border border-line rounded-[var(--radius-xs)] p-1.5">
            <span className="text-xs text-text-3 block mb-0.5">۵ کندل بعد</span>
            <span
              className={`text-xs font-bold num ${
                winRate5 >= 50 ? 'text-up' : 'text-down'
              }`}
            >
              {toFaDigits(winRate5)}٪
            </span>
            <div className="w-full bg-panel-3 rounded-full h-1 mt-1 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  winRate5 >= 50 ? 'bg-up' : 'bg-down'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, winRate5))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ۳. فاکتور سود و نسبت ریسک به ریوارد */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-panel-2 border border-line rounded-[var(--radius-sm)] p-2">
          <span className="text-xs text-text-3 block mb-0.5">فاکتور سود (PF)</span>
          <div className="flex items-baseline gap-1">
            <span
              className={`t-125 font-bold num ${
                profitFactor >= 1.5
                  ? 'text-up'
                  : profitFactor >= 1.0
                  ? 'text-accent'
                  : 'text-down'
              }`}
            >
              {faNum(profitFactor, 2)}
            </span>
            <span className="text-xs text-text-3">
              {profitFactor >= 1.5 ? '(عالی)' : profitFactor >= 1 ? '(مطلوب)' : '(ضعیف)'}
            </span>
          </div>
        </div>

        <div className="bg-panel-2 border border-line rounded-[var(--radius-sm)] p-2">
          <span className="text-xs text-text-3 block mb-0.5">نسبت سود/زیان (R/R)</span>
          <div className="flex items-baseline gap-1">
            <span className="t-125 font-bold num text-text">
              ۱ : {faNum(riskReward, 2)}
            </span>
          </div>
        </div>
      </div>

      {/* ۴. زون‌های فعال نقدینگی و SMC */}
      <div className="bg-panel-2 border border-line rounded-[var(--radius-sm)] p-2.5">
        <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-line">
          <span className="text-xs font-bold text-text-2">
            زون‌های نقدینگی (SMC)
          </span>

          <button
            type="button"
            role="switch"
            aria-checked={showSMCZones}
            onClick={toggleSMCZones}
            className={`h-5 px-2 rounded-[var(--radius-xs)] text-xs font-medium border transition-colors duration-150 flex items-center gap-1 ${
              showSMCZones
                ? 'bg-panel-3 text-accent border-accent/40'
                : 'bg-panel text-text-3 border-line hover:text-text'
            }`}
          >
            <span>{showSMCZones ? 'روشن' : 'خاموش'}</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                showSMCZones ? 'bg-accent' : 'bg-line-strong'
              }`}
            />
          </button>
        </div>

        {activeZones.length === 0 ? (
          <p className="text-xs text-text-3 text-center py-2">
            هیچ زون فعال مصرف‌نشده‌ای یافت نشد
          </p>
        ) : (
          <div className="flex flex-col gap-1 max-h-36 overflow-y-auto">
            {activeZones.slice(0, 4).map((zone: PriceZone) => (
              <div
                key={zone.id}
                className="flex items-center justify-between p-1 rounded-[var(--radius-xs)] bg-panel border border-line/60 text-xs"
              >
                <div className="flex items-center gap-1.5">
                  <span className="px-1 rounded-[var(--radius-xs)] text-xs num bg-panel-3 border border-line text-text-3">
                    {zone.type}
                  </span>
                  <span
                    className={`font-medium ${
                      zone.isBullish ? 'text-up' : 'text-down'
                    }`}
                  >
                    {zone.isBullish ? 'صعودی' : 'نزولی'}
                  </span>
                </div>

                <div className="text-left num text-xs text-text-2">
                  <span>{toFaDigits(Math.round(zone.bottom).toLocaleString('fa-IR'))}</span>
                  <span className="text-text-3 mx-1">-</span>
                  <span>{toFaDigits(Math.round(zone.top).toLocaleString('fa-IR'))}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
        </div>
      )}

      {/* محتوای تب ۲: دیده‌بان ۲۰ نماد شاخص با ناوبری و انتخاب سریع */}
      {activeTab === 'symbols' && (
        <div data-testid="famous-symbols-watchlist" className="flex flex-col gap-2">
          <div className="flex items-center justify-between border-b border-line pb-1.5">
            <span className="text-xs font-bold text-text">دیده‌بان ۲۰ نماد شاخص</span>
            <span className="text-xs text-text-3">انتخاب سریع</span>
          </div>

          {/* فیلتر جستجو درون ۲۰ نماد */}
          <div className="relative">
            <input
              type="text"
              data-testid="symbols-search-input"
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              placeholder="فیلتر نماد یا صنعت..."
              className="w-full h-6 px-2 bg-panel-2 rounded-[var(--radius-xs)] border border-line text-text text-xs focus:outline-none focus:border-accent"
            />
          </div>

          {/* لیست نمادها */}
          <div className="flex flex-col gap-1 max-h-[460px] overflow-y-auto">
            {FAMOUS_20_SYMBOLS.filter(
              (item) =>
                !symbolFilter ||
                item.symbol.includes(symbolFilter) ||
                item.name.includes(symbolFilter) ||
                item.sector.includes(symbolFilter)
            ).map((item) => {
              const isCurrent = item.symbol === activeSymbol;
              return (
                <button
                  key={item.symbol}
                  type="button"
                  data-testid={`symbol-item-${item.symbol}`}
                  onClick={() => {
                    setSelectedSymbol(item.symbol);
                    window.location.hash = `#/technical/${encodeURIComponent(item.symbol)}`;
                  }}
                  className={`flex items-center justify-between p-1.5 rounded-[var(--radius-xs)] border text-right transition-colors ${
                    isCurrent
                      ? 'bg-panel-3 border-accent/60 text-accent font-bold'
                      : 'bg-panel-2 border-line/50 text-text-2 hover:bg-panel-3 hover:text-text'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="text-xs font-bold">{item.symbol}</span>
                    <span className="text-xs text-text-3 truncate max-w-[140px]">{item.name}</span>
                  </div>
                  <span className="text-xs px-1.5 py-0.5 rounded-[var(--radius-xs)] bg-panel border border-line/60 text-text-3">
                    {item.sector}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* محتوای تب ۳: جدول بازرسی زون‌های SMC نهادی */}
      {activeTab === 'smc' && (
        <div data-testid="institutional-smc-panel" className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-line pb-1.5">
            <span className="text-xs font-bold text-text">زون‌های نقدینگی و SMC</span>
            <button
              type="button"
              role="switch"
              aria-checked={showSMCZones}
              onClick={toggleSMCZones}
              className={`h-5 px-2 rounded-[var(--radius-xs)] text-xs font-medium border transition-colors duration-150 flex items-center gap-1 ${
                showSMCZones
                  ? 'bg-panel-3 text-accent border-accent/40'
                  : 'bg-panel text-text-3 border-line hover:text-text'
              }`}
            >
              <span>{showSMCZones ? 'روشن' : 'خاموش'}</span>
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  showSMCZones ? 'bg-accent' : 'bg-line-strong'
                }`}
              />
            </button>
          </div>

          <p className="text-xs text-text-3 leading-relaxed">
            نواحی عدم تعادل (FVG) و بلوک‌های سفارش (Order Block) با خط تعادل ۵۰٪ و رهگیری مصرف‌شدگی.
          </p>

          {activeZones.length === 0 ? (
            <p className="text-xs text-text-3 text-center py-4 bg-panel-2 rounded-[var(--radius-xs)] border border-line">
              هیچ زون فعال مصرف‌نشده‌ای یافت نشد
            </p>
          ) : (
            <div className="flex flex-col gap-1.5 max-h-[440px] overflow-y-auto">
              {activeZones.map((zone: PriceZone) => (
                <div
                  key={zone.id}
                  className="flex flex-col gap-1 p-2 rounded-[var(--radius-xs)] bg-panel-2 border border-line/70 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="px-1.5 py-0.5 rounded-[var(--radius-xs)] text-xs font-mono font-bold bg-panel-3 border border-line text-accent">
                        {zone.type}
                      </span>
                      <span
                        className={`font-semibold ${
                          zone.isBullish ? 'text-up' : 'text-down'
                        }`}
                      >
                        {zone.isBullish ? 'تقاضا (Demand)' : 'عرضه (Supply)'}
                      </span>
                    </div>

                    <span
                      className={`text-xs px-1.5 py-0.5 rounded-[var(--radius-xs)] border ${
                        zone.mitigated
                          ? 'border-line text-text-3 bg-panel'
                          : 'border-emerald-500/40 text-emerald-400 bg-emerald-950/30 font-semibold'
                      }`}
                    >
                      {zone.mitigated ? 'مصرف‌شده' : 'فعال'}
                    </span>
                  </div>

                  {/* محدوده و ۵۰٪ تعادل */}
                  <div className="flex items-center justify-between pt-1 border-t border-line/40 text-xs text-text-3">
                    <span>محدوده:</span>
                    <span className="num text-text-2">
                      {toFaDigits(Math.round(zone.bottom).toLocaleString('fa-IR'))} - {toFaDigits(Math.round(zone.top).toLocaleString('fa-IR'))} ریال
                    </span>
                  </div>

                  {zone.equilibrium ? (
                    <div className="flex items-center justify-between text-xs text-text-3">
                      <span>تعادل (۵۰٪ EQ):</span>
                      <span className="num font-semibold text-accent">
                        {toFaDigits(Math.round(zone.equilibrium).toLocaleString('fa-IR'))} ریال
                      </span>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}

          {/* بخش رویدادهای شرکتی و مجمع نماد */}
          <div data-testid="corporate-events-section" className="flex flex-col gap-2 pt-2 border-t border-line">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text">رویدادهای شرکتی و مجمع</span>
              <span className="text-xs text-text-3 num">{toFaDigits(corporateEvents.length)} رویداد</span>
            </div>

            {corporateEvents.length === 0 ? (
              <p className="text-xs text-text-3 text-center py-2 bg-panel-2 rounded-[var(--radius-xs)] border border-line">
                رویداد مجمع یا افزایش سرمایه برای این نماد ثبت نشده است
              </p>
            ) : (
              <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
                {corporateEvents.map((ev, idx) => {
                  const isShareChange = ev.type === 'shareChange' || ev.kind === 'E';
                  const label = isShareChange ? 'افزایش سرمایه' : 'سود نقدی مجمع';
                  return (
                    <div
                      key={`${ev.date}-${idx}`}
                      className="flex items-center justify-between p-1.5 rounded-[var(--radius-xs)] bg-panel-2 border border-line/70 text-xs"
                    >
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-5 h-5 rounded flex items-center justify-center font-bold text-xs ${
                            isShareChange
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          }`}
                        >
                          {isShareChange ? 'E' : 'D'}
                        </span>
                        <div className="flex flex-col">
                          <span className="font-semibold text-text">{label}</span>
                          <span className="text-xs text-text-3 num">{toFaDigits(ev.date)}</span>
                        </div>
                      </div>

                      <div className="text-left num text-xs text-text-2">
                        {ev.from != null && ev.to != null ? (
                          <span>
                            {toFaDigits(ev.from)} ➔ {toFaDigits(ev.to)}
                          </span>
                        ) : ev.source ? (
                          <span className="text-text-3">{ev.source}</span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
