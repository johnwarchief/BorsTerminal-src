// shared/stores/signalStore.ts -- تخته اعلانات مشترک سیگنال ها
// هر ایجنت تازه ترین سیگنال هر نماد را منتشر می کند؛ مستر مصرف می کند.
import { create } from 'zustand';
import { BaseSignal, isSignalExpired, type AgentId, type AgentSignal } from '@contracts/signal';

export const BUS_AGENTS: AgentId[] = ['fundamental', 'technical', 'tape', 'portfolio'];

type Bus = Record<string, Partial<Record<AgentId, AgentSignal>>>;

type SignalBusState = {
  bus: Bus;
  /** ثبت یا جایگزینی سیگنال؛ نامعتبر رد می شود */
  publishSignal: (signal: AgentSignal) => void;
  /** ثبت دسته‌ای سیگنال‌ها در یک تراکنش واحد با بررسی تفاضلی (جلوگیری از ۳۰۰ بار رندر در ثانیه) */
  publishSignals: (signals: AgentSignal[]) => void;
  /** پاک سازی یک نماد یا کل باس */
  clearSignals: (symbol?: string) => void;
};

export const useSignalStore = create<SignalBusState>((set) => ({
  bus: {},
  publishSignal: (signal) => {
    const check = BaseSignal.safeParse(signal);
    if (!check.success) {
      if (import.meta.env.DEV) {
        console.error('[signal-bus] سیگنال نامعتبر منتشر نشد:', check.error.message);
      }
      return;
    }
    if (!signal.symbol || !BUS_AGENTS.includes(signal.agentId)) return;
    set((s) => {
      const current = s.bus[signal.symbol]?.[signal.agentId];
      if (
        current &&
        current.score === signal.score &&
        current.action === signal.action &&
        current.confidence === signal.confidence &&
        current.rationale === signal.rationale
      ) {
        return s;
      }
      return {
        bus: { ...s.bus, [signal.symbol]: { ...s.bus[signal.symbol], [signal.agentId]: signal } },
      };
    });
  },
  publishSignals: (signals) => {
    if (!signals.length) return;
    set((s) => {
      let changed = false;
      const nextBus = { ...s.bus };
      for (const signal of signals) {
        if (!signal.symbol || !BUS_AGENTS.includes(signal.agentId)) continue;
        const check = BaseSignal.safeParse(signal);
        if (!check.success) continue;

        const current = nextBus[signal.symbol]?.[signal.agentId];
        if (
          !current ||
          current.score !== signal.score ||
          current.action !== signal.action ||
          current.confidence !== signal.confidence ||
          current.rationale !== signal.rationale
        ) {
          nextBus[signal.symbol] = { ...nextBus[signal.symbol], [signal.agentId]: signal };
          changed = true;
        }
      }
      return changed ? { bus: nextBus } : s;
    });
  },
  clearSignals: (symbol) =>
    set((s) => {
      if (symbol == null) return { bus: {} };
      if (!(symbol in s.bus)) return s;
      const next = { ...s.bus };
      delete next[symbol];
      return { bus: next };
    }),
}));

/** سیگنال های غیرمنقضی یک نماد */
export function getActiveSignals(symbol: string, now = Date.now()): Partial<Record<AgentId, AgentSignal>> {
  const entry = useSignalStore.getState().bus[symbol];
  if (!entry) return {};
  const out: Partial<Record<AgentId, AgentSignal>> = {};
  for (const agent of BUS_AGENTS) {
    const s = entry[agent];
    if (s && !isSignalExpired(s, now)) out[agent] = s;
  }
  return out;
}
