const path=require('path'),fs=require('fs');
const REPO=path.join(__dirname,'..','..');
const {chromium}=require(path.join(REPO,'frontend','node_modules','playwright-core'));
const BASE='http://127.0.0.1:8000';
const EXE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
(async()=>{
 const browser=await chromium.launch({executablePath:EXE,args:['--no-first-run']});
 const ctx=await browser.newContext({viewport:{width:1366,height:768}});
 const page=await ctx.newPage();
 const calls=[];
 page.on('request',async r=>{if(r.url().includes('/api/funnel')&&!r.url().includes('registry')) calls.push({t:Date.now(),method:r.method(),url:decodeURIComponent(r.url()).replace(/^https?:\/\/[^/]+/,''),inm:(await r.allHeaders())['if-none-match']||null});});
 page.on('response',r=>{if(r.url().includes('/api/funnel')&&!r.url().includes('registry')) calls.push({t:Date.now(),status:r.status(),etag:r.headers()['etag']||null,gz:r.headers()['content-length']||null});});
 const t0=Date.now();
 await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
 await page.waitForTimeout(1200);
 const src=fs.readFileSync(path.join(REPO,'frontend','src','shared','stores','authStore.ts'),'utf8');
 const u=(src.match(/DEFAULT_USER\s*=\s*'([^']+)'/)||[])[1],p=(src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/)||[])[1];
 if(await page.locator('input[type=password]').count()){await page.locator('input[type=text]').first().fill(u);await page.locator('input[type=password]').first().fill(p);await page.locator('button[type=submit]').first().click();await page.waitForTimeout(2200);}
 await page.waitForTimeout(3000);
 const r0=calls.slice();
 await page.evaluate(()=>{location.hash='#/market';});
 await page.waitForTimeout(6500);
 calls.push({t:Date.now(),mark:'return'});
 await page.evaluate(()=>{location.hash='#/master';});
 await page.waitForTimeout(3000);
 console.log(JSON.stringify(calls.map(c=>({...c,t:c.t-t0})),null,1));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
