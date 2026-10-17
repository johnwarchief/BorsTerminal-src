// tools/tse_saved_filter_eval.mjs — بازتولیدِ **عینی**ِ اجرایِ فیلترِ ذخیره‌شدۀ TSETMC
//
// این فایل هیچ فرمولی را از نو نمی‌نویسد. دو چیز را عیناً از خودِ سایت برداشته‌ام:
//   ۱) `mw.PrepareFilterCode`  (نگاشتِ توکن → فیلدِ ردیف/آرایه)
//   ۲) حلقۀ اجرایِ ExecFilter: `try { R = eval(code) } catch { R = false }`
// و سه باندِ خامِ همان صفحه:
//   tsev2/data/ClosingPriceAll.aspx   → mw.InstHistory[inscode][slot]   ([ih])
//   tsev2/data/InstValue.aspx?t=a     → mw.InstStat[inscode][key]       ([isN])
//   ClosingPrice/GetMarketWatch       → ستون‌هایِ ردیف (l18/tvol/pl/…)
//   ClientType/GetClientTypeAll       → mw.ClientType[inscode]          ((ct))
//
// نتیجه در سطحِ همان نشست سنجیده می‌شود و با فهرستِ مرجع (اجرایِ واقعیِ سایت درِ
// نشستِ مالک، _audit/tse_saved_filter_runs_14050719.json) خودسنجی می‌کند.
//
// اجرا:
//   node tools/tse_saved_filter_eval.mjs            # نوشتن _audit/tse_saved_filter_eval.json
//   node tools/tse_saved_filter_eval.mjs --check     # + خودسنجی با فهرستِ مرجع

import fs from "node:fs";

const FILES = {
  clock: "docs/الگوی ساعت.txt",
  roobi: "docs/کف روبی صف فروش.txt",
  susp: "docs/حجم مشکوک.txt",
  noqteh: "docs/نقطه زنی.txt",
  jet: "docs/فیلتر جت.txt",
  smart: "docs/ورود پول هوشمند.txt",
  legal: "docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt",
};
const IH_FIELDS = ["PClosing", "PDrCotVal", "ZTotTran", "QTotTran5J", "QTotCap",
                   "PriceMin", "PriceMax", "PriceYesterday", "PriceFirst"];

function readText(p) {
  return fs.readFileSync(p, "utf8");
}

// ── mw.LoadInstHistory (عینِ تجزیۀ سایت: ۱۱ ستون = سرآمدنِ نمادِ نو) ─────────
function parseClosingAll(txt) {
  const out = {};
  let cur = "";
  for (const row of txt.split(";")) {
    if (!row) continue;
    const c = row.split(",");
    let code, slot, vals;
    if (c.length === 11) { code = c[0]; slot = +c[1]; vals = c.slice(2); cur = code; }
    else if (c.length === 10) { slot = +c[0]; vals = c.slice(1); }
    else continue;
    const rec = {};
    IH_FIELDS.forEach((f, i) => { rec[f] = parseFloat(vals[i]); });
    if (!out[cur]) out[cur] = [];
    out[cur][slot] = rec;
  }
  return out;
}

// ── mw.LoadInstStat ──────────────────────────────────────────────────────────
function parseInstValue(txt) {
  const out = {};
  let cur = "";
  for (const row of txt.split(";")) {
    if (!row) continue;
    const c = row.split(",");
    if (c.length === 3) { cur = c[0]; if (!out[cur]) out[cur] = {}; out[cur][c[1]] = parseFloat(c[2]); }
    else if (c.length === 2 && cur) { if (!out[cur]) out[cur] = {}; out[cur][c[0]] = parseFloat(c[1]); }
  }
  return out;
}

