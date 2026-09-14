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
    set((s) => ({
      bus: { ...s.bus, [signal.symbol]: { ...s.bus[signal.symbol], [signal.agentId]: signal } },
    }));
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
