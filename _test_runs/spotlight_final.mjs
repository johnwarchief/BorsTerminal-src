import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
const EDGE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const OUT='D:/BorsTerminal-worktrees/4axes-main-integration/_test_runs/live';
const PORT=9231; mkdirSync(OUT,{recursive:true});
const edge=spawn(EDGE,['--headless=new','--disable-gpu','--hide-scrollbars',`--remote-debugging-port=${PORT}`,`--user-data-dir=${OUT}/edge-profile-final`,'--no-first-run','about:blank'],{stdio:'ignore'});
async function getWs(){for(let i=0;i<60;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/list`);const p=await r.json();const pg=p.find(x=>x.type==='page');if(pg?.webSocketDebuggerUrl)return pg.webSocketDebuggerUrl;}catch{}await sleep(300);}throw new Error('no cdp');}
const ws=new WebSocket(await getWs());await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});
let seq=0;const pend=new Map();
ws.onmessage=(e)=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){const{resolve,reject}=pend.get(m.id);pend.delete(m.id);m.error?reject(new Error(m.error.message)):resolve(m.result);}};
const send=(method,params={})=>{const id=++seq;return new Promise((resolve,reject)=>{pend.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pend.has(id)){pend.delete(id);reject(new Error('timeout '+method));}},40000);});};
const ev=async(x)=>{const r=await send('Runtime.evaluate',{expression:x,awaitPromise:true,returnByValue:true});return r.result?.value;};
const shot=async(n)=>{const{data}=await send('Page.captureScreenshot',{format:'png'});writeFileSync(`${OUT}/${n}.png`,Buffer.from(data,'base64'));console.log('saved',n);};
await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width:1366,height:768,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:'http://127.0.0.1:5181/#/technical'});
for(let i=0;i<60;i++){if(await ev('(document.querySelector("#root")?.childElementCount||0)>0'))break;await sleep(1200);}
await sleep(6000);
async function change(sym){
  await ev(`(()=>{const i=document.querySelector('input[type=text]');const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(i,${JSON.stringify(sym)});i.dispatchEvent(new Event('input',{bubbles:true}));return i.value;})()`);
  await sleep(300);
  await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').trim()==='اعمال');if(b){b.click();return true;}return false;})()`);
  await sleep(7000);
  return ev(`(()=>{const el=document.querySelector('[data-testid="spotlight-overlay"]');return JSON.stringify({spot:el?el.textContent.replace(/\s+/g,' ').slice(0,180):null,symbolLegend:(document.body.innerText.match(/فولاد|خودرو|شپنا|فارس|وبملت/g)||[]).join(',')});})()`);
}
for(const s of ['خودرو','شپنا']){
  console.log(s,'->',await change(s));
  await shot(`spotlight-1366-${s}-final`);
}
// weekly on the last symbol
await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').trim()==='هفتگی');if(b){b.click();return true;}return false;})()`);
await sleep(7000);
console.log('weekly ->',await ev(`(()=>{const el=document.querySelector('[data-testid="spotlight-overlay"]');return JSON.stringify({spot:el?el.textContent.replace(/\s+/g,' ').slice(0,180):null});})()`));
await shot('spotlight-1366-weekly-final');
ws.close();edge.kill();
