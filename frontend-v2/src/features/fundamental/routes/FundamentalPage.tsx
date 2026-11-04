import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useScreenerCore } from '../api/useScreenerCore';
import { useFundamentalPrefs } from '../stores/prefs';
import { FundamentalDetail } from '../ui/FundamentalDetail';
import { FundamentalScreenTable } from '../ui/FundamentalScreenTable';
import { FtsSettingsTrigger } from '../ui/FtsSettingsDrawer';

/** as_of پایتون زمانِ اسکن (epoch) است، نه روز تابلو؛ برچسب باید همین را بگوید. */
function scanTimeLabel(value: string | number | null | undefined): string | null {
  if (value == null) return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Tehran',
    }).format(new Date(value * 1000));
  }
  const text = String(value).trim();
  if (!text) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return jalaliFromYmd(Number(text.replace(/-/g, '')));
  return text;
}

export function FundamentalPage() {
  const { symbol } = useParams<{ symbol?: string }>();
  const navigate = useNavigate();
  const screener = useScreenerCore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const surface = useFundamentalPrefs((state) => state.surface);
  const setSurface = useFundamentalPrefs((state) => state.setSurface);
  const scanLabel = scanTimeLabel(screener.data?.as_of);

  if (symbol) {
    return <FundamentalDetail symbol={symbol} onBack={() => navigate('/fundamental')} />;
  }

  return (
    <section
      data-testid="fundamental-page"
      data-fund-surface={surface}
      className="fundamental-surface flex min-h-0 flex-1 flex-col bg-[var(--fd-bg)] text-[var(--fd-text)]"
    >
      <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-[var(--fd-line)] px-3 py-2">
        <b className="t-125 font-extrabold text-[var(--fd-text)]">بنیادی</b>
        <span className="t-9 text-[var(--fd-text-3)]">غربالگری پنج‌محور FTS — هر ستون یک محور</span>
        <span data-testid="fundamental-as-of" className="num ms-auto t-85 text-[var(--fd-text-3)]">
          {scanLabel ? `زمان اسکن: ${scanLabel}` : ''}
        </span>
        <button
          type="button"
          data-testid="fundamental-surface-paper"
          aria-pressed={surface === 'paper'}
          onClick={() => setSurface('paper')}
          className="tape-btn"
        >
          کاغذی
        </button>
        <button
          type="button"
          data-testid="fundamental-surface-ink"
          aria-pressed={surface === 'ink'}
          onClick={() => setSurface('ink')}
          className="tape-btn"
        >
          تیره
        </button>
        {screener.isFetching && !screener.isLoading ? (
          <span data-testid="fundamental-refetching" className="t-85 text-[var(--fd-warn)]">جدول در حال بازسازی…</span>
        ) : null}
      </header>

      {screener.isLoading ? (
        <p data-testid="fundamental-table-loading" className="p-3 t-95 text-[var(--fd-text-3)]">جدول بنیادی در حال خواندن…</p>
      ) : screener.isError || !screener.data ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-3 text-center">
          <p data-testid="fundamental-table-error" className="t-10 text-[var(--fd-text-2)]">جدول بنیادی نیامد — /api/screener</p>
          <button type="button" onClick={() => void screener.refetch()} className="tape-btn">تلاش دوباره</button>
        </div>
      ) : (
        <FundamentalScreenTable
          rows={screener.data.data}
          thresholds={screener.data.thresholds}
          asOf={scanLabel}
          onSelect={(next) => navigate(`/fundamental/${next}`)}
          settingsSlot={<FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((value) => !value)} />}
        />
      )}
    </section>
  );
}
