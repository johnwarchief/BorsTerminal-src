// _audit/ra365_job_smoke.js -- ششمِ نشستِ زنده: آیا لاگین حفظ است + رابطِ چارتِ ره‌آورد چه دارد
// دو کارِ هم‌زمان:
//  ۱) اثباتِ وضعیتِ احراز هویت در rahavard365.com (بدونِ خواندنِ کوکی/توکن؛ فقط DOM)
//  2) اثباتِ مبدأِ asset idها: اگر /asset/453/chart همان «فولاد مبارکه» باشد، برچسب‌هایِ انسانیِ
//     REFERENCE.csv از رابطِ ره‌آورد خوانده شده‌اند (نه تریدرز آرنا) — این مبدأِ گزارشِ قبلی است.
module.exports = async ({ page, shot, probe, say }) => {
  const rep = { auth: {}, assets: {}, chart: {} };

  await page.goto('https://rahavard365.com/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(12000);
  const home = await probe();
  rep.auth.home = { loginButtonPresent: home.loginButtonPresent, logoutTextPresent: home.logoutTextPresent, gate: home.paywallOrGate, title: home.title, nodes: home.nodes };
  rep.shotHome = await shot('ra365_home_loggedin');

  // asset idهایی که REFERENCE.csv گزارشِ قبلی برایِ نمادها ثبت کرده است
  const IDS = { '453': 'فولاد(ادعا)', '462': 'وبملت(ادعا)', '599': 'ولانا(ادعا)', '149': 'فنوال(ادعا)', '167': 'خودرو(ادعا)', '484': 'شپنا(ادعا)' };
  for (const [id, claim] of Object.entries(IDS)) {
    try {
      await page.goto(`https://rahavard365.com/asset/${id}/chart`, { waitUntil: 'domcontentloaded', timeout: 90000 });
      await page.waitForTimeout(14000);
      const p = await probe();
      rep.assets[id] = { claim, title: p.title, url: p.url, loginButtonPresent: p.loginButtonPresent, gate: p.paywallOrGate, tv: p.chartWidgets.tradingview, canvas: p.canvases, nodes: p.nodes };
      say(`${id} (${claim}) -> ${p.title}`);
      if (id === '453') {
        rep.chart = { toolbarItems: p.toolbarItems.slice(0, 90), axisLikeTexts: p.axisLikeTexts.slice(0, 40), jalali: p.jalaliDates, sample: p.visibleTextSample.slice(0, 500) };
        rep.shotChart = await shot('ra365_folad_chart');
      }
    } catch (e) {
      rep.assets[id] = { claim, error: String(e).slice(0, 180) };
    }
  }
  return rep;
};
