// Отрисовать SVG в PNG (для проверки): node qa/svg2png.js <svg> <png> [width] [height]
const fs = require("fs");
const path = require("path");
const http = require("http");
const base = "http://127.0.0.1:9224";
const sleep = ms => new Promise(r => setTimeout(r, ms));
function cdpGet(p){ return new Promise((res,rej)=>{ http.get(base+p, r=>{ let d=""; r.on("data",c=>d+=c); r.on("end",()=>res(d?JSON.parse(d):null)); }).on("error",rej); }); }

async function main(){
  const [svgPath, pngPath, w, h] = process.argv.slice(2);
  const svg = fs.readFileSync(svgPath, "utf8");
  const W = parseInt(w || "1650", 10), H = parseInt(h || "980", 10);
  const html = '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:'+W+'px;height:'+H+'px;overflow:hidden;background:#0a0f1a}svg{display:block}</style>' + svg;
  const ver = await cdpGet("/json/version");
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res,rej)=>{ ws.onopen=res; ws.onerror=rej; });
  let seq=0; const pend=new Map();
  ws.onmessage = ev => { const m=JSON.parse(ev.data); if(m.id&&pend.has(m.id)){ const p=pend.get(m.id); pend.delete(m.id); m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result); } };
  const send=(m,p={},s)=>new Promise((res,rej)=>{ const id=++seq; pend.set(id,{res,rej}); ws.send(JSON.stringify({id,method:m,params:p,sessionId:s})); });
  const t = await send("Target.createTarget",{url:"about:blank"});
  const a = await send("Target.attachToTarget",{targetId:t.targetId,flatten:true});
  const sid = a.sessionId;
  const S=(m,p)=>send(m,p,sid);
  await S("Page.enable"); await S("Runtime.enable");
  await S("Emulation.setDeviceMetricsOverride",{width:W,height:H,deviceScaleFactor:1,mobile:false});
  await S("Page.navigate",{url:"data:text/html;charset=utf-8,"+encodeURIComponent(html)});
  await sleep(2200);
  const shot = await S("Page.captureScreenshot",{format:"png",fromSurface:true});
  fs.writeFileSync(pngPath, Buffer.from(shot.data,"base64"));
  console.log("saved " + pngPath + " " + fs.statSync(pngPath).size + " bytes");
  await send("Target.closeTarget",{targetId:t.targetId});
  ws.close();
}
main().catch(e=>{ console.error("ERR "+e.message); process.exit(1); });
