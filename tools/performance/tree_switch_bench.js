const path=require('path'),fs=require('fs');
const REPO=path.join(__dirname,'..','..');
const {chromium}=require(path.join(REPO,'frontend','node_modules','playwright-core'));
const BASE=process.env.BORS_UI_BASE||'http://127.0.0.1:8000';
const EXE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
(async()=>{const b=await chromium.launch({executablePath:EXE,args:['--no-first-run']});const ctx=await b.newContext({viewport:{width:1366,height:768}});const p=await ctx.newPage();
 await p.goto(BASE+'/',{waitUntil:'domcontentloaded'});await p.waitForTimeout(1000);
 const src=fs.readFileSync(path.join(REPO,'frontend','src','shared','stores','authStore.ts'),'utf8');const u=(src.match(/DEFAULT_USER\s*=\s*'([^']+)'/)||[])[1],pw=(src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/)||[])[1];
 if(await p.locator('input[type=password]').count()){await p.locator('input[type=text]').first().fill(u);await p.locator('input[type=password]').first().fill(pw);await p.locator('button[type=submit]').first().click();await p.waitForTimeout(2200);}
 await p.evaluate(()=>{location.hash='#/strategy-tree';});await p.waitForTimeout(1500);
 const out=[];
 for(let round=0;round<3;round++){
  for(const z of ['S','T','F','M','master']){
   const ms=await p.evaluate(z=>new Promise(res=>{const el=document.querySelector('[data-testid="strategy-tree-workspace"]');const t0=performance.now();let done=false;const fin=()=>{if(done)return;done=true;requestAnimationFrame(()=>requestAnimationFrame(()=>res(performance.now()-t0)));};const mo=new MutationObserver(()=>{if(el&&el.dataset.page===z){mo.disconnect();fin();}});if(el)mo.observe(el,{attributes:true,attributeFilter:['data-page']});document.querySelector(`[data-testid="tree-page-${z}"]`)?.click();setTimeout(()=>{mo.disconnect();fin();},2000);}),z);
   out.push({round,zone:z,ms:Math.round(ms)});
  }
 }
 const zoom=[];
 for(const a of ['chart-zoom-in','chart-zoom-in','chart-zoom-out','chart-fit','chart-focus-T','chart-focus-all']){
  const ms=await p.evaluate(a=>new Promise(res=>{const t0=performance.now();document.querySelector(`[data-testid="${a}"]`)?.click();requestAnimationFrame(()=>requestAnimationFrame(()=>res(performance.now()-t0)));}),a);
  zoom.push({action:a,ms:Math.round(ms)});
 }
 const dom=await p.evaluate(()=>({nodes:document.getElementsByTagName('*').length,svg:document.querySelectorAll('[data-testid="strategy-chart-svg"] *').length}));
 console.log(JSON.stringify({switches:out,zoom,dom},null,1));
 fs.writeFileSync(path.join(REPO,'artifacts/performance/phase2/tree-switch-baseline.json'),JSON.stringify({switches:out,zoom,dom},null,1));
 await b.close();})().catch(e=>{console.error(e);process.exit(1);});
