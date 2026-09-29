// features/master/stores/treeFlowStore.ts — جریانِ مسیرِ درخت استراتژی
//
// جهتِ حرکتِ سرمایه رویِ مسیرِ انتخاب درِ درخت با همین انیمیشن خوانده می‌شود،
// پس بی‌آن درخت فقط یک نقشۀ ساکن است. مشکلِ ۱٫۰٫۵۵: پنجرۀ بومیِ برنامه
// (WebView2) ترجیعِ انیمیشنِ ویندوز را به صفحه می‌دهد و CSSِ پوسته درِ همان
// حالت name انیمیشنِ درخت را کلاً `none` می‌کرد — یعنی رویِ همان ماشینِ مالک
// درخت هیچ‌وقت تکان نمی‌خورد، درحالی‌که سنجشِ من (که فقط play-state می‌خواند)
// «running» گزارش می‌داد.
//
// سه حالت، پیش‌فرض «همیشه»:
//   always : جریانِ مسیر همیشه می‌دود (ترجیعِ سیستم نادیده گرفته می‌شود).
//   system : مثلِ استانداردِ دسترس‌پذیری — با reduceِ سیستم خاموش.
//   off    : همیشه خاموش.
// فلگ رویِ `html[data-tree-flow]` می‌نشیند و CSS از همان می‌خواند، تا درختِ
// ساکن هم جهت را بفهمد سرواژه‌هایِ ایستا سرِ جایشان می‌مانند.
import { create } from 'zustand';

const STORAGE_KEY = 'fts.tree.flow.v1';

export type TreeFlowMode = 'always' | 'system' | 'off';
export const DEFAULT_TREE_FLOW: TreeFlowMode = 'always';

export const TREE_FLOW_LABEL: Record<TreeFlowMode, string> = {
  always: 'همیشه',
  system: 'طبقِ سیستم',
  off: 'خاموش',
};

export const TREE_FLOW_HINT: Record<TreeFlowMode, string> = {
  always: 'جریانِ مسیر می‌دود، حتی اگر ویندوز «انیمیشن» را خاموش کرده باشد.',
  system: 'با «کاهشِ حرکتِ سیستم» خودِ درخت هم می‌ایستد.',
  off: 'مسیر ساکن است؛ جهت فقط با سرواژه‌ها و رنگِ خط خوانده می‌شود.',
};

function saved(): TreeFlowMode {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === '"always"' || raw === '"system"' || raw === '"off"') {
      return JSON.parse(raw) as TreeFlowMode;
    }
    if (raw === 'always' || raw === 'system' || raw === 'off') return raw;
    return DEFAULT_TREE_FLOW;
  } catch {
    return DEFAULT_TREE_FLOW;
  }
}

function persist(m: TreeFlowMode) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(m));
  } catch {
    // حافظه در دسترس نیست — فقط state به‌روز می‌شود
  }
}

/** خالص: آیا در این حالت جریان بدود؟ (CSS هم از همان فلگ می‌خواند.) */
export function isFlowRunning(mode: TreeFlowMode, systemReduce: boolean): boolean {
  return mode === 'always' || (mode === 'system' && !systemReduce);
}

function systemReduce(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/** نشاندنِ فلگ رویِ ریشه. برگمی‌گرداند که جریان بدود یا نه. */
export function applyTreeFlow(mode: TreeFlowMode): boolean {
  const running = isFlowRunning(mode, systemReduce());
  document.documentElement.dataset.treeFlow = mode;
  document.documentElement.dataset.treeFlowRunning = running ? '1' : '0';
  return running;
}

export const useTreeFlowStore = create<{ mode: TreeFlowMode; setMode: (m: TreeFlowMode) => void }>(
  (set) => {
    const init = saved();
    let current = init;
    applyTreeFlow(init);
    // در حالتِ «طبقِ سیستم» اگر ترجیعِ انیمیشن وسطِ نشست عوض شود، فلگِ ریشه هم
    // باید عوض شود؛ وگرنه دانه‌ها (که از React می‌خوانند) می‌روند ولی خط‌چین
    // (که از همان فلگ می‌خواند) می‌ماند.
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      window
        .matchMedia('(prefers-reduced-motion: reduce)')
        .addEventListener?.('change', () => applyTreeFlow(current));
    }
    return {
      mode: init,
      setMode: (m) => {
        if (m !== 'always' && m !== 'system' && m !== 'off') return;
        current = m;
        persist(m);
        applyTreeFlow(m);
        set({ mode: m });
      },
    };
  }
);
