#!/usr/bin/env node
/* Скриншоты веб-интерфейса AnkiVoice: headless Chrome + Chrome DevTools Protocol.
   Ничего не ставить не нужно — нужен установленный Chrome и Node 18+.

   Запуск:
     node web_shot.js jobs.json

   jobs.json — массив снимков:
     [
       { "out": "voice-dark.png", "url": "http://127.0.0.1:8796/",
         "tab": "voice", "theme": "dark",
         "wait": "document.querySelectorAll('#deck option').length>0" },
       { "out": "app-light.png", "tab": "app", "theme": "light", "full": true }
     ]

   Поля задачи:
     out    — куда сохранить PNG (обязательно)
     url    — адрес страницы (по умолчанию http://127.0.0.1:8796/)
     tab    — voice | anki | sound | app  (по умолчанию voice)
     theme  — dark | light (по умолчанию dark)
     wait   — JS-выражение, дождаться его истинности (таймаут 20 с)
     wait2  — то же, но уже после переключения на вкладку
     eval   — JS, выполнить на странице перед снимком (например, нажать кнопку)
     full   — true: снять всю страницу целиком, а не только окно
     w, h   — размер окна (по умолчанию 1440x1000)
*/
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CHROME = process.env.CHROME
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9333;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function httpJson(method, url) {
  let r;
  try { r = await fetch(url, { method }); } catch (e) { throw new Error("нет связи: " + url); }
  if (!r.ok) throw new Error(method + " " + url + " -> HTTP " + r.status);
  return r.json();
}

/* ---- маленький клиент CDP ---- */
function makeCdp(ws) {
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (!m.id || !pending.has(m.id)) return;
    const p = pending.get(m.id);
    pending.delete(m.id);
    if (m.error) p.rej(new Error(m.method ? m.method + ": " + m.error.message : m.error.message));
    else p.res(m.result);
  });
  return (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
    setTimeout(() => {
      if (pending.has(i)) { pending.delete(i); rej(new Error("CDP таймаут: " + method)); }
    }, 30000);
  });
}

function openWs(url) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(url);
    const to = setTimeout(() => rej(new Error("WebSocket не открылся")), 10000);
    ws.addEventListener("open", () => { clearTimeout(to); res(ws); });
    ws.addEventListener("error", () => { clearTimeout(to); rej(new Error("WebSocket ошибка")); });
  });
}

async function waitFor(fn, timeoutMs, what) {
  const t0 = Date.now();
  for (;;) {
    let v;
    try { v = await fn(); } catch (e) { v = false; }
    if (v) return v;
    if (Date.now() - t0 > timeoutMs) throw new Error("не дождался: " + what);
    await sleep(250);
  }
}

async function main() {
  const jobsFile = process.argv[2];
  if (!jobsFile) { console.error("нет файла задач"); process.exit(2); }
  const jobs = JSON.parse(fs.readFileSync(jobsFile, "utf8"));
  const first = jobs[0];
  const W = first.w || 1440, H = first.h || 1000;

  const prof = fs.mkdtempSync(path.join(os.tmpdir(), "avshot-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars",
    "--no-first-run", "--disable-extensions", "--disable-background-networking",
    "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + prof,
    "--window-size=" + W + "," + H,
    "--force-device-scale-factor=1",
    "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  let ws = null, send = null;
  try {
    await waitFor(() => httpJson("GET", "http://127.0.0.1:" + PORT + "/json/version")
      .then(() => true).catch(() => false), 15000, "старт Chrome");

    let target = null;
    try { target = await httpJson("PUT", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }
    catch (e) { target = await httpJson("GET", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }

    ws = await openWs(target.webSocketDebuggerUrl);
    send = makeCdp(ws);
    await send("Page.enable");
    await send("Runtime.enable");

    for (const job of jobs) {
      const url = job.url || "http://127.0.0.1:8796/";
      const w = job.w || W, h = job.h || H;
      await send("Emulation.setDeviceMetricsOverride",
        { width: w, height: h, deviceScaleFactor: 1, mobile: false });

      await send("Page.navigate", { url });
      await waitFor(async () => (await send("Runtime.evaluate",
        { expression: "document.readyState", returnByValue: true })).result.value === "complete",
        20000, "загрузка страницы " + url);

      // дождаться данных: колоды и голоса приходят по API после load
      const waitJs = job.wait
        || "document.querySelectorAll('#deck option').length>0 && document.querySelectorAll('#voice option').length>0";
      await waitFor(async () => (await send("Runtime.evaluate",
        { expression: waitJs, returnByValue: true })).result.value === true,
        20000, "данные (" + waitJs.slice(0, 60) + ")");

      // вкладка
      const tab = job.tab || "voice";
      await send("Runtime.evaluate", { expression:
        "(()=>{const b=document.querySelector(" + JSON.stringify('.nav[data-tab="' + tab + '"]') +
        ");if(b)b.click();return true})()" });
      // некоторые вкладки дозапрашивают данные уже после клика
      if (job.eval) {
        await send("Runtime.evaluate", { expression: job.eval });
      }
      if (job.wait2) {
        await waitFor(async () => (await send("Runtime.evaluate",
          { expression: job.wait2, returnByValue: true })).result.value === true,
          20000, "данные вкладки " + tab);
      }
      // тема (после loadState, который перезаписывает data-theme из конфига)
      const theme = job.theme || "dark";
      await send("Runtime.evaluate",
        { expression: "document.documentElement.dataset.theme='" + theme + "'" });
      await sleep(600);

      let params = { format: "png" };
      if (job.full) {
        const m = await send("Page.getLayoutMetrics");
        const s = m.cssContentSize || m.contentSize;
        params = { format: "png", captureBeyondViewport: true,
                   clip: { x: 0, y: 0, width: s.width, height: s.height, scale: 1 } };
      }
      const shot = await send("Page.captureScreenshot", params);
      fs.mkdirSync(path.dirname(job.out), { recursive: true });
      fs.writeFileSync(job.out, Buffer.from(shot.data, "base64"));
      console.log("OK  " + job.out + "  (" + Buffer.from(shot.data, "base64").length + " байт)");
    }
  } finally {
    if (ws) try { ws.close(); } catch (e) { /* ignore */ }
    try { chrome.kill(); } catch (e) { /* ignore */ }
    await sleep(400);
    try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  }
}

main().catch((e) => { console.error("ОШИБКА: " + e.message); process.exit(1); });
