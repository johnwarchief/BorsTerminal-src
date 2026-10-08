// features/master/stores/funnelPrefsStore.ts -- دستِ کاربر درِ قیفِ غربالگری
//
// قیفِ FTS چهار مرحلۀ جزوه را می‌گذراند و درِ بنیادی سخت‌گیرترینشان است.
// این گزینه‌ها سخت‌گیریِ جزوه را کم نمی‌کنند، فقط حقِ انتخاب را به خودِ مالک
// می‌دهند؛ پیش‌فرض‌هایشان عینِ جزوه است (کفِ سه از پنج، «بی‌داده وتو نیست»،
// و تکنیکالِ غربال‌کن):
//   - `fundFloor`   : چند شاخص از پنج‌شاخصهٔ کدال کافی است.
//   - `unmeasured`  : با ردیفی که بنیادش واقعاً سنجیده نشده چه شود.
//   - `techScreens`: آیا وتوی تکنیکال نماد را حذف کند، یا فقط برچسب بخورد
//                    و ردیف به بنیادی برسد تا خودِ مالک روندِ هفتگی را ببیند.
import { create } from 'zustand';

/** سه سیستمِ انتخاب + ساعت‌شنی — همان `TreePreset` درِ `lib/ftsFunnel.ts`.
 *  اینجا دوباره نوشته شده تا store به لایۀ UI وابسته نشود (چرخۀ import). */
export type FunnelPreset = 'swing' | 'trend' | 'hourglass' | 'custom';
const PRESETS: readonly FunnelPreset[] = ['swing', 'trend', 'hourglass', 'custom'];
/** unset یعنی «کاربر هنوز خودش انتخاب نکرده» — تا آن وقت propِ والد (افقِ
 *  سراسری) مرجع است؛ بعد از اولین انتخاب، همان چیزی که کاربر زد می‌ماند. */
export const DEFAULT_PRESET: FunnelPreset | null = null;

/** دو حالتِ کشفِ نماد — هر دو از یک قراردادِ داوری (`lib/ftsFunnel.ts`). */
export type FunnelMode = 'reverse' | 'review';
/** پیش‌فرضِ جزوه: مهندسیِ معکوس (S ➔ T ➔ F ➔ M). */
export const DEFAULT_FUNNEL_MODE: FunnelMode = 'reverse';

const STORAGE_KEY = 'fts.funnel.prefs.v1';
const MODE_KEY = ['fts', 'funnel', 'fund_mode', 'v1'].join('.');

/** پیش‌فرضِ جزوه: سه از پنج. */
export const DEFAULT_FUND_FLOOR = 3;
export const FUND_FLOOR_MAX = 5;

/** «سنجیده‌نشده» درِ بنیادی: درِ انتظار بماند (جزوه) / عبور کند / حذف شود. */
export type UnmeasuredPolicy = 'hold' | 'pass' | 'drop';
export const DEFAULT_UNMEASURED: UnmeasuredPolicy = 'hold';

export const UNMEASURED_LABEL: Record<UnmeasuredPolicy, string> = {
  hold: 'در انتظارِ گزارش',
  pass: 'عبور با برچسب',
  drop: 'حذف از قیف',
};

export const UNMEASURED_HINT: Record<UnmeasuredPolicy, string> = {
  hold: 'نه رد می‌شوند نه تحویل؛ در گروهِ «سنجیده نشد» زیرِ همان مرحله می‌مانند — قانونِ جزوه.',
  pass: 'با برچسبِ «سنجیده نشد» به تحویل می‌روند؛ خودتان می‌دانید که بنیادشان خوانده نشده.',
  drop: 'از قیف بیرون می‌افتند تا فهرستِ تحویل فقط سنجیده‌ها را نشان دهد.',
};

/** پیش‌فرض: تکنیکال غربال می‌کند، ولی فقط وتوی صریحِ روند هفتگی درِ حذف است. */
export const DEFAULT_TECH_SCREENS = true;

export const TECH_SCREEN_LABEL = { on: 'رد می‌کند', off: 'خودم چک می‌کنم' } as const;

export const TECH_SCREEN_HINT = {
  on: 'وتوی هفتگیِ نزولی/خنثی نماد را از قیف بیرون می‌اندازد؛ Jet/Fib/CHoCH و سایر ستاپ‌ها فقط امتیاز کمکی‌اند.',
  off: 'وتوی هفتگی فقط برچسب می‌خورد و به بنیادی می‌رسد؛ ستاپ‌ها در هیچ حالتی گیت حذف نیستند.',
} as const;

/** سه حالتِ سخت‌گیریِ بنیادی — رأیِ مالک ۱۴۰-۰۷-۱۶ بند ۱۸.
 *  standard پیش‌فرض است: I1/I2/I3 بلاکر، I4/I5 شاهد. */
