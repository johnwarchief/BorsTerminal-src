import { useParams } from 'react-router-dom';
import { TechnicalWorkspace } from '../ui/TechnicalWorkspace';

export function TechnicalPage() {
  const { symbol } = useParams<{ symbol?: string }>();
  // پیش‌فرض به نماد فولاد برای نمایش غنی داده‌ها و تعدیل عملکردی مشابه رهاورد ۳۶۵
  const targetSymbol = symbol ? decodeURIComponent(symbol) : 'فولاد';

  return (
    <div className="flex flex-1 flex-col h-full overflow-hidden">
      <TechnicalWorkspace symbol={targetSymbol} className="flex-1" />
    </div>
  );
}
