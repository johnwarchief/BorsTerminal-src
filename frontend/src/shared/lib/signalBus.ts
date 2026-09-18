// shared/lib/signalBus.ts -- نقطه انتشار یکدست سیگنال در باس
import type { AgentSignal } from '@contracts/signal';
import { useSignalStore } from '@shared/stores/signalStore';

export function publishSignal(signal: AgentSignal): void {
  useSignalStore.getState().publishSignal(signal);
}

export function publishSignals(signals: AgentSignal[]): void {
  useSignalStore.getState().publishSignals(signals);
}
