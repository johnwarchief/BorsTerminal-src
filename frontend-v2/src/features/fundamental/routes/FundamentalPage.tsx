import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useScreenerCore } from '../api/useScreenerCore';
import { FundamentalDetail } from '../ui/FundamentalDetail';
import { FundamentalScreenTable } from '../ui/FundamentalScreenTable';
import { FtsSettingsTrigger } from '../ui/FtsSettingsDrawer';

export function FundamentalPage() {
  const { symbol } = useParams<{ symbol?: string }>();
  const navigate = useNavigate();
  const screener = useScreenerCore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const asOfYmd = screener.data?.as_of ? Number(screener.data.as_of.replace(/-/g, '')) : null;

  if (symbol) {
    return <FundamentalDetail symbol={symbol} onBack={() => navigate('/fundamental')} />;
  }

  return (
    <section data-testid="fundamental-page" className="flex min-h-0 flex-1 flex-col bg-bg">
      <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-line px-3 py-2">
        <b className="t-125 font-extrabold text-text">بنیادی</b>
        <span className="t-9 text-text-3">غربالگری پنج‌شاخص FTS — از جدول به کارت نماد</span>
        {screener.data?.as_of ? (
          <span data-testid="fundamental-as-of" className="num ms-auto t-85 text-text-3">
            روز تابلو: {jalaliFromYmd(asOfYmd)}
          </span>
        ) : null}
      </header>

      {screener.isLoading ? (
        <p data-testid="fundamental-table-loading" className="p-3 t-95 text-text-3">جدول بنیادی در حال خواندن…</p>
      ) : screener.isError || !screener.data ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-3 text-center">
          <p data-testid="fundamental-table-error" className="t-10 text-text-2">جدول بنیادی نیامد — /api/screener</p>
          <button type="button" onClick={() => void screener.refetch()} className="tape-btn">تلاش دوباره</button>
        </div>
      ) : (
        <FundamentalScreenTable
          rows={screener.data.data}
          asOf={screener.data.as_of}
          onSelect={(next) => navigate(`/fundamental/${next}`)}
          settingsSlot={<FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((value) => !value)} />}
        />
      )}
    </section>
  );
}
