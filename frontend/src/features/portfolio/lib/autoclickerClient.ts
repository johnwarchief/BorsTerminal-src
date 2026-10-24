// features/portfolio/lib/autoclickerClient.ts — درِ AutoClickerِ Round 22
//
// همهٔ فراخوانی‌ها از `http` رد می‌شوند (fetch بیرون از shared/api ممنوع است).
// `retries: 0` رویِ POSTها عمدی است: «شروع/توقف/مسلح‌کردن» عملیاتِ دارایِ اثرِ
// جانبی است و تکرارِ خودکارِ یک POSTِ ناموفق می‌تواند سفارشِ دوم بسازد.
import { http } from '@shared/api/http';

const BASE = '/api/execution/autoclicker';

export interface FactView {
  status: string;
  detail?: string;
  source?: string;
  label?: string;
}

export interface PreviewView {
  symbol?: string;
  side?: string;
  expected_price?: number;
  expected_quantity?: number;
  mode?: string;
  total_actions?: number;
  interval_ms?: number;
  timezone?: string;
  target_at_local?: string;
  planned_first_at_local?: string;
  planned_last_at_local?: string;
  max_orders_possible?: number;
  total_shares_possible?: number;
  max_gross_value_rial?: number;
  dry_run?: boolean;
  live_confirmed?: boolean;
  hard_ceiling?: number;
  warning?: string;
}

export interface ActionView {
  idx: number;
  state: string;
  planned_at_ms?: number;
  fired_at_ms?: number | null;
  result?: Record<string, unknown>;
}

export interface RunView {
  run_id: string;
  state: string;
  fired_actions: number;
  config: Record<string, unknown>;
  preview: PreviewView;
  actions?: ActionView[];
}

export interface AutoClickerStateView {
  status: string;
  app_version?: string;
  facts: Record<string, FactView>;
  fact_order: string[];
  run: RunView | null;
  preflight?: Record<string, unknown>;
  panel?: { ticket_active?: boolean; asset?: boolean; path?: string };
  host?: { healthy?: boolean; status?: string };
  session?: { state?: string };
  ceiling?: { max_actions?: number; min_interval_ms?: number; note?: string };
  timezone?: { name?: string; now_local?: string };
}

export interface CreateRunBody {
  symbol: string;
  isin?: string;
  side: 'buy' | 'sell';
  expected_price: number;
  expected_quantity: number;
  target_at: string;
  mode: 'single' | 'repeat';
  total_actions: number;
  interval_ms: number;
  dry_run: boolean;
}

export type ApiReply = Record<string, unknown> & { status?: string };

function post(path: string, body: unknown = {}): Promise<ApiReply> {
  return http<ApiReply>(`${BASE}${path}`, { method: 'POST', body, retries: 0 });
}

export const autoclickerApi = {
  state: (runId = '') =>
    http<AutoClickerStateView>(
      `${BASE}/state${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`,
      { noCache: true },
    ),
  createRun: (body: CreateRunBody) => post('/run', body),
  check: () => post('/check'),
  arm: () => post('/arm'),
  start: () => post('/start'),
  stop: () => post('/stop'),
  reset: () => post('/reset'),
  openPanel: () => post('/panel/open', {}),
};
