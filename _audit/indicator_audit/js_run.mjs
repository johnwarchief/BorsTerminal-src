// `_audit/indicator_audit/js_run.mjs` — اجرایِ ریاضیِ فرانت رویِ دادهٔ واقعی و نوشتنِ JSON.
// اجرا (از پوشهٔ frontend، پس ازِ bundle کردنِ js_entry.ts):
//   node ../_audit/indicator_audit/js_run.mjs <candles.json> <bundle.mjs> <out.json>
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [, , candlesPath, bundlePath, outPath] = process.argv;
const data = JSON.parse(fs.readFileSync(candlesPath, "utf8"));
const mod = await import(pathToFileURL(path.resolve(bundlePath)).href);
const { I, pineStd, MABNA_TEMPLATES } = mod;

const series = {};
const errors = {};
const run = (name, fn) => {
  try {
    series[name] = fn();
  } catch (e) {
    errors[name] = String(e && e.message ? e.message : e);
  }
};

for (const sym of Object.keys(data)) {
  const d = data[sym];
  const c = d.close, h = d.high, l = d.low, v = d.volume, o = d.open;
  const cd = c.map((x, i) => ({ open: o[i], high: h[i], low: l[i], close: x, volume: v[i] }));
  run(`${sym}|I.sma14`, () => I.sma(c, 14));
  run(`${sym}|I.sma20`, () => I.sma(c, 20));
  run(`${sym}|I.sma50`, () => I.sma(c, 50));
  run(`${sym}|I.sma100`, () => I.sma(c, 100));
  run(`${sym}|I.sma120`, () => I.sma(c, 120));
  run(`${sym}|I.ema12`, () => I.ema(c, 12));
  run(`${sym}|I.ema14`, () => I.ema(c, 14));
  run(`${sym}|I.ema26`, () => I.ema(c, 26));
  run(`${sym}|I.ema9of0`, () => I.ema(c, 9));
  run(`${sym}|I.rsi14`, () => I.rsi(c, 14));
  run(`${sym}|I.rsi8`, () => I.rsi(c, 8));
  run(`${sym}|I.rsi5`, () => I.rsi(c, 5));
  run(`${sym}|I.rsi7`, () => I.rsi(c, 7));
  run(`${sym}|I.avgVol20`, () => Array(c.length).fill(I.avgVolume(v, 20)));
  const cl = c.map((x, i) => ({ open: o[i], high: h[i], low: l[i], close: x, volume: v[i] }));
  run(`${sym}|pine.stdev20`, () => pineStd.stdev(c, 20));
  run(`${sym}|pine.rma14`, () => pineStd.rma(c, 14));
  run(`${sym}|pine.trueRange`, () => pineStd.trueRange(cl));
  run(`${sym}|pine.atr14`, () => pineStd.atr(cl, 14));
  run(`${sym}|pine.atr10`, () => pineStd.atr(cl, 10));
  run(`${sym}|pine.vwma20`, () => pineStd.vwma(c, v, 20));
  run(`${sym}|pine.linreg20`, () => pineStd.linreg(c, 20));
  run(`${sym}|pine.stoch5`, () => pineStd.stoch(c, 5));
  run(`${sym}|pine.highest20`, () => pineStd.highest(h, 20));
  run(`${sym}|pine.lowest20`, () => pineStd.lowest(l, 20));
  for (const [key, _unused] of [
    ["MabnaDT", [8, 5, 3, 3]],
    ["MabnaZScore", [20, 2, 1, "close"]],
    ["MabnaSQZMOM", [20, 2, 20, 1.5, true]],
    ["MabnaHalfTrend", [2, 2, true, true, true]],
    ["MabnaSRLevels", [true, 15, 15, 20]],
    ["MabnaWaveTrend", [10, 21, 60, 53, -60, -53]],
    ["MabnaWaveTrendCross", [10, 21, 60, 53, -60, -53]],
    ["MabnaFibBB", [200, 3, "hlc3"]],
    ["MabnaVixFix", [22, 20, 2, 50, 0.85, 1.01, false, false]],
    ["VWAP", []],
    ["SuperTrend", [10, 3, 10]],
    ["HMA", [9]],
    ["Ichimoku", [9, 26, 52, 26]],
    ["MA_Ribbon", [5, 10, 20, 50, 100, 200]],
  ]) {
    const tpl = MABNA_TEMPLATES[key];
    if (!tpl) {
      errors[`${sym}|${key}`] = "not in MABNA_TEMPLATES";
      continue;
    }
    run(`${sym}|${key}`, () => {
      const candles = cl.map((x) => x);
      const rows = tpl.calc(candles, { calcParams: tpl.calcParams });  // پیش‌فرضِ واقعیِ رجیستری
      const out = {};
      for (const f of tpl.figures) out[f.key] = rows.map((r) => (r == null ? null : (r[f.key] === undefined ? null : r[f.key])));
      return { __precision: tpl.precision, __series: tpl.series, __params: tpl.calcParams, rows: out };
    });
  }
}

fs.writeFileSync(outPath, JSON.stringify({ series, errors, stdev_sample_flag: mod.STDEV_SAMPLE }));
const n = Object.keys(series).length;
console.log("ts series:", n, " errors:", Object.keys(errors).length);
for (const [k, e] of Object.entries(errors)) console.log("   ERR", k, "→", e);
