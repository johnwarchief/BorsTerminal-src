import React, { useState } from 'react';
import { IconLock, IconUnlock, IconTrash, IconClose } from './TradingViewIcons';

interface FloatingPropertiesBarProps {
  visible: boolean;
  selectedToolName: string;
  currentColor: string;
  currentWidth: number;
  currentStyle: 'solid' | 'dashed';
  isLocked: boolean;
  onColorChange: (color: string) => void;
  onWidthChange: (width: number) => void;
  onStyleChange: (style: 'solid' | 'dashed') => void;
  onToggleLock: () => void;
  onDelete: () => void;
  onClose: () => void;
}

export const FloatingPropertiesBar: React.FC<FloatingPropertiesBarProps> = ({
  visible,
  selectedToolName,
  currentColor,
  currentWidth,
  currentStyle,
  isLocked,
  onColorChange,
  onWidthChange,
  onStyleChange,
  onToggleLock,
  onDelete,
  onClose
}) => {
  const [showColorPalette, setShowColorPalette] = useState(false);
  const colorOptions = [
    '#2962ff', // آبی تریدینگ‌وی
    '#089981', // سبز صعودی
    '#f23645', // قرمز نزولی
    '#ffab00', // زرد طلایی FTS
    '#ab47bc', // بنفش
    '#00bcd4', // فیروزه‌ای
    '#ffffff', // سفید
    '#787b86'  // خاکستری
  ];

  if (!visible) return null;

  return (
    <div className="tv-floating-properties-bar" onClick={(e) => e.stopPropagation()}>
      <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#ffffff', borderLeft: '1px solid #2a2e39', paddingLeft: '8px' }}>
        {selectedToolName || 'المان رسم'}
      </span>

      {/* انتخاب رنگ */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowColorPalette(!showColorPalette)}
          style={{
            width: '20px',
            height: '20px',
            borderRadius: '4px',
            backgroundColor: currentColor,
            border: '1px solid #363a45',
            cursor: 'pointer'
          }}
          title="تغییر رنگ المان"
        />
        {showColorPalette && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: '6px',
              backgroundColor: '#1e222d',
              border: '1px solid #2a2e39',
              borderRadius: '6px',
              padding: '6px',
              display: 'flex',
              gap: '4px',
              zIndex: 250,
              boxShadow: '0 8px 24px rgba(0,0,0,0.6)'
            }}
          >
            {colorOptions.map(c => (
              <div
                key={c}
                onClick={() => { onColorChange(c); setShowColorPalette(false); }}
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '3px',
                  backgroundColor: c,
                  cursor: 'pointer',
                  border: currentColor === c ? '2px solid #ffffff' : '1px solid #363a45'
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* ضخامت خط */}
      <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
        {[1, 2, 3, 4].map(w => (
          <button
            key={w}
            onClick={() => onWidthChange(w)}
            style={{
              background: currentWidth === w ? 'rgba(41,98,255,0.2)' : 'transparent',
              border: currentWidth === w ? '1px solid #2962ff' : '1px solid transparent',
              color: currentWidth === w ? '#2962ff' : '#d1d4dc',
              borderRadius: '3px',
              padding: '2px 5px',
              fontSize: '11px',
              cursor: 'pointer'
            }}
            title={`ضخامت ${w} پیکسل`}
          >
            {w}px
          </button>
        ))}
      </div>

      {/* سبک خط: LineType فقط solid | dashed است */}
      <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
        <button
          onClick={() => onStyleChange('solid')}
          style={{
            background: currentStyle === 'solid' ? 'rgba(41,98,255,0.2)' : 'transparent',
            border: currentStyle === 'solid' ? '1px solid #2962ff' : '1px solid transparent',
            color: currentStyle === 'solid' ? '#2962ff' : '#d1d4dc',
            borderRadius: '3px',
            padding: '2px 6px',
            fontSize: '10px',
            cursor: 'pointer'
          }}
        >
          خط ممتد
        </button>
        <button
          onClick={() => onStyleChange('dashed')}
          style={{
            background: currentStyle === 'dashed' ? 'rgba(41,98,255,0.2)' : 'transparent',
            border: currentStyle === 'dashed' ? '1px solid #2962ff' : '1px solid transparent',
            color: currentStyle === 'dashed' ? '#2962ff' : '#d1d4dc',
            borderRadius: '3px',
            padding: '2px 6px',
            fontSize: '10px',
            cursor: 'pointer'
          }}
        >
          خط‌چین
        </button>
      </div>

      {/* قفل کردن */}
      <button
        onClick={onToggleLock}
        style={{
          background: isLocked ? 'rgba(41,98,255,0.2)' : 'transparent',
          border: 'none',
          color: isLocked ? '#2962ff' : '#787b86',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          padding: '4px'
        }}
        title={isLocked ? 'باز کردن قفل' : 'قفل کردن المان'}
      >
        {isLocked ? <IconLock size={15} color="#2962ff" /> : <IconUnlock size={15} color="#787b86" />}
      </button>

      {/* حذف المان */}
      <button
        onClick={onDelete}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#f23645',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          padding: '4px'
        }}
        title="حذف این المان"
      >
        <IconTrash size={15} color="#f23645" />
      </button>

      {/* دکمه بستن نوار */}
      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          color: '#787b86',
          cursor: 'pointer',
          padding: '0 4px'
        }}
        title="بستن نوار تنظیمات"
      >
        <IconClose size={14} color="#787b86" />
      </button>
    </div>
  );
};