export type FundStrictness = 'hard' | 'standard' | 'exception';
export const DEFAULT_FUND_MODE: FundStrictness = 'standard';
export const FUND_MODE_LABEL: Record<FundStrictness, string> = {
  hard: 'سختگیرانه', standard: 'استاندارد FTS', exception: 'استثنا',
};
export const FUND_MODE_HINT: Record<FundStrictness, string> = {
  hard: 'هر پنج شاخص باید تأیید باشند.',
  standard: 'سه شاخص اول بلاکرند؛ I4 و I5 فقط شاهد و رتبه‌بندی.',
  exception: 'قانون عوض نمی‌شود؛ فقط استثنایِ صریحِ شما برایِ یک نماد، با برچسب.',
};

/** یک presetِ ذخیره‌شده: زنجیرۀ ترتیب‌دار + پارامترها + نسخۀ رجیستری (§10). */
export type SavedChain = {
  id: string; name: string; chain: string[];
  params: Record<string, Record<string, number>>;
  fundMode: FundStrictness;
  registryVersion: string;
  createdAt: number;
};

const CHAIN_KEY = ['fts', 'funnel', 'chain', 'v1'].join('.');
const PRESETS_KEY = ['fts', 'funnel', 'presets', 'v1'].join('.');
const EXC_KEY = ['fts', 'funnel', 'exceptions', 'v1'].join('.');

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* فقط state */ }
}

export type FunnelPrefsState = {
  /** system انتخابیِ کاربر درِ خودِ workspace — `custom` درِ strategyStore نیست
   *  (افقِ آنجا سه‌تاست و پلنِ معامله به آن وابسته است)، پس قیف preset خودش
   *  را نگه می‌دارد و فقط وقتی یکی از سه افقِ واقعی است، افق را هم عوض می‌کند. */
  preset: FunnelPreset | null;
  /** زنجیرۀ ترتیب‌دارِ Custom — همان چیزی که موتورِ بک‌اند مصرف می‌کند */
  chain: string[];
  setChain: (chain: string[]) => void;
  moveFilter: (from: number, to: number) => void;
  addFilter: (id: string) => void;
  removeFilter: (id: string) => void;
  fundMode: FundStrictness;
  setFundMode: (m: FundStrictness) => void;
  /** استثنایِ صریحِ نماد → شاخص‌ها؛ هیچ جبرانِ خودکاری اینجا نیست */
  exceptions: Record<string, string[]>;
  setException: (symbol: string, indicators: string[]) => void;
  savedChains: SavedChain[];
  saveChain: (name: string, registryVersion: string) => string;
  renameChain: (id: string, name: string) => void;
  loadChain: (id: string) => void;
  deleteChain: (id: string) => void;
  fundFloor: number;
  unmeasured: UnmeasuredPolicy;
  techScreens: boolean;
  mode: FunnelMode;
  setPreset: (p: FunnelPreset) => void;
  setFundFloor: (n: number) => void;
  setUnmeasured: (p: UnmeasuredPolicy) => void;
  setTechScreens: (on: boolean) => void;
  setMode: (m: FunnelMode) => void;
  reset: () => void;
  resetToCanonical: () => void;
};

function clampFloor(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_FUND_FLOOR;
  return Math.min(FUND_FLOOR_MAX, Math.max(1, Math.round(n)));
}

type SavedPrefs = { preset: FunnelPreset | null; fundFloor: number; unmeasured: UnmeasuredPolicy; techScreens: boolean; mode: FunnelMode };

const JOZVE: SavedPrefs = {
  preset: DEFAULT_PRESET,
  fundFloor: DEFAULT_FUND_FLOOR,
  unmeasured: DEFAULT_UNMEASURED,
  techScreens: DEFAULT_TECH_SCREENS,
  mode: DEFAULT_FUNNEL_MODE,
};

function saved(): SavedPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return JOZVE;
    const p = JSON.parse(raw) as { preset?: unknown; fundFloor?: unknown; unmeasured?: unknown; techScreens?: unknown; mode?: unknown };
    return {
      preset: PRESETS.includes(p.preset as FunnelPreset) ? (p.preset as FunnelPreset) : null,
      fundFloor: clampFloor(typeof p.fundFloor === 'number' ? p.fundFloor : DEFAULT_FUND_FLOOR),
      unmeasured:
        p.unmeasured === 'pass' || p.unmeasured === 'drop' ? p.unmeasured : DEFAULT_UNMEASURED,
      // کلیدِ تازه: فایلِ ذخیره‌شده‌هایِ قدیم این را ندارد. نبودش یعنی همان
      // رفتارِ همیشگی (غربال)، نه تغییرِ بی‌صدا.
      techScreens: typeof p.techScreens === 'boolean' ? p.techScreens : DEFAULT_TECH_SCREENS,
      // نبودِ کلیدِ mode درِ فایل‌هایِ قدیم یعنی همان رفتارِ همیشگی (معکوس).
      mode: p.mode === 'review' ? 'review' : DEFAULT_FUNNEL_MODE,
    };
  } catch {
    return JOZVE;
  }
}

