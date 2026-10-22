// Проверка прогресса: сколько карточек считает страница.
const http = require("http");
const base = "http://127.0.0.1:9224";
const sleep = ms => new Promise(r => setTimeout(r, ms));
function g(p){return new Promise((res,rej)=>{http.get(base+p,r=>{let d="";r.on("data",c=>d+=c);r.on("end",()=>res(d?JSON.parse(d):null));}).on("error",rej);});}

(async()=>{
  const ver=await g("/json/version");const ws=new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});
  let seq=0;const pend=new Map();
  ws.onmessage=ev=>{const m=JSON.parse(ev.data);if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);}};
  const send=(m,p={},s)=>new Promise((res,rej)=>{const id=++seq;pend.set(id,{res,rej});ws.send(JSON.stringify({id,method:m,params:p,sessionId:s}));});
  const t=await send("Target.createTarget",{url:"about:blank"});
  const a=await send("Target.attachToTarget",{targetId:t.targetId,flatten:true});const sid=a.sessionId;
  const S=(m,p)=>send(m,p,sid);
  await S("Page.enable");await S("Runtime.enable");
  await S("Page.navigate",{url:"http://127.0.0.1:8842/"});
  for(let i=0;i<40;i++){await sleep(500);const r=await S("Runtime.evaluate",{expression:"typeof ST!=='undefined'",returnByValue:true});if(r.result&&r.result.value)break;}
  await sleep(1500);
  const ev=async e=>{const r=await S("Runtime.evaluate",{expression:e,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)return "JS ERROR: "+JSON.stringify(r.exceptionDetails).slice(0,300);return r.result&&r.result.value;};
  const out = await ev(`(function(){
    resetProgress();
    updateProgress("К озвучке: 48 операций в 24 карточках (голос «X», режим: слово + предложение)", 1);
    // 24 карточки по два куска: предложение и слово
    for (var i = 1; i <= 24; i++) {
      updateProgress("Карточка " + i + " из 24 — звук предложения: 大工は…", i*2);
      updateProgress("OK   [" + (1000+i) + "] звук предложения текст (wav, 200 КБ)", i*2+1);
      updateProgress("OK   [" + (1000+i) + "] звук слова текст (wav, 60 КБ)", i*2+2);
    }
    return document.getElementById("progPct").textContent + " | " + document.getElementById("progText").textContent + " | ширина полосы: " + document.querySelector("#prog i").style.width;
  })()`);
  console.log(out);
  await send("Target.closeTarget",{targetId:t.targetId});ws.close();
})();
