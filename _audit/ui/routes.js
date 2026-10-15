// فهرستِ routeها + نشانۀِ آمادگیِ هرِ صفحه، ازِ خودِ کد (frontend/src/routes.tsx و
// data-testidهایِ واقعیِ هرِ کامپوننت). نشانۀِ خالی یعنی آنِ صفحه testidِ ریشه
// ندارد و سنجش باِ settle انجام می‌شود و درِ گزارش readyBy=no-marker ثبت می‌شود —
// اینِ تفکیک عمداً صادقانه است (درسِ مرحلۀِ سرعت: نشانۀِ غلط، عددِ غلط می‌سازد).
//
// شمارها ازِ _audit/ui/READY_PROBE.json (Edge، ۱۳۶۶×۷۶۸، نشستِ بسته) انتخاب شده‌اند:
// tape-row درِ اینِ نشست ۲۵ ردیف است (نه ۳۰)، و master-breadcrumb فقط رویِ
// /master/<symbol> هست — نمایِ کلیِ مستر باِ fts-funnel-workspace آماده می‌شود.
// نمادِ فولاد دادهٔ واقعی دارد (نمودار و کارت بنیادی)، خوز عمداً به‌عنوانِ
// حالتِ «داده نیست» نگه داشته شده است.
// [route, marker-selector, min-count, یادداشتِ_human]
const ROUTES = [
  ['/market', '[data-testid="tape-row"]', 20, 'تابلوخوانی'],
  ['/market-status', '[data-testid="market-status-page"]', 1, 'وضعیت بازار'],
  ['/technical/فولاد', '[data-testid="chart-area"]', 1, 'تکنیکال باِ نمادِ دارایِ داده'],
  ['/technical/خوز', '[data-testid="nn-no-data"]', 1, 'تکنیکال — حالتِ بی‌داده'],
  ['/technical', '[data-testid="chart-area"]', 1, 'تکنیکال بی‌نماد'],
  ['/fundamental/فولاد', '.glass-panel', 3, 'بنیادی باِ نمادِ دارایِ داده'],
  ['/fundamental/خوز', '.glass-panel', 2, 'بنیادی — حالتِ «صورتِ مالی ندارد»'],
  ['/fundamental', '[data-testid="fts-screen-row"]', 5, 'غربالگری بنیادی'],
  ['/master', '[data-testid="fts-funnel-workspace"]', 1, 'استراتژی FTS (قیف)'],
  ['/master/فولاد', '[data-testid="master-breadcrumb"]', 1, 'مستر باِ نماد'],
  ['/master/خوز', '[data-testid="master-breadcrumb"]', 1, 'مستر — نمادِ بی‌داده'],
  ['/strategy-tree', '[data-testid="strategy-tree-overview"]', 1, 'درخت استراتژی — نمایِ کلی'],
  ['/strategy-tree?page=F', '[data-testid="strategy-tree-page-F"]', 1, 'درخت استراتژی — منطقۀِ F'],
  ['/strategy-tree?page=T', '[data-testid="strategy-tree-page-T"]', 1, 'درخت استراتژی — منطقۀِ T'],
  ['/strategy-tree?page=S', '[data-testid="strategy-tree-page-S"]', 1, 'درخت استراتژی — منطقۀِ S'],
  ['/strategy-tree?page=M', '[data-testid="strategy-tree-page-M"]', 1, 'درخت استراتژی — منطقۀِ M'],
  ['/portfolio', 'main section', 2, 'مدیریت پرتفوی (بی‌testidِ ریشه)'],
  // مأموریت ۱۴۰۵-۰۷-۲۳: مقصدِ تازه‌ای که باید ازِ ناوبریِ اصلی باز شود.
  ['/trade', '[data-testid="trading-page"]', 1, 'معامله (سرخطی وِ ربات)'],
  ['/watch', '[data-testid="watch-market-workspace"]', 1, 'دیده‌بان بازار'],
  ['/notifications', '[data-testid="notice-list"]', 1, 'اطلاعیه‌ها'],
  ['/engine-lab', '[data-testid="engine-lab"]', 1, 'آزمایشگاهِ موتور'],
  ['/zz-not-found', '[data-testid="route-not-found"]', 1, 'صفحۀِ مسیرِ نامعتبر'],
];

module.exports = { ROUTES };
