/**
 * frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx
 *
 * ستون عریض میزکارهای متنوع در سمت چپ چارت (Wide Workspace Drawer):
 * ۱. جدول ۵۰ نماد برتر بازار بر پایه حجم و ارزش معاملات (Top 50 Market Symbols) با امکان سوییچ فوری چارت
 * ۲. کاتالوگ اندیکاتورها و سوئیچرهای مد (Double Tap 3D, SuperTrend Pullback, CHoCH, Multi-Mode Channel)
 * ۳. انتخاب‌گر دراپ‌داون خانواده چندگانه RSI (استاندارد، فیبوناچی ۸، باندهای بولینگر، آراس‌آی هموار)
 * ۴. اسکنر زنده الگوهای کلاسیک و ساختار بازار (Double Tap W/M, Pullback, CHoCH)
 * ۵. پنل تحلیل لبه آماری و پرایس‌اکشن نهادی (CandleEdgeCard)
 * ۶. قابلیت تغییر عرض پویا (۴۲۰ تا ۶۴۰ پیکسل) و پشتیبانی از پورتال React (createPortal)
 */

import React, { useState, useMemo, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { toFaDigits } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { useBoard } from '@features/market/api/useBoard';
import { useTechnicalStore } from '../model/technicalStore';
import type { ChannelMode, RsiVariant, DrawerTab } from '../model/types';
import { ADVANCED_INDICATORS_REGISTRY } from '../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../overlays/userIndicators';
import { CandleEdgeCard } from './CandleEdgeCard';
import { classifyAssetType } from '@features/market/lib/assetType';
import { useUiStore } from '@shared/stores/uiStore';

export interface WideWorkspaceDrawerProps {
  activeSymbol: string;
  isOpen: boolean;
  onToggleOpen: () => void;
  className?: string;
}

const FALLBACK_TOP_SYMBOLS: Array<Partial<MarketRow>> = [
  { symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', sector_name: 'فلزات اساسی', p_last: 5850, percent_last: 2.45, q_tot_cap: 850_000_000_000, tvol: 145_000_000, buyer_power: 1.45 },
  { symbol: 'فملی', name: 'ملی صنایع مس ایران', sector_name: 'فلزات اساسی', p_last: 7420, percent_last: 1.82, q_tot_cap: 720_000_000_000, tvol: 97_000_000, buyer_power: 1.32 },
  { symbol: 'شپنا', name: 'پالایش نفت اصفهان', sector_name: 'فرآورده‌های نفتی', p_last: 4610, percent_last: -0.65, q_tot_cap: 610_000_000_000, tvol: 132_000_000, buyer_power: 0.92 },
  { symbol: 'شستا', name: 'سرمایه‌گذاری تامین اجتماعی', sector_name: 'سرمایه‌گذاری‌ها', p_last: 1190, percent_last: 3.12, q_tot_cap: 580_000_000_000, tvol: 487_000_000, buyer_power: 1.68 },
  { symbol: 'خودرو', name: 'ایران خودرو', sector_name: 'خودرو و قطعات', p_last: 2980, percent_last: 4.95, q_tot_cap: 540_000_000_000, tvol: 181_000_000, buyer_power: 2.10 },
  { symbol: 'خساپا', name: 'سایپا', sector_name: 'خودرو و قطعات', p_last: 2450, percent_last: 4.88, q_tot_cap: 490_000_000_000, tvol: 200_000_000, buyer_power: 1.95 },
  { symbol: 'وبملت', name: 'بانک ملت', sector_name: 'بانک‌ها و موسسات', p_last: 2320, percent_last: 1.15, q_tot_cap: 450_000_000_000, tvol: 194_000_000, buyer_power: 1.20 },
  { symbol: 'شتران', name: 'پالایش نفت تهران', sector_name: 'فرآورده‌های نفتی', p_last: 3120, percent_last: -1.25, q_tot_cap: 390_000_000_000, tvol: 125_000_000, buyer_power: 0.85 },
  { symbol: 'تجارت', name: 'بانک تجارت', sector_name: 'بانک‌ها و موسسات', p_last: 1890, percent_last: 0.55, q_tot_cap: 340_000_000_000, tvol: 180_000_000, buyer_power: 1.10 },
  { symbol: 'ذوب', name: 'ذوب آهن اصفهان', sector_name: 'فلزات اساسی', p_last: 380, percent_last: 2.15, q_tot_cap: 310_000_000_000, tvol: 815_000_000, buyer_power: 1.38 },
  { symbol: 'فارس', name: 'صنایع پتروشیمی خلیج فارس', sector_name: 'محصولات شیمیایی', p_last: 11200, percent_last: 1.45, q_tot_cap: 295_000_000_000, tvol: 26_000_000, buyer_power: 1.18 },
  { symbol: 'شپدیس', name: 'پتروشیمی پردیس', sector_name: 'محصولات شیمیایی', p_last: 154000, percent_last: 0.85, q_tot_cap: 280_000_000_000, tvol: 1_800_000, buyer_power: 1.25 },
  { symbol: 'پارسان', name: 'گسترش نفت و گاز پارسیان', sector_name: 'محصولات شیمیایی', p_last: 23400, percent_last: -0.42, q_tot_cap: 265_000_000_000, tvol: 11_300_000, buyer_power: 0.98 },
  { symbol: 'تاپیکو', name: 'سرمایه‌گذاری نفت و گاز و پتروشیمی تامین', sector_name: 'محصولات شیمیایی', p_last: 16800, percent_last: 1.10, q_tot_cap: 250_000_000_000, tvol: 14_800_000, buyer_power: 1.15 },
  { symbol: 'وبصادر', name: 'بانک صادرات ایران', sector_name: 'بانک‌ها و موسسات', p_last: 1950, percent_last: 2.10, q_tot_cap: 240_000_000_000, tvol: 123_000_000, buyer_power: 1.35 },
  { symbol: 'کگل', name: 'معدنی و صنعتی گل گهر', sector_name: 'استخراج کانه‌های فلزی', p_last: 4980, percent_last: 0.65, q_tot_cap: 230_000_000_000, tvol: 46_000_000, buyer_power: 1.05 },
  { symbol: 'کچاد', name: 'معدنی و صنعتی چادرملو', sector_name: 'استخراج کانه‌های فلزی', p_last: 5320, percent_last: 1.25, q_tot_cap: 220_000_000_000, tvol: 41_000_000, buyer_power: 1.22 },
  { symbol: 'نوری', name: 'پتروشیمی نوری', sector_name: 'محصولات شیمیایی', p_last: 189000, percent_last: 2.80, q_tot_cap: 210_000_000_000, tvol: 1_100_000, buyer_power: 1.60 },
  { symbol: 'شبندر', name: 'پالایش نفت بندرعباس', sector_name: 'فرآورده‌های نفتی', p_last: 8950, percent_last: -0.75, q_tot_cap: 205_000_000_000, tvol: 22_900_000, buyer_power: 0.88 },
  { symbol: 'وغدیر', name: 'سرمایه‌گذاری غدیر', sector_name: 'سرمایه‌گذاری‌ها', p_last: 19800, percent_last: 0.95, q_tot_cap: 195_000_000_000, tvol: 9_800_000, buyer_power: 1.08 },
  { symbol: 'حکشتی', name: 'کشتیرانی جمهوری اسلامی ایران', sector_name: 'حمل و نقل', p_last: 12300, percent_last: 3.45, q_tot_cap: 190_000_000_000, tvol: 15_400_000, buyer_power: 1.55 },
  { symbol: 'همراه', name: 'ارتباطات سیار ایران', sector_name: 'مخابرات', p_last: 4420, percent_last: 0.45, q_tot_cap: 185_000_000_000, tvol: 41_800_000, buyer_power: 1.02 },
  { symbol: 'رمپنا', name: 'گروه مپنا', sector_name: 'خدمات فنی و مهندسی', p_last: 10450, percent_last: 1.65, q_tot_cap: 180_000_000_000, tvol: 17_200_000, buyer_power: 1.28 },
  { symbol: 'آریا', name: 'پلیمر آریا ساسول', sector_name: 'محصولات شیمیایی', p_last: 98000, percent_last: 1.95, q_tot_cap: 175_000_000_000, tvol: 1_780_000, buyer_power: 1.40 },
  { symbol: 'زاگرس', name: 'پتروشیمی زاگرس', sector_name: 'محصولات شیمیایی', p_last: 118000, percent_last: -1.15, q_tot_cap: 170_000_000_000, tvol: 1_440_000, buyer_power: 0.82 },
  { symbol: 'اخابر', name: 'مخابرات ایران', sector_name: 'مخابرات', p_last: 8950, percent_last: 2.15, q_tot_cap: 165_000_000_000, tvol: 18_400_000, buyer_power: 1.30 },
  { symbol: 'شپاس', name: 'نفت پاسارگاد', sector_name: 'فرآورده‌های نفتی', p_last: 38900, percent_last: 4.85, q_tot_cap: 160_000_000_000, tvol: 4_100_000, buyer_power: 2.05 },
  { symbol: 'وبانک', name: 'سرمایه‌گذاری گروه توسعه ملی', sector_name: 'سرمایه‌گذاری‌ها', p_last: 9450, percent_last: 0.75, q_tot_cap: 155_000_000_000, tvol: 16_400_000, buyer_power: 1.10 },
  { symbol: 'وصندوق', name: 'سرمایه‌گذاری صندوق بازنشستگی', sector_name: 'سرمایه‌گذاری‌ها', p_last: 14200, percent_last: -0.35, q_tot_cap: 150_000_000_000, tvol: 10_500_000, buyer_power: 0.94 },
  { symbol: 'شیراز', name: 'پتروشیمی شیراز', sector_name: 'محصولات شیمیایی', p_last: 29500, percent_last: 1.35, q_tot_cap: 145_000_000_000, tvol: 4_900_000, buyer_power: 1.18 },
  { symbol: 'وامید', name: 'گروه مدیریت سرمایه‌گذاری امید', sector_name: 'سرمایه‌گذاری‌ها', p_last: 13800, percent_last: 0.85, q_tot_cap: 140_000_000_000, tvol: 10_100_000, buyer_power: 1.05 },
  { symbol: 'فخوز', name: 'فولاد خوزستان', sector_name: 'فلزات اساسی', p_last: 3450, percent_last: 1.85, q_tot_cap: 135_000_000_000, tvol: 39_100_000, buyer_power: 1.32 },
  { symbol: 'فاسمین', name: 'کالسیمین', sector_name: 'فلزات اساسی', p_last: 6200, percent_last: 2.45, q_tot_cap: 130_000_000_000, tvol: 20_900_000, buyer_power: 1.42 },
  { symbol: 'جم', name: 'پتروشیمی جم', sector_name: 'محصولات شیمیایی', p_last: 48900, percent_last: 0.95, q_tot_cap: 125_000_000_000, tvol: 2_550_000, buyer_power: 1.12 },
  { symbol: 'مارون', name: 'پتروشیمی مارون', sector_name: 'محصولات شیمیایی', p_last: 148000, percent_last: -0.65, q_tot_cap: 120_000_000_000, tvol: 810_000, buyer_power: 0.90 },
  { symbol: 'کرماشا', name: 'صنایع پتروشیمی کرمانشاه', sector_name: 'محصولات شیمیایی', p_last: 67500, percent_last: 1.15, q_tot_cap: 115_000_000_000, tvol: 1_700_000, buyer_power: 1.16 },
  { symbol: 'پاکشو', name: 'گروه صنعتی پاکشو', sector_name: 'محصولات شیمیایی', p_last: 7850, percent_last: 3.10, q_tot_cap: 110_000_000_000, tvol: 14_000_000, buyer_power: 1.58 },
  { symbol: 'شفن', name: 'پتروشیمی فن آوران', sector_name: 'محصولات شیمیایی', p_last: 34200, percent_last: -1.45, q_tot_cap: 105_000_000_000, tvol: 3_070_000, buyer_power: 0.80 },
  { symbol: 'تیپیکو', name: 'سرمایه‌گذاری دارویی تامین', sector_name: 'مواد دارویی', p_last: 21200, percent_last: 2.75, q_tot_cap: 100_000_000_000, tvol: 4_710_000, buyer_power: 1.45 },
  { symbol: 'تاصیکو', name: 'سرمایه‌گذاری صدر تامین', sector_name: 'سرمایه‌گذاری‌ها', p_last: 11400, percent_last: 1.65, q_tot_cap: 98_000_000_000, tvol: 8_590_000, buyer_power: 1.25 },
  { symbol: 'بترانس', name: 'ایران ترانسفو', sector_name: 'دستگاه‌های برقی', p_last: 2950, percent_last: 4.90, q_tot_cap: 95_000_000_000, tvol: 32_200_000, buyer_power: 2.12 },
  { symbol: 'خپارس', name: 'پارس خودرو', sector_name: 'خودرو و قطعات', p_last: 1420, percent_last: 4.80, q_tot_cap: 92_000_000_000, tvol: 64_700_000, buyer_power: 1.90 },
  { symbol: 'خگستر', name: 'گسترش سرمایه‌گذاری ایران خودرو', sector_name: 'سرمایه‌گذاری‌ها', p_last: 3820, percent_last: 4.92, q_tot_cap: 90_000_000_000, tvol: 23_500_000, buyer_power: 2.15 },
  { symbol: 'برکت', name: 'گروه دارویی برکت', sector_name: 'مواد دارویی', p_last: 7420, percent_last: 1.25, q_tot_cap: 88_000_000_000, tvol: 11_800_000, buyer_power: 1.15 },
  { symbol: 'وسپهر', name: 'سرمایه‌گذاری گروه مالی سپهر صادرات', sector_name: 'سرمایه‌گذاری‌ها', p_last: 5320, percent_last: 0.95, q_tot_cap: 85_000_000_000, tvol: 15_900_000, buyer_power: 1.08 },
  { symbol: 'وخارزم', name: 'سرمایه‌گذاری خوارزمی', sector_name: 'سرمایه‌گذاری‌ها', p_last: 3120, percent_last: 2.05, q_tot_cap: 82_000_000_000, tvol: 26_200_000, buyer_power: 1.30 },
  { symbol: 'بپیوند', name: 'برق و انرژی پیوند گستر پارس', sector_name: 'عرضه برق و گاز', p_last: 19800, percent_last: 1.45, q_tot_cap: 80_000_000_000, tvol: 4_040_000, buyer_power: 1.20 },
  { symbol: 'غکورش', name: 'صنعت غذایی کورش', sector_name: 'محصولات غذایی', p_last: 9850, percent_last: 0.65, q_tot_cap: 78_000_000_000, tvol: 7_910_000, buyer_power: 1.04 },
  { symbol: 'افق', name: 'فروشگاه‌های زنجیره‌ای افق کوروش', sector_name: 'خرده‌فروشی', p_last: 18200, percent_last: 1.85, q_tot_cap: 75_000_000_000, tvol: 4_120_000, buyer_power: 1.35 },
  { symbol: 'فولاژ', name: 'فولاد آلیاژی ایران', sector_name: 'فلزات اساسی', p_last: 8950, percent_last: 2.10, q_tot_cap: 72_000_000_000, tvol: 8_040_000, buyer_power: 1.30 },
];

export type AssetCategoryFilter = 'all' | 'stock' | 'right' | 'fund' | 'payeh' | 'bond';

export const ASSET_FILTER_OPTIONS: Array<{ id: AssetCategoryFilter; labelFa: string }> = [
  { id: 'all', labelFa: 'همه' },
  { id: 'stock', labelFa: 'سهام عادی' },
  { id: 'right', labelFa: 'حق تقدم' },
  { id: 'fund', labelFa: 'صندوق‌ها' },
  { id: 'payeh', labelFa: 'بازار پایه' },
  { id: 'bond', labelFa: 'اوراق بدهی' },
];

export interface SymbolSignalInfo {
  text: string;
  badgeClass: string;
  title: string;
}

export function getSymbolSignal(
  row: Partial<MarketRow>,
  isSelected: boolean,
  patterns: any[],
  pullbacks: any[],
  chochs: any[],
  isLight: boolean
): SymbolSignalInfo {
  if (isSelected) {
    if (patterns && patterns.length > 0) {
      const p = patterns[0];
      const isTop = p.type === 'DOUBLE_TOP';
      return {
        text: isTop ? 'سقف M' : 'کف W',
        badgeClass: isTop
          ? (isLight ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-rose-500/15 text-rose-400')
          : (isLight ? 'bg-cyan-50 text-cyan-700 border border-cyan-200' : 'bg-cyan-500/15 text-cyan-400'),
        title: `${isTop ? 'الگوی سقف دوقلو M' : 'الگوی کف دوقلو W'} با امتیاز ${toFaDigits(p.score ?? 85)}٪`,
      };
    }
    if (pullbacks && pullbacks.length > 0) {
      const pb = pullbacks[0];
      const isBull = pb.type === 'BULLISH';
      return {
        text: isBull ? 'پولبک خرید' : 'پولبک فروش',
        badgeClass: isBull
          ? (isLight ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-emerald-500/15 text-emerald-400')
          : (isLight ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-rose-500/15 text-rose-400'),
        title: `سیگنال سوپرترند پولبک با کیفیت ${toFaDigits(pb.qualityScore ?? 80)}٪`,
      };
    }
    if (chochs && chochs.length > 0) {
      const ch = chochs[0];
      return {
        text: ch.isBullish ? 'CHoCH صعودی' : 'CHoCH نزولی',
        badgeClass: ch.isBullish
          ? (isLight ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-emerald-500/15 text-emerald-400')
          : (isLight ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-rose-500/15 text-rose-400'),
        title: `شکست ساختار CHoCH در قیمت ${toFaDigits(Math.round(ch.brokenPrice ?? 0))}`,
      };
    }
  }

  const bp = row.buyer_power ?? 1.0;
  const pct = row.percent_last ?? row.percent_change ?? 0;
  const volRatio = row.vol_ratio ?? row.vol_ratio_file ?? 1.0;

  if (row.f_smart || bp >= 1.6) {
    return {
      text: 'پول هوشمند',
      badgeClass: isLight
        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
        : 'bg-emerald-500/15 text-emerald-400',
      title: `ورود پول هوشمند با قدرت خریدار ${toFaDigits(bp.toFixed(2))}`,
    };
  }

  if (row.f_noqteh || row.f_roobi) {
    return {
      text: 'چرخش ساختار',
      badgeClass: isLight
        ? 'bg-cyan-50 text-cyan-700 border border-cyan-200'
        : 'bg-cyan-500/15 text-cyan-400',
      title: 'سیگنال چرخش ساختار و نقطه عطف روند',
    };
  }

  if (row.f_jet || volRatio >= 2.0) {
    return {
      text: 'شکست حجم',
      badgeClass: isLight
        ? 'bg-purple-50 text-purple-700 border border-purple-200'
        : 'bg-purple-500/15 text-purple-400',
      title: `جهش حجم معاملات ${toFaDigits(volRatio.toFixed(1))} برابر میانگین ماهانه`,
    };
  }

  if (bp >= 1.25 && pct > 1.2) {
    return {
      text: 'پولبک صعودی',
      badgeClass: isLight
        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
        : 'bg-emerald-500/15 text-emerald-400',
      title: 'حرکت مثبت در امتداد پولبک صعودی',
    };
  }

  if (bp <= 0.8 && pct < -1.2) {
    return {
      text: 'فشار عرضه',
      badgeClass: isLight
        ? 'bg-rose-50 text-rose-700 border border-rose-200'
        : 'bg-rose-500/15 text-rose-400',
      title: 'برتری قدرت فروشندگان و فشار منفی',
    };
  }

  return {
    text: 'خنثی',
    badgeClass: isLight
      ? 'bg-slate-100 text-slate-500 border border-slate-200'
      : 'bg-gray-500/10 text-gray-400',
    title: 'بدون سیگنال قطعی در معاملات روز جاری',
  };
}

export const WideWorkspaceDrawer: React.FC<WideWorkspaceDrawerProps> = ({
  activeSymbol,
  isOpen,
  onToggleOpen,
  className = '',
}) => {
  const activeTab = useTechnicalStore((s) => s.activeDrawerTab);
  const setActiveTab = useTechnicalStore((s) => s.setActiveDrawerTab);
  const drawerWidth = useTechnicalStore((s) => s.leftDrawerWidth);
  const setDrawerWidth = useTechnicalStore((s) => s.setLeftDrawerWidth);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);

  const activeUserIndicators = useTechnicalStore((s) => s.activeUserIndicators);
  const toggleUserIndicator = useTechnicalStore((s) => s.toggleUserIndicator);
  const channelMode = useTechnicalStore((s) => s.channelMode);
  const setChannelMode = useTechnicalStore((s) => s.setChannelMode);
  const rsiVariant = useTechnicalStore((s) => s.rsiVariant);
  const setRsiVariant = useTechnicalStore((s) => s.setRsiVariant);

  const detectedDoubleTapPatterns = useTechnicalStore((s) => s.detectedDoubleTapPatterns);
  const detectedPullbackSignals = useTechnicalStore((s) => s.detectedPullbackSignals);
  const detectedCHoCHSignals = useTechnicalStore((s) => s.detectedCHoCHSignals);

  const [symbolSearchQuery, setSymbolSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AssetCategoryFilter>('all');
  const [isPortalModalOpen, setIsPortalModalOpen] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const resizerRef = useRef<HTMLDivElement>(null);

  const theme = useUiStore((s) => s.theme);
  const isLight = theme === 'warm' || theme === 'cool';

  // واکشی داده‌های زنده تابلو
  const boardQuery = useBoard(10_000);

  // ۵۰ نماد برتر بازار
  const top50Symbols: Array<Partial<MarketRow>> = useMemo(() => {
    const rawRows = boardQuery.data?.data;
    if (rawRows && rawRows.length > 0) {
      const sorted = [...rawRows].sort((a, b) => (b.q_tot_cap ?? 0) - (a.q_tot_cap ?? 0));
      return sorted.slice(0, 50);
    }
    return FALLBACK_TOP_SYMBOLS;
  }, [boardQuery.data]);

  // فیلتر دسته‌بندی و جستجو میان نمادهای برتر
  const filteredSymbols = useMemo(() => {
    let list = top50Symbols;
    if (selectedCategory !== 'all') {
      list = list.filter((s) => {
        const cat = classifyAssetType(s);
        return cat === selectedCategory;
      });
    }
    const q = symbolSearchQuery.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (s) =>
        (s.symbol && s.symbol.toLowerCase().includes(q)) ||
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.sector_name && s.sector_name.toLowerCase().includes(q))
    );
  }, [top50Symbols, selectedCategory, symbolSearchQuery]);

  // سوییچ سریع نماد در چارت و نوار آدرس
  const handleSelectSymbol = useCallback(
    (sym: string) => {
      setSelectedSymbol(sym);
      if (typeof window !== 'undefined') {
        window.location.hash = `#/technical/${encodeURIComponent(sym)}`;
      }
    },
    [setSelectedSymbol]
  );

  // درگ و تغییر عرض کشویی سایدبار (حرکت به سمت راست عرض را افزایش و به سمت چپ کاهش می‌دهد)
  const handleMouseDownResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      const startX = e.clientX;
      const startWidth = drawerWidth;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        setDrawerWidth(startWidth + delta);
      };

      const handleMouseUp = () => {
        setIsResizing(false);
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [drawerWidth, setDrawerWidth]
  );

  // دکمه‌های ناوبری تب‌ها
  const TABS: Array<{ id: DrawerTab; labelFa: string; badge?: string | number }> = [
    { id: 'top50', labelFa: '۵۰ نماد برتر', badge: top50Symbols.length },
    { id: 'indicators', labelFa: 'اندیکاتورها و کانال' },
    { id: 'scanner', labelFa: 'اسکنر الگوها', badge: detectedDoubleTapPatterns.length + detectedPullbackSignals.length },
    { id: 'edge', labelFa: 'لبه آماری' },
  ];

  // محتوای مرکزی داخل کشو
  const drawerContent = (
    <div
      data-testid="wide-workspace-drawer"
      aria-label="میزکار عریض تکنیکال و بازار"
      className="flex flex-col h-full bg-panel text-text overflow-hidden select-none"
      dir="rtl"
    >
      {/* سربرگ سایدبار عریض با کنترل‌های تب و دکمه پورتال */}
      <header className="flex flex-col border-b border-line bg-panel-2/60 shrink-0">
        <div className="flex items-center justify-between px-3 py-2 border-b border-line/60">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <h2 className="t-11 font-bold text-accent">میزکار جامع تحلیل و کشف فرصت</h2>
          </div>

          <div className="flex items-center gap-1">
            {/* دکمه پاپ‌اوت به پورتال شناور */}
            <button
              type="button"
              data-testid="portal-modal-btn"
              onClick={() => setIsPortalModalOpen(true)}
              title="باز کردن در پنجره شناور (React Portal)"
              aria-label="باز کردن در پنجره شناور"
              className="p-1 text-text-3 hover:text-accent rounded-[var(--radius-xs)] hover:bg-panel transition-colors"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </button>

            {/* دکمه بستن/جمع کردن سایدبار */}
            <button
              type="button"
              data-testid="close-drawer-btn"
              onClick={onToggleOpen}
              title={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
              aria-label={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
              className="p-1 text-text-3 hover:text-text rounded-[var(--radius-xs)] hover:bg-panel transition-colors"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* نوار تب‌های میزکار */}
        <div className="flex items-center gap-1 px-2 py-1 overflow-x-auto" role="tablist">
          {TABS.map((tab) => {
            const isTabActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                data-testid={`drawer-tab-${tab.id}`}
                aria-selected={isTabActive}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-sm)] t-95 font-medium transition-colors shrink-0 ${
                  isTabActive
                    ? 'bg-panel-3 text-accent border border-accent/30 font-semibold shadow-xs'
                    : 'text-text-3 hover:text-text hover:bg-panel'
                }`}
              >
                <span>{tab.labelFa}</span>
                {tab.badge !== undefined && (
                  <span
                    className={`t-85 px-1 py-0.2 rounded-full font-mono ${
                      isTabActive ? 'bg-accent/20 text-accent font-bold' : 'bg-panel-3 text-text-3'
                    }`}
                  >
                    {toFaDigits(tab.badge)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* ناحیه محتوای تب‌ها */}
      <div className="flex-1 overflow-y-auto min-h-0 relative">
        {/* ۱. تب ۵۰ نماد برتر بازار */}
        {activeTab === 'top50' && (
          <div data-testid="top50-panel" className="p-2 flex flex-col gap-2">
            {/* دسته‌بندی نمادها (سهام عادی، حق تقدم، صندوق‌ها، بازار پایه، اوراق) */}
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5" role="radiogroup" aria-label="دسته‌بندی نمادها">
              {ASSET_FILTER_OPTIONS.map((cat) => {
                const isCatActive = selectedCategory === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    data-testid={`category-filter-${cat.id}`}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`px-2 py-0.5 rounded-[var(--radius-xs)] t-85 font-medium transition-colors shrink-0 ${
                      isCatActive
                        ? 'bg-accent/15 text-accent border border-accent/40 font-bold'
                        : 'bg-panel-2 text-text-3 border border-line hover:text-text hover:bg-panel-3'
                    }`}
                  >
                    {cat.labelFa}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1.5 bg-panel-2 px-2 py-1 rounded-[var(--radius-sm)] border border-line">
              <svg className="w-3.5 h-3.5 text-text-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                data-testid="top50-search-input"
                value={symbolSearchQuery}
                onChange={(e) => setSymbolSearchQuery(e.target.value)}
                placeholder="جستجوی نماد، نام یا صنعت..."
                className="w-full bg-transparent t-95 text-text focus:outline-none"
              />
              {symbolSearchQuery && (
                <button
                  type="button"
                  onClick={() => setSymbolSearchQuery('')}
                  className="text-text-3 hover:text-text t-9 px-1"
                >
                  ✕
                </button>
              )}
            </div>

            {/* جدول ۵۰ نماد برتر با ستون سیگنال */}
            <div className="border border-line rounded-[var(--radius-sm)] overflow-hidden">
              <table className="w-full text-right border-collapse t-9">
                <thead className="bg-panel-2 text-text-3 border-b border-line sticky top-0 z-5 font-semibold">
                  <tr>
                    <th className="py-1.5 px-2 w-8 text-center">#</th>
                    <th className="py-1.5 px-2">نماد</th>
                    <th className="py-1.5 px-2 text-center">سیگنال</th>
                    <th className="py-1.5 px-2 text-left">آخرین (ریال)</th>
                    <th className="py-1.5 px-2 text-center">تغییر ٪</th>
                    <th className="py-1.5 px-2 text-left">ارزش (م.ت)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/40">
                  {filteredSymbols.map((row, idx) => {
                    const isSelected = row.symbol === activeSymbol;
                    const change = row.percent_last ?? row.percent_change ?? 0;
                    const isPos = change > 0;
                    const isNeg = change < 0;
                    const valBillionToman = Math.round((row.q_tot_cap ?? 0) / 10_000_000_000);
                    const sig = getSymbolSignal(
                      row,
                      isSelected,
                      detectedDoubleTapPatterns,
                      detectedPullbackSignals,
                      detectedCHoCHSignals,
                      isLight
                    );

                    return (
                      <tr
                        key={row.symbol || idx}
                        data-testid={`top50-row-${row.symbol}`}
                        onClick={() => row.symbol && handleSelectSymbol(row.symbol)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-accent/15 border-s-2 border-accent text-accent font-semibold'
                            : 'hover:bg-panel-2 text-text-2 hover:text-text'
                        }`}
                      >
                        <td className="py-1.5 px-2 text-center text-text-3 font-mono">{toFaDigits(idx + 1)}</td>
                        <td className="py-1.5 px-2">
                          <div className="font-bold">{row.symbol}</div>
                          <div className="t-8 text-text-3 truncate max-w-[110px]">{row.name || row.sector_name}</div>
                        </td>
                        <td className="py-1.5 px-1.5 text-center" data-testid={`top50-signal-${row.symbol}`}>
                          <span
                            title={sig.title}
                            className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium font-sans truncate max-w-[90px] ${sig.badgeClass}`}
                          >
                            {sig.text}
                          </span>
                        </td>
                        <td className="py-1.5 px-2 text-left font-mono font-medium">
                          {toFaDigits(Number(row.p_last ?? 0).toLocaleString('en-US'))}
                        </td>
                        <td className="py-1.5 px-2 text-center">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                              isPos
                                ? 'bg-emerald-500/15 text-emerald-400'
                                : isNeg
                                ? 'bg-rose-500/15 text-rose-400'
                                : 'bg-gray-500/15 text-gray-400'
                            }`}
                          >
                            {isPos ? '+' : ''}
                            {toFaDigits(change.toFixed(2))}٪
                          </span>
                        </td>
                        <td className="py-1.5 px-2 text-left font-mono text-text-3">
                          {toFaDigits(valBillionToman)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ۲. تب کاتالوگ اندیکاتورها و مدهای معاملاتی */}
        {activeTab === 'indicators' && (
          <div data-testid="indicators-panel" className="p-3 flex flex-col gap-3">
            {/* بخش ۱: اندیکاتورهای جدید تلگرام (@IndicatorsforTV) */}
            <div className="flex flex-col gap-2">
              <span className="t-10 font-bold text-accent">اندیکاتورهای هوشمند پرایس‌اکشن و الگو</span>

              {ADVANCED_INDICATORS_REGISTRY.map((ind) => {
                const isEnabled = activeUserIndicators.includes(ind.id);

                return (
                  <div
                    key={ind.id}
                    className="p-2.5 rounded-[var(--radius-sm)] bg-panel-2 border border-line flex flex-col gap-1.5 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold t-10">{ind.nameFa}</span>
                        {ind.isDefault && (
                          <span className="t-8 px-1 py-0.2 rounded bg-accent/20 text-accent font-semibold">
                            پیش‌فرض
                          </span>
                        )}
                      </div>

                      {/* سوئیچ روشن/خاموش اندیکاتور */}
                      <button
                        type="button"
                        data-testid={`toggle-indicator-${ind.id}`}
                        onClick={() => toggleUserIndicator(ind.id)}
                        className={`h-5 px-2 rounded-[var(--radius-xs)] t-9 font-medium border transition-colors flex items-center gap-1 ${
                          isEnabled
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-bold'
                            : 'bg-panel text-text-3 border-line hover:text-text'
                        }`}
                      >
                        <span>{isEnabled ? 'روشن' : 'خاموش'}</span>
                        <span className={`w-1.5 h-1.5 rounded-full ${isEnabled ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                      </button>
                    </div>

                    <p className="t-85 text-text-3 leading-snug">{ind.descriptionFa}</p>

                    {/* تنظیمات مد ویژه برای اندیکاتور کانال چندحالته */}
                    {ind.id === 'MultiModeChannel' && isEnabled && (
                      <div className="mt-1 pt-1.5 border-t border-line/60 flex flex-col gap-1">
                        <span className="t-85 font-semibold text-text-2">حالت کانال (Channel Mode):</span>
                        <div className="grid grid-cols-3 gap-1">
                          {(
                            [
                              ['regression', 'رگرسیون خطی'],
                              ['retest_channel', 'شکست و پولبک'],
                              ['donchian', 'دانچیان و نوسان'],
                            ] as Array<[ChannelMode, string]>
                          ).map(([m, label]) => {
                            const isModeActive = channelMode === m;
                            return (
                              <button
                                key={m}
                                type="button"
                                data-testid={`channel-mode-btn-${m}`}
                                onClick={() => setChannelMode(m)}
                                className={`h-6 px-1 rounded-[var(--radius-xs)] t-85 font-medium transition-colors ${
                                  isModeActive
                                    ? 'bg-accent/20 text-accent border border-accent/40 font-bold'
                                    : 'bg-panel text-text-3 border border-line hover:text-text'
                                }`}
                              >
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* تنظیمات انتخاب‌گر دراپ‌داون ویژه برای خانواده RSI */}
                    {ind.id === 'MultiVariantRSI' && isEnabled && (
                      <div className="mt-1 pt-1.5 border-t border-line/60 flex items-center justify-between">
                        <span className="t-85 font-semibold text-text-2">فرمول RSI:</span>
                        <select
                          data-testid="rsi-variant-select"
                          value={rsiVariant}
                          onChange={(e) => setRsiVariant(e.target.value as RsiVariant)}
                          className="bg-panel text-text border border-line rounded px-2 py-0.5 t-85 focus:outline-none cursor-pointer"
                        >
                          <option value="standard">استاندارد (RSI 14)</option>
                          <option value="fibo">فیبوناچی (FiboRSI 8 تک‌شلیک)</option>
                          <option value="bb">باندهای بولینگر (BandsRSI)</option>
                          <option value="smooth_ma">آراس‌آی هموار با واگرایی</option>
                        </select>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* بخش ۲: اندیکاتورهای تکمیلی و سفارشی */}
            <div className="flex flex-col gap-2 mt-2 pt-2 border-t border-line/60">
              <span className="t-10 font-bold text-accent">اندیکاتورهای تکمیلی و سفارشی</span>

              {USER_INDICATORS_REGISTRY.map((ind) => {
                const isEnabled = activeUserIndicators.includes(ind.id);

                return (
                  <div
                    key={ind.id}
                    className="p-2.5 rounded-[var(--radius-sm)] bg-panel-2 border border-line flex flex-col gap-1.5 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold t-10">{ind.nameFa}</span>

                      {/* سوئیچ روشن/خاموش اندیکاتور */}
                      <button
                        type="button"
                        data-testid={`toggle-indicator-${ind.id}`}
                        onClick={() => toggleUserIndicator(ind.id)}
                        className={`h-5 px-2 rounded-[var(--radius-xs)] t-9 font-medium border transition-colors flex items-center gap-1 ${
                          isEnabled
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-bold'
                            : 'bg-panel text-text-3 border-line hover:text-text'
                        }`}
                      >
                        <span>{isEnabled ? 'روشن' : 'خاموش'}</span>
                        <span className={`w-1.5 h-1.5 rounded-full ${isEnabled ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                      </button>
                    </div>

                    <p className="t-85 text-text-3 leading-snug">{ind.descriptionFa}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ۳. تب اسکنر الگوهای کلاسیک و ساختار */}
        {activeTab === 'scanner' && (
          <div data-testid="scanner-panel" className="p-3 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="t-10 font-bold text-accent">الگوهای شناسایی‌شده روی نمودار</span>
              <span className="t-85 text-text-3 font-mono">
                {toFaDigits(detectedDoubleTapPatterns.length + detectedPullbackSignals.length + detectedCHoCHSignals.length)} مورد
              </span>
            </div>

            {/* لیست سقف و کف‌های دوقلو */}
            {detectedDoubleTapPatterns.map((pat) => {
              const isDoubleTop = pat.type === 'DOUBLE_TOP';
              const name = isDoubleTop ? 'سقف دوقلو (M)' : 'کف دوقلو (W)';
              const badgeColor = isDoubleTop ? 'text-rose-400 bg-rose-500/15' : 'text-cyan-400 bg-cyan-500/15';

              return (
                <div
                  key={pat.id}
                  className="p-2.5 rounded-[var(--radius-sm)] bg-panel-2 border border-line flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between">
                    <span className={`px-1.5 py-0.5 rounded t-85 font-bold ${badgeColor}`}>{name}</span>
                    <span className="t-85 font-bold text-accent font-mono">امتیاز: {toFaDigits(pat.score)}٪</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1 t-85 text-text-3 mt-1 font-mono">
                    <div>خط‌گردن: {toFaDigits(Math.round(pat.neckline.price))}</div>
                    <div>هدف ۱: {toFaDigits(Math.round(pat.target1))}</div>
                    <div>هدف ۲: {toFaDigits(Math.round(pat.target2))}</div>
                    <div>حد ضرر: {toFaDigits(Math.round(pat.stopLoss))}</div>
                  </div>
                </div>
              );
            })}

            {/* سیگنال‌های پولبک سوپرترند */}
            {detectedPullbackSignals.map((sig) => {
              const isBull = sig.type === 'BULLISH';
              return (
                <div
                  key={sig.id}
                  className="p-2 rounded-[var(--radius-sm)] bg-panel-2 border border-line flex items-center justify-between"
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`px-1.5 py-0.5 rounded t-85 font-bold ${
                        isBull ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                      }`}
                    >
                      {isBull ? 'پولبک صعودی (خرید)' : 'پولبک نزولی (فروش)'}
                    </span>
                    <span className="t-85 text-text-3 font-mono">قیمت: {toFaDigits(Math.round(sig.price))}</span>
                  </div>
                  <span className="t-8 text-accent font-mono">{toFaDigits(sig.qualityScore)}٪</span>
                </div>
              );
            })}

            {/* سیگنال‌های تغییر ماهیت ساختار (CHoCH) */}
            {detectedCHoCHSignals.map((ch) => (
              <div
                key={ch.id}
                className="p-2 rounded-[var(--radius-sm)] bg-panel-2 border border-line flex items-center justify-between"
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded t-85 font-bold ${
                      ch.isBullish ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                    }`}
                  >
                    {ch.isBullish ? 'CHoCH صعودی' : 'CHoCH نزولی'}
                  </span>
                  <span className="t-85 text-text-3 font-mono">سطح: {toFaDigits(Math.round(ch.levelPrice))}</span>
                </div>
                <span className="t-8 text-text-3 font-mono">شکست در: {toFaDigits(Math.round(ch.brokenPrice))}</span>
              </div>
            ))}

            {detectedDoubleTapPatterns.length === 0 &&
              detectedPullbackSignals.length === 0 &&
              detectedCHoCHSignals.length === 0 && (
                <div className="p-4 text-center text-text-3 t-9">
                  در کندل‌های فعلی این نماد، الگوی قطعی تشکیل نشده است.
                </div>
              )}
          </div>
        )}

        {/* ۴. تب لبه آماری کندل‌ها (همیشه سوار در DOM برای آزمون‌های سیستمی) */}
        <div
          data-testid="edge-tab-panel"
          className={activeTab === 'edge' ? 'block p-3' : 'hidden'}
        >
          <CandleEdgeCard symbol={activeSymbol} />
        </div>
      </div>
    </div>
  );

  const ACTIVITY_TOOLS: Array<{
    id: DrawerTab;
    labelFa: string;
    icon: React.ReactNode;
    badge?: number;
  }> = [
    {
      id: 'top50',
      labelFa: 'میز کار جامع و ۵۰ نماد برتر',
      badge: top50Symbols.length,
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      ),
    },
    {
      id: 'indicators',
      labelFa: 'کاتالوگ اندیکاتورها و مدهای کانال',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
        </svg>
      ),
    },
    {
      id: 'scanner',
      labelFa: 'اسکنر الگوهای کلاسیک و ساختار',
      badge: detectedDoubleTapPatterns.length + detectedPullbackSignals.length + detectedCHoCHSignals.length,
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      ),
    },
    {
      id: 'edge',
      labelFa: 'لبه آماری و پرایس‌اکشن نهادی',
      icon: (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
  ];

  const handleActivityIconClick = (tabId: DrawerTab) => {
    if (!isOpen) {
      setActiveTab(tabId);
      onToggleOpen();
    } else {
      if (activeTab === tabId) {
        onToggleOpen();
      } else {
        setActiveTab(tabId);
      }
    }
  };

  // در صورت بسته بودن سایدبار، نوار باریک آیکون‌های فعالیت در منتهی‌الیه چپ نشان داده می‌شود
  if (!isOpen) {
    return (
      <aside
        data-testid="wide-workspace-drawer-collapsed"
        className="w-11 h-full bg-panel border-r border-line flex flex-col items-center py-2 shrink-0 select-none z-15"
        dir="rtl"
      >
        <button
          type="button"
          onClick={onToggleOpen}
          title={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
          aria-label={isOpen ? 'بستن سایدبار لبه آماری' : 'باز کردن سایدبار لبه آماری'}
          className="flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel-2 transition-colors"
        >
          <svg className="w-4 h-4 rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        {/* نوار باریک آیکون‌های ابزار و میزکار */}
        <div className="flex flex-col items-center gap-2 mt-4 text-text-3 w-full px-1">
          {ACTIVITY_TOOLS.map((tool) => (
            <button
              key={tool.id}
              type="button"
              data-testid={`activity-bar-icon-${tool.id}`}
              onClick={() => handleActivityIconClick(tool.id)}
              title={tool.labelFa}
              className="relative flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel-2 transition-colors"
            >
              {tool.icon}
              {tool.badge !== undefined && tool.badge > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-accent text-bg text-[9px] font-bold font-mono flex items-center justify-center">
                  {toFaDigits(Math.min(tool.badge, 99))}
                </span>
              )}
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <>
      <aside
        style={{ width: `${drawerWidth}px` }}
        className={`relative h-full border-r border-line bg-panel flex flex-row shrink-0 select-none z-15 transition-[width] duration-75 ${
          isResizing ? 'cursor-col-resize select-none' : ''
        } ${className}`}
        dir="rtl"
      >
        {/* دستگیره درگ جهت تغییر عرض روی مرز مشترک با چارت */}
        <div
          ref={resizerRef}
          data-testid="drawer-resizer-handle"
          onMouseDown={handleMouseDownResize}
          title="درگ برای تغییر عرض ستون"
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-accent/40 active:bg-accent z-20 transition-colors"
        />

        {/* ستون خیلی باریک آیکون‌ها در منتهی‌الیه چپ */}
        <div
          data-testid="slim-activity-bar"
          className="w-11 h-full bg-panel-2/80 border-e border-line flex flex-col items-center py-2 shrink-0 z-10"
        >
          {/* دکمه بستن/جمع کردن سایدبار */}
          <button
            type="button"
            onClick={onToggleOpen}
            title="جمع کردن نوار فعالیت"
            aria-label="جمع کردن نوار فعالیت"
            className="flex items-center justify-center w-8 h-8 rounded text-text-3 hover:text-accent hover:bg-panel transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>

          {/* آیکون‌های ابزار و تب‌های عمودی */}
          <div className="flex flex-col items-center gap-2 mt-4 text-text-3 w-full px-1">
            {ACTIVITY_TOOLS.map((tool) => {
              const isActive = activeTab === tool.id;
              return (
                <button
                  key={tool.id}
                  type="button"
                  data-testid={`activity-bar-icon-${tool.id}`}
                  onClick={() => handleActivityIconClick(tool.id)}
                  title={tool.labelFa}
                  className={`relative flex items-center justify-center w-8 h-8 rounded transition-colors ${
                    isActive
                      ? 'bg-panel-3 text-accent border border-accent/40 shadow-xs font-bold'
                      : 'hover:text-accent hover:bg-panel'
                  }`}
                >
                  {tool.icon}
                  {tool.badge !== undefined && tool.badge > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-accent text-bg text-[9px] font-bold font-mono flex items-center justify-center">
                      {toFaDigits(Math.min(tool.badge, 99))}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* محتوای سایدبار عریض */}
        <div className="flex-1 h-full min-w-0 overflow-hidden flex flex-col">
          {drawerContent}
        </div>
      </aside>

      {/* مودال پورتال در صورت تمایل کاربر به داشتن میزکار شناور تمام‌صفحه */}
      {isPortalModalOpen && typeof document !== 'undefined' &&
        createPortal(
          <div
            data-testid="portal-modal-backdrop"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-6"
            dir="rtl"
          >
            <div className="relative w-full max-w-4xl h-[85vh] bg-panel border border-line rounded-[var(--radius-md)] shadow-2xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-line bg-panel-2">
                <span className="font-bold text-accent t-12">میزکار جامع (پنجره شناور پورتال)</span>
                <button
                  type="button"
                  onClick={() => setIsPortalModalOpen(false)}
                  className="px-2 py-0.5 rounded text-text-3 hover:text-text hover:bg-panel"
                >
                  ✕ بستن
                </button>
              </div>
              <div className="flex-1 overflow-hidden">{drawerContent}</div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
};
