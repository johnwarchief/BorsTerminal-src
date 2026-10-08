// نمای یک گام از قیف: سرخطِ فشرده + جدولِ همان گام.
//
// پیشِ این بالایِ همین صفحه یک hero با عنوان/شرح/چهار کارتِ آماری/تراشه‌هایِ
// قاعده بود و جدول بعد از آن می‌آمد. حکمِ مالک (۱۴۰۵-۰۷-۱۶): «جدول مهم‌تر از
// کارت و تزئینات است». شمارش‌ها به یک خطِ سرخطِ پوسته (FtsFunnelStages) رفته‌اند
// و توضیحِ قواعد درِ `title` همان ستون‌ها می‌نشیند؛ چیزی از داوری کم نشده.
import { toFaDigits } from '@shared/lib/fmt';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { funnelStagePath } from './FtsProcessStepper';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import type { FunnelStageKey, TreePreset } from '../lib/ftsFunnel';

const STAGE_TITLE: Record<Exclude<FunnelStageKey, 'handover'>, string> = {
  tape: 'تابلوخوانی',
  technical: 'تکنیکال دو زمانه',
  fundamental: 'بنیادی پنج‌شاخصه',
};

export default function FtsFunnelStageView({
  stage,
  preset,
}: {
  stage: Exclude<FunnelStageKey, 'handover'>;
  preset: TreePreset;
}) {
  const { funnel, mode } = useFtsFunnel(preset);
  const data = funnel.stages[stage];

  return (
    <div className="flex w-full flex-col gap-1" data-testid={`fts-stage-${stage}`}>
      <div className="flex items-baseline justify-between gap-2 px-0.5">
        <h2 className="text-sm font-black text-text-primary">
          {STAGE_TITLE[stage]}
          <span className="ms-2 text-3xs font-bold text-text-muted" data-testid="fts-stage-mode">
            {mode === 'review' ? 'مرور کامل بازار' : 'مهندسی معکوس'}
          </span>
        </h2>
        <span className="text-3xs tabular-nums text-text-muted" data-testid={`fts-stage-count-${stage}`}>
          {toFaDigits(data.summary.pass)} عبور از {toFaDigits(data.ruled)} نمادِ universe
        </span>
      </div>
      <FtsFunnelAllStages
        preset={preset}
        only={stage}
        onStageSelect={() => undefined}
      />
    </div>
  );
}

export { funnelStagePath };
