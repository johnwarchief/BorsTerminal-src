import React, { useState } from 'react';
import {
  IconCrosshair, IconDot, IconArrowCursor, IconEraser,
  IconTrendLine, IconRay, IconInfoLine, IconHorizontalLine, IconVerticalLine, IconParallelChannel,
  IconFibRetracement, IconPitchfork,
  IconBrush, IconRectangle, IconCircle,
  IconText, IconPriceLabel,
  IconPatterns,
  IconLongPosition, IconShortPosition,
  IconRuler, IconMagnet, IconLock, IconUnlock, IconEye, IconEyeOff, IconTrash, IconCheck
} from './TradingViewIcons';

export interface ToolItem {
  id: string;
  name: string;
  overlayType: string;
  icon: React.ReactNode;
}

export interface ToolSlot {
  slotId: string;
  name: string;
  defaultTool: ToolItem;
  items: ToolItem[];
}

interface DrawingToolbarProps {
  activeToolId: string | null;
  onSelectTool: (toolId: string, overlayType: string) => void;
  onClearDrawings: () => void;
  isMagnetActive: boolean;
  onToggleMagnet: () => void;
  isLocked: boolean;
  onToggleLock: () => void;
  isHideActive: boolean;
  onToggleHide: () => void;
}

export const DrawingToolbar: React.FC<DrawingToolbarProps> = ({
  activeToolId,
  onSelectTool,
  onClearDrawings,
  isMagnetActive,
  onToggleMagnet,
  isLocked,
  onToggleLock,
  isHideActive,
  onToggleHide,
}) => {
  const [openFlyout, setOpenFlyout] = useState<string | null>(null);
  const [selectedTools, setSelectedTools] = useState<{ [slotId: string]: ToolItem }>({
    cursor: { id: 'crosshair', name: 'نشانگر صلیبی', overlayType: 'crosshair', icon: <IconCrosshair /> },
    lines: { id: 'trendLine', name: 'خط روند', overlayType: 'segment', icon: <IconTrendLine /> },
    fib: { id: 'fibRetracement', name: 'بازگشتی فیبوناچی', overlayType: 'fibonacciLine', icon: <IconFibRetracement /> },
    shapes: { id: 'rectangle', name: 'مستطیل', overlayType: 'rect', icon: <IconRectangle /> },
    text: { id: 'text', name: 'متن یادداشت', overlayType: 'simpleAnnotation', icon: <IconText /> },
    patterns: { id: 'xabcd', name: 'الگوی هارمونیک', overlayType: 'segment', icon: <IconPatterns /> },
    prediction: { id: 'longPosition', name: 'موقعیت خرید', overlayType: 'rect', icon: <IconLongPosition /> },
  });

  const toolSlots: ToolSlot[] = [
    {
      slotId: 'cursor',
      name: 'نشانگرها',
      defaultTool: { id: 'crosshair', name: 'نشانگر صلیبی', overlayType: 'crosshair', icon: <IconCrosshair /> },
      items: [
        { id: 'crosshair', name: 'نشانگر صلیبی', overlayType: 'crosshair', icon: <IconCrosshair /> },
        { id: 'dot', name: 'نقطه', overlayType: 'crosshair', icon: <IconDot /> },
        { id: 'arrow', name: 'پیکان انتخاب', overlayType: 'crosshair', icon: <IconArrowCursor /> },
        { id: 'eraser', name: 'پاک‌کن', overlayType: 'eraser', icon: <IconEraser /> },
      ]
    },
    {
      slotId: 'lines',
      name: 'خطوط روند',
      defaultTool: { id: 'trendLine', name: 'خط روند', overlayType: 'segment', icon: <IconTrendLine /> },
      items: [
        { id: 'trendLine', name: 'خط روند', overlayType: 'segment', icon: <IconTrendLine /> },
        { id: 'ray', name: 'نیم‌خط (Ray)', overlayType: 'rayLine', icon: <IconRay /> },
        { id: 'infoLine', name: 'خط اطلاعاتی', overlayType: 'segment', icon: <IconInfoLine /> },
        { id: 'horizontalLine', name: 'خط افقی', overlayType: 'straightLine', icon: <IconHorizontalLine /> },
        { id: 'verticalLine', name: 'خط عمودی', overlayType: 'verticalStraightLine', icon: <IconVerticalLine /> },
        { id: 'parallelChannel', name: 'کانال موازی', overlayType: 'priceChannelLine', icon: <IconParallelChannel /> },
      ]
    },
    {
      slotId: 'fib',
      name: 'فیبوناچی و چنگال',
      defaultTool: { id: 'fibRetracement', name: 'بازگشتی فیبوناچی', overlayType: 'fibonacciLine', icon: <IconFibRetracement /> },
      items: [
        { id: 'fibRetracement', name: 'بازگشتی فیبوناچی', overlayType: 'fibonacciLine', icon: <IconFibRetracement /> },
        { id: 'fibExtension', name: 'اکستنشن فیبوناچی', overlayType: 'fibonacciLine', icon: <IconFibRetracement /> },
        { id: 'pitchfork', name: 'چنگال اندروز', overlayType: 'priceChannelLine', icon: <IconPitchfork /> },
      ]
    },
    {
      slotId: 'shapes',
      name: 'اشکال هندسی',
      defaultTool: { id: 'rectangle', name: 'مستطیل', overlayType: 'rect', icon: <IconRectangle /> },
      items: [
        { id: 'brush', name: 'قلم‌مو (Brush)', overlayType: 'brush', icon: <IconBrush /> },
        { id: 'rectangle', name: 'مستطیل', overlayType: 'rect', icon: <IconRectangle /> },
        { id: 'circle', name: 'دایره', overlayType: 'circle', icon: <IconCircle /> },
      ]
    },
    {
      slotId: 'text',
      name: 'متن و برچسب',
      defaultTool: { id: 'text', name: 'متن یادداشت', overlayType: 'simpleAnnotation', icon: <IconText /> },
      items: [
        { id: 'text', name: 'متن یادداشت', overlayType: 'simpleAnnotation', icon: <IconText /> },
        { id: 'priceLabel', name: 'برچسب قیمت', overlayType: 'simpleAnnotation', icon: <IconPriceLabel /> },
      ]
    },
    {
      slotId: 'patterns',
      name: 'الگوها',
      defaultTool: { id: 'xabcd', name: 'الگوی هارمونیک', overlayType: 'segment', icon: <IconPatterns /> },
      items: [
        { id: 'xabcd', name: 'الگوی هارمونیک', overlayType: 'segment', icon: <IconPatterns /> },
        { id: 'headShoulders', name: 'سر و شانه', overlayType: 'segment', icon: <IconPatterns /> },
        { id: 'elliott', name: 'امواج الیوت', overlayType: 'segment', icon: <IconPatterns /> },
      ]
    },
    {
      slotId: 'prediction',
      name: 'پیش‌بینی و موقعیت',
      defaultTool: { id: 'longPosition', name: 'موقعیت خرید', overlayType: 'rect', icon: <IconLongPosition /> },
      items: [
        { id: 'longPosition', name: 'موقعیت خرید (Long)', overlayType: 'rect', icon: <IconLongPosition /> },
        { id: 'shortPosition', name: 'موقعیت فروش (Short)', overlayType: 'rect', icon: <IconShortPosition /> },
        { id: 'priceRange', name: 'محدوده قیمت', overlayType: 'rect', icon: <IconRuler /> },
        { id: 'dateRange', name: 'محدوده زمان', overlayType: 'rect', icon: <IconRuler /> },
      ]
    },
  ];

  const handleSlotClick = (slot: ToolSlot) => {
    const currentSelected = selectedTools[slot.slotId] || slot.defaultTool;
    if (activeToolId === currentSelected.id) {
      setOpenFlyout(openFlyout === slot.slotId ? null : slot.slotId);
    } else {
      onSelectTool(currentSelected.id, currentSelected.overlayType);
    }
  };

  const handleArrowClick = (e: React.MouseEvent, slotId: string) => {
    e.stopPropagation();
    setOpenFlyout(openFlyout === slotId ? null : slotId);
  };

  const handleItemSelect = (slotId: string, item: ToolItem) => {
    setSelectedTools(prev => ({ ...prev, [slotId]: item }));
    setOpenFlyout(null);
    onSelectTool(item.id, item.overlayType);
  };

  return (
    <aside className="nn-left-toolbar" onClick={() => setOpenFlyout(null)}>
      {toolSlots.map((slot) => {
        const curItem = selectedTools[slot.slotId] || slot.defaultTool;
        const isActive = activeToolId === curItem.id;
        const isFlyoutOpen = openFlyout === slot.slotId;

        return (
          <div key={slot.slotId} className="tv-slot-wrapper">
            <div
              className={`tool-item ${isActive ? 'active' : ''}`}
              title={curItem.name}
              onClick={(e) => {
                e.stopPropagation();
                handleSlotClick(slot);
              }}
            >
              {curItem.icon}
              <span
                className="tv-slot-arrow"
                onClick={(e) => handleArrowClick(e, slot.slotId)}
                title="مشاهده زیرابزارها"
              >
                ▸
              </span>
            </div>

            {/* منوی بازشونده فلای‌اوت */}
            {isFlyoutOpen && (
              <div
                className="tv-flyout-menu"
                onClick={(e) => e.stopPropagation()}
              >
                <div style={{ padding: '6px 12px', fontSize: '11px', color: '#787b86', borderBottom: '1px solid #2a2e39', fontWeight: 'bold' }}>
                  {slot.name}
                </div>
                {slot.items.map((it) => (
                  <div
                    key={it.id}
                    className={`tv-flyout-item ${curItem.id === it.id ? 'active' : ''}`}
                    onClick={() => handleItemSelect(slot.slotId, it)}
                  >
                    <span style={{ display: 'inline-flex', width: '20px' }}>{it.icon}</span>
                    <span style={{ flex: 1 }}>{it.name}</span>
                    {curItem.id === it.id && <IconCheck size={14} color="#2962ff" />}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      <div className="nn-tool-divider" />

      {/* خط‌کش اندازه‌گیری */}
      <div
        className={`tool-item ${activeToolId === 'ruler' ? 'active' : ''}`}
        title="خط‌کش اندازه‌گیری"
        onClick={() => onSelectTool('ruler', 'rect')}
      >
        <IconRuler />
      </div>

      {/* حالت آهنربا */}
      <div
        className={`tool-item ${isMagnetActive ? 'active' : ''}`}
        title={isMagnetActive ? 'آهنربا: فعال' : 'آهنربا: غیرفعال'}
        onClick={onToggleMagnet}
      >
        <IconMagnet color={isMagnetActive ? '#2962ff' : 'currentColor'} />
      </div>

      {/* قفل کردن ترسیم‌ها */}
      <div
        className={`tool-item ${isLocked ? 'active' : ''}`}
        title={isLocked ? 'قفل ترسیم‌ها: فعال' : 'قفل ترسیم‌ها: باز'}
        onClick={onToggleLock}
      >
        {isLocked ? <IconLock color="#2962ff" /> : <IconUnlock />}
      </div>

      {/* مخفی‌سازی ترسیم‌ها */}
      <div
        className={`tool-item ${isHideActive ? 'active' : ''}`}
        title={isHideActive ? 'ترسیم‌ها: مخفی' : 'ترسیم‌ها: نمایان'}
        onClick={onToggleHide}
      >
        {isHideActive ? <IconEyeOff color="#f23645" /> : <IconEye />}
      </div>

      {/* حذف تمام ترسیم‌ها */}
      <div
        className="tool-item"
        title="حذف تمام ترسیم‌ها"
        onClick={() => {
          if (typeof window !== 'undefined' && window.confirm) {
            if (window.confirm('آیا از حذف تمام ترسیم‌های این نماد اطمینان دارید؟')) {
              onClearDrawings();
            }
          } else {
            onClearDrawings();
          }
        }}
        style={{ color: '#f23645' }}
      >
        <IconTrash />
      </div>
    </aside>
  );
};
