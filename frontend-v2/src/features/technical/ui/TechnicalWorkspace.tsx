/**
 * frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx
 *
 * میزکار پیشرفته تکنیکال و کوانت (S2 Advanced Technical Workspace):
 * - ترکیب کامل کامپوننت‌های تعاملی با استایل برنجی (Brass Theme)
 * - نوار ابزار رسم عمودی در سمت راست (DrawingToolbar)
 * - نوار کنترل‌های پیش‌بینی هوش مصنوعی Kronos/Chronos در بالای چارت (ForecastControls)
 * - هسته مرکزی چارت کانواسی KLineCharts با فریم‌ریت بالا (KLineChartWrapper)
 * - سایدبار تاشوی تحلیل لبه آماری و پرایس‌اکشن نهادی (CandleEdgeCard)
 * - هماهنگی خودکار با اندپوینت‌های بک‌اند:
 *   - GET /api/chart/{symbol}/forecast?horizon=...
 *   - GET /api/chart/{symbol}/edge
 *   - GET /api/chart/{symbol}/indicators
 */

import React, { useEffect, useContext } from 'react';
import { QueryClient, QueryClientContext, QueryClientProvider } from '@tanstack/react-query';
import { useTechnicalStore } from '../model/technicalStore';
import {
  useForecastQuery,
  useCandleEdgeQuery,
  useIndicatorsQuery,
} from '../api/useTechnicalQueries';
import { DrawingToolbar } from './DrawingToolbar';
import { ForecastControls } from './ForecastControls';
import { WideWorkspaceDrawer } from './WideWorkspaceDrawer';
import { KLineChartWrapper } from './KLineChartWrapper';

export interface TechnicalWorkspaceProps {
  symbol?: string;
  className?: string;
}

const defaultQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 60_000,
    },
  },
});

const TechnicalWorkspaceInner: React.FC<TechnicalWorkspaceProps> = ({
  symbol = 'FOOLAD',
  className = '',
}) => {
  // استور تکنیکال
  const isLeftDrawerOpen = useTechnicalStore((s) => s.isLeftDrawerOpen);
  const toggleLeftDrawer = useTechnicalStore((s) => s.toggleLeftDrawer);
  const selectedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);
  const forecastHorizon = useTechnicalStore((s) => s.forecastHorizon);
  const forecastModel = useTechnicalStore((s) => s.forecastModel);
  const adjustmentMode = useTechnicalStore((s) => s.adjustmentMode);
  const setPredictionData = useTechnicalStore((s) => s.setPredictionData);
  const setCandleEdgeData = useTechnicalStore((s) => s.setCandleEdgeData);
  const setIsLoadingForecast = useTechnicalStore((s) => s.setIsLoadingForecast);
  const setIsLoadingEdge = useTechnicalStore((s) => s.setIsLoadingEdge);

  // عدم فعال‌سازی خودکار اندیکاتورها تا چارت پیش‌فرض تمیز باشد (کاربر از دراپ‌داون بالا انتخاب می‌کند)

  const activeSymbol = symbol || selectedSymbol;

  // همگام‌سازی نماد فعال با استور
  useEffect(() => {
    if (activeSymbol && activeSymbol !== selectedSymbol) {
      setSelectedSymbol(activeSymbol);
    }
  }, [activeSymbol, selectedSymbol, setSelectedSymbol]);

  // فراخوانی اندپوینت‌های تحلیلی بک‌اند
  const forecastQuery = useForecastQuery(activeSymbol, forecastHorizon, forecastModel, adjustmentMode, Boolean(activeSymbol));
  const edgeQuery = useCandleEdgeQuery(activeSymbol, 5, Boolean(activeSymbol));
  const indicatorsQuery = useIndicatorsQuery(activeSymbol, Boolean(activeSymbol));

  // به‌روزرسانی استور با داده‌های پیش‌بینی
  useEffect(() => {
    if (forecastQuery.data) {
      setPredictionData(forecastQuery.data);
    }
    setIsLoadingForecast(forecastQuery.isLoading);
  }, [forecastQuery.data, forecastQuery.isLoading, setPredictionData, setIsLoadingForecast]);

  // به‌روزرسانی استور با داده‌های لبه آماری
  useEffect(() => {
    if (edgeQuery.data) {
      setCandleEdgeData(edgeQuery.data);
    }
    setIsLoadingEdge(edgeQuery.isLoading);
  }, [edgeQuery.data, edgeQuery.isLoading, setCandleEdgeData, setIsLoadingEdge]);

  // همگام‌سازی محاسبات شاخص‌های سرورساید
  useEffect(() => {
    if (indicatorsQuery.data) {
      // داده‌های شاخص‌های سرورساید در کش کوئری آماده است
    }
  }, [indicatorsQuery.data]);

  return (
    <div
      data-testid="technical-workspace"
      aria-label="میزکار تحلیل تکنیکال"
      className={`flex w-full h-full overflow-hidden bg-bg text-text select-none relative ${className}`}
      dir="rtl"
    >
      {/* ۱. نوار ابزار رسم عمودی در سمت راست */}
      <DrawingToolbar />

      {/* ۲. ناحیه مرکزی چارت کانواسی و کنترل‌های بالایی */}
      <div className="flex-1 flex flex-col h-full overflow-hidden border-x border-line min-w-0">
        {/* کنترل‌های بالای چارت */}
        <ForecastControls />

        {/* بستر کانواسی نمودار KLineCharts */}
        <div className="flex-1 w-full h-full relative overflow-hidden bg-bg">
          <KLineChartWrapper symbol={activeSymbol} />
        </div>
      </div>

      {/* ۳. سایدبار عریض چپ: ۵۰ نماد برتر، کاتالوگ اندیکاتورها، مدهای کانال، اسکنر و لبه آماری */}
      <WideWorkspaceDrawer
        activeSymbol={activeSymbol}
        isOpen={isLeftDrawerOpen}
        onToggleOpen={toggleLeftDrawer}
      />
    </div>
  );
};

export const TechnicalWorkspace: React.FC<TechnicalWorkspaceProps> = (props) => {
  const existingClient = useContext(QueryClientContext);
  if (!existingClient) {
    return (
      <QueryClientProvider client={defaultQueryClient}>
        <TechnicalWorkspaceInner {...props} />
      </QueryClientProvider>
    );
  }
  return <TechnicalWorkspaceInner {...props} />;
};