// ── نگاشتِ باندِ تابلو به نام‌هایِ ExecFilter (مستند درِ tape_flags.py) ───────
function toRow(r, ct) {
  const b = (r.blDs && r.blDs[0]) || {};
  const num = (v) => (v === undefined || v === null || v === "" ? 0 : +v);
  const py = num(r.py);
  const pl = num(r.pdv);
  return {
    inscode: String(r.insCode), iid: r.insID, l18: r.lva, l30: r.lvc,
    tvol: num(r.qtj), tno: num(r.ztt), tval: num(r.qtc),
    pl, pc: num(r.pcl), plc: num(r.pc), pcp: num(r.pcpc),
    py, pf: num(r.pf), pmin: num(r.pmn), pmax: num(r.pmx),
    tmin: r.pMin === undefined ? undefined : num(r.pMin),
    tmax: r.pMax === undefined ? undefined : num(r.pMax),
    eps: num(r.eps), pe: num(r.pe), bvol: num(r.bv), mv: num(r.ztd),
    // cfield0/1/2 درِ سایت رشته‌هایِ خالی‌اند و فیلتر «نقطه‌زنی» پیش از
    // فراخوانیِ MinPriceOfMonth() آن‌ها را می‌خواند؛ `"" < 3` درِ JS درست است
    // ولی `undefined < 3` نادرست — پس نبودنش کلِ فیلتر را صفر می‌کرد.
    cfield0: r.cfield0 === undefined ? "" : r.cfield0,
    cfield1: r.cfield1 === undefined ? "" : r.cfield1,
    cfield2: r.cfield2 === undefined ? "" : r.cfield2,
    cs: num(r.csv), predtran: num(r.pRedTran), buyop: num(r.buyOP), z: num(r.ztd),
    yval: num(r.yVal), visitcount: num(r.vc), heven: r.hEven,
    pd1: num(b.pmd), qd1: num(b.qmd), zd1: num(b.zmd),
    po1: num(b.pmo), qo1: num(b.qmo), zo1: num(b.zmo),
    // plp درِ سایت درصدِ آخرین نسبت به دیروز است (نه پایانی)
    plp: py > 0 ? Math.round((100 * (pl - py)) / py * 100) / 100 : 0,
    ct: ct ? {
      Buy_I_Volume: num(ct.buy_I_Volume), Buy_N_Volume: num(ct.buy_N_Volume),
      Buy_CountI: num(ct.buy_CountI), Buy_CountN: num(ct.buy_CountN),
      Sell_I_Volume: num(ct.sell_I_Volume), Sell_N_Volume: num(ct.sell_N_Volume),
      Sell_CountI: num(ct.sell_CountI), Sell_CountN: num(ct.sell_CountN),
    } : undefined,
  };
}

// ── PrepareFilterCode، عینِ تابعِ صفحه (ترتیبِ replaceها محفوظ) ──────────────
function prepareFilterCode(raw) {
  let code = raw;
  const simple = {
    l18: 'row["l18"]', l30: 'row["l30"]', tno: 'parseInt(row["tno"],10)',
    tvol: 'parseInt(row["tvol"],10)', tval: 'parseInt(row["tval"],10)',
    py: 'parseFloat(row["py"])', pf: 'parseFloat(row["pf"])',
    pmin: 'parseFloat(row["pmin"])', pmax: 'parseFloat(row["pmax"])',
    pl: 'parseFloat(row["pl"])', plc: 'parseFloat(row["plc"])', plp: 'parseFloat(row["plp"])',
    pc: 'parseFloat(row["pc"])', pcc: 'parseFloat(row["pcc"])', pcp: 'parseFloat(row["pcp"])',
    eps: 'parseFloat(row["eps"])', pe: 'parseFloat(row["pe"])', mv: 'parseFloat(row["mv"])',
    bvol: 'parseInt(row["bvol"],10)', cs: 'parseInt(row["cs"],10)',
    predtran: 'parseInt(row["predtran"],10)', buyop: 'parseInt(row["buyop"],10)',
    tmax: 'parseFloat(row["tmax"])', tmin: 'parseFloat(row["tmin"])',
    z: 'parseInt(row["z"],10)',
  };
  for (const d of ["1", "2", "3", "4", "5"]) {
    simple[`pd${d}`] = `parseFloat(row["pd${d}"])`; simple[`zd${d}`] = `parseInt(row["zd${d}"],10)`;
    simple[`qd${d}`] = `parseFloat(row["qd${d}"])`; simple[`po${d}`] = `parseFloat(row["po${d}"])`;
    simple[`zo${d}`] = `parseInt(row["zo${d}"],10)`; simple[`qo${d}`] = `parseFloat(row["qo${d}"])`;
  }
  for (const k of ["cfield0", "cfield1", "cfield2"]) simple[k] = `row["${k}"]`;
  // (name) — با فاصله‌هایِ ممکن داخلِ پرانتز
  code = code.replace(/\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)/g, (m, name) =>
    simple[name] ? simple[name] : m);
  code = code.replace(/\(ct\)\.(\w+)/g, 'mw.ClientType[row["inscode"]].$1');
  code = code.replace(/\[is/g, 'mw.InstStat[row["inscode"]][');
  code = code.replace(/\[ih\]/g, 'mw.InstHistory[row["inscode"]]');
  return code;
}

