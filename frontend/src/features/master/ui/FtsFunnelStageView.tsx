// نمای یک گام از قیف: همان جدولِ گام، بی‌سربرگِ تکراری.
//
// پیشِ این بالایِ همین صفحه یک hero با عنوان/شرح/چهار کارتِ آماری/تراشه‌هایِ
// قاعده بود و جدول بعد از آن می‌آمد. حکمِ مالک (۱۴۰۵-0۷-۱۶): «جدول مهم‌تر از کارت و
// تزئینات است». شمارش‌ها به سرخطِ پوسته رفت.
//
// مأموریتِ ۲۰۲۶-۱۰-۱۸: عنوانِ گام، حالتِ کشف و «چند نماد عبور کرد» درِ این فایل هم
// تکرار می‌شدند، در حالی که استپر (کارتِ فعال باِ «گام جاری») و `FtsFunnelHeader`
// هر سه را یک‌بار می‌گویند. سه‌تکراری حذف شد؛ چیزی از داوری یا از داده کم نشده.
import { funnelStagePath } from './FtsProcessStepper';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import type { FunnelStageKey, TreePreset } from '../lib/ftsFunnel';

export default function FtsFunnelStageView({
  stage,
  preset,
}: {
  stage: Exclude<FunnelStageKey, 'handover'>;
  preset: TreePreset;
}) {
  return (
    <div className="flex w-full flex-col gap-1" data-testid={`fts-stage-${stage}`}>
      <FtsFunnelAllStages preset={preset} only={stage} />
    </div>
  );
}

export { funnelStagePath };
