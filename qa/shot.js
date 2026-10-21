// Помощник для UX-проверки: открыть приложение, выполнить JS, снять скриншот.
// node qa/shot.js --out qa/first-users/01.png [--url http://127.0.0.1:8842/]
//                [--width 1500] [--height 1150] [--js "closeWizard(); goTab('voice');"]
//                [--wait 2500] [--full]
const fs = require("fs");
const path = require("path");
const http = require("http");

const args = {};
process.argv.slice(2).forEach((a, i, arr) => {
  if (a.startsWith("--")) args[a.slice(2)] = arr[i + 1] && !arr[i + 1].startsWith("--") ? arr[i + 1] : true;
});
const base = "http://127.0.0.1:9224";
const url = args.url || "http://127.0.0.1:8842/";
const out = args.out || "qa/shot.png";
const width = parseInt(args.width || "1500", 10);
const height = parseInt(args.height || "1150", 10);
const js = args.js || "";
const waitMs = parseInt(args.wait || "2500", 10);
const full = !!args.full;

const sleep = ms => new Promise(r => setTimeout(r, ms));

function cdpGet(pathname) {
  return new Promise((res, rej) => {
    http.get(base + pathname, r => {
      let d = "";
      r.on("data", c => d += c);
      r.on("end", () => res(d ? JSON.parse(d) : null));
    }).on("error", rej);
  });
}

async function main() {
  const ver = await cdpGet("/json/version");
  const wsUrl = ver.webSocketDebuggerUrl;
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
    }
  };
  function send(method, params = {}, sessionId) {
    return new Promise((res, rej) => {
      const id = ++seq;
      pending.set(id, { res, rej });
      ws.send(JSON.stringify({ id, method, params, sessionId }));
    });
  }
  // своя вкладка — чтобы не мешать другим агентам
  const target = await send("Target.createTarget", { url: "about:blank" });
  const att = await send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
  const sid = att.sessionId;
  const S = (m, p) => send(m, p, sid);

  await S("Page.enable");
  await S("Runtime.enable");
  await S("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 500 });
  await S("Page.navigate", { url });
  // ждём, пока страница поднимется
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try {
      const r = await S("Runtime.evaluate", { expression: "typeof ST !== 'undefined' && typeof applyLang === 'function'", returnByValue: true });
      if (r.result && r.result.value) break;
    } catch (e) { /* ещё грузится */ }
  }
  await sleep(waitMs);
  if (js) {
    try { await S("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true }); }
    catch (e) { console.error("JS error: " + e.message); }
    await sleep(900);
  }
  const shot = await S("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: full });
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log("saved " + out + " " + fs.statSync(out).size + " bytes (" + width + "x" + height + ")");
  await send("Target.closeTarget", { targetId: target.targetId });
  ws.close();
}
main().catch(e => { console.error("ERR " + e.message); process.exit(1); });
