import clsx from 'clsx';
import {
  changePct, faNum, fmtInt, fmtMcap, fmtPe, fmtShare, fmtVolume, tone,
} from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';

const TONE = { up: 'text-up', down: 'text-down', flat: 'text-flat' } as const;

function value(input: number | null | undefined, format: (n: number) => string): string {
  return input == null || !Number.isFinite(input) ? '—' : format(input);
}

interface Stat {
  key: string;
  label: string;
  value: string;
  hint: string;
}

function statsOf(row: MarketRow): Stat[] {
  return [
    { key: 'value', label: 'ارزش معاملات', value: value(row.q_tot_cap, (n) => `${fmtMcap(n)} همت`), hint: 'ارزش معاملات امروز (q_tot_cap) به همت' },
    { key: 'volume', label: 'حجم', value: value(row.q_tot_tran, fmtVolume), hint: 'حجم معاملات امروز (q_tot_tran)' },
    { key: 'trades', label: 'تعداد معاملات', value: value(row.z_tot_tran, fmtInt), hint: 'تعداد دفعات معاملهٔ امروز (z_tot_tran)' },
    { key: 'pe', label: 'P/E', value: value(row.pe, fmtPe), hint: 'نسبت قیمت به سود هر سهم (pe)' },
    { key: 'mcap', label: 'ارزش بازار', value: value(row.mcap, (n) => `${fmtMcap(n)} همت`), hint: 'ارزش بازار (mcap) به همت' },
    {
      key: 'range',
      label: 'کف/سقف امروز',
      value: row.p_min == null && row.p_max == null
        ? '—'
        : `${value(row.p_min, fmtInt)} / ${value(row.p_max, fmtInt)}`,
      hint: 'کمترین و بیشترین قیمت امروز (p_min / p_max)',
    },
  ];
}

function pressureOf(row: MarketRow): Array<{ key: 'retail' | 'legal'; label: string; buy: number }> {
  const out: Array<{ key: 'retail' | 'legal'; label: string; buy: number }> = [];
  if (row.retail_buy_pct != null && Number.isFinite(row.retail_buy_pct)) {
    out.push({ key: 'retail', label: 'حقیقی', buy: row.retail_buy_pct });
  }
  if (row.legal_buy_pct != null && Number.isFinite(row.legal_buy_pct)) {
    out.push({ key: 'legal', label: 'حقوقی', buy: row.legal_buy_pct });
  }
  return out;
}

export function SymbolGlance({ row }: { row: MarketRow | null }) {
  if (!row) return null;
  const price = row.p_last ?? row.p_closing ?? null;
  const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
  const pressure = pressureOf(row);

  return (
    <div data-testid="symbol-glance" className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2 px-2 pt-1">
        <b data-testid="symbol-price" className="num t-125 font-extrabold text-text">{value(price, fmtInt)}</b>
        <span data-testid="symbol-pct"
          className={clsx('num t-95', pct == null ? 'text-text-3' : TONE[tone(pct)])}>
          {pct == null ? '—' : `${pct > 0 ? '▲' : pct < 0 ? '▼' : '•'} ${faNum(Math.abs(pct), 1)}٪`}
        </span>
        <span className="ms-auto t-85 text-text-3" title="این ناحیه همیشه ردیفِ فعالِ تابلو را نشان می‌دهد">
          پیروِ تابلو
        </span>
      </div>

      {pressure.length > 0 ? (
        <div data-testid="symbol-pressure" className="flex flex-col gap-1 px-2 py-0.5">
          {pressure.map((item) => {
            const buy = Math.min(100, Math.max(0, item.buy));
            return (
              <div key={item.key} data-testid={`pressure-${item.key}`}
                title={`سهمِ خریدِ ${item.label} از کلِ معاملاتِ ${item.label}`}>
                <div className="flex justify-between t-85 text-text-3">
                  <span>{item.label}</span>
                  <span className="num">{fmtShare(buy)} خرید · {fmtShare(100 - buy)} فروش</span>
                </div>
                <div className="flex h-1.5 overflow-hidden rounded-full bg-panel-3">
                  <span className="bg-up" style={{ width: `${buy}%` }} />
                  <span className="bg-down" style={{ width: `${100 - buy}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-x-3 gap-y-[2px] px-2 t-9">
        {statsOf(row).map((stat) => (
          <span key={stat.key} data-testid={`symbol-stat-${stat.key}`} title={stat.hint}
            className="flex justify-between gap-1">
            <span className="truncate text-text-3">{stat.label}</span>
            <b className="num shrink-0 text-text-2">{stat.value}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
