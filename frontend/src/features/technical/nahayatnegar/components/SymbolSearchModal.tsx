import React, { useState, useEffect } from 'react';
import { IconSearch, IconClose, IconCheck } from './TradingViewIcons';
import { matchFa } from '@shared/lib/normalizeFa';

export interface SymbolInfo {
  symbol: string;
  name: string;
  market: string;
  lastPrice?: number;
  changePercent?: number;
}

interface SymbolSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSymbol: (sym: SymbolInfo) => void;
  currentSymbol?: string;
}

export const SymbolSearchModal: React.FC<SymbolSearchModalProps> = ({
  isOpen,
  onClose,
  onSelectSymbol,
  currentSymbol
}) => {
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'bourse' | 'fara' | 'funds'>('all');
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // واکشی داده‌های زنده نمادها از اندپوینت‌های بک‌اند پروژه
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setIsLoading(true);

    const fetchMarketSymbols = async () => {
      try {
        // ابتدا تلاش برای دریافت از /api/market
        const res = await fetch('/api/market');
        if (res.ok) {
          const json = await res.json();
          const items = Array.isArray(json) ? json : (json.data || json.symbols || json.rows || []);
          if (Array.isArray(items) && items.length > 0) {
            const mapped: SymbolInfo[] = items.map((it: any) => ({
              symbol: String(it.symbol || it.ticker || it.l18 || ''),
              name: String(it.name || it.title || it.l30 || it.symbol || ''),
              market: String(it.market || (it.flow_title?.includes('فرابورس') ? 'فرابورس' : 'بورس') || 'بورس'),
              lastPrice: Number(it.last_price || it.pl || it.close || 0),
              changePercent: Number(it.change_percent || it.plp || 0)
            })).filter(s => s.symbol.length > 0);

            if (isMounted) {
              setSymbols(mapped);
              setIsLoading(false);
              return;
            }
          }
        }

        // اگر /api/market موجود نبود، تلاش از /api/screener
        const resScreener = await fetch('/api/screener');
        if (resScreener.ok) {
          const json = await resScreener.json();
          const items = Array.isArray(json) ? json : (json.data || json.rows || []);
          if (Array.isArray(items) && items.length > 0) {
            const mapped: SymbolInfo[] = items.map((it: any) => ({
              symbol: String(it.symbol || it.ticker || ''),
              name: String(it.name || it.title || it.symbol || ''),
              market: String(it.market || 'بورس'),
              lastPrice: Number(it.close || it.last || 0),
              changePercent: Number(it.change || 0)
            })).filter(s => s.symbol.length > 0);

            if (isMounted) {
              setSymbols(mapped);
              setIsLoading(false);
              return;
            }
          }
        }
      } catch {
        // عدم پرتاب خطا؛ در صورت نبود شبکه لیست خالی می‌ماند
      }

      if (isMounted) {
        setIsLoading(false);
      }
    };

    fetchMarketSymbols();

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // فیلتر کردن نمادها بر اساس جستجو و تب فعال
  const filtered = symbols.filter(s => {
    const matchQuery = matchFa(s.symbol, query) || matchFa(s.name, query);
    if (!matchQuery) return false;

    if (activeTab === 'bourse') return s.market.includes('بورس') && !s.market.includes('فرابورس');
    if (activeTab === 'fara') return s.market.includes('فرابورس');
    if (activeTab === 'funds') return s.market.includes('صندوق') || s.name.includes('صندوق');
    return true;
  });

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        direction: 'rtl'
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '540px',
          maxWidth: '92vw',
          backgroundColor: 'var(--nn-bg-secondary)',
          border: '1px solid var(--nn-border)',
          borderRadius: '8px',
          boxShadow: 'var(--glass-shadow)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* نوار کادر جستجو */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--nn-border)', gap: '10px' }}>
          <IconSearch size={18} color="var(--nn-text-secondary)" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجوی نماد یا نام شرکت..."
            autoFocus
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'var(--nn-text-primary)',
              fontSize: '14px',
              outline: 'none',
              fontFamily: 'inherit'
            }}
          />
          {query && (
            <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', color: 'var(--nn-text-secondary)', cursor: 'pointer' }}>
              <IconClose size={14} />
            </button>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--nn-text-secondary)', cursor: 'pointer' }}>
            <IconClose size={18} />
          </button>
        </div>

        {/* دسته‌بندی بازارها */}
        <div style={{ display: 'flex', padding: '0 16px', gap: '8px', borderBottom: '1px solid var(--nn-border)', backgroundColor: 'var(--nn-bg-primary)' }}>
          {[
            { id: 'all', label: 'همه نمادها' },
            { id: 'bourse', label: 'سهام بورس' },
            { id: 'fara', label: 'فرابورس' },
            { id: 'funds', label: 'صندوق‌ها' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as never)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid var(--nn-bg-active)' : '2px solid transparent',
                color: activeTab === tab.id ? 'var(--nn-text-active)' : 'var(--nn-text-secondary)',
                padding: '8px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                fontWeight: activeTab === tab.id ? 'bold' : 'normal'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* لیست نمادها */}
        <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
          {/* گزینه ثابت شاخص کل بورس (TEDPIX) */}
          <div
            onClick={() => {
              onSelectSymbol({ symbol: 'شاخص کل', name: 'شاخص کل بورس تهران', market: 'بورس' });
              onClose();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 16px',
              borderBottom: '1px solid var(--nn-border)',
              cursor: 'pointer',
              backgroundColor: currentSymbol === 'شاخص کل' ? 'rgba(41, 98, 255, 0.12)' : 'transparent'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 'bold', color: '#ffab00', fontSize: '13px' }}>شاخص کل</span>
              <span style={{ color: 'var(--nn-text-secondary)', fontSize: '12px' }}>نمای کلان بازار سرمایه (TEDPIX)</span>
            </div>
            <span style={{ fontSize: '11px', color: '#ffab00' }}>شاخص کل</span>
          </div>

          {isLoading ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--nn-text-secondary)', fontSize: '13px' }}>
              در حال دریافت فهرست نمادها...
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--nn-text-secondary)', fontSize: '13px' }}>
              {query ? 'نمادی با این عنوان یافت نشد.' : 'داده‌ای در دسترس نیست.'}
            </div>
          ) : (
            filtered.map(s => {
              const isSelected = currentSymbol === s.symbol;
              const isUp = (s.changePercent ?? 0) >= 0;

              return (
                <div
                  key={s.symbol}
                  onClick={() => {
                    onSelectSymbol(s);
                    onClose();
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 16px',
                    borderBottom: '1px solid var(--nn-border)',
                    cursor: 'pointer',
                    backgroundColor: isSelected ? 'rgba(41, 98, 255, 0.12)' : 'transparent',
                    transition: 'background-color 0.1s'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--nn-bg-hover)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 'bold', color: 'var(--nn-text-primary)', fontSize: '14px' }}>{s.symbol}</span>
                    <span style={{ color: 'var(--nn-text-secondary)', fontSize: '12px' }}>{s.name}</span>
                    <span
                      style={{
                        fontSize: '10px',
                        backgroundColor: s.market.includes('فرابورس') ? 'rgba(255, 171, 0, 0.15)' : 'rgba(41, 98, 255, 0.15)',
                        color: s.market.includes('فرابورس') ? '#ffab00' : 'var(--nn-text-active)',
                        padding: '1px 5px',
                        borderRadius: '3px'
                      }}
                    >
                      {s.market}
                    </span>
                  </div>

                  <div style={{ textAlign: 'left', direction: 'ltr', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {s.lastPrice ? (
                      <span style={{ color: 'var(--nn-text-primary)', fontSize: '13px' }}>
                        {s.lastPrice.toLocaleString('fa-IR')}
                      </span>
                    ) : null}

                    {s.changePercent !== undefined && (
                      <span style={{ color: isUp ? '#089981' : '#f23645', fontSize: '11px', fontWeight: 'bold' }}>
                        {isUp ? '+' : ''}{s.changePercent.toFixed(2)}%
                      </span>
                    )}

                    {isSelected && <IconCheck size={14} color="#2962ff" />}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
