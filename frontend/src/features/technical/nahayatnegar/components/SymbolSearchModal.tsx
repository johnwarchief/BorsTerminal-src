import React, { useState } from 'react';

export interface SymbolInfo {
  symbol: string;
  name: string;
  market: string;
  lastPrice: number;
  changePercent: number;
}

interface SymbolSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSymbol: (symbol: SymbolInfo) => void;
}

const DEFAULT_SYMBOLS: SymbolInfo[] = [
  { symbol: 'خودرو', name: 'ایران خودرو', market: 'بورس', lastPrice: 3120, changePercent: 1.45 },
  { symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', market: 'بورس', lastPrice: 5620, changePercent: -0.85 },
  { symbol: 'فملی', name: 'ملی صنایع مس ایران', market: 'بورس', lastPrice: 7890, changePercent: 2.10 },
  { symbol: 'وبصادر', name: 'بانک صادرات ایران', market: 'بورس', lastPrice: 1980, changePercent: 0.50 },
  { symbol: 'اهرم', name: 'صندوق اهرمی کاریزما', market: 'فرابورس', lastPrice: 2240, changePercent: 3.20 },
  { symbol: 'شستا', name: 'سرمایه گذاری تامین اجتماعی', market: 'بورس', lastPrice: 1350, changePercent: -0.20 },
  { symbol: 'خساپا', name: 'سایپا', market: 'بورس', lastPrice: 2450, changePercent: 1.10 }
];

export const SymbolSearchModal: React.FC<SymbolSearchModalProps> = ({ isOpen, onClose, onSelectSymbol }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'stock' | 'etf' | 'index'>('all');

  if (!isOpen) return null;

  const filtered = DEFAULT_SYMBOLS.filter(s =>
    s.symbol.includes(searchTerm) || s.name.includes(searchTerm)
  );

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
      backgroundColor: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(3px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
      direction: 'rtl', fontFamily: 'Vazirmatn, sans-serif'
    }} onClick={onClose}>
      <div style={{
        width: '540px', background: '#1e222d', border: '1px solid #2a2e39',
        borderRadius: '8px', boxShadow: '0 16px 40px rgba(0, 0, 0, 0.7)',
        overflow: 'hidden', display: 'flex', flexDirection: 'column'
      }} onClick={e => e.stopPropagation()}>
        {/* Header Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid #2a2e39', gap: '10px' }}>
          <span style={{ color: '#787b86', fontSize: '16px' }}>🔍</span>
          <input
            type="text"
            placeholder="جستجوی نماد یا نام شرکت..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            autoFocus
            style={{
              flex: 1, background: 'transparent', border: 'none', color: '#fff',
              fontSize: '14px', outline: 'none', fontFamily: 'inherit'
            }}
          />
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#787b86', cursor: 'pointer', fontSize: '16px' }}>✕</button>
        </div>

        {/* Filter Tabs */}
        <div style={{ display: 'flex', padding: '0 16px', gap: '8px', borderBottom: '1px solid #2a2e39', background: '#181b24' }}>
          {[
            { id: 'all', label: 'همه' },
            { id: 'stock', label: 'سهام' },
            { id: 'etf', label: 'صندوق‌ها (ETF)' },
            { id: 'index', label: 'شاخص‌ها' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as never)}
              style={{
                background: 'none', border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid #2962ff' : '2px solid transparent',
                color: activeTab === tab.id ? '#2962ff' : '#787b86',
                padding: '8px 10px', fontSize: '12px', cursor: 'pointer', fontWeight: activeTab === tab.id ? 'bold' : 'normal'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Results List */}
        <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
          {filtered.map(item => (
            <div
              key={item.symbol}
              onClick={() => {
                onSelectSymbol(item);
                onClose();
              }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 16px', borderBottom: '1px solid #242832', cursor: 'pointer',
                transition: 'background 0.1s'
              }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#2a2e39')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontWeight: 'bold', fontSize: '13px', color: '#fff' }}>{item.symbol}</span>
                <span style={{ color: '#787b86', fontSize: '12px' }}>{item.name}</span>
                <span style={{ fontSize: '10px', background: 'rgba(41,98,255,0.15)', color: '#2962ff', padding: '1px 5px', borderRadius: '3px' }}>{item.market}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '13px', color: '#d1d4dc' }}>{item.lastPrice.toLocaleString()}</span>
                <span style={{
                  fontSize: '12px', fontWeight: 'bold', minWidth: '55px', textAlign: 'left',
                  color: item.changePercent >= 0 ? '#089981' : '#f23645'
                }}>
                  {item.changePercent >= 0 ? `+${item.changePercent}%` : `${item.changePercent}%`}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
