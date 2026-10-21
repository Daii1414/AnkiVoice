// Драйвер страницы через CDP: выполнить JS и напечатать результат.
//   node qa/cdp.js "document.title"
//   node qa/cdp.js --click "#btnStart"        (клик по CSS-селектору)
//   node qa/cdp.js --wait "Готово"           (ждать текст, до 120 с)
//   node qa/cdp.js --text                    (весь видимый текст страницы)
//   node qa/cdp.js --url http://127.0.0.1:8842/   (открыть заново)
const http = require("http");
const args = process.argv.slice(2);
function flag(name) { const i = args.indexOf("--" + name); return i >= 0 ? args[i + 1] : null; }
const expr = args.filter((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1] && args[i - 1].startsWith("--"))).join(" ");
const base = "http://127.0.0.1:9224";
const sleep = ms => new Promise(r => setTimeout(r, ms));
function cdpGet(p) { return new Promise((res, rej) => { http.get(base + p, r => { let d = ""; r.on("data", c => d += c); r.on("end", () => res(d ? JSON.parse(d) : null)); }).on("error", rej); }); }

async function main() {
  const ver = await cdpGet("/json/version");
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } };
  function send(method, params = {}, sessionId) { return new Promise((res, rej) => { const id = ++seq; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params, sessionId })); }); }
  const target = await send("Target.createTarget", { url: "about:blank" });
  const att = await send("Target.attachToTarget", { targetId: target.targetId, flatten: true });
  const sid = att.sessionId;
  const S = (m, p) => send(m, p, sid);
  await S("Page.enable"); await S("Runtime.enable");
  const url = flag("url") || "http://127.0.0.1:8842/";
  await S("Page.navigate", { url });
  for (let i = 0; i < 40; i++) {
    await sleep(500);
    try { const r = await S("Runtime.evaluate", { expression: "typeof ST !== 'undefined' && typeof applyLang === 'function'", returnByValue: true }); if (r.result && r.result.value) break; } catch (e) {}
  }
  await sleep(1200);
  const click = flag("click");
  if (click) {
    const r = await S("Runtime.evaluate", { expression: `(function(){var e=document.querySelector(${JSON.stringify(click)}); if(!e) return 'NOT FOUND'; e.click(); return 'clicked '+(e.textContent||'').trim().slice(0,40);})()`, returnByValue: true });
    console.log(r.result && r.result.value);
    await sleep(1500);
  }
  const wait = flag("wait");
  if (wait) {
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      const r = await S("Runtime.evaluate", { expression: `document.body.innerText.includes(${JSON.stringify(wait)})`, returnByValue: true });
      if (r.result && r.result.value) { console.log("found: " + wait); break; }
      await sleep(2000);
    }
  }
  if (flag("text")) {
    const r = await S("Runtime.evaluate", { expression: "document.body.innerText", returnByValue: true });
    console.log(r.result && r.result.value);
  }
  if (expr) {
    const r = await S("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) console.log("JS ERROR: " + JSON.stringify(r.exceptionDetails).slice(0, 400));
    else console.log(typeof r.result.value === "object" ? JSON.stringify(r.result.value, null, 1) : r.result.value);
  }
  await send("Target.closeTarget", { targetId: target.targetId });
  ws.close();
}
main().catch(e => { console.error("ERR " + e.message); process.exit(1); });