function main() {
  const hist = parseClosingAll(readText("_audit/tse_cache_ClosingPriceAll.txt"));
  const inst = parseInstValue(readText("_audit/tse_cache_InstValue.txt"));
  const mwRows = JSON.parse(readText("_audit/tse_cache_mw_rows.json"));
  const ctList = JSON.parse(readText("_audit/tse_cache_ct.json"));
  const ctBy = Object.fromEntries(ctList.map((x) => [String(x.insCode), x]));

  const src = {};
  for (const [k, p] of Object.entries(FILES)) src[k] = readText(p).replace(/\r/g, "");

  const hits = Object.fromEntries(Object.keys(FILES).map((k) => [k, []]));
  const throws = Object.fromEntries(Object.keys(FILES).map((k) => [k, 0]));
  const throwKinds = Object.fromEntries(Object.keys(FILES).map((k) => [k, {}]));
  // هر سه آرایه درِ سایت «شیءِ کلیدرشته‌ای» است (نه Map)؛ `mw.InstStat[code][6]`
  // و `mw.InstHistory[code][k]` باید عیناً همین‌طور کار کنند.
  const ctObj = {};
  for (const [code, a] of Object.entries(ctBy)) {
    ctObj[code] = {
      Buy_I_Volume: +(a.buy_I_Volume || 0), Buy_N_Volume: +(a.buy_N_Volume || 0),
      Buy_CountI: +(a.buy_CountI || 0), Buy_CountN: +(a.buy_CountN || 0),
      Sell_I_Volume: +(a.sell_I_Volume || 0), Sell_N_Volume: +(a.sell_N_Volume || 0),
      Sell_CountI: +(a.sell_CountI || 0), Sell_CountN: +(a.sell_CountN || 0),
    };
  }
  const env = { mw: { InstStat: inst, InstHistory: hist, ClientType: ctObj } };

  const names = Object.keys(env.mw);
  let evaluated = 0;
  for (const r of mwRows) {
    const row = toRow(r, ctBy[String(r.insCode)]);
    evaluated++;
    for (const key of Object.keys(FILES)) {
      const code = prepareFilterCode(src[key]);
      let res = false;
      // حلقۀ عینِ سایت: یک `eval` روی **کلِ** متنِ چندسطری. JS مقدارِ آخرین
      // عبارتِ اجرایی را برمی‌گرداند، ولی همۀ خطوطِ پیشین اجرا می‌شوند و هر
      // استثنای آن‌ها (مثلاً `[ih][17].QTotTran5J`ِ غایب، یا «نقطه‌زنی» که
      // ۲۴ خطش یک عبارتِ واحد است) ردیف را بیرون می‌اندازد ⇒ false.
      //
      // «نقطه‌زنی» stateful است: `(cfield2)<3` **پیش از** نوشته‌شدنِ `(cfield2)`
      // خوانده می‌شود، پس درِ passِ اول آن شرط با رشتهِ خالی درست می‌آید و
      // فیلترِ واقعی از passِ دوم کار می‌کند. سایت هر ردیف را درِ هر تیک دوباره
      // می‌سنجد، پس اینجا هم دو pass می‌زنیم و ارزشِ passِ آخر را نگه می‌داریم.
      const passes = key === "noqteh" ? 2 : 1;
      for (let p = 0; p < passes; p++) {
        try {
          const f = new Function("row", "mw",
            `let FilterResult; try { FilterResult = eval(${JSON.stringify(code)}); }`
            + ` catch (e) { return [false, (e && e.constructor && e.constructor.name) || 'Error']; }`
            + ` return [!!FilterResult, null];`);
          const [v, kind] = f(row, env.mw);
          res = v;
          if (kind && p === passes - 1) {
            throws[key]++;
            throwKinds[key][kind] = (throwKinds[key][kind] || 0) + 1;
          }
        } catch (e) {
          throws[key]++;
          res = false;
        }
      }
      if (res === true) hits[key].push(row.inscode);
    }
  }

  const counts = Object.fromEntries(Object.entries(hits).map(([k, v]) => [k, v.length]));
  const out = { generated_by: "tools/tse_saved_filter_eval.mjs", rows: evaluated,
                hist_codes: Object.keys(hist).length, inst_codes: Object.keys(inst).length, ct_codes: Object.keys(ctBy).length,
                counts, throws, throw_kinds: throwKinds,
                codes: Object.fromEntries(Object.entries(hits).map(([k, v]) => [k, v.join(" ")])) };
  fs.mkdirSync("_audit", { recursive: true });
  fs.writeFileSync("_audit/tse_saved_filter_eval.json", JSON.stringify(out, null, 1), "utf8");
  console.log("rows:", evaluated, "| counts:", JSON.stringify(counts));
  console.log("throws:", JSON.stringify(throws));
  console.log("throw kinds:", JSON.stringify(throwKinds));

  if (process.argv.includes("--check")) {
    const ref = JSON.parse(readText("_audit/tse_saved_filter_runs_14050719.json"));
    const map = { clock: "f0_clock", roobi: "f1_roobi", susp: "f2_susp", noqteh: "f3_noqteh",
                  jet: "f4_jet", smart: "f5_smart", legal: "f6_legal" };
    console.log("\n== خودسنجی در برابرِ اجرایِ واقعیِ سایت (نشستِ مالک)");
    for (const [k, key] of Object.entries(map)) {
      const want = new Set(((ref.site_results?.[key]?.codes) || "").split(" ").filter(Boolean));
      const got = new Set(hits[k]);
      const inter = [...want].filter((x) => got.has(x)).length;
      console.log(`   ${k.padEnd(6)} مرجع=${String(want.size).padStart(4)} بازتولید=${String(got.size).padStart(4)}`
        + ` مشترک=${String(inter).padStart(4)} فقط‌مرجع=${want.size - inter} فقط‌این=${got.size - inter}`);
    }
  }
  console.log("wrote _audit/tse_saved_filter_eval.json");
}

main();