function persist(s: SavedPrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // حافظه در دسترس نیست — فقط state به‌روز می‌شود
  }
}


function clampIndex(n: number, len: number): number {
  return Math.max(0, Math.min(len - 1, Math.round(n)));
}

function moved<T>(list: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || from >= list.length) return list;
  const out = list.slice();
  const [x] = out.splice(from, 1);
  out.splice(clampIndex(to, out.length), 0, x);
  return out;
}

export const useFunnelPrefsStore = create<FunnelPrefsState>((set, get) => {
  const init = saved();
  const chains = readJson<string[]>(CHAIN_KEY, []);
  const fundMode = readJson<FundStrictness>(MODE_KEY, DEFAULT_FUND_MODE);
  const exceptions = readJson<Record<string, string[]>>(EXC_KEY, {});
  const savedChains = readJson<SavedChain[]>(PRESETS_KEY, []);
  return {
    preset: init.preset,
    chain: chains,
    setChain: (c) => { writeJson(CHAIN_KEY, c); set({ chain: c }); },
    moveFilter: (from, to) => {
      const next = moved(get().chain, from, to);
      writeJson(CHAIN_KEY, next); set({ chain: next });
    },
    addFilter: (id) => {
      if (get().chain.includes(id)) return;
      const next = [...get().chain, id];
      writeJson(CHAIN_KEY, next); set({ chain: next });
    },
    removeFilter: (id) => {
      const next = get().chain.filter((x) => x !== id);
      writeJson(CHAIN_KEY, next); set({ chain: next });
    },
    fundMode: (fundMode === 'hard' || fundMode === 'exception') ? fundMode : DEFAULT_FUND_MODE,
    setFundMode: (m) => { writeJson(MODE_KEY, m); set({ fundMode: m }); },
    exceptions,
    setException: (symbol, indicators) => {
      const cur = { ...get().exceptions };
      if (indicators.length) cur[symbol] = indicators; else delete cur[symbol];
      writeJson(EXC_KEY, cur); set({ exceptions: cur });
    },
    savedChains,
    saveChain: (name, registryVersion) => {
      const id = `c${Date.now().toString(36)}`;
      const row: SavedChain = { id, name, chain: get().chain.slice(), params: {},
                                fundMode: get().fundMode, registryVersion,
                                createdAt: Date.now() };
      const next = [...get().savedChains.filter((c) => c.name !== name), row];
      writeJson(PRESETS_KEY, next); set({ savedChains: next });
      return id;
    },
    renameChain: (id, name) => {
      const next = get().savedChains.map((c) => (c.id === id ? { ...c, name } : c));
      writeJson(PRESETS_KEY, next); set({ savedChains: next });
    },
    loadChain: (id) => {
      const row = get().savedChains.find((c) => c.id === id);
      if (!row) return;
      writeJson(CHAIN_KEY, row.chain); writeJson(MODE_KEY, row.fundMode);
      set({ chain: row.chain.slice(), fundMode: row.fundMode, preset: 'custom' });
    },
    deleteChain: (id) => {
      const next = get().savedChains.filter((c) => c.id !== id);
      writeJson(PRESETS_KEY, next); set({ savedChains: next });
    },
    fundFloor: init.fundFloor,
    unmeasured: init.unmeasured,
    techScreens: init.techScreens,
    mode: init.mode,
    setPreset: (p) => {
      if (!PRESETS.includes(p)) return;
      persist({ ...get(), preset: p });
      set({ preset: p });
    },
    setFundFloor: (n) => {
      const v = clampFloor(n);
      persist({ ...get(), fundFloor: v });
      set({ fundFloor: v });
    },
    setUnmeasured: (p) => {
      persist({ ...get(), unmeasured: p });
      set({ unmeasured: p });
    },
    setTechScreens: (on) => {
      persist({ ...get(), techScreens: on });
      set({ techScreens: on });
    },
    setMode: (m) => {
      persist({ ...get(), mode: m });
      set({ mode: m });
    },
    reset: () => {
      persist(JOZVE);
      set(JOZVE);
    },
    /** بازگشت به canon: زنجیرۀ Custom و استثنناها پاک می‌شوند، presetِ افق نه. */
    resetToCanonical: () => {
      writeJson(CHAIN_KEY, []); writeJson(MODE_KEY, DEFAULT_FUND_MODE);
      writeJson(EXC_KEY, {});
      set({ chain: [], fundMode: DEFAULT_FUND_MODE, exceptions: {} });
    },
  };
});
