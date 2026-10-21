// Дымовая проверка правок 1.6 на живой странице.
const fs = require("fs");
const http = require("http");
const base = "http://127.0.0.1:9224";
const sleep = ms => new Promise(r => setTimeout(r, ms));
function cdpGet(p){ return new Promise((res,rej)=>{ http.get(base+p, r=>{ let d=""; r.on("data",c=>d+=c); r.on("end",()=>res(d?JSON.parse(d):null)); }).on("error",rej); }); }

async function main(){
  const ver = await cdpGet("/json/version");
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res,rej)=>{ ws.onopen=res; ws.onerror=rej; });
  let seq=0; const pending=new Map();
  ws.onmessage = ev => { const m=JSON.parse(ev.data); if(m.id&&pending.has(m.id)){ const p=pending.get(m.id); pending.delete(m.id); m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result); } };
  const send=(method,params={},sessionId)=>new Promise((res,rej)=>{ const id=++seq; pending.set(id,{res,rej}); ws.send(JSON.stringify({id,method,params,sessionId})); });
  const t = await send("Target.createTarget",{url:"about:blank"});
  const att = await send("Target.attachToTarget",{targetId:t.targetId,flatten:true});
  const sid = att.sessionId;
  const S=(m,p)=>send(m,p,sid);
  await S("Page.enable"); await S("Runtime.enable");
  await S("Emulation.setDeviceMetricsOverride",{width:1500,height:1150,deviceScaleFactor:1,mobile:false});
  await S("Page.navigate",{url:"http://127.0.0.1:8842/"});
  for(let i=0;i<40;i++){ await sleep(500); const r=await S("Runtime.evaluate",{expression:"typeof ST!=='undefined'&&typeof applyLang==='function'",returnByValue:true}); if(r.result&&r.result.value) break; }
  await sleep(2500);
  const ev = async (expr) => {
    const r = await S("Runtime.evaluate",{expression:expr,awaitPromise:true,returnByValue:true});
    if(r.exceptionDetails) return "JS ERROR: "+JSON.stringify(r.exceptionDetails).slice(0,300);
    return r.result && r.result.value;
  };
  console.log("1. лимит по умолчанию: " + await ev("document.getElementById('limit').value"));
  console.log("2. подпись колоды: " + await ev("document.getElementById('deckHint').innerText"));
  console.log("3. смена колоды -> " + await ev("(function(){var s=document.getElementById('deck'); s.value='Архитектура'; s.dispatchEvent(new Event('change')); return document.getElementById('deckHint').innerText;})()"));
  console.log("4. мусорный лимит: " + await ev("api('/api/run',{kind:'voice',voice:'narrator',deck:'AnkiVoice_Проверка чтения',limit:'-5'}).then(()=>'ПРОПУСТИЛ (плохо)').catch(e=>e.message)"));
  console.log("5. «abc» вместо числа: " + await ev("api('/api/run',{kind:'voice',voice:'narrator',deck:'AnkiVoice_Проверка чтения',limit:'abc'}).then(()=>'ПРОПУСТИЛ (плохо)').catch(e=>e.message)"));
  console.log("6. «Проверить» не пишет в конфиг: " + await ev("(async function(){ var before = JSON.stringify(ST.cfg.indextts_path); var j = await api('/api/config',{check_path:true, indextts_path:'C:\\\\Нет\\\\Такой\\\\Папки'}); var st = await api('/api/state'); return (before===JSON.stringify(st.cfg.indextts_path)) ? 'не изменил ✓' : 'ИЗМЕНИЛ (плохо)'; })()"));
  console.log("7. голосов готово: " + await ev("document.getElementById('engineHint').innerText"));
  console.log("8. кнопки: " + await ev("Array.from(document.querySelectorAll('#p-voice button')).map(b=>b.id||b.textContent.trim()).join(' | ')"));
  console.log("9. есть ли «Пропустить» в мастере: " + await ev("!!document.getElementById('wzSkip')"));
  await ev("closeWizard(); openWizard(0);");
  await sleep(800);
  console.log("10. шаг мастера: " + await ev("document.querySelector('.wizard h3') ? document.querySelector('.wizard h3').innerText : '?'"));
  await ev("closeWizard(); goTab('voice');");
  await sleep(600);
  const shot = await S("Page.captureScreenshot",{format:"png",fromSurface:true,captureBeyondViewport:true});
  fs.writeFileSync("qa/first-users/06-after-fixes-main.png", Buffer.from(shot.data,"base64"));
  console.log("снимок: qa/first-users/06-after-fixes-main.png");
  await send("Target.closeTarget",{targetId:t.targetId});
  ws.close();
}
main().catch(e=>{ console.error("ERR "+e.message); process.exit(1); });
