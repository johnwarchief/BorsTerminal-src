// features/technical/lib/tvIndicatorCatalog.ts — کاتالوگِ اندیکاتورهای آمادهٔ
// react-klinecharts-ui. این فایل عمداً هیچ پکیجی را import نمی‌کند تا
// KLineChartWrapper بتواند منو را مستقیم از همین لیست بسازد. پیش از این،
// منو داخلِ کامپوننت hardcode بود و listِ ثبت هم این‌جا؛ یک نامِ اضافه در
// منو createIndicator را روی نامِ ثبت‌نشده می‌زد و کلیک بی‌صدا هیچی
// نمی‌ساخت (همان باگی که گاردِ overlayها را ساخت).
export type TvIndicator = {
  name: string;
  label: string;
  /** روی کندل‌ها می‌نشیند؛ اگر false باشد پنلِ جدا (زیرنمودار) می‌گیرد */
  overlay: boolean;
};

/** منتخبِ سلف — همان‌ها که در نهایت‌نگار/TradingView استفادهٔ واقعی دارند */
export const TV_INDICATORS: TvIndicator[] = [
  { name: 'VWAP', label: 'میانگین وزنی حجمی (VWAP)', overlay: true },
  { name: 'SuperTrend', label: 'سوپر ترند', overlay: true },
  { name: 'Ichimoku', label: 'ایچیموکو (Ichimoku Kinko Hyo)', overlay: true },
  { name: 'MA_Ribbon', label: 'نوار میانگین‌ها (MA Ribbon)', overlay: true },
  { name: 'HMA', label: 'میانگین هال (HMA)', overlay: true },
  { name: 'PivotPoints', label: 'پیوت‌پوینت‌ها', overlay: true },
  { name: 'Stochastic', label: 'استوکستیک', overlay: false },
  { name: 'CCI_TV', label: 'CCI', overlay: false },
  { name: 'MACD_TV', label: 'MACD (نسخهٔ TV)', overlay: false },
  { name: 'RSI_TV', label: 'RSI (نسخهٔ TV)', overlay: false },
];

export const TV_INDICATOR_NAMES: string[] = TV_INDICATORS.map((i) => i.name);
