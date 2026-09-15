import React, { useState } from 'react';
import {
  IconCrosshair, IconTrendLine, IconRay, IconHorizontalLine, IconVerticalLine,
  IconParallelChannel, IconFibRetracement, IconPitchfork, IconRectangle,
  IconCircle, IconText, IconRuler, IconMagnet, IconLock, IconTrash
} from './TradingViewIcons';

interface DrawingToolbarProps {
  activeTool?: string;
  onSelectTool: (tool: string) => void;
  onClearAll: () => void;
  isMagnetActive?: boolean;
  onToggleMagnet?: () => void;
  isLocked?: boolean;
  onToggleLock?: () => void;
}

export const DrawingToolbar: React.FC<DrawingToolbarProps> = ({
  activeTool = 'crosshair',
  onSelectTool,
  onClearAll,
  isMagnetActive = false,
  onToggleMagnet,
  isLocked = false,
  onToggleLock
}) => {
  const [openFlyout, setOpenFlyout] = useState<string | null>(null);

  const handleSlotClick = (slotName: string, defaultOverlay: string) => {
    if (openFlyout === slotName) {
      setOpenFlyout(null);
    } else {
      setOpenFlyout(slotName);
      onSelectTool(defaultOverlay);
    }
  };

  return (
    <aside className="nn-left-toolbar" onClick={(e) => e.stopPropagation()}>
      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (activeTool === 'crosshair' ? 'active' : '')}
          onClick={() => { setOpenFlyout(null); onSelectTool('crosshair'); }}
          title="نشانگر چلیپایی"
        >
          <IconCrosshair size={18} />
        </div>
      </div>

      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (['segment', 'rayLine', 'straightLine', 'verticalStraightLine', 'priceChannelLine'].includes(activeTool) ? 'active' : '')}
          onClick={() => handleSlotClick('lines', 'segment')}
          title="خطوط روند"
        >
          <IconTrendLine size={18} />
          <span className="tv-tool-arrow" />
        </div>
        {openFlyout === 'lines' && (
          <div className="tv-flyout open">
            <div className="tv-flyout-item" onClick={() => { onSelectTool('segment'); setOpenFlyout(null); }}>
              <IconTrendLine size={16} /> خط روند (Trend Line)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('rayLine'); setOpenFlyout(null); }}>
              <IconRay size={16} /> پرتو (Ray)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('straightLine'); setOpenFlyout(null); }}>
              <IconHorizontalLine size={16} /> خط افقی (Horizontal Line)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('verticalStraightLine'); setOpenFlyout(null); }}>
              <IconVerticalLine size={16} /> خط عمودی (Vertical Line)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('priceChannelLine'); setOpenFlyout(null); }}>
              <IconParallelChannel size={16} /> کانال موازی
            </div>
          </div>
        )}
      </div>

      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (['fibonacciLine', 'parallelStraightLine'].includes(activeTool) ? 'active' : '')}
          onClick={() => handleSlotClick('fib', 'fibonacciLine')}
          title="فیبوناچی و چنگال"
        >
          <IconFibRetracement size={18} />
          <span className="tv-tool-arrow" />
        </div>
        {openFlyout === 'fib' && (
          <div className="tv-flyout open">
            <div className="tv-flyout-item" onClick={() => { onSelectTool('fibonacciLine'); setOpenFlyout(null); }}>
              <IconFibRetracement size={16} /> فیبوناچی ریتریسمنت
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('parallelStraightLine'); setOpenFlyout(null); }}>
              <IconPitchfork size={16} /> چنگال اندروز
            </div>
          </div>
        )}
      </div>

      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (['rect', 'circle'].includes(activeTool) ? 'active' : '')}
          onClick={() => handleSlotClick('shapes', 'rect')}
          title="اشکال هندسی"
        >
          <IconRectangle size={18} />
          <span className="tv-tool-arrow" />
        </div>
        {openFlyout === 'shapes' && (
          <div className="tv-flyout open">
            <div className="tv-flyout-item" onClick={() => { onSelectTool('rect'); setOpenFlyout(null); }}>
              <IconRectangle size={16} /> مستطیل (Rectangle)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('circle'); setOpenFlyout(null); }}>
              <IconCircle size={16} /> دایره (Circle)
            </div>
          </div>
        )}
      </div>

      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (['simpleAnnotation', 'priceLine'].includes(activeTool) ? 'active' : '')}
          onClick={() => handleSlotClick('text', 'simpleAnnotation')}
          title="متن و یادداشت"
        >
          <IconText size={18} />
          <span className="tv-tool-arrow" />
        </div>
        {openFlyout === 'text' && (
          <div className="tv-flyout open">
            <div className="tv-flyout-item" onClick={() => { onSelectTool('simpleAnnotation'); setOpenFlyout(null); }}>
              <IconText size={16} /> متن تحلیلی (Text)
            </div>
            <div className="tv-flyout-item" onClick={() => { onSelectTool('priceLine'); setOpenFlyout(null); }}>
              برچسب قیمت (Price Tag)
            </div>
          </div>
        )}
      </div>

      <div className="nn-tool-divider" />

      <div className="tv-tool-slot">
        <div className="nn-left-toolbar-item" title="خط‌کش اندازه‌گیری"><IconRuler size={18} /></div>
      </div>
      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (isMagnetActive ? 'active' : '')}
          onClick={onToggleMagnet}
          title="آهنربا (اسنپ به قیمت)"
        >
          <IconMagnet size={18} />
        </div>
      </div>
      <div className="tv-tool-slot">
        <div
          className={'nn-left-toolbar-item ' + (isLocked ? 'active' : '')}
          onClick={onToggleLock}
          title="قفل کردن ترسیمات"
        >
          <IconLock size={18} />
        </div>
      </div>

      <div className="nn-tool-divider" />

      <div className="tv-tool-slot">
        <div
          className="nn-left-toolbar-item"
          title="حذف تمام ترسیمات"
          style={{ color: '#f23645' }}
          onClick={onClearAll}
        >
          <IconTrash size={18} />
        </div>
      </div>
    </aside>
  );
};
