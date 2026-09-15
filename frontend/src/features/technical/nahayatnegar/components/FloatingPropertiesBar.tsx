import React, { useState } from 'react';

interface FloatingPropertiesBarProps {
  visible: boolean;
  onColorChange?: (color: string) => void;
  onWidthChange?: (width: number) => void;
  onStyleChange?: (style: string) => void;
  onLockToggle?: () => void;
  onDelete?: () => void;
}

export const FloatingPropertiesBar: React.FC<FloatingPropertiesBarProps> = ({
  visible,
  onColorChange,
  onWidthChange,
  onStyleChange,
  onLockToggle,
  onDelete
}) => {
  const [activeColor, setActiveColor] = useState('#2962ff');
  const [activeWidth, setActiveWidth] = useState(2);
  const [activeStyle, setActiveStyle] = useState('solid');
  const [isLocked, setIsLocked] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);

  if (!visible) return null;

  const colors = ['#2962ff', '#089981', '#f23645', '#f59e0b', '#ab47bc', '#ffffff', '#787b86'];

  return (
    <div className="tv-floating-properties visible">
      {/* Drag handle */}
      <span style={{ color: '#787b86', cursor: 'grab', fontSize: '10px' }}>⋮⋮</span>

      {/* Color Swatch */}
      <div style={{ position: 'relative' }}>
        <div
          className="color-dot"
          style={{ backgroundColor: activeColor }}
          onClick={() => setShowColorPicker(!showColorPicker)}
          title="تغییر رنگ"
        />
        {showColorPicker && (
          <div style={{
            position: 'absolute', top: '100%', right: 0, marginTop: '6px',
            background: '#1e222d', border: '1px solid #2a2e39', borderRadius: '6px',
            padding: '6px', display: 'flex', gap: '5px', zIndex: 120, boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
          }}>
            {colors.map(c => (
              <div
                key={c}
                style={{ width: '16px', height: '16px', borderRadius: '50%', background: c, cursor: 'pointer', border: c === activeColor ? '2px solid #fff' : 'none' }}
                onClick={() => {
                  setActiveColor(c);
                  setShowColorPicker(false);
                  onColorChange?.(c);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Line Width */}
      <select
        value={activeWidth}
        onChange={(e) => {
          const w = Number(e.target.value);
          setActiveWidth(w);
          onWidthChange?.(w);
        }}
        style={{
          background: '#131722', border: '1px solid #2a2e39', color: '#d1d4dc',
          fontSize: '11px', borderRadius: '3px', padding: '1px 4px', height: '22px'
        }}
      >
        <option value={1}>1px</option>
        <option value={2}>2px</option>
        <option value={3}>3px</option>
        <option value={4}>4px</option>
      </select>

      {/* Line Style */}
      <select
        value={activeStyle}
        onChange={(e) => {
          setActiveStyle(e.target.value);
          onStyleChange?.(e.target.value);
        }}
        style={{
          background: '#131722', border: '1px solid #2a2e39', color: '#d1d4dc',
          fontSize: '11px', borderRadius: '3px', padding: '1px 4px', height: '22px'
        }}
      >
        <option value="solid">ممتد</option>
        <option value="dashed">خط‌چین</option>
      </select>

      <div style={{ width: '1px', height: '14px', background: '#2a2e39', margin: '0 2px' }} />

      {/* Lock */}
      <button
        className="tv-btn"
        style={{ height: '22px', padding: '0 6px', color: isLocked ? '#2962ff' : '#787b86' }}
        onClick={() => {
          setIsLocked(!isLocked);
          onLockToggle?.();
        }}
        title="قفل موقعیت"
      >
        {isLocked ? '🔒' : '🔓'}
      </button>

      {/* Delete */}
      <button
        className="tv-btn"
        style={{ height: '22px', padding: '0 6px', color: '#f23645' }}
        onClick={onDelete}
        title="حذف ابزار"
      >
        🗑
      </button>
    </div>
  );
};
