import React, { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { FlashNum } from '@shared/components/FlashNum';

export interface DepthLevel {
  buyCount: number;
  buyVolume: number;
  buyPrice: number;
  sellPrice: number;
  sellVolume: number;
  sellCount: number;
}

export interface MarketDepthWidgetProps {
  symbol: string;
  boardRow?: {
    p_last?: number | null;
    p_closing?: number | null;
    percent_change?: number | null;
    p_min?: number | null;
    p_max?: number | null;
    price_yesterday?: number | null;
    tvol?: number | null;
    q_tot_tran?: number | null;
  } | null;
  onClose?: () => void;
  isOpen: boolean;
}

export const MarketDepthWidget: React.FC<MarketDepthWidgetProps> = ({
  symbol,
  boardRow,
  onClose,
  isOpen,
}) => {
  // توجه: هیچ return زودرسِ شرطی قبل از هوک‌ها نباشد — در غیر این صورت با
  // باز/بسته‌شدن پنل ترتیب هوک‌ها عوض و React کرش می‌کند. گِیتِ نمایش پایین انجام می‌شود.
  const basePrice = Math.round(boardRow?.p_last ?? boardRow?.p_closing ?? 10000);
  const pClosing = Math.round(boardRow?.p_closing ?? basePrice);
  const pYesterday = Math.round(boardRow?.price_yesterday ?? pClosing);
  const pMin = Math.round(boardRow?.p_min ?? Math.round(pYesterday * 0.93));
  const pMax = Math.round(boardRow?.p_max ?? Math.round(pYesterday * 1.07));

  // محاسبه ۵ ردیف مظنه با فواصل استاندارد قیمتی
  const tick = Math.max(1, Math.round(basePrice * 0.001));

  const levels: DepthLevel[] = useMemo(() => {
    const list: DepthLevel[] = [];
    const baseVol = Math.max(10000, Math.round((boardRow?.tvol ?? 500000) / 25));

    for (let i = 0; i < 5; i++) {
      const step = i;
      const bPrice = Math.max(pMin, basePrice - step * tick);
      const sPrice = Math.min(pMax, basePrice + (step + 1) * tick);
      const factor = 1 + (i * 0.35);

      list.push({
        buyCount: Math.max(1, Math.round(15 / factor) + (4 - i)),
        buyVolume: Math.round(baseVol * factor),
        buyPrice: bPrice,
        sellPrice: sPrice,
        sellVolume: Math.round(baseVol * (1.2 + i * 0.2)),
        sellCount: Math.max(1, Math.round(10 / factor) + (5 - i)),
      });
    }
    return list;
  }, [basePrice, pMin, pMax, tick, boardRow?.tvol]);

  const maxVolume = useMemo(() => {
    let m = 1;
    for (const l of levels) {
      if (l.buyVolume > m) m = l.buyVolume;
      if (l.sellVolume > m) m = l.sellVolume;
    }
    return m;
  }, [levels]);

  const totalBuyVol = levels.reduce((acc, l) => acc + l.buyVolume, 0);
  const totalSellVol = levels.reduce((acc, l) => acc + l.sellVolume, 0);
  const buyRatio = (totalBuyVol / (totalBuyVol + totalSellVol)) * 100;

  if (!isOpen) return null;

  return (
    <div
      className="market-depth-modal"
      data-testid="market-depth-widget"
      style={{
        position: 'absolute',
        top: '48px',
        left: '56px',
        zIndex: 140,
        width: '380px',
        backgroundColor: 'var(--nn-bg-secondary, #1e222d)',
        border: '1px solid var(--nn-border, #2a2e39)',
        borderRadius: '8px',
        boxShadow: '0 12px 32px rgba(0,0,0,0.65)',
        direction: 'rtl',
        fontFamily: 'Vazirmatn, sans-serif',
        overflow: 'hidden',
      }}
    >
      {/* هدر پنجره */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid var(--nn-border, #2a2e39)',
          backgroundColor: 'rgba(0,0,0,0.2)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: '800', fontSize: '13px', color: 'var(--nn-text-primary, #ffffff)' }}>
            عمق بازار — نمایش تقریبی
          </span>
          <span
            style={{
              fontSize: '10px',
              fontWeight: '700',
              padding: '1px 6px',
              borderRadius: '4px',
              backgroundColor: 'rgba(234, 179, 8, 0.18)',
              color: '#eab308',
            }}
            title="دادهٔ تفکیکی حقیقی پنج‌مظنه‌ای از تابلو در دسترس نیست؛ سطرها بر پایهٔ قیمت و حجم کل شبیه‌سازی شده‌اند و فقط نمای تقریبی‌اند."
          >
            شبیه‌سازی
          </span>
          <span
            style={{
              fontSize: '11px',
              fontWeight: '700',
              padding: '1px 6px',
              borderRadius: '4px',
              backgroundColor: 'rgba(41, 98, 255, 0.15)',
              color: '#2962ff',
            }}
          >
            {symbol}
          </span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="بستن عمق بازار"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--nn-text-secondary, #787b86)',
              cursor: 'pointer',
              fontSize: '15px',
              padding: '2px 6px',
              borderRadius: '4px',
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* سرستون‌ها */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          padding: '6px 4px',
          fontSize: '10px',
          fontWeight: '700',
          color: 'var(--nn-text-secondary, #787b86)',
          borderBottom: '1px solid var(--nn-border, #2a2e39)',
          textAlign: 'center',
          backgroundColor: 'rgba(0,0,0,0.1)',
        }}
      >
        <span>تعداد</span>
        <span>حجم خرید</span>
        <span style={{ color: '#089981' }}>قیمت خرید</span>
        <span style={{ color: '#f23645' }}>قیمت فروش</span>
        <span>حجم فروش</span>
        <span>تعداد</span>
      </div>

      {/* ردیف‌های ۵‌گانه */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {levels.map((lvl, idx) => {
          const buyBarWidth = `${Math.min(100, Math.round((lvl.buyVolume / maxVolume) * 100))}%`;
          const sellBarWidth = `${Math.min(100, Math.round((lvl.sellVolume / maxVolume) * 100))}%`;

          return (
            <div
              key={idx}
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(6, 1fr)',
                padding: '5px 4px',
                fontSize: '11px',
                textAlign: 'center',
                borderBottom: idx === 4 ? 'none' : '1px solid rgba(42, 46, 57, 0.4)',
                position: 'relative',
                fontFamily: 'monospace, Vazirmatn',
              }}
            >
              {/* بار پس‌زمینه خرید */}
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  right: '50%',
                  width: `calc(${buyBarWidth} / 2)`,
                  height: '100%',
                  backgroundColor: 'rgba(8, 153, 129, 0.12)',
                  pointerEvents: 'none',
                }}
              />
              {/* بار پس‌زمینه فروش */}
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: '50%',
                  width: `calc(${sellBarWidth} / 2)`,
                  height: '100%',
                  backgroundColor: 'rgba(242, 54, 69, 0.12)',
                  pointerEvents: 'none',
                }}
              />

              <FlashNum
                value={lvl.buyCount}
                render={(v) => toFaDigits(v ?? 0)}
                className="depth-cell"
                style={{ color: 'var(--nn-text-secondary, #787b86)' }}
              />
              <FlashNum
                value={lvl.buyVolume}
                render={(v) => fmtInt(v ?? 0)}
                className="depth-cell"
                style={{ fontWeight: '600', color: 'var(--nn-text-primary, #d1d4dc)' }}
              />
              <FlashNum
                value={lvl.buyPrice}
                render={(v) => fmtInt(v ?? 0)}
                className="depth-cell"
                style={{ fontWeight: '700', color: '#089981' }}
              />

              <FlashNum
                value={lvl.sellPrice}
                render={(v) => fmtInt(v ?? 0)}
                className="depth-cell"
                style={{ fontWeight: '700', color: '#f23645' }}
              />
              <FlashNum
                value={lvl.sellVolume}
                render={(v) => fmtInt(v ?? 0)}
                className="depth-cell"
                style={{ fontWeight: '600', color: 'var(--nn-text-primary, #d1d4dc)' }}
              />
              <FlashNum
                value={lvl.sellCount}
                render={(v) => toFaDigits(v ?? 0)}
                className="depth-cell"
                style={{ color: 'var(--nn-text-secondary, #787b86)' }}
              />
            </div>
          );
        })}
      </div>

      {/* نوار پایین: تعادل عرضه و تقاضا */}
      <div
        style={{
          padding: '8px 12px',
          borderTop: '1px solid var(--nn-border, #2a2e39)',
          backgroundColor: 'rgba(0,0,0,0.25)',
          fontSize: '11px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ color: '#089981', fontWeight: 'bold' }}>
            برآورد تقاضا: {fmtInt(totalBuyVol)} ({toFaDigits(buyRatio.toFixed(1))}٪)
          </span>
          <span style={{ color: '#f23645', fontWeight: 'bold' }}>
            برآورد عرضه: {fmtInt(totalSellVol)} ({toFaDigits((100 - buyRatio).toFixed(1))}٪)
          </span>
        </div>
        <div
          style={{
            height: '4px',
            width: '100%',
            backgroundColor: '#f23645',
            borderRadius: '2px',
            overflow: 'hidden',
            display: 'flex',
          }}
        >
          <div style={{ width: `${buyRatio}%`, backgroundColor: '#089981', height: '100%' }} />
        </div>
      </div>
    </div>
  );
};
