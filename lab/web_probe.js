#!/usr/bin/env node
/* Пробник живой веб-страницы AnkiVoice: выполняет JS на странице и печатает результат.
   Запуск:
     node web_probe.js "http://127.0.0.1:8796/" "выражение1" "выражение2" ...
   Удобно, когда нужно посмотреть, что реально лежит в DOM/переменных,
   не приближая браузер руками.
*/
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CHROME = process.env.CHROME
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9334;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function httpJson(method, url) {
  const r = await fetch(url, { method });
  if (!r.ok) throw new Error(method + " " + url + " -> " + r.status);
  return r.json();
}

function makeCdp(ws) {
  let id = 0; const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (!m.id || !pending.has(m.id)) return;
    const p = pending.get(m.id); pending.delete(m.id);
    m.error ? p.rej(new Error(m.error.message)) : p.res(m.result);
  });
  return (method, params = {}) => new Promise((res, rej) => {
    const i = ++id; pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
}

function openWs(url) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(url);
    ws.addEventListener("open", () => res(ws));
    ws.addEventListener("error", () => rej(new Error("WebSocket ошибка")));
  });
}

async function main() {
  const url = process.argv[2] || "http://127.0.0.1:8796/";
  const exprs = process.argv.slice(3);
  if (!exprs.length) { console.error("нет выражений"); process.exit(2); }

  const prof = fs.mkdtempSync(path.join(os.tmpdir(), "avprobe-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
    "--remote-debugging-port=" + PORT, "--user-data-dir=" + prof,
    "--window-size=1440,1000", "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  try {
    let ver = null;
    for (let i = 0; i < 60 && !ver; i++) {
      try { ver = await httpJson("GET", "http://127.0.0.1:" + PORT + "/json/version"); }
      catch (e) { await sleep(300); }
    }
    if (!ver) throw new Error("Chrome не поднялся");

    let target;
    try { target = await httpJson("PUT", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }
    catch (e) { target = await httpJson("GET", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }

    const ws = await openWs(target.webSocketDebuggerUrl);
    const send = makeCdp(ws);
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Page.navigate", { url });
    for (let i = 0; i < 80; i++) {
      const r = await send("Runtime.evaluate",
        { expression: "document.readyState", returnByValue: true });
      if (r.result.value === "complete") break;
      await sleep(250);
    }
    await sleep(2500);   // дать прогрузиться API (колоды, голоса, конфиг)

    for (const e of exprs) {
      const r = await send("Runtime.evaluate",
        { expression: e, returnByValue: true, awaitPromise: true });
      const val = r.exceptionDetails
        ? "ОШИБКА: " + (r.exceptionDetails.exception
            ? r.exceptionDetails.exception.description
            : r.exceptionDetails.text)
        : r.result.value;
      console.log(">>> " + e);
      console.log(JSON.stringify(val, null, 2));
      console.log("");
    }
    ws.close();
  } finally {
    try { chrome.kill(); } catch (e) { /* ignore */ }
    await sleep(300);
    try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  }
}

main().catch((e) => { console.error("ОШИБКА: " + e.message); process.exit(1); });
