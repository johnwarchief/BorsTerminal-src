const path=require('path'),fs=require('fs');
const REPO=path.join(__dirname,'..','..');
const {chromium}=require(path.join(REPO,'frontend','node_modules','playwright-core'));
const BASE=process.env.BORS_UI_BASE||'http://127.0.0.1:8000';
const EXE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
(async()=>{const b=await chromium.launch({executablePath:EXE,args:['--no-first-run']});const ctx=await b.newContext({viewport:{width:1366,height:768}});const p=await ctx.newPage();const calls=[];const t0=Date.now();
 p.on('request',r=>{if(r.url().includes('/api/'))calls.push({t:Date.now()-t0,ev:'req',method:r.method(),url:decodeURIComponent(r.url()).replace(/^https?:\/\/[^/]+/,''),body:r.postData()?r.postData().slice(0,100):null});});
 p.on('response',r=>{if(r.url().includes('/api/'))calls.push({t:Date.now()-t0,ev:'res',status:r.status(),url:decodeURIComponent(r.url()).replace(/^https?:\/\/[^/]+/,''),len:r.headers()['content-length']||null});});
 await p.goto(BASE+'/',{waitUntil:'domcontentloaded'});await p.waitForTimeout(900);
 const src=fs.readFileSync(path.join(REPO,'frontend','src','shared','stores','authStore.ts'),'utf8');const u=(src.match(/DEFAULT_USER\s*=\s*'([^']+)'/)||[])[1],pw=(src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/)||[])[1];
 if(await p.locator('input[type=password]').count()){await p.locator('input[type=text]').first().fill(u);await p.locator('input[type=password]').first().fill(pw);await p.locator('button[type=submit]').first().click();await p.waitForTimeout(2200);}
 await p.evaluate(()=>{location.hash='#/technical/فولاد';});await p.waitForTimeout(6000);
 calls.push({t:Date.now()-t0,ev:'MARK-switch'});
 await p.evaluate(()=>{location.hash='#/technical/خودرو';});await p.waitForTimeout(6000);
 fs.writeFileSync(path.join(REPO,'artifacts/performance/phase2/tech-trace.json'),JSON.stringify(calls,null,1));
 for(const c of calls) console.log(`+${c.t} ${c.ev} ${c.method||''} ${c.status||''} ${c.url||''} ${c.len||''}`.slice(0,190));
 await b.close();})().catch(e=>{console.error(e);process.exit(1);});
