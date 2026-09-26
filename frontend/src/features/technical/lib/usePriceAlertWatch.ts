// features/technical/lib/usePriceAlertWatch.ts -- نگهبانِ هشدارها روی فیدِ تازهٔ تابلو
// هر بار که ردیف‌هایِ تابلو می‌آیند، آستانه‌هایِ فعال داوری می‌شوند. شلیک
// یک‌بارمصرف است (هشدار پس از شلیک خاموش می‌شود) تا بنر هر چند ثانیه دوباره
// پرش نداشته باشد؛ کاربر با «بازنشانی» دوباره فعالش می‌کند.
import { useEffect } from 'react';
import { usePriceAlertStore } from '../stores/priceAlertStore';
import { dueAlertIds, type AlertTick } from './priceAlerts';

export function usePriceAlertWatch(rows: readonly AlertTick[] | undefined | null): void {
  const alerts = usePriceAlertStore((s) => s.alerts);
  const fire = usePriceAlertStore((s) => s.fire);

  useEffect(() => {
    if (!rows || rows.length === 0) return;
    const armed = alerts.filter((a) => a.active && a.firedAt == null);
    if (armed.length === 0) return;
    const due = dueAlertIds(armed, rows);
    if (due.length > 0) fire(due);
  }, [rows, alerts, fire]);
}
